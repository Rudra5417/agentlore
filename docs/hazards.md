# Hazards: “don't touch billing”

> A hazard is a pointer to a control, not a control. What the type can and cannot do.

> Part of [agentlore](../README.md) — adopt it via [INTEGRATION.md](../INTEGRATION.md).

## Hazards: "don't touch billing"

This is the type that shows what memory can and cannot carry.

**A hazard is not an enforcement mechanism.** A markdown file cannot stop an agent editing a
directory. CODEOWNERS, branch protection and permissions do that, and any org that genuinely
means "don't touch billing" already uses one of them. So `agentlore` does not pretend to hold the
policy — it holds the **pointer**:

```sh
agentlore add --type hazard --title "Billing ledger is frozen pending audit" \
         --anchor 'src/billing/**' --owner '@epic/payments-team' \
         --enforcement 'CODEOWNERS'
```

Both fields are required. `hazards-enforced` fails when either is missing, because a prohibition
that nothing enforces has the worst cost profile of any memory type: an agent obeys it and
refuses legitimate work, or ignores it and ships an incident.

When the enforcement names CODEOWNERS, the claim is checked against the real file: a rule must
cover the anchored path, **and** the owner the hazard names must be the owner CODEOWNERS assigns.
A catch-all (`* @someone`) nominally covers everything, so path coverage alone proves nothing.
Real output:

```
HAZ-2026-09-28-95d1  Auth internals are frozen (codeowners claim)
  claims: src/auth/**
  problem: src/auth/**: CODEOWNERS assigns @rudra, hazard claims @epic/security
```

The direction of the fix matters: the resolution is usually to **add the missing CODEOWNERS
rule**, not to delete the memory. Appending `/src/auth/** @epic/security` turns the gate green
because the control now genuinely exists. That is the whole point of the type.

Hazards compile into `AGENTS.md` as a separate **Frozen areas** section that names the owner and
the control, so an agent reads it as a platform boundary rather than a suggestion it may weigh
against the task.

### What a hazard cannot do

* It cannot block a merge. Nothing in a markdown file can. If the boundary is load-bearing, the
  control has to be real and this is only the signpost.
* It cannot be trusted when the control is missing — that is false governance, which is worse
  than an honest absence.
* It should never carry auth, secrets, CI-config or permission instructions. A memory that
  instructs an agent about security boundaries is the poisoning surface described below, and
  those decisions belong to the platform.

