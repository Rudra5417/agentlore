<!-- Keep this short. A reviewer should know what changed and why in under a minute. -->

## What breaks without this

<!-- The reason the change exists. "It adds X" is not a reason; "X silently does nothing without
     this" is. -->

## What it changes

<!-- One concern per PR. If this is two things, it is probably two PRs. -->

## Proof

<!-- Which check fires, and which test proves it? If you added or changed a check:
       - [ ] the test fails against the old code and passes against the new one
       - [ ] the count assertion in tests/test_agentlore.py still matches
       - [ ] the table in README.md mentions it -->

- [ ] `python3 run_tests.py` is green
- [ ] CI is green — actually checked, not assumed
- [ ] If I added a check, I have watched it fail for the right reason

## Notes for the reviewer

<!-- Anything you tried that did not work, or that you are unsure about. Honest beats tidy. -->
