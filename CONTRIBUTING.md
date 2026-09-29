# Contributing

The most valuable thing you can send is **a case where it does the wrong thing** — a false
failure, a missed staleness, a gate that went green when it should have gone red. This tool
exists to be trusted, so a reproducible wrong answer is worth more than a feature.

## Setup

One file, Python standard library, no dependencies. Nothing to install:

```bash
git clone https://github.com/Rudra5417/rmem
cd rmem
python3 run_tests.py                 # the suite, ~35s
python3 run_tests.py -k subdirectory # a subset
```

Supported on Python 3.9 and 3.12; CI runs both.

## The rules that matter here

**Write the failing test first.** Every bug fixed in this repo started as a test that failed for
the right reason. "It works now" is not a fix — the test that would have caught it is.

**Then confirm the test has teeth.** Run it against the *old* code and watch it fail. Two tests
in this repo's history passed against both the broken and the fixed version, and were caught only
by going back and checking — one seeded a taken id carrying a hardcoded date while the generator
stamped today's, so no collision was ever forced.

**A guard must fail closed.** Unresolvable `--since`, an ambiguous id, un-fingerprinted memory, a
blank `--resolved-by`: all refuse rather than pass. If a check cannot decide, it abstains
explicitly — it must never quietly return green.

**Match only what is decidable; never guess.** `claims-agree` catches two live memories with
divergent values for the same key and *refuses to pick a winner*. Prose-against-prose
contradiction detection was deliberately not built — see [docs/contradictions.md](docs/contradictions.md).

**One variable at a time in `bench/`.** Changing two things between samples means the difference
you measure is not the one you think. See [bench/README.md](bench/README.md).

## Changing a check

`rmem check` runs 18 checks and prints `MEMORY-HEALTH: N/N GREEN`. If you add one:

1. Add the check, and make its failure message name the fix.
2. Update the count assertion in `tests/test_rmem.py`.
3. Update the table in `README.md`, and the count in `run_tests.py`'s neighbours if it appears.
4. If it belongs in the action, wire the input in `action.yml` and add a job to
   `.github/workflows/tests.yml` that proves it fires **and** that it passes when it should.

A check nobody has watched fail is decoration.

## Vendored copies

`examples/billing-service/tools/rmem` is a byte-for-byte copy of the root `rmem`, and the suite
asserts that. After changing the tool:

```bash
cp rmem examples/billing-service/tools/rmem
```

The same test asserts each example's committed `AGENTS.md` matches `rmem compile` output. Both
exist because a stale generated file once went red in CI for three pushes unnoticed.

## Pull requests

- Keep the diff reviewable. One concern per PR.
- Explain **what breaks without it**, not just what it adds.
- If it changes behaviour, say which check fires and which test proves it.
- CI must be green — and check it, rather than assuming. A successful `git push` says nothing
  about whether the gate passed.

## Secret hygiene

Never commit a real credential, and never commit a *fake* one in a recognisable provider format
either: a literal `AKIA…` or `ghp_…` in a tracked file trips the pre-push scanner and third-party
secret scanning, and blocking the push is the guard working, not a false positive to silence with
an allowlist. Assemble fakes from pieces:

```python
FAKE_AWS_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
```

## Reporting a vulnerability

Please do not open a public issue — use
[private vulnerability reporting](https://github.com/Rudra5417/rmem/security/advisories/new).
See [SECURITY.md](SECURITY.md).
