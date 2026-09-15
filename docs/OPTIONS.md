# agents-scaffold — 전체 옵션

`bin/agents-scaffold.sh` 의 모든 옵션. 개요는 [README](../README.ko.md) 참조.

## 스택 프리셋

| 프리셋 | 룰 파일 | pre-commit 게이트 |
|--------|---------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `./gradlew build` |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant 컴파일 (자동 감지) |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check` + `mypy` |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

## Forge 프리셋 (`--forge`)

이슈/PR 워크플로를 forge 별로 주입한다. 스택 프리셋보다 먼저 머지된다.

| 프리셋 | CLI | PR/MR | 이슈 클로즈 |
|--------|-----|-------|------------|
| `github` (기본) | `gh` | PR | `Closes #N` 로 머지 시 **자동 클로즈** |
| `gitlab` | `glab` | MR | `Closes #N` 자동 클로즈 동작 — 머지 후 확인, `opened` 시만 수동 |

주입 파일: `.claude/rules/forge.md`(항상 로드) + `.claude/commands/fix-issue.md`·`sdlc-cycle.md`(forge 변형으로 덮어씀). 베이스 파일은 forge 중립("이슈/PR·MR").

## 요구사항 다지기 도구 고르기

구현 전에 요구사항을 다지는 수단은 세 가지고, **성격이 서로 다르니 작업마다 골라 쓴다.**
동봉되는 것은 `grill-me` 하나뿐이고 나머지 둘은 별도 설치다.

| | `grill-me` | superpowers | Ouroboros |
|---|---|---|---|
| **범위** | 취조만 | 워크플로 전반 | 취조 → 스펙 → 실행 → 평가 루프 |
| **상태** | 대화 안에서 끝 | 대화 + 파일 산출물 | MCP 서버가 영속 관리 |
| **무게** | 가벼움 | 중간 | 무거움 — 질문마다 서브에이전트 fanout |
| **설치** | **동봉** (`.claude/skills/grill-me/`) | 플러그인 [obra/superpowers](https://github.com/obra/superpowers) | 마켓플레이스 [Q00/ouroboros](https://github.com/Q00/ouroboros) (MCP 서버 동반) |

**고르는 기준**

- 이미 방향이 선 기능의 스펙에 구멍이 있는지 → **`grill-me`**. 설치 없이 바로, 대화 한 판으로 끝난다.
- 백지 아이디어를 발산·수렴하고 산출물(문서)까지 남겨야 함 → **superpowers 의 `brainstorming`**.
- 요구사항이 모호한 큰 작업을 **스펙화하고 실행·평가까지 루프로 돌려야 함** → **Ouroboros**.
  세션이 끊겨도 상태가 남는 대신 토큰 비용이 가장 크다.

무게 순으로 올라가되, **아래에서 위로만 간다** — 가벼운 걸로 충분한 작업에 Ouroboros 를
쓰면 비용만 커진다. 셋 다 설치돼 있어도 자동 발동은 안 하며, 작업마다 사용자가 택일한다.

## 하네스 (`--harness`)

| 값 | 대상 | 하는 일 |
|---|---|---|
| `claude` (기본) | Claude Code | 전체 설치 — settings.json 훅 바인딩·서브에이전트·슬래시 커맨드·workflows 포함 |
| `codex` | Codex | `AGENTS.md`·`.agents/skills`와 공통 rules/hooks/memory 설치, Claude 전용 계층 제거 |
| `all` | 혼용 팀 | Claude용 `.claude/skills`와 Codex용 `.agents/skills`를 함께 설치 |

**보장 수준은 2단이다 (#21)** — "지원한다/안 한다" 이분법이 아니다.

| 수준 | 무엇이 성립하나 | 어느 하네스에서 |
|---|---|---|
| **baseline** | `AGENTS.md` 본문의 P0/P1(선택한 스택 P0 포함) + **진짜 `.git/hooks/pre-commit` 게이트** + CI | **전 하네스, `--harness` 값 무관.** 하네스가 무엇을 읽든, 사람이 터미널에서 직접 커밋하든 동일하게 걸린다 |
| **full** | baseline + 그 하네스의 네이티브 계층(서브에이전트·스킬·슬래시 커맨드·조건부 룰 로딩·lifecycle 훅) | 어댑터가 실측 검증된 하네스만 |

git hook 은 **하네스와 무관하게 항상 배선된다**(#21). Claude Code 의 `PreToolUse` 훅은 그 세션이
Bash 툴로 커밋할 때만 발동하므로 조기 피드백 계층이지 강제선이 아니다 — 결정적 강제선은
하네스 밖(`.git/hooks` + CI)에 둔다. 기존 `.git/hooks/pre-commit` 이 있으면 덮어쓰지 않고 경고만 낸다.

선택한 스택의 P0 는 `AGENTS.md` **본문에 직접 삽입**된다 — `.claude/rules/` 참조 링크에 의존하지
않으므로 `.claude/` 를 로드하지 않는 하네스에서도 도달 가능하다. 선택하지 않은 스택은 삽입되지
않는다(Codex instruction 합산 기본 한도 32KiB — context flooding 방지).

### 실측 검증 (2026-09-15)

| 하네스 | 실측 버전 | baseline | full 쪽 확인된 것 / 확인 안 된 것 |
|---|---|---|---|
| Claude Code | 2.1.239 | 성립 | `.claude/rules/*.md` 의 `paths:` 조건부 로딩, 서브에이전트, skills, `settings.json` 훅 — 전부 [공식 문서](https://code.claude.com/docs/en/memory.md)로 확인 |
| Codex | codex-cli 0.154.0 / GPT-6 Astra | 성립 | `AGENTS.md`·스택 P0 자동 로드와 `.agents/skills` 발견, `.env` 게이트를 실측 |
| Antigravity | agy **1.1.18** (미재검증) | 성립 | 1.1.17 에서 **headless(`-p`) 규칙 미로드** 실측 — 원인 미규명. 1.1.18 재검증·인터랙티브 모드 모두 미실시 |

Codex(codex-cli 0.154.0, `gpt-6-astra`)는 `codex` 모드 산출물의 AGENTS.md 와 인라인된
스택 P0를 자동 로드하고 `.agents/skills`의 저장소 스킬만 발견했다. `.claude/skills`는
Codex 발견 경로가 아니다. 모델이 규칙을 놓쳐도 git hook이 exit 2로 차단한다.

지원 상태의 단일 진실원천은 [`docs/harness-matrix.json`](harness-matrix.json) 이다. 이 표는
그 manifest 와 대조되며, `scripts/check-harness-matrix.py` 가 CI 에서 검사한다 — `full` 등급이
90일 넘게 재측정되지 않았거나 판정에 근거가 없으면 **빌드가 실패한다**. 재측정은
`scripts/spike-codex-contract.sh --dynamic` 으로 수행한다.

`--harness codex`는 저장소 스킬을 네이티브 경로인 `.agents/skills`에 설치한다.
`--harness all`은 Claude·Antigravity 호환용 `.claude/skills`와 Codex용 `.agents/skills`를
함께 둔다. Codex 서브에이전트·경로 조건부 룰·lifecycle hook은 아직 미검증이므로 전체
등급은 계속 baseline이다.

Codex 쪽 추가 제약 두 가지도 설계에 영향을 준다.

- **instruction 합산 기본 한도 32KiB** (`project_doc_max_bytes`). 그래서 스택 P0 는 선택한
  스택만 `AGENTS.md` 에 인라인한다 (`--stack javaweb` 기준 실측 6,869 B — 한도의 21%).
- **`.codex/` 레이어는 프로젝트를 신뢰한 경우에만 로드된다.** 파일을 생성했다고 활성화가
  보장되지 않는다. 그래서 결정적 강제선을 `.git/hooks` + CI 에 둔다.

## 언어 (`--lang`)

베이스 트리(agents·rules·skills·commands·`AGENTS.md`·훅/settings 메시지)는 **기본이
한국어다**(#36 반전 — 한국어가 원본, 영어는 번역 오버레이). `--lang en` 을 주면 영어
번역을 **가장 마지막에** 얹는다 — 베이스 복사 → forge 프리셋 → 스택 프리셋이 끝난 뒤
`presets/lang-en/base` + `presets/lang-en/forge-<forge>` + `presets/lang-en/stacks/<stack>`
콘텐츠로 동일 파일을 덮어쓴다.

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`.claude/hooks/pre-commit.sh` 는 `--lang` 오버레이 대상이 아니다(스택 파셜이 삽입되는
파일이라 언어 단일본 — 코드 동작에는 영향 없음). `--update` 는 한국어 베이스만
갱신하므로, 영어 오버레이가 필요하면 `--lang en` 으로 다시 실행한다.

## 사용법 1 — 스크립트

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge 기본값 github. GitLab 레포면 --forge gitlab
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

대화형으로 쓰려면 `--forge`/`--stack`/`--name` 생략 → 프롬프트가 묻는다(forge 기본 github).

### 옵션

| 옵션 | 설명 |
|---|---|
| `<target-dir>` | 대상 디렉터리. 기본 `.` |
| `--forge <forge>` | `github`(기본) 또는 `gitlab` |
| `--lang <lang>` | `ko`(기본) 또는 `en` |
| `--stack <목록>` | 쉼표구분 스택 프리셋. 미지정 시 대화형 프롬프트 |
| `--name <name>` | `{{PROJECT_NAME}}` 치환값. 기본 = 대상 디렉터리명 |
| `--yes` | 대화형 프롬프트 생략(비대화 모드) |
| `--update` | 이미 부트스트랩된 프로젝트의 베이스 파일 최신화 (아래 참조) |

### 원격 원커맨드 설치 (clone 불필요)

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

로컬에 레포가 없는 상태(파이프 실행)로 감지되면 `AGENTS_SCAFFOLD_REPO`(기본
`github.com/leeyudok/agents-scaffold`, env 로 오버라이드) tarball 을 임시 디렉터리에 받아 템플릿 소스로 쓴다. 브랜치/태그 지정은
`AGENTS_SCAFFOLD_REF`(기본 `main`) 로 오버라이드.

### 베이스 갱신 — `--update`

이미 부트스트랩된 프로젝트에 최신 베이스(`.claude/`, `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`)를
반영한다.

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
```

- `.claude/hooks/pre-commit.sh` 는 스택 파셜이 삽입돼 있어 항상 건너뛴다(수동 병합 필요).
- 그 외 베이스 파일은 대상과 diff 없으면 스킵, 다르면 기존 파일은 그대로 두고 새 버전을
  `<file>.new` 로 저장한다. `{{PLACEHOLDER}}` 치환은 `.new` 파일에도 적용된다.
- 실행 끝에 추가/갱신 대기/건너뜀/변경없음 목록을 요약 출력 — `.new` 파일은 `diff` 로 확인 후
  수동 반영.

## 사용법 2 — GitLab 템플릿

새 프로젝트 생성 시 구성을 자동으로 깔리게 하는 법은 **[docs/GITLAB_TEMPLATE.md](GITLAB_TEMPLATE.md)** 참조.

> 주의: self-hosted GitLab 기준. **CE** 는 네이티브 커스텀 프로젝트 템플릿(Premium)이 불가.
> CE 에서는 **Import by URL + `bin/agents-scaffold.sh`**(B안) 또는 **스크립트 단독**(C안)을 쓴다.
> 생성/주입 후 `bin/agents-scaffold.sh .` 1회 실행 → 스택 적용 + 치환 + `bin/`·`presets/`·`docs/superpowers/` self-clean.

## 치환 플레이스홀더

| 토큰 | 값 |
|---|---|
| `{{PROJECT_NAME}}` | `--name` 또는 대상 디렉터리명 |
| `{{JAVA_VERSION}}` | `1.8` (springboot 프리셋 기본) |
