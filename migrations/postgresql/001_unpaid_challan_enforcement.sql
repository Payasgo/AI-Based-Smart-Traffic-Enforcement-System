-- PostgreSQL starting schema. Apply via migration runner; SQLite is local/test only.
CREATE TABLE IF NOT EXISTS enforcement_challans (
 challan_id UUID PRIMARY KEY, jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 vehicle_registration TEXT NOT NULL, responsible_person_ref TEXT, offence_type TEXT NOT NULL,
 issued_at TIMESTAMPTZ NOT NULL, due_at TIMESTAMPTZ NOT NULL CHECK(due_at>issued_at),
 amount_minor BIGINT NOT NULL CHECK(amount_minor>=0), paid_minor BIGINT NOT NULL DEFAULT 0 CHECK(paid_minor>=0 AND paid_minor<=amount_minor),
 status TEXT NOT NULL CHECK(status IN ('ISSUED','PARTIALLY_PAID','PAID','DISPUTED','DISMISSED','ADJUDICATED')),
 source_event_id UUID, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_enforcement_challan_due ON enforcement_challans(status,due_at);
CREATE INDEX IF NOT EXISTS ix_enforcement_challan_person ON enforcement_challans(jurisdiction,responsible_person_ref);
CREATE TABLE IF NOT EXISTS enforcement_payments (
 payment_id UUID PRIMARY KEY, challan_id UUID NOT NULL REFERENCES enforcement_challans,
 amount_minor BIGINT NOT NULL CHECK(amount_minor>0), paid_at TIMESTAMPTZ NOT NULL,
 external_reference TEXT NOT NULL UNIQUE, recorded_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS enforcement_disputes (
 dispute_id UUID PRIMARY KEY, challan_id UUID NOT NULL REFERENCES enforcement_challans,
 filed_at TIMESTAMPTZ NOT NULL, reference TEXT NOT NULL UNIQUE,
 status TEXT NOT NULL CHECK(status IN ('OPEN','UPHELD','REJECTED','WITHDRAWN')),
 resolved_at TIMESTAMPTZ, resolution_ref TEXT);
CREATE TABLE IF NOT EXISTS enforcement_offence_dispositions (
 disposition_id UUID PRIMARY KEY, challan_id UUID NOT NULL UNIQUE REFERENCES enforcement_challans,
 jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 person_ref TEXT NOT NULL, offence_at TIMESTAMPTZ NOT NULL, disposition_ref TEXT NOT NULL UNIQUE,
 qualifies_for_repeat_review BOOLEAN NOT NULL DEFAULT FALSE, finalised_by TEXT NOT NULL, finalised_at TIMESTAMPTZ NOT NULL);
CREATE INDEX IF NOT EXISTS ix_enforcement_offence_count ON enforcement_offence_dispositions(jurisdiction,person_ref,offence_at) WHERE qualifies_for_repeat_review;
CREATE TABLE IF NOT EXISTS enforcement_licence_orders (
 order_id UUID PRIMARY KEY, jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 person_ref TEXT NOT NULL, order_type TEXT NOT NULL CHECK(order_type IN ('SUSPENSION','DISQUALIFICATION')),
 official_order_ref TEXT NOT NULL UNIQUE, issuing_authority TEXT NOT NULL, valid_from TIMESTAMPTZ NOT NULL,
 valid_until TIMESTAMPTZ, recorded_by TEXT NOT NULL, recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 revoked_at TIMESTAMPTZ, revocation_ref TEXT);
CREATE INDEX IF NOT EXISTS ix_enforcement_active_licence ON enforcement_licence_orders(jurisdiction,person_ref,valid_from,valid_until) WHERE revoked_at IS NULL;
CREATE TABLE IF NOT EXISTS post_disqualification_detections (
 detection_id UUID PRIMARY KEY, jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 person_ref TEXT, vehicle_registration TEXT NOT NULL, camera_id TEXT NOT NULL, detected_at TIMESTAMPTZ NOT NULL,
 evidence_manifest_ref TEXT NOT NULL, driver_identity_verified BOOLEAN NOT NULL DEFAULT FALSE,
 matched_order_id UUID REFERENCES enforcement_licence_orders, result TEXT NOT NULL
 CHECK(result IN ('UNVERIFIED_DRIVER','ACTIVE_ORDER_MATCH','NO_ACTIVE_ORDER')), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_post_disqualification_time ON post_disqualification_detections(jurisdiction,detected_at);
CREATE TABLE IF NOT EXISTS vehicle_detention_records (
 detention_id UUID PRIMARY KEY, jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 vehicle_registration TEXT NOT NULL, detection_id UUID REFERENCES post_disqualification_detections,
 legal_basis_ref TEXT NOT NULL, authorising_order_ref TEXT NOT NULL, officer_subject TEXT NOT NULL,
 detained_at TIMESTAMPTZ NOT NULL, location_ref TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('DETAINED','RELEASED')), released_at TIMESTAMPTZ,
 release_order_ref TEXT, released_by TEXT);
CREATE INDEX IF NOT EXISTS ix_vehicle_detention_open ON vehicle_detention_records(jurisdiction,vehicle_registration,status);
CREATE TABLE IF NOT EXISTS enforcement_audit (
 audit_id UUID PRIMARY KEY, jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 actor_subject TEXT NOT NULL, actor_role TEXT NOT NULL, action TEXT NOT NULL, entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL, occurred_at TIMESTAMPTZ NOT NULL, details_json JSONB NOT NULL);
CREATE INDEX IF NOT EXISTS ix_enforcement_audit_entity ON enforcement_audit(entity_type,entity_id,occurred_at);
