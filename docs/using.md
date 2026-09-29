# Using it

> The full command reference, the memory lifecycle, and the CI integration.

> Part of [rmem](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

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

