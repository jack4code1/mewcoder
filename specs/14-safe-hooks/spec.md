# Approval-Gated Project Hooks

Project `.mewcode/hooks.yaml` hooks may run Bash commands on `task_start` or
`task_complete`, but only through the existing execution gateway. Missing
authorization blocks the task; hooks never bypass tool approval.
