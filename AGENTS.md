# AGENTS.md

<!-- agentlore:begin (generated from .memory/ - do not edit) -->
## House rules

- **the vendored example copy stays byte-identical to the root tool** `examples/billing-service/tools/agentlore`
  examples/billing-service/tools/agentlore is what a consumer copies, so it must match ./agentlore exactly. CI asserts cmp equality; a drift means the shipped example demonstrates a tool nobody is shipping. Re-copy it whenever the tool changes.
- **a check that cannot run is never counted as a pass** `agentlore`
  The score has three states: pass, fail, and not-run. A check that cannot see what changed is excluded from the denominator and named in the header as (not run: ...). Adding a check that can silently skip its work and still report green is the exact fail-open this tool exists to catch.
- **the gate requires a boundary and fails closed without one** `action.yml`
  Without --since the change-scoped check cannot see what a change touched, so the action defaults require-since to true and refuses to run blind: a green gate that skipped a check is worse than a red one. An unresolvable ref is a hard error naming the fix, never a silently empty change set.

### Frozen areas

_Do not edit these. The enforcement lives in the repo's controls, not in this file._

- **an sdist ships untracked files unless MANIFEST.in prunes them** `MANIFEST.in` -- owner: maintainer; enforced by: tests.yml, package job (asserts the sdist carries only tracked files)
- **git diff needs --relative or anchors never match from a subdirectory** `agentlore` -- owner: maintainer; enforced by: tests/test_agentlore.py, TestSubdirectoryLayout

<!-- agentlore:end -->
