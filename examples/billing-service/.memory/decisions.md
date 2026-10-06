# Decisions

<!-- agentlore: one entry per '## ' heading -->

## Billing goes through the gateway (superseded)
<!-- agentlore
id: DEC-2026-09-27-6e39
type: decision
status: superseded
superseded_by: DEC-2026-09-27-5ca9
anchors: src/billing/**
author: Rudra Patel
created: 2026-09-27
verified_at: 81de8f1
-->

All charges and refunds must go through src/billing/gateway.py so we keep one place for retries, idempotency keys and audit logging. Direct provider calls bypass all three.

## Billing goes through the gateway
<!-- agentlore
id: DEC-2026-09-27-5ca9
type: decision
status: accepted
anchors: src/billing/**
author: Rudra Patel
created: 2026-09-27
verified_at: 1fc89b9
anchor_hash: e0659bc9227564c5
anchor_norm: 4ca6e11d5e3d2971
-->

All provider traffic goes through the Gateway class in src/billing/gateway.py. The idempotency key is generated in charge(); retries and audit logging live inside the gateway.
