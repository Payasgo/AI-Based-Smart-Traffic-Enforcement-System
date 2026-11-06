"""Optional Flask blueprint; actor_resolver must validate a government IdP identity."""
from flask import Blueprint,jsonify,request
from .service import EnforcementError,EnforcementService
from .queries import overdue_challans

def create_enforcement_blueprint(service:EnforcementService,actor_resolver):
    bp=Blueprint("enforcement",__name__,url_prefix="/api/v1/enforcement")
    def actor():
        value=actor_resolver(request)
        if not value: raise EnforcementError("Authentication required.")
        return value
    def body():
        value=request.get_json(silent=True)
        if not isinstance(value,dict): raise EnforcementError("JSON object required.")
        return value
    @bp.errorhandler(EnforcementError)
    def error(e): return jsonify({"error":str(e)}),400
    @bp.post("/challans")
    def create(): return jsonify(service.create_challan(body(),actor())),201
    @bp.get("/challans/overdue/<jurisdiction>")
    def overdue(jurisdiction): return jsonify(overdue_challans(service,jurisdiction,actor()))
    @bp.post("/challans/<cid>/payments")
    def payment(cid):
        p=body(); return jsonify(service.record_payment(cid,p["amount_minor"],p["external_reference"],p["paid_at"],actor()))
    @bp.post("/challans/<cid>/disputes")
    def dispute(cid):
        p=body(); return jsonify(service.file_dispute(cid,p["reference"],p["filed_at"],actor())),201
    @bp.post("/challans/<cid>/finalise")
    def finalise(cid):
        p=body(); return jsonify(service.finalise_offence(cid,p["person_ref"],p["offence_at"],p["disposition_ref"],bool(p.get("qualifies_for_repeat_review",False)),actor()))
    @bp.get("/repeat-offender/<jurisdiction>/<person_ref>")
    def repeat(jurisdiction,person_ref): return jsonify(service.repeat_offender_review(jurisdiction,person_ref,actor()))
    @bp.post("/licence-orders")
    def order(): return jsonify(service.record_licence_order(body(),actor())),201
    @bp.post("/licence-orders/<oid>/revoke")
    def revoke(oid): return jsonify(service.revoke_licence_order(oid,body()["revocation_ref"],actor()))
    @bp.post("/disqualified-driver-detections")
    def detection(): return jsonify(service.record_post_disqualification_detection(body(),actor())),201
    @bp.post("/vehicle-detentions")
    def detention(): return jsonify(service.record_vehicle_detention(body(),actor())),201
    @bp.post("/vehicle-detentions/<oid>/release")
    def release(oid): return jsonify(service.release_vehicle(oid,body()["release_order_ref"],actor()))
    return bp
