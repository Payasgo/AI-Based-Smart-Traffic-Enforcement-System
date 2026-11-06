from datetime import datetime,timedelta,timezone
import pytest
from enforcement import EnforcementError,EnforcementService,SQLiteEnforcementStore
from enforcement.queries import overdue_challans

ADMIN={"subject":"admin","roles":["CHALLAN_ADMIN"]}
ADJ={"subject":"adjudicator","roles":["ADJUDICATOR"]}
LIC={"subject":"licensing","roles":["LICENSING_AUTHORITY"]}
POLICE={"subject":"officer","roles":["POLICE_OFFICER"]}
def ts(d): return d.astimezone(timezone.utc).isoformat()
@pytest.fixture
def svc(): return EnforcementService(SQLiteEnforcementStore())
def make(svc,cid="C-1",state="TELANGANA"):
    n=datetime.now(timezone.utc)
    return svc.create_challan({"challan_id":cid,"jurisdiction":state,"vehicle_registration":"TS09AB1234",
      "responsible_person_ref":"P-1","offence_type":"RED_LIGHT","issued_at":ts(n-timedelta(days=5)),
      "due_at":ts(n-timedelta(days=1)),"amount_minor":50000},ADMIN)
def test_payment_and_overpayment(svc):
    make(svc); assert svc.record_payment("C-1",20000,"PAY-1",ts(datetime.now(timezone.utc)),ADMIN)["status"]=="PARTIALLY_PAID"
    assert svc.record_payment("C-1",30000,"PAY-2",ts(datetime.now(timezone.utc)),ADMIN)["status"]=="PAID"
    with pytest.raises(EnforcementError): svc.record_payment("C-1",1,"PAY-3",ts(datetime.now(timezone.utc)),ADMIN)
def test_overdue_query_is_read_only(svc):
    make(svc); result=overdue_challans(svc,"TELANGANA",ADMIN)
    assert result["count"]==1 and result["items"][0]["outstanding_minor"]==50000
    assert result["items"][0]["automatic_licence_action"] is False
def test_open_dispute_blocks_finalisation(svc):
    make(svc); svc.file_dispute("C-1","D-1",ts(datetime.now(timezone.utc)),ADMIN)
    with pytest.raises(EnforcementError,match="Open dispute"):
        svc.finalise_offence("C-1","P-1",ts(datetime.now(timezone.utc)),"ORDER-1",True,ADJ)
def test_repeat_threshold_only_refers(svc):
    for n in range(5):
        cid=f"C-{n}"; make(svc,cid)
        svc.finalise_offence(cid,"P-1",ts(datetime.now(timezone.utc)),f"DISP-{n}",True,ADJ)
    result=svc.repeat_offender_review("TELANGANA","P-1",ADJ)
    assert result["review_candidate"] is True and result["automatic_suspension"] is False
def test_plate_alone_never_matches_licence(svc):
    svc.record_licence_order({"jurisdiction":"TELANGANA","person_ref":"P-1","order_type":"SUSPENSION",
      "official_order_ref":"LIC-1","issuing_authority":"Licensing Authority",
      "valid_from":ts(datetime.now(timezone.utc)-timedelta(days=1))},LIC)
    result=svc.record_post_disqualification_detection({"jurisdiction":"TELANGANA","vehicle_registration":"TS09AB1234",
      "camera_id":"CAM-1","detected_at":ts(datetime.now(timezone.utc)),"evidence_manifest_ref":"manifest://1",
      "driver_identity_verified":False,"person_ref":"P-1"},POLICE)
    assert result["result"]=="UNVERIFIED_DRIVER" and result["vehicle_seizure_authorised"] is False
def test_verified_driver_match_is_alert_not_seizure(svc):
    svc.record_licence_order({"jurisdiction":"ANDHRA_PRADESH","person_ref":"P-2","order_type":"DISQUALIFICATION",
      "official_order_ref":"AP-LIC-1","issuing_authority":"Licensing Authority",
      "valid_from":ts(datetime.now(timezone.utc)-timedelta(days=1))},LIC)
    result=svc.record_post_disqualification_detection({"jurisdiction":"ANDHRA_PRADESH","person_ref":"P-2",
      "vehicle_registration":"AP01CD5678","camera_id":"AP-CAM-1","detected_at":ts(datetime.now(timezone.utc)),
      "evidence_manifest_ref":"manifest://2","driver_identity_verified":True},POLICE)
    assert result["result"]=="ACTIVE_ORDER_MATCH" and result["vehicle_seizure_authorised"] is False
def test_detention_requires_police_and_order(svc):
    payload={"jurisdiction":"TELANGANA","vehicle_registration":"TS09AB1234","legal_basis_ref":"SECTION-REF",
      "authorising_order_ref":"SIGNED-ORDER","detained_at":ts(datetime.now(timezone.utc)),"location_ref":"STATION-1"}
    with pytest.raises(EnforcementError): svc.record_vehicle_detention(payload,ADMIN)
    record=svc.record_vehicle_detention(payload,POLICE)
    assert record["status"]=="DETAINED" and record["physical_action_performed"] is False
    assert svc.release_vehicle(record["detention_id"],"RELEASE-ORDER",POLICE)["status"]=="RELEASED"

def test_dispute_can_be_resolved_with_official_reference(svc):
    make(svc)
    svc.file_dispute("C-1","D-RESOLVE",ts(datetime.now(timezone.utc)),ADMIN)
    result=svc.resolve_dispute("C-1","D-RESOLVE","REJECTED","HEARING-ORDER-1",ADJ)
    assert result["status"]=="REJECTED"
    assert result["challan_status"]=="ISSUED"
