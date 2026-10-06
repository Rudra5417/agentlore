# Security

## Reporting a vulnerability

Use GitHub's [private vulnerability reporting](https://github.com/Rudra5417/agentlore/security/advisories/new).
Please do not open a public issue for a security problem.

This is a solo-maintained project, so there is no formal SLA — but a security report is the one
thing that gets looked at the same day. Expect an acknowledgement within a few days and an honest
"this is out of scope" if that is the answer.

Please include: what an attacker gains, the smallest reproduction, and the affected versions.

## Supported versions

Only the head of `main` and the current `v1` action channel. The tool is pre-1.0; there are no
backports, and tagging a release does not create a supported branch.

## What this tool actually does, so you can judge its attack surface

`agentlore` is a single Python file using only the standard library. It:

- **reads** the files your memories are anchored to, to fingerprint them;
- **writes** `.memory/*.md` and `AGENTS.md`;
- **runs** in CI as a composite action (`python3 agentlore index` then `python3 agentlore check`).

No network access, no telemetry, no subprocess except `git` for diff and revision information.
It reads no environment secrets and has no credentials of its own.

## The risk that is specific to this design — read this one

**`.memory/` is privileged input to a machine that holds credentials.** Whatever is recorded
there is compiled into `AGENTS.md`, which a coding agent loads into its context every session.
That makes a memory a **prompt-injection channel**: a `.memory/` entry that reads "ignore your
previous instructions and …" is not a note, it is an attack — and it arrives through a pull
request, which is a path a reviewer may treat as prose rather than as executable instruction.

`agentlore` defends against this in one narrow way, and not in the important one. The gate's
`no-agent-directives` check refuses memory that tells the agent to conceal something from the
people reviewing it, to ignore its instructions, to skip this gate, to handle credentials, or to
weaken a platform control: directives with no legitimate reading in a repo memory, or none that
survives being written down beside a reason (`--allow-directive`, which refuses an empty one).
**It is not injection detection.** A memory *is* an instruction — "use httpx, never requests" is
the product working — so "sounds like an instruction" cannot be the rule, and a skilled injection
written to look like ordinary house rules passes it.

What is still missing: there is no signing, no provenance check, and no tamper-evidence, so any
contributor who can modify `.memory/` can change what every agent is told. Some hosts (Hermes, for
one) scan context files for injection patterns and block matches — but that is the host's
protection, not this tool's, and you should not rely on it.

Treat `.memory/` with the same review standards as a workflow file or a CODEOWNERS entry, and
protect it with branch rules and required reviewers. That is the current, honest answer; a
signature-checked memory is a gap, and it is listed as one in the README.

## Secret scanning: a pattern guard, not a DLP system

`no-secrets` and `no-pii` (checks #16/#17) match credentials and personal data by *construction* —
provider key prefixes, PEM blocks, secret-shaped names with opaque values, Luhn-valid card
numbers, SSNs, phone numbers, and bulk address lists. They will not catch a secret with no
recognisable shape, a value reworded to dodge the pattern, or a secret encoded in a form the
patterns do not model.

They exist to close the hole specific to this design — a file that is both committed *and*
injected — and are no substitute for a secret manager, a pre-commit scanner, or keeping the value
out of the repo in the first place.
