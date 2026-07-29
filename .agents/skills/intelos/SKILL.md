```markdown
# intelos Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill introduces the core development patterns and workflows used in the `intelos` Python codebase. It covers coding conventions, commit styles, and step-by-step guides for adding new backend features, exposing them via APIs, and ensuring robust continuous integration (CI) practices. Whether you're contributing new features, updating tests, or maintaining CI pipelines, this guide will help you align with the established standards of the repository.

## Coding Conventions

- **Language:** Python
- **Framework:** None detected

### File Naming
- Use `snake_case` for all file and module names.
  - Example: `auditable_answer.py`, `test_evidence_answer_api.py`

### Import Style
- Use **relative imports** within modules.
  - Example:
    ```python
    from .auditable_models import EvidenceModel
    ```

### Export Style
- Use **named exports** (explicitly export classes, functions, etc.).
  - Example:
    ```python
    __all__ = ["EvidenceModel", "AuditableAnswer"]
    ```

### Commit Patterns
- Use [Conventional Commits](https://www.conventionalcommits.org/) with the following prefixes:
  - `feat`: New features
  - `fix`: Bug fixes
  - `docs`: Documentation changes
  - `test`: Adding or updating tests
  - `ci`: CI/CD or workflow changes
- Keep commit messages concise (average: ~41 characters).
  - Example: `feat: add auditable answer API endpoint`

## Workflows

### Feature Development with API and Tests
**Trigger:** When adding a new backend feature that is exposed via an API and needs to be tested  
**Command:** `/new-api-feature`

1. **Define or update the feature contract/model**
   - Edit or create a model in `evidence/auditable_models.py`.
   - Example:
     ```python
     class AuditableAnswer(BaseModel):
         answer: str
         created_at: datetime
     ```
2. **Implement the feature logic**
   - Add logic in `evidence/auditable_answer.py`.
   - Example:
     ```python
     def create_auditable_answer(data):
         # Implementation logic
         pass
     ```
3. **Expose the feature via an API endpoint**
   - Add a new route in `api/routers/evidence.py`.
   - Example:
     ```python
     @router.post("/auditable-answer")
     def create_answer(answer: AuditableAnswer):
         return create_auditable_answer(answer)
     ```
4. **Register the new API route**
   - Update `api/main.py` to include the new router if necessary.
     ```python
     app.include_router(evidence_router)
     ```
5. **Write or update tests for the model/logic**
   - Add or update tests in `tests/test_auditable_answer_models.py` and `tests/test_auditable_answer.py`.
   - Example:
     ```python
     def test_create_auditable_answer():
         # Test logic
         pass
     ```
6. **Write or update tests for the API endpoint**
   - Add or update tests in `tests/test_evidence_answer_api.py`.
7. **Update CI workflows to include new tests**
   - Edit `.github/workflows/evidence-core.yml` to ensure new tests are run.

**Files Involved:**
- `services/knowledge-engine/open_notebook/evidence/*.py`
- `services/knowledge-engine/api/routers/*.py`
- `services/knowledge-engine/api/main.py`
- `services/knowledge-engine/tests/*.py`
- `.github/workflows/evidence-core.yml`

---

### CI Workflow Update for Feature or Test
**Trigger:** When adding new tests or features that require CI validation or test runs  
**Command:** `/update-ci`

1. **Modify CI workflow file**
   - Update `.github/workflows/evidence-core.yml` to include new tests or validation steps.
2. **Trigger CI validation**
   - Push changes or open a pull request to ensure CI runs on the new or updated code.
3. **Ensure CI runs on pull requests**
   - Confirm that the workflow is configured to trigger on PRs.

**Files Involved:**
- `.github/workflows/evidence-core.yml`

## Testing Patterns

- **Framework:** Unknown (no explicit framework detected)
- **Test File Pattern:** Python test files use `snake_case` and are named like `test_*.py`.
- **API and model logic are tested separately.**
- **Test Example:**
  ```python
  def test_create_auditable_answer():
      # Arrange
      # Act
      # Assert
      pass
  ```

## Commands

| Command          | Purpose                                                      |
|------------------|--------------------------------------------------------------|
| /new-api-feature | Scaffold and implement a new backend feature with API & tests|
| /update-ci       | Update CI workflow files to include or validate new tests    |
```
