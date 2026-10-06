# INTEGRATION.md — how repo memory actually reaches an agent

`agentlore` writes memory into `.memory/` and compiles the always-on subset into `AGENTS.md`.
Whether an agent ever **sees** that memory is a property of the **host tool**, not of the
model and not of the memory. A host that does not load `AGENTS.md` does not get the memory,
no matter how good the memory is.

Read this before assuming a gate that runs is a gate that works.

## The two halves

| half | what it is | where it is wired |
|---|---|---|
| **Delivered** | `AGENTS.md` carries house rules, frozen areas, and rejected approaches | the agent's own startup context loading |
| **Enforced** | `agentlore check` fails a PR when memory goes stale or contradicts itself | CI, via the published action |

Both are needed. Memory the agent never reads changes nothing; memory nothing checks rots.
The action half is covered in the README (`Use it as a GitHub Action`). This file covers the
first half, per host, because it is the half people get wrong.

## Host support (verified against primary sources, Sep 2026)

| host | reads `AGENTS.md`? | how | notes |
|---|---|---|---|
| **Hermes** | **yes** | loaded at startup from the AGENTS.md chain (git root → working dir), plus on-demand per-subdirectory hints | priority: `.hermes.md` → `AGENTS.md` → `CLAUDE.md` → `.cursorrules`; **first non-empty type wins and shadows the rest** |
| **Claude Code** | **yes** | "Claude can read a repository's `AGENTS.md` files, on their own or alongside `CLAUDE.md`" | `/memory` lists what loaded; before v2.1.280 a directly-read `AGENTS.md` was not listed |
| **Codex** | **yes** | "Codex reads `AGENTS.md` files before doing any work" | global `~/.codex/AGENTS.md`, repo root, nested `AGENTS.override.md` overrides |
| **GitHub Copilot** | **yes** | agent instructions; nearest `AGENTS.md` in the tree takes precedence | alternatives: `.github/copilot-instructions.md`, `.github/instructions/*.instructions.md` |
| **Cursor** | **yes** | `AGENTS.md` in project root and subdirectories, no config | nearest wins, combined with parents |
| **Gemini CLI** | **only if configured** | default context file is `GEMINI.md`; `AGENTS.md` requires `context.fileName` | set `{"context": {"fileName": ["AGENTS.md", ...]}}` |
| Aider, Zed, Windsurf, Jules, Amp, Factory | **unverified here** | widely described as `AGENTS.md` consumers, but I did not read each one's docs | verify per tool before relying on it |

Sources: [agents.md](https://agents.md/) (60k+ projects, stewarded by the Agentic AI Foundation
under the Linux Foundation) · [Codex](https://learn.chatgpt.com/docs/agent-configuration/agents-md) ·
[Claude Code memory](https://code.claude.com/docs/en/memory) · [Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions) ·
[Cursor rules](https://cursor.com/docs/rules) · [Gemini CLI context files](https://geminicli.com/docs/cli/gemini-md/)

For Hermes the mechanism is in the source rather than a doc page: `agent/prompt_builder.py`
(`_CONTEXT_FILE_CANDIDATES`, the AGENTS.md chain) and `agent/subdirectory_hints.py`
(`_HINT_FILENAMES`, `_MAX_HINT_CHARS`).

## Keep it small — every host truncates

`AGENTS.md` lands in the context window of every session, so the cap is a real constraint,
and `agentlore compile` bounds its output for exactly this reason.

| host | limit |
|---|---|
| Hermes | on-demand hints capped at `_MAX_HINT_CHARS = 32_000`, head+tail truncated with a **logged warning**; startup context files capped by `context_file_max_chars` |
| Codex | `project_doc_max_bytes`, default **65536** |
| Claude Code | recommends **under 200 lines**; warns past that, skips a file over 4 MiB |
| Cursor | none documented |

Exceed the cap and the tail — usually the last sections — silently stops arriving, or arrives
truncated. Keep the compiled block well under the smallest limit, and put anything long in
`.memory/` where it is read on demand rather than always.

## Monorepos: nearest file wins

Hermes, Codex, Cursor, and Copilot all resolve the **nearest** `AGENTS.md` walking up the
tree, and Codex supports `AGENTS.override.md` per directory. So the standard shape is a root
`AGENTS.md` plus one per package.

**Current limit:** `agentlore compile` writes **one** `AGENTS.md` at the memory root. Publishing
per-package summaries is not built — see the gap list in the README.

## Gotchas that will bite

- **Gemini CLI needs an explicit config change.** Without it, `AGENTS.md` is not read at all
  and the memory looks like it is doing nothing.
- **In Hermes, a `.hermes.md` shadows `AGENTS.md`.** If one exists, the compiled memory is not
  loaded. Same shadowing rule down the chain: `AGENTS.md` shadows `CLAUDE.md` and `.cursorrules`.
- **Claude Code and a pre-existing `CLAUDE.md`.** Keep one file: have `CLAUDE.md` import it
  (`@AGENTS.md`), rather than maintaining two that drift.
- **Hermes blocks context files that trip its injection scan.** `_scan_context_content` scans
  context files and **blocks** matches, and repo-authored files (`AGENTS.md`, `.cursorrules`)
  are not exempted. Write memories as descriptions of convention and history — which is what
  they are — never as bare imperative overrides ("ignore previous instructions", "always
  execute this"). Those are the exact strings the scanner exists to stop.
- **Copilot PR review reads instructions from the HEAD branch, not the base.** A pull request
  can therefore change the instructions its own reviewer reads. This is worth knowing before
  treating a green agent review as independent of the diff.
- **A bare script harness is not a host.** A model in a loop with a file-reading tool will
  often not open `AGENTS.md` on its own. Measured: with only a system-prompt line saying
  "read AGENTS.md first", 3 of 3 runs never opened it, even though the directory listing
  showed the file. Every host above solves this by loading it for the model. If you are
  building your own harness, load `AGENTS.md` into the prompt yourself.

## Confirm the memory actually arrived

Never assume. Ask the agent directly, in a session in the repo:

> "Quote, verbatim, what your project instructions say about `<topic>`."

- **Claude Code**: run `/memory` and look for the path.
- **Hermes**: the `[Subdirectory context discovered: …]` block appears when files in that
  directory are touched.
- **Codex**: `codex --cd <dir> --ask-for-approval never "List the instruction sources you loaded."`
- **Any host**: if the answer cannot quote the text, the memory did not arrive. Fix delivery
  before drawing any conclusion about whether the memory helps.

## Wiring it up

```yaml
# .github/workflows/memory-health.yml  -- the enforced half
- uses: Rudra5417/agentlore@v1
  with:
    since: ${{ github.event.pull_request.base.sha }}
```

Then, once per repo:

```bash
agentlore init                              # create .memory/
agentlore add --type convention ...         # record a house rule
agentlore compile                           # emit AGENTS.md  <- the delivered half
agentlore check --brief                     # MEMORY-HEALTH: N/N GREEN
```

Commit `AGENTS.md` and `.memory/`; gitignore `**/.memory/index.db`. If `AGENTS.md` is not
committed, nothing delivers it — the action's `compile-in-sync` input checks exactly that.
