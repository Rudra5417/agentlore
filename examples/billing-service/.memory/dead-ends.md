# Dead ends

<!-- rmem: one entry per '## ' heading -->

## Direct provider SDK calls from handlers
<!-- rmem
id: DEAD-2026-09-27-784d
type: dead-end
status: accepted
anchors: src/api/**
evidence: PR #4821 - double-charge incident, reverted in 9f31ac2
author: Rudra Patel
created: 2026-09-27
verified_at: 3b122b2
anchor_hash: f2f5c3062e2a8e0e
-->

We tried calling the provider SDK straight from the API handlers to shave a hop. Rejected: retries duplicated, idempotency keys missing, double-charges in prod.
