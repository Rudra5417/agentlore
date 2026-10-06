# Known gaps and enterprise notes

> What is not built, stated plainly, and what realistic adoption looks like.

> Part of [agentlore](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

## Known gaps in this prototype

* **Contradiction detection covers DECLARED claims only.** Two memories that disagree in prose
  are not caught -- only memories that declare the same `--key` with different `--value`. That
  limit is the main design claim of v0.4.0, not an oversight; the section above is the evidence.
* **`--since` requires the base commit to be present.** The tool now refuses to run blind,
  so a `fetch-depth: 1` checkout fails the gate instead of quietly skipping the check. That is
  the intended direction, but it does mean the failure mode is now "loud error" rather than
  "silent pass" and the fix is in your checkout config.
* **No conflict queue as a separate artifact.** `gitmem` emits a browsable `conflicts.json`;
  here a contradiction is a failing check, so it is enforced rather than advisory.
* **No `agentlore move`/re-anchor workflow.** Changing which files a memory covers means
  `verify --anchor`, which also re-stamps it; there is no way to re-scope without asserting
  it is still true.
* **CODEOWNERS matching is best-effort**, not GitHub's matcher. It errs toward finding a rule,
  because a false "covered" is a softer failure than failing a repo that is in fact protected.
* **Retrieval is term-overlap scoring, not semantic.** Agents read `.memory/*.md` directly in
  testing and never called `recall`, so this matters only past ~100 entries. FTS5 is available.
* **No monorepo scoping.** `lore` detects eight build systems and scopes memory per package;
  `agentlore` has flat anchors.
* **No compression.** `lore` digests at 500 entries. `agentlore` has no answer for growth.
* **No history sweep for `rm`.** The tool warns that history is untouched but cannot tell you
  whether a given string ever appeared in a memory. `git log -S` does that, unassisted.
* **Not listed on the Marketplace yet.** The action is consumed by tag (`Rudra5417/agentlore@v1`),
  which is all `uses:` needs. As of v0.8.0 the published release exists, so listing is one
  web-UI step away (publisher settings plus the Marketplace tick, which needs 2FA). Held on
  purpose, not blocked.
* **No `latest`/floating major beyond `v1`.** Standard for actions (re-point `v1` at each
  release), but it does mean `@v1` is a moving target by design.
* **AST-aware anchors remain the right upgrade** for the raw hash; the stripped view only
  softens the most common false positive (reformatting), it does not eliminate it.
* **`dead-ends-settled` has never been observed firing on a live agent run.** It was proven by
  direct construction (exit 1 with the right entry and files), not by an uncontaminated trial.
  That trial is still owed.

## Enterprise notes

* **Self-hosted by construction.** One stdlib file, no SaaS, no vendor account, no data
  egress. The check runs in your CI on your runners.
* **Memory is instructions, so protect it like code.** Put `.memory/` in CODEOWNERS. A wrong
  or malicious entry is read by every agent in every session: it is a persistent prompt
  injection, not a typo. Never let a memory instruct anything about auth, secrets, CI config
  or permissions. The gate refuses the blatant cases -- `no-agent-directives` catches
  concealment, skipping the check, credential handling and weakening a control -- but that is
  **not** injection detection: a skilled injection written as ordinary house rules passes, and
  review is the control. Nothing yet fails a PR that changes `.memory/` without a review. Git history is forever, so treat every memory as published — no customer
  names, no incident detail, no internal-only hostnames. That is also why `retract` is the
  default way to remove a bad memory and `rm` is the exception.
* **The winner is a platform team, not a purchase.** Realistic adoption is vendoring this into
  a repo template with a required status check and an org-level baseline, not selling seats.

