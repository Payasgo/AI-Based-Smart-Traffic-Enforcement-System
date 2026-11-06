# Unpaid Challan Recovery and Repeat-Offender Enforcement

## Scope and safety

This adds a state-scoped administrative workflow for Telangana and Andhra Pradesh. It is a software foundation, not a legal determination, government integration, or enforcement authorisation. Example policies are disabled in both states.

Unpaid challans are surfaced for notice and authority review. A repeat-offender threshold creates a referral candidate only. Only a licensing-authority role can record an official suspension/disqualification order. A plate hit is not proof of who was driving. Vehicle detention records require an authorised officer, a legal-basis reference and an authorising-order reference. No camera, AI model or API in this package automatically suspends a licence, issues a government challan, immobilises a vehicle or seizes it.

## Workflow

1. Record an issued challan and due date.
2. Reconcile full/partial payments using a unique external payment reference.
3. Record disputes; open disputes block offence finalisation.
4. An adjudicator records the official final disposition and explicitly marks whether it qualifies under the approved state policy.
5. Count only finalised qualifying dispositions in a rolling policy window. The example default is five within 365 days, as a review/referral threshold only.
6. A licensing authority records the official order, authority and effective dates. Revocation requires an official reference.
7. A camera detection matches an active order only when driver identity has been independently verified.
8. An authorised officer records any detention with legal basis, order and location; a release also requires an official reference.

## Roles

- CHALLAN_ADMIN: issue challans, reconcile payments, register disputes, view overdue items.
- ADJUDICATOR: record final dispositions and qualification status.
- LICENSING_AUTHORITY: record/revoke official licence orders and review repeat-offender referrals.
- POLICE_OFFICER: record verified detections and officer-authorised detention/release.
- ENFORCEMENT_SUPERVISOR: review referrals and authorised enforcement records.

The optional Flask blueprint requires an actor_resolver connected to the approved government identity provider. Implement MFA, jurisdiction-scoped authorisation, least privilege, CSRF/session protections and rate limits at the integration boundary. Never trust role or jurisdiction from an ordinary request body.

## Local development

SQLiteEnforcementStore is for tests and local development only. Create EnforcementService with the store, then register create_enforcement_blueprint(service, actor_resolver) with the existing Flask app. actor_resolver must return a verified actor containing subject and roles. The package requires the existing Flask dependency only for the optional HTTP blueprint.

## API

All paths are under /api/v1/enforcement:
- POST /challans
- GET /challans/overdue/{jurisdiction}
- POST /challans/{challan_id}/payments
- POST /challans/{challan_id}/disputes
- POST /challans/{challan_id}/finalise
- GET /repeat-offender/{jurisdiction}/{person_ref}
- POST /licence-orders
- POST /licence-orders/{order_id}/revoke
- POST /disqualified-driver-detections
- POST /vehicle-detentions
- POST /vehicle-detentions/{detention_id}/release

Timestamps are ISO-8601 with timezone. Amounts are integer minor currency units (paise). Use opaque government person references; do not place Aadhaar numbers, full licence numbers or direct identifiers in URLs/logs.

## Production requirements

- Apply migrations/postgresql/001_unpaid_challan_enforcement.sql with the approved migration runner.
- Replace SQLiteEnforcementStore with a PostgreSQL repository before production; SQLite is not a 100+ camera deployment database.
- Integrate e-Challan, VAHAN and SARATHI only with written government approval and approved API credentials.
- Add signed-source ingestion and cryptographic verification for payment, adjudication, licence and detention orders.
- Add idempotency keys, outbox delivery, pagination, rate limits, request correlation, immutable audit retention and backup/restore.
- Enforce state tenant isolation at database and service layers; test cross-state access denial.
- Obtain competent-authority and legal-counsel confirmation of current state rules, delegated powers, notice/service, limitation periods, appeals, qualifying offences, detention/impounding grounds and release procedure.
- Validate the five-in-365 example against the operative law and policy before enabling it. Do not treat the sample threshold as legal advice.
- Complete privacy impact review, retention approval, security assessment, penetration test, disaster recovery and field acceptance.
- Keep challan submission and enforcement disabled until approvals and integration tests are complete.

## Safety invariants

- Unpaid status alone never changes a licence order.
- Repeat threshold only creates a referral candidate.
- Only an official authority order creates a recorded suspension/disqualification.
- Unverified plate detections never match a driver's licence.
- Detection does not authorise detention.
- Detention requires officer role and legal/order references.
- Every state-changing operation writes an audit row in the same transaction.
