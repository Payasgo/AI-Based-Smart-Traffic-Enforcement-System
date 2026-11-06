# Enforcement module integration

See docs/UNPAID_CHALLAN_AND_REPEAT_OFFENDER_ENFORCEMENT.md.

The enforcement package adds unpaid challan and payment tracking, dispute handling, finalised offence dispositions, repeat-offender referral, official licence-order records, verified post-disqualification detection alerts, and officer-authorised detention/release records. It is disabled by default. No automatic licence suspension, government challan issue, driver inference from a plate, immobilisation or seizure is performed. SQLite is local/test only; use PostgreSQL and a production repository adapter for deployment.
