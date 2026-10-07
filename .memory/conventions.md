# Conventions

<!-- agentlore: one entry per '## ' heading -->

## the vendored example copy stays byte-identical to the root tool
<!-- agentlore
id: CONV-2026-10-07-1778
type: convention
status: accepted
anchors: examples/billing-service/tools/agentlore
owner: maintainer
enforcement: tests.yml, example job (cmp agentlore examples/billing-service/tools/agentlore)
author: Rudra5417
created: 2026-10-07
verified_at: f3fee94
anchor_hash: 98a80c4dc85e5836
anchor_norm: 0f40891a6042a11d
-->

examples/billing-service/tools/agentlore is what a consumer copies, so it must match ./agentlore exactly. CI asserts cmp equality; a drift means the shipped example demonstrates a tool nobody is shipping. Re-copy it whenever the tool changes.

## a check that cannot run is never counted as a pass
<!-- agentlore
id: CONV-2026-10-07-a629
type: convention
status: accepted
anchors: agentlore
owner: maintainer
enforcement: tests/test_agentlore.py, TestSinceBoundary
author: Rudra5417
created: 2026-10-07
verified_at: f3fee94
anchor_hash: 0fa0c6e0cb3d0198
anchor_norm: e5d8fb0fc7b639ac
-->

The score has three states: pass, fail, and not-run. A check that cannot see what changed is excluded from the denominator and named in the header as (not run: ...). Adding a check that can silently skip its work and still report green is the exact fail-open this tool exists to catch.

## the gate requires a boundary and fails closed without one
<!-- agentlore
id: CONV-2026-10-07-948b
type: convention
status: accepted
anchors: action.yml
owner: maintainer
enforcement: action.yml, require-since; tests/test_agentlore.py, TestActionMetadata
author: Rudra5417
created: 2026-10-07
verified_at: f3fee94
anchor_hash: 3b6cdd8afe115950
anchor_norm: 0c2276517ed75f62
-->

Without --since the change-scoped check cannot see what a change touched, so the action defaults require-since to true and refuses to run blind: a green gate that skipped a check is worse than a red one. An unresolvable ref is a hard error naming the fix, never a silently empty change set.
