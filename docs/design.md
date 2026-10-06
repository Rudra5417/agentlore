# Design

> The rules the tool is built on, the checks it runs, and why accuracy is the gap nobody else closes.

> Part of [agentlore](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

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

## MEMORY-HEALTH

Eighteen checks. The value is not the score — it is that a failure **names the broken thing**.

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
| **no-agent-directives** | **a memory aimed at the agent's own process: concealment, bypassing the gate, credential handling, or weakening a control** |

One softer signal is reported but never breaks the build: a **notice** when anchored files
were only reformatted (bytes changed, meaning identical).

`no-agent-directives` is deliberately narrow, and the reason is worth stating. A `.memory/`
entry *is* an instruction — "use httpx, never requests" is the product working — so "this
sounds like an instruction" cannot be the rule. It matches only directives aimed at the
agent's own process, concealment, credentials, or a platform control: the cases where the
legitimate reading is absent, or narrow enough to be worth a stated reason. A deliberate one
is recorded with `--allow-directive "why"`, and an empty reason is refused, because nothing
gets switched off anonymously. **It is not injection detection.** A skilled injection written
to look like an ordinary house rule passes it, and the honest answer to that is not a cleverer
regex — it is that memory rides a pull request, in a diff, in front of a reviewer.

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
`agentlore add|verify --resolved-by` appends ` (settled)`, idempotently.

