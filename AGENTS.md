# Repository Guidelines

## Code quality

- Write clean, simple, readable code that follows the existing project conventions.
- Keep changes focused and avoid unnecessary abstractions or duplication.
- Add or update relevant tests for every behavior change and bug fix.

## Required verification

Before completing any code change:

1. Run the complete test suite with `uv run pytest`.
2. Run Ruff with `uv run ruff check .`.
3. Resolve every test or lint failure introduced by the change.
