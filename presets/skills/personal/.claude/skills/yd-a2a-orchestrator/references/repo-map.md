# 저장소 지도 (repo-map)

지휘자가 "이 작업은 어느 저장소 소관인가" 를 먼저 판단할 때 보는 표다. 저장소별 규칙 원본은
그 저장소의 `AGENTS.md`·`AGENTS.yaml` 이며, 여기에는 위임에 필요한 최소 사실만 적는다.
표와 원본이 어긋나면 원본이 옳다.

| 저장소 | 역할 | 로컬 경로 | 원격 |
| :--- | :--- | :--- | :--- |
| `dok3search` | 폐쇄망 문서·코드 검색 플랫폼 모노레포. Rust 백엔드 워크스페이스 + React/Vite 프론트 | `/Users/dok123/workspace/github.com/LeeYudok/dok3search` | GitHub `LeeYudok/dok3search` |
| `dok3search-design` | `dok3search` 의 설계 SSOT(아키텍처·데이터 계약·운영 프로토콜) | `/Users/dok123/workspace/github.com/LeeYudok/dok3search-design` | GitHub `LeeYudok/dok3search-design` |
| `llmgw` | 설정 기반 LLM 게이트웨이(Rust `gateway-rs`, 운영 콘솔 `admin/`) | `/Users/dok123/workspace/gitlab.doksam.com/llmgw` | GitLab `llmgw` |
| `llm` | LLM 벤치·모델 선정·llmgw 운영 배포 설정(`deploy/llmgw/llmgw.toml`) | `/Users/dok123/workspace/gitlab.doksam.com/llm` | GitLab `llm` |
| `a2a-acp-bridge` | A2A/ACP 에이전트 브리지(Go 단일 바이너리) | `/Users/dok123/workspace/github.com/LeeYudok/a2a-acp-bridge` | GitHub `LeeYudok/a2a-acp-bridge` |
| `agents-scaffold` | 에이전트 스킬·룰·훅·프리셋 SSOT | `/Users/dok123/workspace/github.com/LeeYudok/agents-scaffold` | GitHub `LeeYudok/agents-scaffold` |
| `doksam-ui` | doksam 프로젝트 공통 UI 표준(컴포넌트·패턴·템플릿, shadcn 기반) | `/Users/dok123/workspace/gitlab.doksam.com/doksam-ui` | GitLab `doksam-ui` |

## 검증 명령 (게이트)

작업을 완료로 적기 전에 그 저장소의 아래 명령을 실제로 돌리고 출력을 증거로 남긴다.

### dok3search

```sh
cargo fmt   --manifest-path backend/rust/Cargo.toml --all -- --check
cargo clippy --manifest-path backend/rust/Cargo.toml --workspace --all-targets -- -D warnings
cargo test  --manifest-path backend/rust/Cargo.toml --workspace
npm --prefix frontend run build
scripts/check-agents-yaml.sh
python3 scripts/check-design-copy.py --source ../dok3search-design   # 설계 사본을 건드렸을 때만
```

CI(`.github/workflows/ci.yml`)의 필수 검사는 `rust-fmt`·`rust-clippy`·`rust-test`·`frontend-build` 다.

### dok3search-design

설계 문서·계약 예시(`contracts/*.example.yaml`)·로드맵의 원본이다. 화면·API 계약·검색 동작을 바꾸면
`dok3search` 의 사본(`frontend/src/samples/design/`)과 `provenance.json` 정합성까지 확인한다.

### a2a-acp-bridge

```sh
gofmt -l .                 # 출력이 없어야 한다
go vet ./...
go test -race ./...
go build -o ~/.local/bin/a2a-acp-bridge ./cmd/a2a-acp-bridge
```

Go 1.22 표준 라이브러리만 쓴다(`go.mod` 에 의존성 추가 금지). 파일 300줄 이하, 함수 인지 복잡도 15 이하.

### agents-scaffold

```sh
bats tests/agents-scaffold.bats
python3 -m unittest discover -s tests
scripts/dev/run-skill-tests.sh <스킬명>
python3 scripts/dev/build-plugins.py
python3 scripts/dev/check-doc-numbers.py
```

스킬을 고치면 `python3 scripts/dev/build-plugins.py` 로 플러그인 사본(`plugins/*/skills/`)을 다시 만들어
같은 커밋에 넣는다. CI 가 드리프트(`build-plugins.py --check`)를 막는다.

### llmgw / llm

게이트웨이는 `gateway-rs/`(Rust)와 `admin/`(Go)다. 운영 라우트·provider·클라이언트 설정은
`llm` 레포 `deploy/llmgw/llmgw.toml` 에 있고, `llmgw` 레포 `config/`·`data/` 는 런타임 설정·DB 다.
설정을 바꾸면 `/admin/reload` 로 반영하고, 각 레포의 `AGENTS.md` 검증 명령을 따른다.

### doksam-ui

Next.js 카탈로그(라이브 `https://ui.doksam.com`). 작성 규칙 SSOT 는 `/rules` 페이지와 레포
`AGENTS.md` 다. 화면을 만들기 전에 컴포넌트·패턴·템플릿 카탈로그를 먼저 확인한다.

## 브랜치·워크트리·PR 규칙

- 작업마다 GitHub/GitLab 이슈를 먼저 연다. 이슈 번호를 브랜치·커밋·PR 에 쓴다.
- 브랜치는 `batch/<agent>-<YYYYMMDD>-<8자리 hex>`(`openssl rand -hex 4`) 다. `main` 에 직접 push 하지 않는다.
- 커밋 제목은 `[<모델명>] <type>: <설명> (#N)` 이다.
- PR/MR 본문에 `Closes #N` 을 쓴다. 머지는 merge commit 으로 한다(squash 금지).
- **동시에 도는 작업은 각자 워크트리와 브랜치를 가진다.** 혼자 하는 작업이 아니면 에이전트마다 자기 git
  worktree 를 쓰고, 남의 워크트리를 직접 고치지 않는다.
- 크로스 레포 커밋은 `git -C <저장소 경로> ...` 로 대상 저장소를 명시한다. 잘못된 cwd 커밋은 금지다.
