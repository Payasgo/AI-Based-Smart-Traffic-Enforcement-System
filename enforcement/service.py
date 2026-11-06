"""Business rules for challan recovery and authority-controlled enforcement."""
import json
import sqlite3
import uuid
from datetime import datetime,timedelta,timezone
from .store import SQLiteEnforcementStore

STATES={"TELANGANA","ANDHRA_PRADESH"}
CHALLAN_ADMIN="CHALLAN_ADMIN"
ADJUDICATOR="ADJUDICATOR"
LICENSING_AUTHORITY="LICENSING_AUTHORITY"
POLICE_OFFICER="POLICE_OFFICER"
ENFORCEMENT_SUPERVISOR="ENFORCEMENT_SUPERVISOR"

class EnforcementError(ValueError):
    """Rejected request or invalid state transition."""

def now(): return datetime.now(timezone.utc).isoformat()
def new_id(): return str(uuid.uuid4())
def parse_time(value):
    try: d=datetime.fromisoformat(value.replace("Z","+00:00"))
    except (TypeError,ValueError) as e: raise EnforcementError("Timestamp must be ISO-8601 with timezone.") from e
    if d.tzinfo is None: raise EnforcementError("Timestamp must include a timezone.")
    return d.astimezone(timezone.utc)

class EnforcementService:
    """Records official decisions and alerts. Never performs physical enforcement."""
    def __init__(self,store:SQLiteEnforcementStore,repeat_threshold=5,repeat_window_days=365):
        if repeat_threshold<1 or repeat_window_days<1: raise ValueError("Invalid repeat policy")
        self.store=store; self.repeat_threshold=repeat_threshold; self.repeat_window_days=repeat_window_days
    @staticmethod
    def state(value):
        s=str(value).upper()
        if s not in STATES: raise EnforcementError("jurisdiction must be TELANGANA or ANDHRA_PRADESH.")
        return s
    @staticmethod
    def require(actor,*roles):
        subject=actor.get("subject"); matched=sorted(set(actor.get("roles",[])).intersection(roles))
        if not subject or not matched: raise EnforcementError("Authenticated actor lacks required role.")
        return str(subject),matched[0]
    def audit(self,c,state,subject,role,action,kind,eid,details):
        c.execute("INSERT INTO enforcement_audit VALUES(?,?,?,?,?,?,?,?,?)",
          (new_id(),state,subject,role,action,kind,eid,now(),json.dumps(details,sort_keys=True)))
    def get_challan(self,cid):
        with self.store.transaction() as c:
            row=c.execute("SELECT * FROM challans WHERE challan_id=?",(cid,)).fetchone()
            if not row: raise EnforcementError("Challan not found.")
            return dict(row)
    def create_challan(self,p,a):
        subject,role=self.require(a,CHALLAN_ADMIN); state=self.state(p["jurisdiction"])
        issued,due=parse_time(p["issued_at"]),parse_time(p["due_at"])
        amount=int(p["amount_minor"])
        if due<=issued or amount<0: raise EnforcementError("Invalid due date or amount.")
        cid=str(p.get("challan_id") or new_id())
        with self.store.transaction() as c:
            c.execute("INSERT INTO challans VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (cid,state,p["vehicle_registration"].upper(),p.get("responsible_person_ref"),p["offence_type"],
               issued.isoformat(),due.isoformat(),amount,0,"ISSUED",p.get("source_event_id"),now()))
            self.audit(c,state,subject,role,"CHALLAN_CREATED","challan",cid,{})
        return self.get_challan(cid)
    def record_payment(self,cid,amount_minor,external_reference,paid_at,actor):
        subject,role=self.require(actor,CHALLAN_ADMIN); amount=int(amount_minor); paid=parse_time(paid_at)
        if amount<=0 or not external_reference: raise EnforcementError("Positive payment and external reference required.")
        with self.store.transaction() as c:
            r=c.execute("SELECT * FROM challans WHERE challan_id=?",(cid,)).fetchone()
            if not r: raise EnforcementError("Challan not found.")
            if r["status"] in ("DISPUTED","DISMISSED","ADJUDICATED"): raise EnforcementError("Payment blocked in current state.")
            if amount>r["amount_minor"]-r["paid_minor"]: raise EnforcementError("Payment exceeds outstanding balance.")
            pid=new_id()
            c.execute("INSERT INTO payments VALUES(?,?,?,?,?,?)",(pid,cid,amount,paid.isoformat(),external_reference,subject))
            total=r["paid_minor"]+amount; status="PAID" if total==r["amount_minor"] else "PARTIALLY_PAID"
            c.execute("UPDATE challans SET paid_minor=?,status=? WHERE challan_id=?",(total,status,cid))
            self.audit(c,r["jurisdiction"],subject,role,"PAYMENT_RECORDED","challan",cid,{"payment_id":pid,"amount_minor":amount})
        return self.get_challan(cid)
    def file_dispute(self,cid,reference,filed_at,actor):
        subject,role=self.require(actor,CHALLAN_ADMIN); filed=parse_time(filed_at)
        with self.store.transaction() as c:
            r=c.execute("SELECT * FROM challans WHERE challan_id=?",(cid,)).fetchone()
            if not r: raise EnforcementError("Challan not found.")
            if r["status"] in ("PAID","DISMISSED","ADJUDICATED"): raise EnforcementError("Challan cannot be disputed now.")
            did=new_id(); c.execute("INSERT INTO disputes VALUES(?,?,?,?,?,?,?)",(did,cid,filed.isoformat(),reference,"OPEN",None,None))
            c.execute("UPDATE challans SET status='DISPUTED' WHERE challan_id=?",(cid,))
            self.audit(c,r["jurisdiction"],subject,role,"DISPUTE_FILED","challan",cid,{"dispute_id":did})
        return {"dispute_id":did,"status":"OPEN"}
    def finalise_offence(self,cid,person_ref,offence_at,disposition_ref,qualifies_for_repeat_review,actor):
        subject,role=self.require(actor,ADJUDICATOR); offence=parse_time(offence_at)
        if not person_ref or not disposition_ref: raise EnforcementError("Verified person and official disposition references required.")
        with self.store.transaction() as c:
            r=c.execute("SELECT * FROM challans WHERE challan_id=?",(cid,)).fetchone()
            if not r: raise EnforcementError("Challan not found.")
            if c.execute("SELECT 1 FROM disputes WHERE challan_id=? AND status='OPEN'",(cid,)).fetchone():
                raise EnforcementError("Open dispute must be resolved before offence finalisation.")
            if r["status"]=="DISMISSED": raise EnforcementError("Dismissed offence cannot qualify.")
            c.execute("INSERT INTO offence_dispositions VALUES(?,?,?,?,?,?,?,?,?)",
              (new_id(),cid,r["jurisdiction"],person_ref,offence.isoformat(),disposition_ref,
               int(bool(qualifies_for_repeat_review)),subject,now()))
            c.execute("UPDATE challans SET status='ADJUDICATED' WHERE challan_id=?",(cid,))
            self.audit(c,r["jurisdiction"],subject,role,"OFFENCE_FINALISED","challan",cid,
                       {"disposition_ref":disposition_ref,"qualifies":bool(qualifies_for_repeat_review)})
            state=r["jurisdiction"]
        return self.repeat_offender_review(state,person_ref,actor)
    def repeat_offender_review(self,jurisdiction,person_ref,actor):
        self.require(actor,CHALLAN_ADMIN,ADJUDICATOR,LICENSING_AUTHORITY,ENFORCEMENT_SUPERVISOR)
        state=self.state(jurisdiction); end=datetime.now(timezone.utc); start=(end-timedelta(days=self.repeat_window_days)).isoformat()
        with self.store.transaction() as c:
            rows=c.execute("""SELECT challan_id FROM offence_dispositions WHERE jurisdiction=? AND person_ref=?
              AND qualifies_for_repeat_review=1 AND offence_at>=? AND offence_at<=?""",
              (state,person_ref,start,end.isoformat())).fetchall()
        count=len(rows)
        return {"jurisdiction":state,"person_ref":person_ref,"qualifying_offences":count,
          "threshold":self.repeat_threshold,"window_days":self.repeat_window_days,
          "review_candidate":count>=self.repeat_threshold,
          "action":"REFER_TO_LICENSING_AUTHORITY" if count>=self.repeat_threshold else "NO_REPEAT_REFERRAL",
          "automatic_suspension":False}
    def record_licence_order(self,p,a):
        subject,role=self.require(a,LICENSING_AUTHORITY); state=self.state(p["jurisdiction"])
        start=parse_time(p["valid_from"]); end=parse_time(p["valid_until"]) if p.get("valid_until") else None
        if end and end<=start: raise EnforcementError("Invalid licence order validity period.")
        if p.get("order_type") not in ("SUSPENSION","DISQUALIFICATION"): raise EnforcementError("Invalid order type.")
        for k in ("person_ref","official_order_ref","issuing_authority"):
            if not p.get(k): raise EnforcementError(f"{k} is required.")
        oid=new_id()
        with self.store.transaction() as c:
            c.execute("INSERT INTO licence_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (oid,state,p["person_ref"],p["order_type"],p["official_order_ref"],p["issuing_authority"],
               start.isoformat(),end.isoformat() if end else None,subject,now(),None,None))
            self.audit(c,state,subject,role,"LICENCE_ORDER_RECORDED","licence_order",oid,{"official_order_ref":p["official_order_ref"]})
        return {"order_id":oid,"status":"RECORDED","automatic_suspension":False}
    def revoke_licence_order(self,oid,revocation_ref,actor):
        subject,role=self.require(actor,LICENSING_AUTHORITY)
        if not revocation_ref: raise EnforcementError("Official revocation reference required.")
        with self.store.transaction() as c:
            r=c.execute("SELECT * FROM licence_orders WHERE order_id=?",(oid,)).fetchone()
            if not r: raise EnforcementError("Licence order not found.")
            c.execute("UPDATE licence_orders SET revoked_at=?,revocation_ref=? WHERE order_id=?",(now(),revocation_ref,oid))
            self.audit(c,r["jurisdiction"],subject,role,"LICENCE_ORDER_REVOKED","licence_order",oid,{"ref":revocation_ref})
        return {"order_id":oid,"status":"REVOKED"}
    def record_post_disqualification_detection(self,p,a):
        subject,role=self.require(a,POLICE_OFFICER,ENFORCEMENT_SUPERVISOR); state=self.state(p["jurisdiction"])
        detected=parse_time(p["detected_at"])
        for k in ("vehicle_registration","camera_id","evidence_manifest_ref"):
            if not p.get(k): raise EnforcementError(f"{k} is required.")
        verified=bool(p.get("driver_identity_verified")) and bool(p.get("person_ref"))
        result="UNVERIFIED_DRIVER"; matched=None
        with self.store.transaction() as c:
            if verified:
                orders=c.execute("""SELECT * FROM licence_orders WHERE jurisdiction=? AND person_ref=?
                  AND revoked_at IS NULL AND valid_from<=? AND (valid_until IS NULL OR valid_until>=?)""",
                  (state,p["person_ref"],detected.isoformat(),detected.isoformat())).fetchall()
                if orders: result="ACTIVE_ORDER_MATCH"; matched=orders[0]["order_id"]
                else: result="NO_ACTIVE_ORDER"
            did=new_id()
            c.execute("INSERT INTO post_disqualification_detections VALUES(?,?,?,?,?,?,?,?,?,?,?)",
              (did,state,p.get("person_ref") if verified else None,p["vehicle_registration"].upper(),
               p["camera_id"],detected.isoformat(),p["evidence_manifest_ref"],int(verified),matched,result,now()))
            self.audit(c,state,subject,role,"DISQUALIFIED_DRIVER_DETECTION","detection",did,{"result":result})
        return {"detection_id":did,"result":result,"requires_officer_verification":True,"vehicle_seizure_authorised":False}
    def record_vehicle_detention(self,p,a):
        subject,role=self.require(a,POLICE_OFFICER,ENFORCEMENT_SUPERVISOR); state=self.state(p["jurisdiction"])
        detained=parse_time(p["detained_at"])
        for k in ("vehicle_registration","legal_basis_ref","authorising_order_ref","location_ref"):
            if not p.get(k): raise EnforcementError(f"{k} is required.")
        did=p.get("detection_id"); oid=new_id()
        with self.store.transaction() as c:
            if did:
                d=c.execute("SELECT * FROM post_disqualification_detections WHERE detection_id=?",(did,)).fetchone()
                if not d or d["jurisdiction"]!=state: raise EnforcementError("Detection not found in jurisdiction.")
            c.execute("INSERT INTO vehicle_detentions VALUES(?,?,?,?,?,?,?,?,?,'DETAINED',?,?,?)",
              (oid,state,p["vehicle_registration"].upper(),did,p["legal_basis_ref"],p["authorising_order_ref"],
               subject,detained.isoformat(),p["location_ref"],None,None,None))
            self.audit(c,state,subject,role,"VEHICLE_DETENTION_RECORDED","vehicle_detention",oid,
              {"legal_basis_ref":p["legal_basis_ref"],"authorising_order_ref":p["authorising_order_ref"]})
        return {"detention_id":oid,"status":"DETAINED","physical_action_performed":False}
    def release_vehicle(self,oid,release_order_ref,actor):
        subject,role=self.require(actor,POLICE_OFFICER,ENFORCEMENT_SUPERVISOR)
        if not release_order_ref: raise EnforcementError("Official release order reference required.")
        with self.store.transaction() as c:
            r=c.execute("SELECT * FROM vehicle_detentions WHERE detention_id=?",(oid,)).fetchone()
            if not r: raise EnforcementError("Detention record not found.")
            if r["status"]!="DETAINED": raise EnforcementError("Vehicle is not recorded as detained.")
            c.execute("UPDATE vehicle_detentions SET status='RELEASED',released_at=?,release_order_ref=?,released_by=? WHERE detention_id=?",
              (now(),release_order_ref,subject,oid))
            self.audit(c,r["jurisdiction"],subject,role,"VEHICLE_RELEASE_RECORDED","vehicle_detention",oid,{"ref":release_order_ref})
        return {"detention_id":oid,"status":"RELEASED"}
