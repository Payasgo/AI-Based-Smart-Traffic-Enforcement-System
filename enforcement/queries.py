"""Read-only overdue-challan query helpers."""
from datetime import datetime,timezone
from .service import EnforcementError,EnforcementService

def overdue_challans(service:EnforcementService,jurisdiction:str,actor:dict):
    service.require(actor,"CHALLAN_ADMIN","ADJUDICATOR","LICENSING_AUTHORITY","ENFORCEMENT_SUPERVISOR")
    state=service.state(jurisdiction); now=datetime.now(timezone.utc).isoformat()
    with service.store.transaction() as c:
        rows=c.execute("""SELECT challan_id,vehicle_registration,responsible_person_ref,offence_type,
          due_at,amount_minor,paid_minor,(amount_minor-paid_minor) AS outstanding_minor
          FROM challans WHERE jurisdiction=? AND status IN ('ISSUED','PARTIALLY_PAID')
          AND due_at<? ORDER BY due_at ASC""",(state,now)).fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        due=datetime.fromisoformat(item["due_at"])
        item["overdue_days"]=max(0,(datetime.now(timezone.utc)-due).days)
        item["next_step"]="NOTICE_OR_AUTHORITY_REVIEW"
        item["automatic_licence_action"]=False
        item["automatic_vehicle_action"]=False
        result.append(item)
    return {"jurisdiction":state,"as_of":now,"count":len(result),"items":result}
