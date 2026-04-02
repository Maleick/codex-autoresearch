# Interaction Wizard

Use this contract for every new interactive run.

## Minimum Questions

Confirm or infer:

1. What outcome matters most?
2. How should progress be measured?
3. What command verifies the target metric?
4. Is there a guard command that must continue to pass?
5. Should the run stay in `foreground` or move to `background`?

## Launch Rule

Do not start a new interactive loop until the user has had one chance to correct the setup summary.

## After Launch

Once the user approves the launch, keep going until:

- the stop condition is met
- the user stops the run
- the loop reaches a real blocker that requires human input
