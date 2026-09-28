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

## The 409 fallback to a credit note loops (settled)
<!-- rmem
id: DEAD-2026-09-28-8613
type: dead-end
status: accepted
anchors: src/billing/**
evidence: ProviderError(409, "charge is 120 days old, beyond the 90 day refund window: issue a credit note")
author: Rudra Patel
created: 2026-09-28
verified_at: 7cd74bf
anchor_hash: e0659bc9227564c5
anchor_norm: 4ca6e11d5e3d2971
resolved_by: PR #1 - this change removed the fallback
-->

Falling back to a credit_note when the provider refuses a refund does not work: credit_note runs the same window check, so the same 409 comes back and the retry loops. Settled by this change, which raises OutOfRefundWindow instead of falling back.
