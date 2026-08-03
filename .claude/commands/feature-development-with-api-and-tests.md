---
name: feature-development-with-api-and-tests
description: Workflow command scaffold for feature-development-with-api-and-tests in intelos.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /feature-development-with-api-and-tests

Use this workflow when working on **feature-development-with-api-and-tests** in `intelos`.

## Goal

Implements a new backend feature, exposes it via an API endpoint, and covers it with tests.

## Common Files

- `services/knowledge-engine/open_notebook/evidence/*.py`
- `services/knowledge-engine/api/routers/*.py`
- `services/knowledge-engine/api/main.py`
- `services/knowledge-engine/tests/*.py`
- `.github/workflows/evidence-core.yml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Define or update the feature contract/model (e.g., in evidence/auditable_models.py)
- Implement the feature logic (e.g., in evidence/auditable_answer.py)
- Expose the feature via an API endpoint (e.g., in api/routers/evidence.py)
- Register the new API route (e.g., in api/main.py)
- Write or update tests for the model/logic (e.g., in tests/test_auditable_answer_models.py, tests/test_auditable_answer.py)

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.