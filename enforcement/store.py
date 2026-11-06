"""SQLite development/test store. Production must use PostgreSQL HA."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS challans (
 challan_id TEXT PRIMARY KEY, jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('TELANGANA','ANDHRA_PRADESH')),
 vehicle_registration TEXT NOT NULL, responsible_person_ref TEXT, offence_type TEXT NOT NULL,
 issued_at TEXT NOT NULL, due_at TEXT NOT NULL, amount_minor INTEGER NOT NULL CHECK(amount_minor>=0),
 paid_minor INTEGER NOT NULL DEFAULT 0 CHECK(paid_minor>=0), status TEXT NOT NULL,
 source_event_id TEXT, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_challan_person ON challans(jurisdiction,responsible_person_ref);
CREATE INDEX IF NOT EXISTS ix_challan_due ON challans(status,due_at);
CREATE TABLE IF NOT EXISTS payments(payment_id TEXT PRIMARY KEY,challan_id TEXT NOT NULL REFERENCES challans,
 amount_minor INTEGER NOT NULL CHECK(amount_minor>0),paid_at TEXT NOT NULL,external_reference TEXT NOT NULL UNIQUE,recorded_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS disputes(dispute_id TEXT PRIMARY KEY,challan_id TEXT NOT NULL REFERENCES challans,
 filed_at TEXT NOT NULL,reference TEXT NOT NULL UNIQUE,status TEXT NOT NULL,resolved_at TEXT,resolution_ref TEXT);
CREATE TABLE IF NOT EXISTS offence_dispositions(disposition_id TEXT PRIMARY KEY,challan_id TEXT NOT NULL UNIQUE REFERENCES challans,
 jurisdiction TEXT NOT NULL,person_ref TEXT NOT NULL,offence_at TEXT NOT NULL,disposition_ref TEXT NOT NULL UNIQUE,
 qualifies_for_repeat_review INTEGER NOT NULL,finalised_by TEXT NOT NULL,finalised_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_offence_person_time ON offence_dispositions(jurisdiction,person_ref,offence_at);
CREATE TABLE IF NOT EXISTS licence_orders(order_id TEXT PRIMARY KEY,jurisdiction TEXT NOT NULL,person_ref TEXT NOT NULL,
 order_type TEXT NOT NULL,official_order_ref TEXT NOT NULL UNIQUE,issuing_authority TEXT NOT NULL,
 valid_from TEXT NOT NULL,valid_until TEXT,recorded_by TEXT NOT NULL,recorded_at TEXT NOT NULL,
 revoked_at TEXT,revocation_ref TEXT);
CREATE INDEX IF NOT EXISTS ix_licence_person ON licence_orders(jurisdiction,person_ref,valid_from,valid_until);
CREATE TABLE IF NOT EXISTS post_disqualification_detections(detection_id TEXT PRIMARY KEY,jurisdiction TEXT NOT NULL,
 person_ref TEXT,vehicle_registration TEXT NOT NULL,camera_id TEXT NOT NULL,detected_at TEXT NOT NULL,
 evidence_manifest_ref TEXT NOT NULL,driver_identity_verified INTEGER NOT NULL,matched_order_id TEXT REFERENCES licence_orders,
 result TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vehicle_detentions(detention_id TEXT PRIMARY KEY,jurisdiction TEXT NOT NULL,
 vehicle_registration TEXT NOT NULL,detection_id TEXT REFERENCES post_disqualification_detections,
 legal_basis_ref TEXT NOT NULL,authorising_order_ref TEXT NOT NULL,officer_subject TEXT NOT NULL,
 detained_at TEXT NOT NULL,location_ref TEXT NOT NULL,status TEXT NOT NULL,released_at TEXT,
 release_order_ref TEXT,released_by TEXT);
CREATE TABLE IF NOT EXISTS enforcement_audit(audit_id TEXT PRIMARY KEY,jurisdiction TEXT NOT NULL,
 actor_subject TEXT NOT NULL,actor_role TEXT NOT NULL,action TEXT NOT NULL,entity_type TEXT NOT NULL,
 entity_id TEXT NOT NULL,occurred_at TEXT NOT NULL,details_json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON enforcement_audit(entity_type,entity_id,occurred_at);
"""

class SQLiteEnforcementStore:
    """Local/test adapter only; not suitable for a 100+ camera production deployment."""
    def __init__(self, database=":memory:"):
        self.database=str(database)
        self._keeper=None
        if self.database==":memory:":
            self._keeper=sqlite3.connect(":memory:",check_same_thread=False)
            self._keeper.row_factory=sqlite3.Row
            self._keeper.executescript(SCHEMA)
        else:
            Path(self.database).parent.mkdir(parents=True,exist_ok=True)
            with self.transaction() as c: c.executescript(SCHEMA)
    def _connect(self):
        if self.database==":memory:":
            return self._keeper
        c=sqlite3.connect(self.database,timeout=30)
        c.row_factory=sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA journal_mode=WAL")
        return c
    @contextmanager
    def transaction(self):
        c=self._connect()
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            if self.database!=":memory:": c.close()
