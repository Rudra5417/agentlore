# Secrets and personal data in `.memory/`

> Why a memory is a worse place for a secret than ordinary source, and the two guards.

> Part of [agentlore](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

## Secrets and personal data in `.memory/`

`.memory/` is a worse place for a secret than ordinary source. Memories **ride the PR**, so a
value pasted into a note is committed, reviewed as prose, and then **compiled into `AGENTS.md`**,
which every agent loads every session. A leak here is delivered on purpose, repeatedly, to a
machine that holds credentials.

So there are two guards, because there are two ways a secret gets in:

```console
$ agentlore add --type decision --title "Prod keys" \
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

