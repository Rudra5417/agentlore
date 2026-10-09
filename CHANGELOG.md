# Changelog

## Two version streams, and why the tags look out of order

Read the tag list top-down and it appears to regress: `v1.0.0`, `v1.0.1`, then `v0.5.1`. That
is not a rollback. There are two things being versioned, and the first two releases conflated
them:

| stream | what it is | today |
|---|---|---|
| **`v1`** (major channel) | the **action interface** — the contract `uses: Rudra5417/agentlore@v1` depends on. A moving tag, updated as the tool improves, exactly like `actions/checkout@v4`. | `v1` |
| **`v0.x`** (product) | the **tool** — `agentlore --version`, the CLI you run locally. | `0.9.1` |

`v1.0.0` and `v1.0.1` were tagged as if the product were 1.0. Development carried on at `0.x`,
which is why they sit above later product releases in date order.

**From here on:** product releases are `v0.x` (this file), and `v1` is only ever the action
channel. The product reaches `1.0.0` when the honest-status table in the README has no
*unproven* rows that matter — not before.

Notable entries are grouped by what they fixed, not by commit. Every release notes its evidence.

---

## v1 — 2026-10-07 — the action refuses to run blind (action channel, not a product release)

An action-channel change with no CLI change, so there is no `v0.x` entry for it:
`agentlore --version` is still `0.9.1` and the tool behaves identically. What changed is what
`uses: Rudra5417/agentlore@v1` does when it has no boundary.

`since` is what lets `dead-ends-settled` see what a change touched. With no `--since` and a
clean tree that check cannot run — and the previous release taught the score to say so
(`not run: dead-ends-settled`) rather than counting it as a pass. But a gate that is green
having skipped a check is still the fail-open this tool exists to catch, and "not run" in a
parenthesis is easy to miss.

`require-since` now defaults to **true**, and the action fails the step with an error naming
the fix instead of warning and passing:

    'since' is empty and require-since is true, so the change-scoped check would never run
    and this gate would be green having checked less than it claims.

**This is a behavior change for anyone on `@v1` who never passed `since`** — their gate now
fails where it previously passed. That is the point: a check that could not run was being
reported as a passing gate. Pass the boundary, or set `require-since: false` to run the static
checks alone.

Not hypothetical, and not someone else's repository: this repository's own `memory-health.yml`
passed `github.event.pull_request.base.sha` on a `push` trigger, where it is empty, so its
example gate had been running blind since it was written. It now uses
`github.event.pull_request.base.sha || github.event.before`, which is a real commit on a push
to main.

The `action` CI job gains a third case — no boundary, must fail — because a gate nobody has
watched fail in its default configuration is decoration.

**The repo now keeps its own memory.** Six entries in `.memory/`, compiled to `AGENTS.md`, and
gated by a new `dogfood` job that uses the published action by tag rather than the working
tree, so the job exercises what a consumer actually gets. It earned its keep on the first run:
`check` came back `17/18 BROKEN -- hazards-enforced`, because a hazard had no owner and no
enforcement. A hazard with nobody accountable is a wish, and the tool said so about mine.

Evidence: `TestActionMetadata.test_the_action_refuses_to_run_without_a_boundary` pins the
default, and the `action` job asserts all three outcomes in `tests.yml`. 116 tests.

---

## v0.9.1 — 2026-10-07 — a check that could not run was counted as a pass

The gate could print `18/18 GREEN` while one of the eighteen had not run. With no `--since` and a
clean working tree there is no change set to read, so `dead-ends-settled` — the check that catches
a dead end recorded by the very change that settled it — inspected nothing and reported `ok`.

That is the **default state in CI**: a checkout leaves a clean tree, and
`github.event.pull_request.base.sha` is empty on a `push` trigger, so wiring the action into a push
workflow produced a permanently green gate that checked nothing. The action warned about this
("a silent check is a disabled check") without failing closed on it.

`ok` is now three states. A check that cannot run reports `n/a`, is **excluded from the
denominator**, and is named in the header:

    MEMORY-HEALTH: 17/17 GREEN (not run: dead-ends-settled)

An unresolvable `--since` still fails closed, and an absent one with real working-tree changes
still runs. Evidence: `TestSinceBoundary.test_a_missing_boundary_is_not_run_never_a_pass`, and
`TestBaseline.test_fresh_repo_is_green` now asserts the denominator excludes it. 115 tests.

Also here: `tests.yml` builds the wheel and sdist on every push, so a packaging break fails on the
push that caused it rather than mid-publish; the test matrix covers the 3.10 and 3.11 the
classifiers already claimed; and `MANIFEST.in` prunes `bench/` and egg-info, so the sdist carries
only tracked files.

## v0.9.0 — 2026-10-06 — the name was invisible, so it changed

The tool was called `rmem`. Search that and you get Cambridge's relaxed-memory model, an academic
video-segmentation paper, and a motor-refurbishment firm — not this. A dev tool that cannot be found
by name starts every launch behind. Renamed to **agentlore** everywhere: the CLI, the action, the
docs, the examples, the tests.

- 40 files and 3 paths renamed (`agentlore`, `tests/test_agentlore.py`,
  `examples/billing-service/tools/agentlore`). `--version` reports `0.9.0`.
- Packaging added (`pyproject.toml`), so `uv tool install` / `pipx install` / `pip install` work
  alongside the single-file curl install. The zero-dependency, self-contained file is unchanged —
  the package is a wrapper around it, not a replacement.
- Repository renamed to `Rudra5417/agentlore`; old URLs redirect.

Evidence: 114 tests, CI green.

## v0.8.0 — 2026-09-29 — a memory is an instruction, so the gate reads it as one

`.memory/` is compiled into `AGENTS.md`, so an entry there is a persistent instruction to whatever
agent reads it. New check `no-agent-directives`, plus a fail-open closed in the id generator.

- `no-agent-directives` refuses memory that tells the agent to conceal something from the people
  reviewing it, to ignore its instructions, to skip the gate, to handle credentials, or to weaken a
  platform control. It is **not injection detection**: a memory *is* an instruction ("use httpx,
  never requests" is the product working), so "sounds like an instruction" cannot be the rule.
  Exempting one needs `--allow-directive "why"`, and an empty reason is refused.
- `add` fails closed when the ids in use cannot be read, instead of carrying on with an empty set.
  The quiet version hands out a duplicate id, which makes `verify`, `supersede` and `retract`
  ambiguous. A guard that cannot read its own state has not guarded anything.
- The suite no longer writes into the repo it is testing — it used to run `index` and `compile`
  inside the shipped example, regenerating the tracked `AGENTS.md` it then asserted on. A failing
  run now keeps its evidence (test names, hash seed, tool SHA, full output) in `.test-failures/`.

The README became a product page with the depth moved into `docs/`, and gained an install section.
`action.yml`'s description was 170 characters — past the Marketplace limit of 125 — and contained a
`: ` that broke the YAML; a local test now enforces both.

Evidence: 108 tests, 18 checks, CI green on 5 jobs plus the live gate.

## v0.7.1 — 2026-09-29 — a secret in the memory is delivered on purpose

`.memory/` rides the PR and is compiled into `AGENTS.md`, which every agent loads on a machine
that holds credentials — so a value recorded there is committed, reviewed as prose, and then
injected. Two new checks (`no-secrets`, `no-pii`) plus a refusal at the write path.

- `add` refuses before writing. A guard that warns and writes anyway has not guarded anything.
- `check` re-reads the files, because a memory can also arrive by hand-edit or in someone else's PR.
- Matched by construction, never by entropy alone: the tool stores a commit SHA in every evidence
  field and a sha256 fingerprint in every entry, so an entropy rule fires on its own output.
- Cards (Luhn-checked), SSNs, phone numbers and bulk address lists fail; a single email is a
  notice, because naming the on-call owner is usually right.
- The value is never echoed, in the refusal, the check output or the CI annotation.

Two bugs found by pointing it at a real repository — both in the first version of the scanner:
`search` reported one finding per *line* (so two secrets on a line counted as one, and the bulk
rule never fired), and a `\b` anchor missed `gateway_token` / `AWS_SECRET_ACCESS_KEY` /
`db_password` because `_` is a word character.

## v0.6.1 — 2026-09-29 — an empty audit trail is not an audit trail

`verify --resolved-by ""` cleared a stale flag while writing no reason, so a caller using
`--resolved-by "$UNSET_VAR"` believed an audit trail had been recorded. Both flags now use a
sentinel default, and a blank value is refused with exit 1 without touching anything.

## v0.6.0 — 2026-09-29 — the memory you recorded but never delivered

New check `compile-current`: the committed block in `AGENTS.md` must be what `agentlore compile` would
produce now. Uncompiled memory is memory nothing delivers, and the failure is silent in every
direction. It abstains when there is no `AGENTS.md` or no compiled block, because not every repo
compiles to one.

## v0.5.1 — 2026-09-29 — an id collision can fail the gate

The id suffix is 4 random hex characters (16 bits), so two memories in one repo can draw the same
id; one collision failed `ids-unique` in CI on a two-entry fixture. A randomly flaky gate is worse
than a broken one for a tool whose value is being trusted. Ids now regenerate on collision and
widen rather than loop.

## v1.0.1 — 2026-09-28 — two fail-opens closed

`compile-in-sync` now requires `AGENTS.md` to be *tracked* (git diff is silent on untracked files,
so the comparison passed vacuously), and `fail-on-broken: false` emits a warning rather than
succeeding quietly.

## v1.0.0 — 2026-09-28 — repo memory that can be checked

First published action: `uses: Rudra5417/agentlore@v1`. Typed memories in `.memory/`, a compiled
`AGENTS.md`, and a gate that fails a pull request when code moves under a memory and the memory
does not.
