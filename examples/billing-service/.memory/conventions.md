# Conventions

<!-- rmem: one entry per '## ' heading -->

## Use httpx, never requests
<!-- rmem
id: CONV-2026-09-27-82fb
type: convention
status: accepted
anchors: src/api/**
author: Rudra Patel
created: 2026-09-27
verified_at: 3b122b2
anchor_hash: f2f5c3062e2a8e0e
-->

httpx is already a dependency and supports the async client we use in handlers.

## HTTP handlers live in src/api/handlers/
<!-- rmem
id: CONV-2026-09-27-a11f
type: convention
status: accepted
anchors: src/api/**
author: Rudra Patel
created: 2026-09-27
verified_at: 3b122b2
anchor_hash: f2f5c3062e2a8e0e
review_by: 2027-06-01
-->

One module per resource. Do not add handlers next to the app entrypoint.
