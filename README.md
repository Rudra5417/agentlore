# rmem — git-reviewable repo memory for coding agents

Prototype v0.7.1. One file, stdlib only, no dependencies, and a test suite that runs in
fifteen seconds.

**The idea in one line:** coding agents forget everything between sessions, and the
facts worth keeping — decisions, dead ends, house rules — live in people's heads.
`rmem` lets the agent write them into the repo, as normal files, so they show up as
a **diff in the pull request that motivated them**. Teammates review memory like code.

> **Start here if you are adopting this:** [INTEGRATION.md](INTEGRATION.md) covers how the
> memory actually reaches an agent — which hosts read `AGENTS.md` and which need config, the
> truncation limits that silently drop the end of the file, and the one-command check that
> tells you whether the memory arrived at all. A gate that runs is not automatically a gate
> that works.
>
> **Does it actually help an agent?** Unproven. [bench/](bench/README.md) holds the harness and
> the method, so you can re-run the measurement instead of taking our word for it — including
> the honest null and an explanation of why that fixture could not detect an effect.

## Three rules the design is built on

1. **Markdown is the source of truth; the index is derived.** `.memory/*.md` is
   committed and reviewable. `.memory/index.db` is gitignored, rebuilt any time, never
   merged. No binary churn, no merge hell.
2. **Every memory is anchored to file globs, and drift is decided by CONTENT.** Two
   fingerprints of the anchored files are stored when the memory is stamped: the raw
   content hash (**the authority**) and a comment/whitespace-stripped view. If the raw
   hash moves, the memory is flagged **STALE** instead of silently steering the next
   agent. Deliberately *not* commit SHAs — squash-merging and rebasing rewrite history,
   and a memory system that can fail open is worse than none. The stripped view may only
   ever *downgrade* a real change to "reformatted" — it can never excuse one.
3. **Memory is a hint, never ground truth.** `check` reports; it does not enforce, and
   it never claims authority over code or a failing test. It does, however, fail closed:
   a memory with no fingerprint is an error, not a pass.

## Use

```sh
rmem init                                  # create .memory/, gitignore the index
rmem add --type decision|dead-end|convention --title T --body B \
         --anchor "src/billing/**" --evidence "PR #4821 - double charge" \
         [--resolved-by "what settled it"]
rmem add --type hazard --title T --body B --anchor "src/billing/**" \
         --owner "@epic/payments-team" --enforcement "CODEOWNERS"   # both required
rmem check [--brief|--github] [--since REF]  # MEMORY-HEALTH; exit 1 when broken
rmem recall "add a new payment provider"   # bounded context block for a task
rmem compile                               # emit conventions + hazards into AGENTS.md
rmem add ... --key refund.window_days --value 90  # a claim: comparable with other claims
rmem verify <id> [--anchor glob] [--resolved-by S]  # "still true" — re-stamp / narrow
rmem verify <id> --coexists-with <other> --coexists-why "..."   # both true, on purpose
rmem supersede <old-id> <new-id>           # was true, now replaced
rmem retract <id> --reason "..."           # was NEVER true — keeps the text, labels it
rmem rm <id>                               # must not exist at all — deletes the block
rmem list
```

Types: `decision`, `dead-end`, `convention`, `hazard`.

## MEMORY-HEALTH

Fourteen checks. The value is not the score — it is that a failure **names the broken thing**.

| check | catches |
|---|---|
| index-present | `.memory/` with no index |
| index-fresh | markdown edited in review without a rebuild |
| ids-present / ids-unique | malformed or duplicated entries |
| supersedes-resolve | a memory pointing at a replacement that does not exist |
| anchors-resolve | a memory anchored to code that is gone |
| dead-ends-evidenced | a "we tried this" with no proof — i.e. superstition |
| reviews-current | a `review_by` date that has passed |
| anchors-not-stale | the anchored content changed and the memory did not |
| anchors-stamped | a memory with no fingerprint — drift would be undetectable |
| dead-ends-settled | a dead end recorded by the very change that settled it |
| **hazards-enforced** | **a "do not touch" that no control actually enforces** |
| **claims-agree** | **two live memories claiming different things about the same key** |
| **supersedes-acyclic** | **a retirement chain that loops or lands on a retired memory** |
| **compile-current** | **`AGENTS.md` is not what `compile` would produce now — the memory is recorded but never delivered** |
| **no-secrets** | **a key, token, or private key looks like it is recorded in `.memory/`** |
| **no-pii** | **a payment card, SSN, phone number, or a bulk list of personal addresses** |

One softer signal is reported but never breaks the build: a **notice** when anchored files
were only reformatted (bytes changed, meaning identical).

## The accuracy gate

Every other tool in this space checks whether memory is **stale**. None checks whether it is
**accurate** — and that is the failure that actually happens.

Observed twice in testing, from two independent agent runs: an agent un-windowed a vendor's
`credit_note` path to make refunds work, then recorded the dead end *"The refund window
rejects credit notes too."* True before its own fix. Inverted after it. The body hedged
("before the fix") and the title did not, so a skimming agent would have read it as a live
warning and routed around a remedy that now works.

`dead-ends-settled` mechanises the fix: when a `dead-end` is added or changed in the same
change that modifies the files it is anchored to, the gate fails and demands a decision —
say what settled it (`--resolved-by`), or retype it as a `decision` and write the title about
the **current** rule. In CI it needs `--since <base-sha>` to know where the change begins.

### What its first real test revealed

Arm 4 *obeyed* the gate and the memory still came out dangerous. The agent added `resolved_by`
and a body ending "Settled by this change; the condition no longer holds" — and left the heading
exactly as it was:

```
before:  ## The refund window rejects credit notes too
after:   ## The refund window rejects credit notes too (settled)   <- the tool now does this
```

Agents read the markdown directly and the heading is the first thing they see, so an honest
body does not protect them. A gate can force an agent to *state* something; it cannot make an
agent reword a title it has already chosen. So the tool rewrites the heading itself —
`rmem add|verify --resolved-by` appends ` (settled)`, idempotently.

## Contradictions: what can be decided, and what must never be guessed

Every memory product has to answer "what if two memories disagree?". The honest answer is that
most of it cannot be answered mechanically, so `rmem` splits the problem.

**Decidable, so it is enforced.** A memory may declare a claim:

```sh
rmem add --type convention --title "Refunds close at 90 days" \
         --anchor 'src/billing/**' --key refund.window_days --value 90
```

Two *live* memories that declare the same key and different values contradict each other **by
construction** — no inference, no model, no similarity threshold, and therefore no
false-positive surface. `claims-agree` fails and names both sides.

**Not decidable, so it is never guessed.** Two memories that disagree in prose are not compared.
No embedding score, no language model in the check. That is not modesty, it is what the evidence
says:

| who tried | what actually happened |
|---|---|
| Graphiti (Zep), LLM edge invalidation | an unscoped candidate search retired **1,616 of 3,950 facts (41%)**; a hand audit of four found **three were collateral**, not real change — and it was silent |
| Mnemos, embedding similarity at threshold 0.55 | its own README's top known limitation: on long contexts it flags *"David works at Google"* vs *"Sarah works at Microsoft"* as a conflict |
| NLI models on context mismatch (REFNLI) | finetuned NLI and few-shot LLMs both fail to notice the mismatch, giving **>80% false positives** |
| STALE benchmark | "implicit conflict" — a later fact invalidating an earlier one without saying so — is unsolved; the best model scores **55.2%** |

A contradiction detector that is wrong is worse than none, in both directions: false positives
either train people to ignore the gate, or silently retire true memories. Graphiti's numbers are
what that looks like at production scale.

So the rules are:

* **Surface, never resolve.** `rmem` will not pick a winner. It names both sides and stops.
  Resolution is a human act, recorded as a normal diff.
* **Abstain on ambiguity.** A `--key` with no `--value` is a *notice*, not a failure. Incomplete
  metadata must never break the build.
* **Some conflicts are real and must not be collapsed.** "Python at work, JS for personal
  projects" is not a contradiction to resolve — it is a context-dependent pair. Declaring that
  takes a reason:

  ```sh
  rmem verify <id> --coexists-with <other> --coexists-why "partner-tier contracts override it"
  ```

  The pair then reports as `declared coexistence` and stops failing: visible, attributable, never
  silent. `--coexists-why` is required for exactly the same reason `retract` needs `--reason` —
  nothing gets switched off anonymously.

**Latest-wins is not the rule.** When one memory supersedes another, the tool records *that* it
happened and *what replaced it*; it does not decide the new one is true. `StateFuse`, the research
system closest to this posture, is explicit that its measured gain comes from **surfacing plus
abstention**, not from choosing a better winner.

### The retirement chain has to terminate

`supersedes-acyclic` closes the neighbouring hole: following "this was replaced by X" must land
on something live. A cycle (A replaced by B, B replaced by A), or a chain ending on a superseded
or retracted memory, means the area has no live rule **and nothing says so**. The easy way in is
`rmem supersede A <missing-id>` — it retires A whether or not the replacement exists.

## Hazards: "don't touch billing"

This is the type that shows what memory can and cannot carry.

**A hazard is not an enforcement mechanism.** A markdown file cannot stop an agent editing a
directory. CODEOWNERS, branch protection and permissions do that, and any org that genuinely
means "don't touch billing" already uses one of them. So `rmem` does not pretend to hold the
policy — it holds the **pointer**:

```sh
rmem add --type hazard --title "Billing ledger is frozen pending audit" \
         --anchor 'src/billing/**' --owner '@epic/payments-team' \
         --enforcement 'CODEOWNERS'
```

Both fields are required. `hazards-enforced` fails when either is missing, because a prohibition
that nothing enforces has the worst cost profile of any memory type: an agent obeys it and
refuses legitimate work, or ignores it and ships an incident.

When the enforcement names CODEOWNERS, the claim is checked against the real file: a rule must
cover the anchored path, **and** the owner the hazard names must be the owner CODEOWNERS assigns.
A catch-all (`* @someone`) nominally covers everything, so path coverage alone proves nothing.
Real output:

```
HAZ-2026-09-28-95d1  Auth internals are frozen (codeowners claim)
  claims: src/auth/**
  problem: src/auth/**: CODEOWNERS assigns @rudra, hazard claims @epic/security
```

The direction of the fix matters: the resolution is usually to **add the missing CODEOWNERS
rule**, not to delete the memory. Appending `/src/auth/** @epic/security` turns the gate green
because the control now genuinely exists. That is the whole point of the type.

Hazards compile into `AGENTS.md` as a separate **Frozen areas** section that names the owner and
the control, so an agent reads it as a platform boundary rather than a suggestion it may weigh
against the task.

### What a hazard cannot do

* It cannot block a merge. Nothing in a markdown file can. If the boundary is load-bearing, the
  control has to be real and this is only the signpost.
* It cannot be trusted when the control is missing — that is false governance, which is worse
  than an honest absence.
* It should never carry auth, secrets, CI-config or permission instructions. A memory that
  instructs an agent about security boundaries is the poisoning surface described below, and
  those decisions belong to the platform.

## Retiring a memory: retract, not delete

Once a memory is wrong, there are three different situations and they need different verbs.
Collapsing them into "delete" loses the evidence a reviewer needs.

* **verify** — it is still true. Re-stamp it against HEAD.
* **verify --anchor** — true, but scoped too broadly. Narrow it. (An anchor like `src/**` goes
  stale on every change; that is a scope bug, not a fact bug.)
* **supersede OLD NEW** — it was true and has been replaced. The old entry stays marked
  `(superseded)` with a pointer, so reviewers see *why* it changed.
* **verify --resolved-by** — a dead end that has been settled. Marks the heading `(settled)` so
  the next agent does not read the title as a live warning.
* **retract ID --reason** — it was **never** true. An agent inferred something plausible and
  wrong, or someone recorded a rule that was always mistaken. The text stays on disk, labelled
  `(retracted)` with the reason, and is excluded from live checks. `--reason` is required:
  a memory that disappears with no explanation is worse than one that was wrong, because the
  next agent cannot tell whether it was retracted or simply lost.

### `rm` — for one case only

`rmem rm <id>` deletes the entry block. It exists for text that must not be in the repository
at all: a pasted customer name, a token, an internal URL. Everywhere else `retract` is the right
verb, because deleting a memory removes the evidence along with the mistake.

It prints the limit every time:

```
! this rewrites the file, not history: the text is still in every existing clone and in `git log -p`.
  if it was sensitive, removing it here does not unpublish it.
```

That warning is the whole reason the command is safe to offer. `rm` rewrites a file; it does not
rewrite history, and in a shared repo the text is already in every clone. The deletion is itself
a reviewable diff, which is the real safeguard.

## Secrets and personal data in `.memory/`

`.memory/` is a worse place for a secret than ordinary source. Memories **ride the PR**, so a
value pasted into a note is committed, reviewed as prose, and then **compiled into `AGENTS.md`**,
which every agent loads every session. A leak here is delivered on purpose, repeatedly, to a
machine that holds credentials.

So there are two guards, because there are two ways a secret gets in:

```console
$ rmem add --type decision --title "Prod keys" \
    --body "gateway_token: REDACTEDFORTESTING0123456789ab" ...
refused: this memory looks like it carries a secret or personal data.
    line 15: a secret-looking assignment  [RE****************]
  Nothing was written.
```

`add` **refuses before writing** — a guard that warns and writes anyway has not guarded anything.
`check` re-reads the files, because a memory can also arrive by hand-edit or in someone else's
PR, which is exactly how a leak reaches a repo without anyone running the tool. Same shape as
every other failure here: annotated on the offending line, exit 1.

**What is decided, and what is only noticed.** Secrets are matched by construction — provider key
prefixes, PEM blocks, a secret-shaped name with an opaque value. They are *not* matched by entropy
alone, deliberately: this tool stores a commit SHA in every evidence field and a sha256
fingerprint in every entry, so an entropy rule fires on its own output. A guard that blocks
legitimate memories gets switched off, which is worse than no guard. Tests pin that down — commit
SHAs, fingerprints, prose *about* a secret, and a 16-digit non-card number must all pass.

Personal data splits the same way. A payment card, an SSN, a phone number, or a **bulk list** of
addresses fails: one address is a citation, ten are a customer list. A single email is a
**notice**, not a failure — naming the on-call owner is usually exactly what an ownership memory
should do.

**The value is never echoed.** Not in the refusal, not in the check output, not in the CI
annotation — all of which land in logs readable by anyone who can read the repo. Type, file and
line are enough to find it.

**What this is not.** A pattern guard, not a DLP system. It will not catch a secret with no
recognisable shape, or one you reworded to dodge it, and it is no substitute for a secret manager
or a pre-commit scan. It closes the one hole that is specific to this design: the file that is
committed *and* injected.

## Evidence: what testing actually showed

### First, what is and is not established

The distinction that matters: **the memory *mechanism* is proven, the memory's *benefit* is
not.**

| claim | status | evidence |
|---|---|---|
| memory can be recorded, anchored, and versioned in the repo | **proven** | 74 tests; the shipped example |
| staleness is detected by **content**, not git history | **proven** | a fixture whose memory root is a subdirectory; the `--relative` fix |
| the gate **blocks a PR** that rides its own dead end | **proven** | a real check run on PR #1: `memory-health: failure`, two annotations, then `success` when the same PR resolved it |
| an ambiguous id, or an unresolvable `--since`, **fails closed** | **proven** | `TestFailClosed`, `TestSinceBoundary`; `rmem verify 2026` exits 1 and changes nothing |
| decided contradictions are caught | **proven, narrowly** | shared claim key + divergent value only; prose-vs-prose is deliberately out of scope |
| every host reads the compiled memory | **mixed** | [INTEGRATION.md](INTEGRATION.md): most do; Gemini CLI needs config; all have truncation caps that silently drop the tail |
| **memory makes an agent do better work** | **unproven** | [bench/](bench/README.md): 12 v 12, no difference — and that fixture had no power to detect one |
| works in a monorepo | **unproven** | no per-package scoping; the `--relative` bug proved silent failure in subfolders |
| safe against a poisoned memory | **no** | `.memory/` is privileged input to a machine with credentials; no signing, no tamper-evidence, no secret scan on write |

Nothing in this repo asks you to believe a claim that is not on that table. If a row says
unproven, it is because the experiment has not been run or has come back null — not because the
result was inconvenient.

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

## How this differs from what already exists

* **AGENTS.md / CLAUDE.md** — plain prose, hand-written, loaded in full every session, and
  it rots silently. `rmem compile` feeds it: typed fragments are the source, AGENTS.md is a
  build target, so nothing has to change its read path.
* **mem0 / claude-mem / OpenMemory** — auto-capture into an opaque store. Not reviewable,
  not shared ground truth, not versioned with the code.
* **ADRs** — reviewable and versioned, but too much ceremony per decision and no agent
  write path. Nothing in an ADR tells you it has stopped being true.
* **fiberplane/drift** (the most-adopted tool here, ~146★) — AST-symbol anchoring, which is
  better at decay than a content hash. But it watches *docs*, has no typed decisions or
  supersession, and no accuracy check. `rmem` keeps a fail-closed variant: the stripped
  view can down-rank a reformat to a notice, never excuse a real change.
* **gitmem, stalebrain, agent-memory, sverklo, lore** — each owns a piece (conflict queues,
  decay, staged review, symbol graphs, monorepo scopes). Nobody composes it into one loop
  that also refuses to hand over memory it suspects is wrong — and nobody binds a memory to
  the control that enforces it.

## Use it as a GitHub Action

```yaml
name: memory-health
on: [pull_request]

permissions:
  contents: read

jobs:
  memory:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # only so an annotation can name the file that drifted
      - uses: Rudra5417/rmem@v1
        with:
          since: ${{ github.event.pull_request.base.sha }}
```

That is the whole integration: no vendored copy, no `tools/rmem`, nothing to keep in sync. The
action rebuilds the derived index, runs the gate, and annotates the diff.

| input | default | what it does |
|---|---|---|
| `since` | *(empty)* | commit/ref the change starts from; required for `dead-ends-settled` |
| `github` | `true` | emit check-run annotations and the job summary table |
| `fail-on-broken` | `true` | set `false` to report without blocking the merge |
| `compile-in-sync` | `false` | also assert the committed `AGENTS.md` matches `rmem compile` |
| `working-directory` | `.` | directory containing `.memory/` |

`since` is the only input worth setting, and it is the only one that matters: without it
`dead-ends-settled` cannot tell what your change touched, and a silent check is a disabled check.

`fetch-depth: 0` is **not** needed for drift detection — that is content-based, so a squashed or
shallow history still fails correctly. It is only there so the annotation can name the specific
file that invalidated a memory.

Two details the action gets right that a hand-rolled workflow usually does not:

* With `compile-in-sync`, it first checks that `AGENTS.md` is actually tracked. `git diff` is
  silent on an untracked file, so a naive in-sync check passes vacuously forever.
* `fail-on-broken: false` reports and emits a warning rather than quietly succeeding, because a
  gate that is configured off should say so out loud.

This repository runs its own shipped example through this exact gate on every pull request,
using the published tag — see `.github/workflows/memory-health.yml`. So the action and the
`--since` path are exercised continuously rather than only at release time.

If you would rather not depend on a third-party action, vendor the single file and run it
yourself — that is the next section, and it is the same tool either way.

## CI: the review gate

`.github/workflows/memory-health.yml` is the whole integration:

```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0     # only improves the message; drift detection is content-based
      - run: python3 tools/rmem index            # the index is derived; CI rebuilds it
      - run: |                                   # exit 1 -> the PR is blocked
          python3 tools/rmem check --github \
            --since "${{ github.event.pull_request.base.sha }}"
      - run: |
          python3 tools/rmem compile
          git diff --exit-code AGENTS.md         # committed AGENTS.md must match .memory/
```

`check --github` emits real check-run annotations, anchored at the line of the memory that
is wrong, plus a second annotation on the **changed code file** so it renders inline on the
diff — the memory file usually is not part of the PR, so an annotation on it alone would
never be seen. It also writes the MEMORY-HEALTH table into `$GITHUB_STEP_SUMMARY`.

Verified on a real private repo: a PR that added a billing function without updating memory
went red; re-verifying the memory in that same PR turned it green. (At the time the report
read `9/10` — the tool has since grown checks 10 through 17 and now reads `17/17`.)

## Tests

```sh
python3 run_tests.py          # 74 tests, ~25s, stdlib only
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
- **CLI robustness** — `rmem list | head` does not dump a stack trace

CI runs the suite on Python 3.9 and 3.12, then runs the shipped example through its own memory
gate and asserts the vendored copy still matches the tool at the root.

## Known gaps in this prototype

* **Contradiction detection covers DECLARED claims only.** Two memories that disagree in prose
  are not caught -- only memories that declare the same `--key` with different `--value`. That
  limit is the main design claim of v0.4.0, not an oversight; the section above is the evidence.
* **`--since` requires the base commit to be present.** The tool now refuses to run blind,
  so a `fetch-depth: 1` checkout fails the gate instead of quietly skipping the check. That is
  the intended direction, but it does mean the failure mode is now "loud error" rather than
  "silent pass" and the fix is in your checkout config.
* **No conflict queue as a separate artifact.** `gitmem` emits a browsable `conflicts.json`;
  here a contradiction is a failing check, so it is enforced rather than advisory.
* **No `rmem move`/re-anchor workflow.** Changing which files a memory covers means
  `verify --anchor`, which also re-stamps it; there is no way to re-scope without asserting
  it is still true.
* **CODEOWNERS matching is best-effort**, not GitHub's matcher. It errs toward finding a rule,
  because a false "covered" is a softer failure than failing a repo that is in fact protected.
* **Retrieval is term-overlap scoring, not semantic.** Agents read `.memory/*.md` directly in
  testing and never called `recall`, so this matters only past ~100 entries. FTS5 is available.
* **No monorepo scoping.** `lore` detects eight build systems and scopes memory per package;
  `rmem` has flat anchors.
* **No compression.** `lore` digests at 500 entries. `rmem` has no answer for growth.
* **No history sweep for `rm`.** The tool warns that history is untouched but cannot tell you
  whether a given string ever appeared in a memory. `git log -S` does that, unassisted.
* **No Marketplace listing.** The action is consumed by tag (`Rudra5417/rmem@v1`), which is
  all `uses:` needs; Marketplace needs a published release plus publisher settings.
* **No `latest`/floating major beyond `v1`.** Standard for actions (re-point `v1` at each
  release), but it does mean `@v1` is a moving target by design.
* **AST-aware anchors remain the right upgrade** for the raw hash; the stripped view only
  softens the most common false positive (reformatting), it does not eliminate it.
* **`dead-ends-settled` has never been observed firing on a live agent run.** It was proven by
  direct construction (exit 1 with the right entry and files), not by an uncontaminated trial.
  That trial is still owed.

## Enterprise notes

* **Self-hosted by construction.** One stdlib file, no SaaS, no vendor account, no data
  egress. The check runs in your CI on your runners.
* **Memory is instructions, so protect it like code.** Put `.memory/` in CODEOWNERS. A wrong
  or malicious entry is read by every agent in every session: it is a persistent prompt
  injection, not a typo. Never let a memory instruct anything about auth, secrets, CI config
  or permissions. Git history is forever, so treat every memory as published — no customer
  names, no incident detail, no internal-only hostnames. That is also why `retract` is the
  default way to remove a bad memory and `rm` is the exception.
* **The winner is a platform team, not a purchase.** Realistic adoption is vendoring this into
  a repo template with a required status check and an org-level baseline, not selling seats.
