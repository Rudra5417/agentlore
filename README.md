# rmem — git-reviewable repo memory for coding agents

Prototype v0.3.0. One file, stdlib only, no dependencies.

**The idea in one line:** coding agents forget everything between sessions, and the
facts worth keeping — decisions, dead ends, house rules — live in people's heads.
`rmem` lets the agent write them into the repo, as normal files, so they show up as
a **diff in the pull request that motivated them**. Teammates review memory like code.

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
rmem supersede <old-id> <new-id>           # retire a memory that is no longer true
rmem verify <id> [--anchor glob] [--resolved-by S]  # "still true" — re-stamp / narrow
rmem list
```

Types: `decision`, `dead-end`, `convention`, `hazard`.

## MEMORY-HEALTH

Twelve checks. The value is not the score — it is that a failure **names the broken thing**.

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

## The four ways a stale or settled memory gets resolved

Without these, the gate is just nagging and teams disable it.

* **verify** — the memory is still true; re-stamp it against HEAD.
* **verify --anchor** — the memory is true but was scoped too broadly; narrow it.
  (An anchor like `src/**` goes stale on every change; that is a scope bug, not a fact bug.)
* **supersede** — the memory is now false; retire it and point at its replacement.
  The old entry stays in history marked `(superseded)`, so reviewers see *why* it changed.
* **verify --resolved-by** — a dead end that has been settled. Keeps the history, records what
  settled it, and marks the heading `(settled)` so the next agent does not read the title as a
  live warning.

## Evidence: what testing actually showed

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
  write path.
* **fiberplane/drift** (the most-adopted tool here, ~146★) — AST-symbol anchoring, which is
  better at decay than a content hash. But it watches *docs*, has no typed decisions or
  supersession, and no accuracy check. `rmem` keeps a fail-closed variant: the stripped
  view can down-rank a reformat to a notice, never excuse a real change.
* **gitmem, stalebrain, agent-memory, sverklo, lore** — each owns a piece (conflict queues,
  decay, staged review, symbol graphs, monorepo scopes). Nobody composes it into one loop
  that also refuses to hand over memory it suspects is wrong — and nobody binds a memory to
  the control that enforces it.

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
read `9/10` — the tool has since grown checks 10, 11 and 12 and now reads `12/12`.)

## Known gaps in this prototype

* **No `rmem rm`** — removing an entry means editing the markdown by hand.
* **No contradiction detection.** Two live memories that disagree are not caught. `gitmem`
  has a conflict queue; `lore` flags them in an audit. This is the hardest remaining piece
  and is deliberately not faked with keyword heuristics.
* **CODEOWNERS matching is best-effort**, not GitHub's matcher. It errs toward finding a rule,
  because a false "covered" is a softer failure than failing a repo that is in fact protected.
* **Retrieval is term-overlap scoring, not semantic.** Agents read `.memory/*.md` directly in
  testing and never called `recall`, so this matters only past ~100 entries. FTS5 is available.
* **No monorepo scoping.** `lore` detects eight build systems and scopes memory per package;
  `rmem` has flat anchors.
* **No compression.** `lore` digests at 500 entries. `rmem` has no answer for growth.
* **The Action expects `rmem` vendored at `tools/rmem`.** A published action is the real fix.
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
  names, no incident detail, no internal-only hostnames.
* **The winner is a platform team, not a purchase.** Realistic adoption is vendoring this into
  a repo template with a required status check and an org-level baseline, not selling seats.
