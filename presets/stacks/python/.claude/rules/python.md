---
paths:
  - "**/*.py"
  - "app/**/*.py"
  - "src/**/*.py"
---

# Python 규칙

## 런타임 & 패키지 관리
- **uv** 우선 (`uv.lock` 있으면). 없으면 pip.
- 의존성 고정: `uv.lock` 또는 `requirements.txt` 반드시 커밋.
- 가상환경 커밋 금지 (`.venv/`, `venv/` — .gitignore 추가).

## 타입 & 린트
- **타입 힌트 필수** — 모든 함수 시그니처. `Any` 금지.
- `ruff check --fix .` + `ruff format .` — 커밋 전 실행.
- `mypy` strict 모드 (`--strict`) — 에러 없이 커밋.
- bare `except:` 금지 → 구체적인 예외 타입 사용.

## 테스트
- pytest + pytest-asyncio (async 코드).
- 커버리지 목표 80% (`pytest --cov=app --cov-fail-under=80`).
- `asyncio_mode = "auto"` (`pyproject.toml`에 설정).

## 아키텍처 (FastAPI 기준)
- **레이어 분리**: `routes/` (HTTP 변환만) → `services/` (비즈니스) → `repositories/` (DB).
- DI: `Annotated[T, Depends(...)]` 형식 사용 (FastAPI 0.95+).
- 라우터에 `response_model` 항상 명시.
- async def 기본 — 동기 블로킹 I/O 라우트에 금지.

## 보안
- 환경변수: `os.environ.get("XXX")` 또는 pydantic-settings. 하드코딩 금지.
- SQL: ORM(SQLAlchemy/SQLModel) 또는 파라미터 바인딩. f-string SQL 금지.

## P0
- 시크릿 하드코딩 금지
- `mypy` + `ruff` 에러 없이 커밋
- `.env` git 스테이징 금지

## P1
- `pyproject.toml`에 `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` 정의
- 의존성 추가 시 `pyproject.toml` + lock 파일 동시 업데이트
