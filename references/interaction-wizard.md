# Interaction Wizard

Use this contract for every new interactive run.

## Minimum Questions

Confirm or infer:

1. What outcome matters most?
2. What scope is actually in play?
3. How should progress be measured?
4. What command verifies the target metric?
5. Is there a guard command that must continue to pass?
6. Should the run stay in `foreground` or move to `background`?

Use `python scripts/autoresearch_wizard.py` to build the first setup summary, then only ask about fields that are still missing or risky.

## Launch Rule

Do not start a new interactive loop until the user has had one chance to correct the setup summary.

## After Launch

Once the user approves the launch, keep going until:

- the stop condition is met
- the user stops the run
- the loop reaches a real blocker that requires human input
