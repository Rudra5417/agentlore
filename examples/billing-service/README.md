# rmem — git-reviewable repo memory for coding agents

Prototype v0.1.0. One file, stdlib only, no dependencies.

**The idea in one line:** coding agents forget everything between sessions, and the
facts worth keeping — decisions, dead ends, house rules — live in people's heads.
`rmem` lets the agent write them into the repo, as normal files, so they show up as
a **diff in the pull request that motivated them**. Teammates review memory like code.

## Three rules the design is built on

1. **Markdown is the source of truth; the index is derived.** `.memory/*.md` is
   committed and reviewable. `.memory/index.db` is gitignored, rebuilt any time, never
   merged. No binary churn, no merge hell.
2. **Every memory is anchored to file globs, and drift is decided by CONTENT.** A
   fingerprint of the anchored files is stored when the memory is stamped; if the code
   changes underneath it, the memory is flagged **STALE** instead of silently steering
   the next agent. Deliberately *not* commit SHAs — squash-merging and rebasing rewrite
   history, and a memory system that can fail open is worse than none.
3. **Memory is a hint, never ground truth.** `check` reports; it does not enforce, and
   it never claims authority over code or a failing test. It does, however, fail closed:
   a memory with no fingerprint is an error, not a pass.

## Use

```sh
rmem init                                  # create .memory/, gitignore the index
rmem add --type dead-end --title "..." --body "..." \
         --anchor "src/api/**" --evidence "PR #4821 - double-charge incident"
rmem check                                 # MEMORY-HEALTH report; exit 1 when broken
rmem check --brief                         # one line, for session start
rmem recall "add a new payment provider"   # bounded context block for a task
rmem compile                               # emit conventions into AGENTS.md
rmem supersede <old-id> <new-id>           # retire a memory that is no longer true
rmem verify <id> [--anchor glob]           # "still true" — re-stamp / narrow scope
rmem list
```

Types: `decision`, `dead-end`, `convention`.

## MEMORY-HEALTH

Ten checks. The value is not the score — it is that a failure **names the broken thing**.

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

## The three ways a stale memory gets resolved

Without these, the gate is just nagging and teams disable it.

* **verify** — the memory is still true; re-stamp it against HEAD.
* **verify --anchor** — the memory is true but was scoped too broadly; narrow it.
  (An anchor like `src/**` goes stale on every change; that is a scope bug, not a fact bug.)
* **supersede** — the memory is now false; retire it and point at its replacement.
  The old entry stays in history marked `(superseded)`, so reviewers see *why* it changed.

## How this differs from what already exists

* **AGENTS.md / CLAUDE.md** — plain prose, hand-written, loaded in full every session, and
  it rots silently. `rmem compile` feeds it: typed fragments are the source, AGENTS.md is a
  build target, so nothing has to change its read path.
* **mem0 / claude-mem / OpenMemory** — auto-capture into an opaque store. Not reviewable,
  not shared ground truth, not versioned with the code.
* **ADRs** — reviewable and versioned, but too much ceremony per decision and no agent
  write path.
* **fiberplane/drift, gitmem, stalebrain, agent-memory, lore** — each owns a piece of this
  (anchoring, conflict queues, decay, review gates). Nobody composes all of it into one loop
  that also refuses to hand over memory it suspects is stale.

## CI: the review gate

`.github/workflows/memory-health.yml` is the whole integration:

```yaml
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0     # only improves the message; drift detection is content-based
      - run: python3 tools/rmem index            # the index is derived; CI rebuilds it
      - run: python3 tools/rmem check --github   # exit 1 -> the PR is blocked
      - run: |
          python3 tools/rmem compile
          git diff --exit-code AGENTS.md         # committed AGENTS.md must match conventions.md
```

`check --github` emits real check-run annotations, anchored at the line of the memory that
is wrong, plus a second annotation on the **changed code file** so it renders inline on the
diff — the memory file usually is not part of the PR, so an annotation on it alone would
never be seen. It also writes the MEMORY-HEALTH table into `$GITHUB_STEP_SUMMARY`.

Verified on a real private repo: a PR that added a billing function without updating memory
went red with `MEMORY-HEALTH: 9/10 BROKEN`; re-verifying the memory in that same PR turned
it green.

## Known gaps in this prototype

* **Staleness is a content hash, not AST-aware.** Reformatting an anchored file marks the
  memory stale. `fiberplane/drift` normalizes via tree-sitter and is the right upgrade.
* No `rmem rm` — removing an entry means editing the markdown by hand.
* Retrieval is term-overlap scoring, not semantic. Fine under ~100 entries; FTS5 is available.
* The Action expects `rmem` vendored at `tools/rmem`. A published action is the real fix.
* Anchors that are too broad (`src/**`) generate noise. There is no lint for that yet —
  arguably there should be, and it is probably the next check worth writing.
