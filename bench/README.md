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
   before trusting a classifier that reports "no difference".
7. **Counting a run that crashed.** Unmodified code reads as a behavioural failure.

## Results so far

Fixture: `idempotent-refund`. Task: make retried refunds idempotent. Outcome: does `refund()`
dedupe on `request_id` (correct) or on `(order_id, amount_cents)` (the trap)? Both make the
given suite green — verified before running — so the tests cannot tell them apart and the
memory is the only signal.

| configuration | valid runs | trap | correct |
|---|---|---|---|
| no memory (arm B) | 12 | 0 | 12 |
| with memory, no injection | 12 | 0 | 12 |

**No difference, and the null is explained rather than mysterious:** the correct answer is
derivable from the repo — `request_id` is a parameter of the very function being edited — so a
capable model solves it unaided. The fixture therefore has little power to detect an effect,
and the honest reading is *this experiment cannot tell us whether memory helps*, not *memory
does not help*.

What the experiment did establish, at full strength:

- Delivery is a property of the **host**, not the model (row 2 above; see
  [INTEGRATION.md](../INTEGRATION.md)).
- A gate that reports GREEN can be checking nothing at all — the trial is what surfaced the
  `--since` and path-relativity fail-opens fixed in v0.4.1.

## What a fixture with power would look like

The discriminating task must ask for something **not derivable from the repo** — a fact about
the outside world, which is the only thing institutional memory adds that reading the code
cannot:

- A provider rule the code does not encode (a threshold, an enumerated set of allowed values).
- A compliance obligation with no trace in the source.
- Two repo-consistent options where the wrong one is the one a reasonable engineer picks, and
  the memory is the only tiebreaker.

Not yet built. It is deliberately not built as an arbitrary number chosen to make the memory
look necessary: a rigged fixture would spend the one asset that makes this project worth
anything.

## Caveats

Small samples; one model; one task. This is a pilot harness meant to be re-run against a real
repo and a real host, not a published effect size. If you run it and get a different answer,
that is a result — please open an issue with your output.
