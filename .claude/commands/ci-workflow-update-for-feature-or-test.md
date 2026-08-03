---
name: ci-workflow-update-for-feature-or-test
description: Workflow command scaffold for ci-workflow-update-for-feature-or-test in intelos.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /ci-workflow-update-for-feature-or-test

Use this workflow when working on **ci-workflow-update-for-feature-or-test** in `intelos`.

## Goal

Updates CI workflow files to include or validate new features and tests, especially for pull requests.

## Common Files

- `.github/workflows/evidence-core.yml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Modify CI workflow file to include new tests or validation steps (e.g., evidence-core.yml)
- Trigger CI validation for new API or feature
- Ensure CI runs on pull requests

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.