# Evidence and tests

> What testing actually showed, what it did not, and the suite that pins the invariants.

> Part of [agentlore](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

## Evidence: what testing actually showed

### First, what is and is not established

The distinction that matters: **the memory *mechanism* is proven, the memory's *benefit* is
not.**

| claim | status | evidence |
|---|---|---|
| memory can be recorded, anchored, and versioned in the repo | **proven** | 115 tests; the shipped example |
| staleness is detected by **content**, not git history | **proven** | a fixture whose memory root is a subdirectory; the `--relative` fix |
| the gate **blocks a PR** that rides its own dead end | **proven** | a real check run on PR #1: `memory-health: failure`, two annotations, then `success` when the same PR resolved it |
| an ambiguous id, an unresolvable `--since`, or a check that cannot run at all, **fails closed or is not counted** | **proven** | `TestFailClosed`, `TestSinceBoundary`; `agentlore verify 2026` exits 1 and changes nothing; a check with no boundary and a clean tree is excluded from the score, never reported as a pass |
| decided contradictions are caught | **proven, narrowly** | shared claim key + divergent value only; prose-vs-prose is deliberately out of scope |
| every host reads the compiled memory | **mixed** | [INTEGRATION.md](../INTEGRATION.md): most do; Gemini CLI needs config; all have truncation caps that silently drop the tail |
| **memory makes an agent do better work** | **preliminary** | [bench/](../bench/README.md): trap rate 4-in-7 → 2-in-22, Fisher p = 0.018 — but the control arm is only n=7 (the gateway ran out of credit mid-run), so this is "pending a full control arm", not a result. An earlier fixture returned a real null. |
| works in a monorepo | **unproven** | no per-package scoping; the `--relative` bug proved silent failure in subfolders |
| safe against a poisoned memory | **no** | `.memory/` is privileged input to a machine with credentials; no signing, no tamper-evidence, no secret scan on write |

Nothing in this repo asks you to believe a claim that is not on that table. If a row says
unproven, it is because the experiment has not been run or has come back null — not because the
result was inconvenient. `preliminary` means it ran and points somewhere, but the sample is too
small to claim.

### The agent-write-path arms

Identical repos, same task, fresh agents, no memory mentioned in the prompt.

| | memory protocol in `AGENTS.md` | tool + `.memory/` | result |
|---|---|---|---|
| arm 1 | yes | yes | 16 tests pass; wrote `DEAD-…0c5e`; re-verified 2 memories |
| arm 2 | no | no tool, no `.memory/` | 16 tests pass; wrote nothing |
| arm 3 | **no** (section deleted) | yes | 18 tests pass; wrote `DEAD-…15b1`; re-verified 3 |
| arm 4 | **no** | yes, v0.2 | 18 tests pass, gate green — **contaminated, see below** |

Arm 3 is the important one: with the memory protocol **removed** from `AGENTS.md`, the agent
still discovered the tool, wrote a memory, and re-stamped the memories its change invalidated.
Same title, same anchors, same verbatim evidence as the instructed run. The convention is not
load-bearing — the artifacts are. Ship the files; don't sermonise at the agent.

All arms converged on functionally identical code, which is the other half of the finding:
memory did not change what got built. It changed what survived.

Arm 2's silence proves nothing (no tool means no write path); it is a control for the
mechanism, not for willingness.

**Arm 4 was contaminated and proved nothing about the gate's reach.** It was meant to show
whether the gate teaches the fix with no instruction. Instead the agent found the tool's own
documentation and a sibling experiment copy while orienting, learned `--resolved-by` from the
docs rather than from a failure, and complied first time — so `dead-ends-settled` never fired
once. When measuring whether a guard changes behaviour, keep the agent's readable surface to the
repo under test: experiment copies, the tool's README and its docs directory all leak.

## Tests

```sh
python3 run_tests.py          # 115 tests, ~40s, stdlib only
```

No pytest, no dependencies — same as the tool. Each test builds a throwaway git repo in a temp
directory and asserts on real process output and real exit codes, because most of the bugs this
suite exists to prevent were invisible from the inside: a check that passed when it should have
failed, or a heading that kept asserting a condition its own commit had removed.

It pins the invariants that caught real bugs:

- **fail closed** — a memory with no fingerprint is an error, not a pass; and drift is decided
  by content, so pointing `verified_at` at a nonexistent commit (the squash-merge case) must
  still fail rather than go quiet
- **anchors resolve** — a deleted file must not be satisfied by its empty leftover directory,
  while live anchors must not be flagged as dead
- **normalisation may only downgrade** — reformatting yields a notice, and a real edit to the
  same file still fails
- **supersede marks the entry, not the file header** — the bug that made health unable to go
  green again
- **the accuracy gate** — a dead end riding the change that settled it fails, `--resolved-by`
  clears it, the `(settled)` marker is idempotent, and a committed dead end is not dragged into
  unrelated work
- **hazards** — no owner, no enforcement, a missing CODEOWNERS rule, and a catch-all that only
  *looks* like coverage all fail; creating the rule is the fix
- **retract** — keeps the body, labels the heading, requires a reason, is idempotent, and is
  excluded from live checks *in both directions* (an obligation while live, history after)
- **contradiction** — the same key with different values fails and names both sides; a retired
  entry no longer contradicts; a key with no value is a notice rather than a failure; and
  declaring coexistence without a reason is refused
- **retirement chains** — a supersede to a missing id, a chain landing on a retracted memory, and
  a hand-edited cycle all fail, and a 2-cycle is reported once rather than twice
- **rm** — removes only the target block, never the file header even for the first entry,
  leaves a parseable file, and says out loud that history is untouched
- **compile** — idempotent, preserves surrounding `AGENTS.md`, and hazards land as a Frozen
  areas section naming the control
- **a live dead end reaches `AGENTS.md`** — a dead end that is not compiled into the file
  agents actually read is a memory nothing delivers. Measured, not assumed: an agent trial
  had the agent solve the task without ever opening `.memory/`. Settled dead ends are
  excluded, because history is not a warning
- **an id names exactly one memory** — matching is anchored and exact, and an ambiguous
  prefix is refused rather than resolved. It was a substring test, so `verify 2026`
  re-stamped every memory created in 2026, and a re-stamp resets the staleness clock: the
  tool silently certified memories nobody had named
- **a memory root that is not the git root is still checked** — git reports changed paths
  relative to the repo root while `.memory/` and anchors are relative to the working
  directory; without `--relative` the two never match, so `dead-ends-settled` matched nothing
  and reported GREEN **while checking nothing** in any monorepo or service-subdirectory layout
- **`--since` fails closed** — an unresolvable boundary (a sha a shallow clone never
  fetched, `github.event.before` on a new branch) fails the gate instead of silently
  switching dead-ends-settled off; a resolvable one still passes, and the arm-4 shape is
  exercised end to end through the real `--since <base-sha>` path
- **CLI robustness** — `agentlore list | head` does not dump a stack trace

CI runs the suite on Python 3.9 and 3.12, then runs the shipped example through its own memory
gate and asserts the vendored copy still matches the tool at the root.

