# Evidence review journal

Operator review decisions are recorded in `logs/evidence_reviews.csv`, a separate
append-only journal. Camera-created records remain in `logs/violations.csv`
and are never rewritten by an operator action.

Columns: review_id, event_id, review_status, reviewed_by, review_note,
reviewed_at_utc. Multiple decisions for an event are retained; the most recent
decision is used by the dashboard's review queue.

This design avoids lost camera events from a read/modify/replace race between
the dashboard and inference workers. The journal is protected by the shared
evidence file lock. Back up both CSV files together.

This remains an internal review record, not a cryptographically signed or
tamper-proof legal audit system. Restrict filesystem permissions, back up the
files, and consider a transactional database plus append-only external audit
storage before operational deployment.
