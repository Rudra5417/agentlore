# Contradictions

> What can be decided mechanically, what must never be guessed, and the prior art behind that line.

> Part of [rmem](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

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

