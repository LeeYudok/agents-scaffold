---
paths:
  - "**/*.py"
  - "app/**/*.py"
  - "src/**/*.py"
---

# Python Rules

## Runtime & package management
- Prefer **uv** (if `uv.lock` exists). Otherwise pip.
- Pin dependencies: always commit `uv.lock` or `requirements.txt`.
- Do not commit virtual environments (`.venv/`, `venv/` — add to .gitignore).

## Types & linting
- **Type hints required** — on every function signature. No `Any`.
- `ruff check --fix .` + `ruff format .` — run before committing.
- `mypy` strict mode (`--strict`) — no errors before committing.
- No bare `except:` → use specific exception types.

## Testing
- pytest + pytest-asyncio (for async code).
- Coverage target 80% (`pytest --cov=app --cov-fail-under=80`).
- `asyncio_mode = "auto"` (set in `pyproject.toml`).

## Architecture (FastAPI-based)
- **Layer separation**: `routes/` (HTTP conversion only) → `services/` (business logic) → `repositories/` (DB).
- DI: use the `Annotated[T, Depends(...)]` form (FastAPI 0.95+).
- Always specify `response_model` on routers.
- async def by default — no synchronous blocking I/O in routes.

## Security
- Environment variables: `os.environ.get("XXX")` or pydantic-settings. No hardcoding.
- SQL: use an ORM (SQLAlchemy/SQLModel) or parameter binding. No f-string SQL.

## P0
- No hardcoded secrets
- `mypy` + `ruff` must pass with no errors before committing
- No `.env` staged into git

## P1
- Define `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` in `pyproject.toml`
- Update `pyproject.toml` + the lock file together when adding a dependency
