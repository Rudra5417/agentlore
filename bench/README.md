# bench — measuring whether repo memory changes agent behaviour

`rmem`'s central claim is that recording decisions, dead ends, and house rules in the repo
makes coding agents do better work. That claim is testable, so it is tested here rather than
asserted. The harness, the fixture, and the method are all in this directory, because a
measurement you cannot re-run is not evidence.

**Current status: the claim is NOT yet demonstrated.** See [Results](#results-so-far).

## Run it

```bash
python3 bench/run_trial.py --dry-run     # build both arms, no model calls, no cost
BENCH_URL=http://localhost:11434/v1/chat/completions BENCH_MODEL=llama3:latest \
  python3 bench/run_trial.py --runs 6
```

`--dry-run` builds both arms and **asserts they are identical apart from the memory**. Run it
first, always: if the arms differ by anything else, the comparison measures the wrong variable
and every number that follows is worthless.

`BENCH_URL` is any OpenAI-compatible chat-completions endpoint. `BENCH_PACE` (seconds between
calls) exists because a rate-limited endpoint returning 429s is easy to mistake for model
behaviour. `--runs` is per arm.

## The method

| element | choice | why |
|---|---|---|
| arms | A: fixture + `.memory/` + compiled `AGENTS.md`. B: fixture only | the only variable is the memory |
| delivery | `AGENTS.md` is **injected into the system prompt** | real hosts load it themselves; a harness that merely asks the model to read it is not a stand-in |
| containment | four tools, every path resolved under the arm directory | the agent cannot read the answer from anywhere else |
| history | `.git` stripped from both arms | a commit message would identify the treatment arm |
| model | one model, pinned | a gateway that routes per request swaps models mid-run |
| validity | a run counts only if it **finished** and the file **changed** | a crashed run leaves pristine code, which scores as a "failure" of that arm |
| measurement | the artifact is read by the runner | the model's own summary of what it did is not evidence |

## Seven ways to produce a confident wrong answer

Each of these cost a real run before it went in the list:

1. **A task whose answer is derivable from the repo.** If a model can solve it unaided, both
   arms succeed and the test has no power — a null result then says nothing about memory.
2. **Not delivering the memory.** Given only "read `AGENTS.md` first", a model skipped it in
   3 of 3 runs while the directory listing showed the file.
3. **Not verifying delivery landed.** Probe it: *"quote verbatim what your project
   instructions say."* Without that, "no effect" and "never arrived" are indistinguishable.
4. **A model that changes mid-run.** Escalation and fallback retries silently swap models.
5. **A commit message that reveals the arm.**
6. **An unchecked classifier.** Label two hand-written implementations — correct and trap —
   before trusting a classifier that reports "no difference". And never re-write the classifier
   for a quick look: doing exactly that mid-analysis put every run in the trap column, because
   the *correct* implementation's record dict also contains `amount_cents`. Reading the source
   would not have caught it; running the verified classifier did.
7. **Counting a run that crashed.** Unmodified code reads as a behavioural failure.
8. **A fixture that resets only the state it knows about.** See below — this one nearly
   produced the finding that memory *harms* agents.
9. **Changing two things between samples.** A later sample differed from the first in both
   `max_tokens` and whether the memory was injected, so the two are not comparable at all.
   One variable at a time, or the difference you measure is not the one you think.

### A near-miss worth recording

The first version of this fixture reset state by clearing `LEDGER` by name. The task is "make a
retried refund idempotent", and keeping a separate cache keyed by `request_id` is a completely
reasonable way to do that — but the cache survived `setUp`, so such a solution failed on a stale
entry left by a *previous test* (`0 != 5000` from a record that should not have existed). The
failure has nothing to do with idempotency.

The consequence was not hypothetical. With the memory injected, the agent chose the cache style,
watched tests fail, re-ran them, and burned its step budget in 5 runs of 6; without the memory it
finished in 6–7 steps every time. Read at face value that is a clean result — *memory makes agents
worse* — and it is entirely an artifact of the fixture.

`setUp` now calls `importlib.reload(refund)`, which resets **all** module state and is agnostic to
how a solution stores what it has already refunded. Verified against three implementations:

| implementation | old fixture | fixed fixture |
|---|---|---|
| dedupe on `request_id`, scanning the ledger | green | green |
| dedupe on `request_id`, separate cache | **RED** | green |
| trap: dedupe on `(order, amount)` | green | green |

The lesson generalises: a benchmark fixture must be indifferent to *how* a correct answer is
implemented, or it will report the implementation style as a treatment effect. Before trusting
any arm, check that more than one reasonable correct implementation passes.

## The second fixture: `unsettled-void`

The first fixture could not detect an effect — its answer was derivable from the code, so both
arms solved it and the null said nothing about memory. This one asks for something the repo does
not encode.

| element | choice |
|---|---|
| task | make `cancel_order` work for a charge that has not settled |
| the trap | refund it — which is what the existing code does for settled charges, so it is the natural extension |
| the correct answer | reverse the authorization |
| where the fact lives | **the memory.** Nothing in the code says a refund on an unsettled charge is refused |

The fixture's provider stub accepts anything, so **the trap makes the visible suite GREEN**. That
is the point: the tests cannot tell the two apart, so the memory is the only signal that can.

The measurement is a **probe**, not a regex. `fixtures/unsettled-void/probe.py` patches the
provider to behave like the real one — a refund on an unsettled charge is rejected — then runs the
arm's own code and reports what happened. It is behavioural, so a solution that catches the
rejection and falls back still counts: it works in production.

The dry run asserts four properties, and the first three are worthless without the fourth:

- the arms differ only by the memory
- the untouched fixture fails (so there is a task)
- **both** hand-written implementations pass the visible suite (the fixture has power)
- the probe labels the hand-written correct and trap implementations correctly (the ruler works)

Known limitation, stated rather than hidden: the probe exercises the **unsettled** path only. An
implementation that voided a *settled* charge would score as correct here. `results.json` keeps each
run's source (`primary_src`), so that is checkable after the fact rather than assumed away.

## Results so far

Fixture: `idempotent-refund`. Task: make retried refunds idempotent. Outcome: does `refund()`
dedupe on `request_id` (correct) or on `(order_id, amount_cents)` (the trap)? Both make the
given suite green — checked automatically by `--dry-run` — so the visible tests cannot tell them
apart and the memory is the only signal that can.

Latest run, fixture fixed, one model (`gpt-4o-mini`), 6 runs per arm:

| configuration | runs | finished | file parses | chose correct | chose the trap |
|---|---|---|---|---|---|
| no memory (arm B) | 6 | 6 | 6 | 6 | 0 |
| memory injected (arm A) | 6 | 3 | 4 | 4 | 0 |

**No difference in what was built.** Every run in both arms that produced a file that loads
keyed on `request_id` — 10 of 12 — and arm A's two remaining runs, which wrote files that do not
parse (a docstring missing its closing quotes), were textually aiming at the same key. **The trap
was never chosen, with or without the memory.** The memory changed nothing that this fixture can
see.

Note the three separate measures, because they are not the same and conflating them is how a null
becomes a finding: **finished** (did the agent stop on its own), **parses** (is the result usable),
and **correct** (which key did it use). Arm A is 3 / 4 / 4 on those. Reporting only the first
would understate it; reporting only the last would overstate it.

The null is explained rather than mysterious: the correct answer is derivable from the repo —
`request_id` is a parameter of the very function being edited — so a capable model solves it
unaided, and the memory can only confirm what the code already said. The honest reading is
*this experiment cannot tell us whether memory helps*, which is not the same as *memory does not
help*.

The one between-arm difference is **file quality** (2 of 6 arm A runs produced a file that does
not load, vs 0 of 6 in arm B), and it is **not** a memory effect: those runs are the model
emitting a broken docstring and then re-running the failing tests instead of repairing it. The
harness parser was verified faithful (escaped triple-quotes round-trip exactly), so this is model
competence, and at n=6 it is not a significant difference. It does say something useful about
method: **with a small model, run-to-run variance in code-generation correctness can be larger
than the effect you are trying to measure.**

What the experiment did establish, at full strength:

- Delivery is a property of the **host**, not the model (row 2 above; see
  [INTEGRATION.md](../INTEGRATION.md)).
- A gate that reports GREEN can be checking nothing at all — the trial is what surfaced the
  `--since` and path-relativity fail-opens fixed in v0.4.1.

## What a fixture with power looks like

The discriminating task must ask for something **not derivable from the repo** — a fact about
the outside world, which is the only thing institutional memory adds that reading the code
cannot:

- A provider rule the code does not encode (a threshold, an enumerated set of allowed values).
- A compliance obligation with no trace in the source.
- Two repo-consistent options where the wrong one is the one a reasonable engineer picks, and
  the memory is the only tiebreaker.

`unsettled-void` is that fixture, and it is built: see the result above. It is not an arbitrary
number chosen to make the memory look necessary — the provider rule is real, the trap is the
change a reasonable engineer makes, and both implementations leave the visible suite green. A
rigged fixture would spend the one asset that makes this project worth anything.

## Result: `unsettled-void`

One model (`openai/gpt-4o`), one fixture, one task. The outcome is measured by the probe, not
read from the source: did the arm's own code actually return the customer's money against a
provider that behaves like the real one?

| arm | runs | suite green | chose correct | chose the trap | trap rate |
|---|---|---|---|---|---|
| with memory | 22 | 21 | 20 | 2 | 9% |
| no memory | 7 | 7 | 3 | 4 | 57% |

Fisher exact, two-sided: **p = 0.018**.

The visible suite was green in 21 of the 22 memory runs and all 7 control runs, and it was green
in **every** run that mattered here: the trap runs it fails to catch are exactly the ones where
the agent shipped something that breaks in production. The tests cannot see the difference, the
memory is the only signal that can, and it moved the trap rate from 4-in-7 to 2-in-22.

**This is preliminary, and the reason matters.** The memory arm reached n=22 across two sittings;
the control arm reached only n=7 because the gateway account ran out of credit mid-run (HTTP 402)
and the rest of the control arm could not be collected. A large effect can reach significance on
a small control arm — that is what happened — but the control arm is the weaker half of this
table, and the honest statement is "preliminary, pending a full control arm", not "p = 0.018,
done".

Two things the run established beyond the number:

- **The compiled block works through its title alone.** `read_memory` was false in every single
  run — neither arm ever opened `.memory/`. Arm A's `AGENTS.md` says only *"Refunding an
  unsettled charge is refused by the provider"* plus a pointer to `.memory/dead-ends.md`, and
  that title was enough to steer the agent off the trap, because the alternative was discoverable
  in the provider module the agent did read. The fix does not have to be inlined for the warning
  to land.
- **The instrument, not the model, was the first thing to fail.**

### Three instrument failures that each looked like a finding

Recorded because each one, published, would have been a confident wrong answer:

1. **10 of 12 runs "invalid" was the harness, not the model.** The contract never said how to put
   a multi-line file inside a JSON string, so the model used a triple-quoted block with raw
   newlines, which is not JSON. Three of those ended a run.
2. **The fix for that made it worse.** Telling the model to "escape newlines as \n" made it
   double-escape, so files landed with literal backslash-n and died on a `SyntaxError` that read
   like the agent's own mistake.
3. **A dead gateway looked like a slow model.** The account's 402 came back wrapped in a 502, and
   502 is a retryable code, so every step retried nine times with backoff — about nine minutes
   per step. The harness now detects a permanent upstream failure, names it, caps the retry
   budget, and the runner aborts the trial instead of collecting more runs from a model it cannot
   reach.

## Caveats

Small samples; one model; one task. This is a pilot harness meant to be re-run against a real
repo and a real host, not a published effect size. If you run it and get a different answer,
that is a result — please open an issue with your output.
