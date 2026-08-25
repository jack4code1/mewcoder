# Plan

Extend task results with their worktree lease, create and clean worktrees in a
`TaskRunner.run_isolated` lifecycle, and add `TeamCoordinator.run_all` with a
concurrency cap and context-conflict rejection.
