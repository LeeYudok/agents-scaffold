# agents-scaffold — 전체 옵션

`bin/agents-scaffold.sh` 의 모든 옵션. 개요는 [README](../README.ko.md) 참조.

## 스택 프리셋

| 프리셋 | 룰 파일 | pre-commit 게이트 |
|--------|---------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `gradle testClasses` / `mvn test-compile` (전체 테스트는 `SPRINGBOOT_GATE_TESTS=1`) |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant 컴파일 (자동 감지) |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check`, `mypy` 는 프로젝트에 설정이 있을 때만 |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `php-laravel` | php-laravel.md (paths: app/**/*.php, routes/**/*.php, composer.json) | `composer validate` + `pint --test` + `phpunit` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

`--list-stacks` 가 이 이름들을 한 줄에 하나씩 찍는다. 목록에 없는 이름은 오류다(exit 1). 쓸 수 있는 스택을 보여주고
아무것도 설치하지 않는다. 예전에는 경고만 했다.

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
| `codex` | Codex | `AGENTS.md`·스킬과 공통 rules/hooks/memory 설치, `.claude/agents` 를 `.codex/agents`(TOML, #64)로, 훅을 `.codex/hooks.json`(#65)으로 생성, Claude 전용 계층(commands·workflows) 제거 |
| `agy` | Antigravity | `codex` 와 같은 공통 레이아웃에 더해 `.claude/rules` 를 `.agents/rules`(`trigger: glob`, #63)로, `.claude/agents` 를 `.agents/agents`(#64)로, 훅을 `.agents/hooks.json`(#65)으로 생성한다 |
| `all` | 혼용 팀 | `claude` 전체 + 모든 어댑터(agy 룰, Codex·agy 서브에이전트·훅). 스킬 레이아웃은 하네스와 무관하다(#61) |

**스킬 원본은 한 곳이다 (#61).** 스킬은 하네스와 무관하게 `.agents/skills/`(Codex·agy 네이티브
경로)에 한 번만 두고, Claude Code 는 `.claude/skills -> ../.agents/skills` 심볼릭 링크로 같은 원본을
읽는다(claude 2.1.318 실측 — 링크 없이 `.agents/skills` 만 두면 스킬을 찾지 못한다). 사본 두 벌이
갈라지는 일이 없고, 나중에 다른 하네스를 붙여도 재설치가 필요 없다.

- 링크를 만들 수 없는 환경(Windows Git Bash 기본값 등)이나 `AGENTS_SCAFFOLD_NO_SYMLINK=1` 이면
  `.claude/skills` 를 사본으로 둔다. 스테이징된 사본이 원본과 다르면 pre-commit 게이트가 커밋을 차단한다
  (인덱스 기준 비교라 `__pycache__` 같은 미추적 파일은 무관).
  환경에 따라 링크 가능 여부가 달라질 수 있다(망 분리 PC 의 정책 등) — [OFFLINE_INSTALL.md](OFFLINE_INSTALL.md) 6단계.
- Git for Windows 의 `core.symlinks=false` 체크아웃은 링크를 경로 문자열이 든 일반 파일로 만든다.
  이때 Claude Code 는 스킬을 찾지 못하며, 게이트가 경고를 낸다 — `git config core.symlinks true` 후
  다시 체크아웃한다.
- 설치 전부터 실디렉터리 `.claude/skills` 가 있으면 `.agents/skills` 로 옮기고 링크한다. 같은 경로의
  내용이 `.agents/skills` 와 다르면 `.agents/skills` 를 원본으로 두고 기존 디렉터리를
  `.claude/skills.pre-ssot-<시각>/` 에 남긴다.
- 룰·서브에이전트는 링크하지 않는다. `.codex/rules` 는 명령 실행 정책, agy `.agents/rules` 는
  Claude `paths:` 조건부 로딩을 모르고, Claude `.md` 와 Codex `.toml` 서브에이전트는 포맷이 다르다.
  대신 설치·`--update` 때 하네스 형식으로 생성한다(#63, #64).

세 하네스 모두 루트 `AGENTS.md` 를 네이티브로 읽으므로 `CLAUDE.md`·`GEMINI.md` 포인터나
`.gemini/settings.json` 셤은 만들지 않는다(#54, #60). 지원 대상은 Claude Code·Codex·Antigravity
최신판이며, Gemini CLI 는 지원 대상에서 뺐다.

**보장 수준은 2단이다 (#21)** — "지원한다/안 한다" 이분법이 아니다.

| 수준 | 무엇이 성립하나 | 어느 하네스에서 |
|---|---|---|
| **baseline** | `AGENTS.md` 본문의 P0/P1(선택한 스택 P0 포함) + **진짜 `.git/hooks/pre-commit` 게이트** + CI | **전 하네스, `--harness` 값 무관.** 하네스가 무엇을 읽든, 사람이 터미널에서 직접 커밋하든 동일하게 걸린다 |
| **full** | baseline + 그 하네스의 네이티브 계층(서브에이전트·스킬·슬래시 커맨드·조건부 룰 로딩·lifecycle 훅) | 어댑터가 실측 검증된 하네스만 |

git hook 은 **하네스와 무관하게 항상 배선된다**(#21). Claude Code 의 `PreToolUse` 훅은 그 세션이
Bash 툴로 커밋할 때만 발동하므로 조기 피드백 계층이지 강제선이 아니다 — 결정적 강제선은
하네스 밖(`.git/hooks` + CI)에 둔다. 기존 pre-commit 훅이 있으면 덮어쓰지 않고, 그 훅에 넣을 한 줄을 경고로 알려준다. 훅은 git 이 실제로 실행하는 위치에 쓴다. worktree, submodule(`.git` 이 파일), `.husky` 같은 `core.hooksPath` 디렉터리를 처리하고, `--update` 는 없는 훅을 연결한다(#106). [TROUBLESHOOTING.md](TROUBLESHOOTING.md#기존-pre-commit-훅이나-husky-가-있다) 참조.

선택한 스택의 P0 는 `AGENTS.md` **본문에 직접 삽입**된다 — `.claude/rules/` 참조 링크에 의존하지
않으므로 `.claude/` 를 로드하지 않는 하네스에서도 도달 가능하다. 선택하지 않은 스택은 삽입되지
않는다(Codex instruction 합산 기본 한도 32KiB — context flooding 방지).

### 실측 검증 (2026-11-04)

| 하네스 | 실측 버전 | 등급 | baseline | full 쪽 확인된 것 / 확인 안 된 것 |
|---|---|---|---|---|
| Claude Code | 2.1.318 | **full** | 성립 | `.claude/rules/*.md` 의 `paths:` 조건부 로딩, 서브에이전트, skills, `settings.json` 훅 — 전부 [공식 문서](https://code.claude.com/docs/en/memory.md)로 확인 |
| Codex | codex-cli 0.166.0 | **baseline** | 성립 | `AGENTS.md`·스택 P0 자동 로드, `.agents/skills` 발견, `.env` 게이트, `.codex/agents` 서브에이전트(신뢰 프로젝트만), `.codex/hooks.json` 훅(프로젝트 + 훅 정의 신뢰 필요), cwd 기준 하위 `AGENTS.md` 를 실측. 파일 경로 조건부 지침은 없다 |
| Antigravity | agy 1.5.0 | **baseline** | 성립 | headless(`-p`)로 `AGENTS.md`·스택 P0 자동 로드, `.agents/skills` 발견, `.env` 게이트, `.agents/agents` 서브에이전트, `.agents/hooks.json` 훅(신뢰 확인 없이 실행)을 실측. **`.agents/rules` 의 `trigger: glob` 룰은 1.5.0 에서 일치 파일을 읽어도 로드되지 않는다**(1.4.2 까지 pass, `always_on` 은 정상, #90). 하위 `AGENTS.md` 는 cwd 기준으로만 로드 |

Codex(codex-cli 0.166.0)와 agy(1.5.0)는 각 모드 산출물의 AGENTS.md 와 인라인된
스택 P0를 툴 호출 없이 자동 로드하고 `.agents/skills`의 저장소 스킬만 발견했다. `.claude/skills`는
둘 다 발견 경로가 아니다. agy 1.2.7 headless 는 `AGENTS.md`·`GEMINI.md` 를 모두 읽지 못했으나
1.2.16 에서 해소됐다. 모델이 규칙을 놓쳐도 git hook이 exit 2로 차단한다.

지원 상태의 단일 진실원천은 [`docs/harness-matrix.json`](harness-matrix.json) 이다. 이 표는
그 manifest 와 대조되며, `scripts/dev/check-harness-matrix.py` 가 CI 에서 검사한다 — 판정에 근거가 없거나
버전이 어긋나면 **빌드가 실패한다**. `full` 등급이 90일 넘게 재측정되지 않으면 주간 `harness-matrix` 워크플로가 실패하고,
PR 에서는 만료 14일 전부터 경고만 낸다. 재측정은
`scripts/dev/spike-codex-contract.sh --dynamic`·`scripts/dev/spike-agy-contract.sh --dynamic` 으로 수행한다.

**agy 룰 어댑터 (#63).** `--harness agy|all` 이면 `.claude/rules/*.md` 를 `.agents/rules/*.md` 로 생성한다. `paths:` 는
`trigger: glob` + `globs:`, `paths:` 가 없으면 `trigger: always_on` 이다. 패턴은 agy 1.2.16 실측대로 바꾼다 — 슬래시가 든
상대 패턴(`src/**`)은 `**/src/**` 로, 슬래시 없는 패턴(`Dockerfile`·`*.py`)은 파일 이름에 일치하므로 그대로 둔다. 여러 패턴은
공백 없이 쉼표로 잇는다(쉼표 뒤 공백은 패턴에 포함돼 일치하지 않는다). `.claude/rules` 가 원본이며 `--update` 때 다시 생성하고(기존 프로젝트는 `--update --harness agy` 로 처음 생성한다),
원본이 사라진 생성물은 지운다. 생성 표시가 없는 같은 이름의 파일(사용자 소유)은 건드리지 않는다.

**서브에이전트 어댑터 (#64).** `.claude/agents/*.md` 를 Codex(`--harness codex|all`)용 `.codex/agents/<이름>.toml` 과
agy(`--harness agy|all`)용 `.agents/agents/<이름>.md` 로 생성한다. Codex 는 `name`·`description`·`developer_instructions`
(본문을 TOML 리터럴 문자열 `'''` 로 그대로) 형식이고, 본문에 `'''` 가 있으면 경고하고 건너뛴다. agy 는 `name`·`description`
만 둔다 — Claude 의 `tools`·`model`·`memory` 가 frontmatter 에 있으면 agy 1.2.16 이 그 에이전트를 조용히 빼기 때문이다(실측).
툴·모델은 각 하네스 기본값을 상속하고, 본문의 Claude 전용 지시는 그대로 남는다. `.claude/agents` 가 원본이라 codex/agy
모드에서도 지우지 않는다. Codex 의 `.codex/` 레이어는 신뢰 프로젝트에서만 로드되므로 생성만으로 활성화되지는 않는다.
갱신 규칙은 룰 어댑터와 같다(`--update` 재생성, 원본이 사라진 생성물 삭제, 표시 없는 사용자 파일 보존,
기존 프로젝트는 `--update --harness codex|agy|all` 로 처음 생성).

**훅 어댑터 (#65).** 훅 원본은 Claude 형식(`.claude/settings.json` 의 `hooks` + `.claude/hooks/*`)이고,
`.claude/hooks/hook-adapter.py` 가 Codex(`--harness codex|all`)용 `.codex/hooks.json` 과 agy(`--harness agy|all`)용
`.agents/hooks.json` 을 생성한다. 실행할 때도 같은 어댑터가 하네스 입력을 Claude 형식으로 바꿔 원래 스크립트를 부르고
응답을 하네스 형식으로 돌려준다(2026-10-04 실측):

- Codex 입력은 Claude 와 거의 같다. 셸은 `Bash`, 파일 편집은 `apply_patch`(패치 텍스트에서 파일별로 나눠 `Edit` 로 전달).
  Stop 의 `{"decision":"block"}` 을 그대로 받아 한 턴 더 돈다. 프로젝트 신뢰 + 훅 정의 신뢰(`/hooks` 검토)가 있어야 실행된다.
- agy 입력은 camelCase(`conversationId`·`toolCall`)다. `run_command` → `Bash`, `write_to_file` 등 → `Write`/`Edit` 로 바꾸고,
  Stop 의 `block` 을 agy 의 `continue` 로 바꾼다. 명령 출력이 오지 않아 테스트 결과 알림은 판정하지 못한다.
  **신뢰 확인 없이 실행된다**(clone 만으로 레포의 `.claude/hooks/*` 가 돈다 — `security-audit` 가 검사한다).
- 옮기지 않는 것: PreToolUse 커밋 게이트(`.git/hooks` 가 맡는다), prompt 타입 훅, matcher 가 걸린 비-툴 이벤트(SessionStart `compact` 압축 리마인드, #72).
- 어댑터는 `python3` 가 필요하다(없으면 생성을 건너뛴다). `.claude/settings.json` 은 훅 원본이라 codex/agy 모드에서도 남긴다.
- Stop 훅(메모리 리마인드)은 headless(`-p`·`exec`)에서도 한 턴을 더 돌린다. 자동화에서 원치 않으면 `settings.json` 에서
  빼고 `--update` 한다. 갱신 규칙은 다른 어댑터와 같다.

스캐폴드는 서브에이전트(#64)·훅(#65)을 두 하네스에, 경로 조건부 룰(#63)을 agy 에 생성하고 각각 e2e 로 실측했다. agy 는
1.4.2 까지 full 이었으나 **1.5.0 에서 glob 룰이 로드되지 않아 baseline 으로 내렸다**(#90) — 생성기는 그대로 두고, agy 가
고치면 재실측해 되돌린다. **Codex 는 baseline** 이다 — 파일 경로 조건부 지침이 없어서
`.claude/rules` 의 `paths:` 룰을 전달할 수단이 없다(하위 `AGENTS.md` 는 cwd 기준으로만 읽힌다). 훅은 Claude Code 와 마찬가지로
조기 피드백이지 강제선이 아니다. agy 는 레포의 `.agents/hooks.json` 을 신뢰 확인 없이 실행하므로, 외부
레포에서 agy 를 돌리기 전에 그 파일을 확인한다(`security-audit` 에이전트가 검사한다).

Codex 쪽 추가 제약 두 가지도 설계에 영향을 준다.

- **instruction 합산 기본 한도 32KiB** (`project_doc_max_bytes`). 그래서 스택 P0 는 선택한
  스택만 `AGENTS.md` 에 인라인한다 (`--stack javaweb` 기준 실측 6,869 B — 한도의 21%).
- **`.codex/` 레이어는 프로젝트를 신뢰한 경우에만 로드된다.** 파일을 생성했다고 활성화가
  보장되지 않는다. 그래서 결정적 강제선을 `.git/hooks` + CI 에 둔다.

## 스킬 묶음 (`--with-yd-skills`, `--no-yd-skills`, `--with-personal-skills`)

| 설치 | 스킬 | 서브에이전트 |
|---|---|---|
| `--lang ko` (기본) | 24 — 워크플로 10 + `yd-*` 14 | 19 — 7 + `yd-*` 12 |
| `--lang en` | 10 — 워크플로 스킬 | 7 |
| `--with-personal-skills` 추가 | +9 | +4 |

워크플로 스킬 10개는 `review`·`status`·`search-first`·`security-precheck`·`docs-sync`·`handoff`·
`memory-factcheck`·`skill-evolve`·`grill-me` 와 템플릿 `example-skill` 이다. `yd-*` 14개는
[LeeYudok/doksam-skills](https://github.com/LeeYudok/doksam-skills) 에서 옮겨 온 13개(DB·Go·React·TypeScript·빌드·
화면설계·글쓰기 등)와 의존성 CVE 점검 `yd-cve-check`(#79)다. 딸린 에이전트 12개(`.claude/agents/yd-*.md`)도 함께
들어간다(#78).

| 옵션 | 효과 |
|---|---|
| `--with-yd-skills` | `yd-*` 14개와 그 에이전트를 설치한다. `--lang ko` 의 기본값 |
| `--no-yd-skills` | 뺀다. `--lang en` 의 기본값이다. `yd-*` 스킬은 한국어로 쓰여 있고 영어 오버레이가 없다(#105) |
| `--with-personal-skills` | 옵트인 묶음 `presets/skills/personal/` 도 스택 프리셋 다음에 머지한다 |

옵트인 묶음은 스킬 9개(`yd-agents-mem`·`yd-claude-auth-sync`·`yd-git-sync`·`yd-git-ship`·`yd-doksam-ui`·
`yd-finguard`·`yd-sdlc-orchestrator`·`yd-script-editor`·`yd-session-recording`)와 에이전트 4개다.
특정 GitLab·호스트·ui.doksam.com·FinGuard 를 전제하므로 다른 환경에서는 쓰지 않는다.

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --stack go --with-yd-skills
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --stack go --with-personal-skills
```

- 선택은 `.claude/.scaffold.json`(`yd_skills`, `personal_skills`)에 기록되고 `--update` 는 같은 묶음을 유지한다.
  이 파일이 없는 설치에서는 `yd-db-expert` 가 있으면 `yd-*` 묶음을, 옵트인 스킬이 하나라도 있으면 옵트인 묶음을
  설치한 것으로 본다.
- 기본 설치를 `--update` 해도 옵트인 묶음이 새로 들어가지는 않는다. `--update --with-yd-skills` 는 기존 설치에
  `yd-*` 묶음을 추가한다. `--update --no-yd-skills` 는 기록만 바꾸고, 이미 설치된 스킬은 지우지 않는다.
- 스캐폴드 없이 스킬만 설치하는 방법(플러그인, `npx skills`, `install-skills.sh`)은 [SKILLS.md](SKILLS.md) 에 있다.

## 언어 (`--lang`)

베이스 트리(agents·rules·skills·commands·`AGENTS.md`·훅/settings 메시지)는 **기본이
한국어다**(#36 반전 — 한국어가 원본, 영어는 번역 오버레이). `--lang en` 을 주면 영어
번역을 **가장 마지막에** 얹는다 — 베이스 복사 → forge 프리셋 → 스택 프리셋이 끝난 뒤
`presets/lang/en/base` + `presets/lang/en/forge/<forge>` + `presets/lang/en/stacks/<stack>`
콘텐츠로 동일 파일을 덮어쓴다.

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`--lang en` 은 한국어 전용인 `yd-*` 스킬도 뺀다. 넣으려면 `--with-yd-skills` 를 준다
([스킬 묶음](#스킬-묶음---with-yd-skills---no-yd-skills---with-personal-skills) 참조).

`.claude/hooks/pre-commit.sh` 는 `--lang` 오버레이 대상이 아니다(스택 파셜이 삽입되는
파일이라 두 언어가 한 벌을 쓴다. 코드 동작에는 영향이 없다). 언어는 `.claude/.scaffold.json` 에
기록되고, `--update` 는 그 언어로 설치한 결과와 비교한다. 영어 설치에 한국어 파일을 제안하던
문제는 없어졌다.

## 사용법 1 — 스크립트

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge 기본값 github. GitLab 레포면 --forge gitlab
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

대화형으로 쓰려면 `--forge`/`--stack`/`--lang` 을 생략한다. 프롬프트가 묻는다(forge 기본 github, 언어 기본 ko).
없는 대상 디렉터리는 만든다.

설치가 끝나면 요약(버전, 룰 파일·스킬·서브에이전트 수, 게이트)과 다음 단계를 찍는다. `AGENTS.md` 의 빈 섹션을
채우고, 게이트가 스테이징된 `.env` 를 막는지 확인하고, 결과를 커밋하는 순서다.

### 옵션

| 옵션 | 설명 |
|---|---|
| `<target-dir>` | 대상 디렉터리. 기본 `.`. 없으면 만든다(`--update`·`--uninstall`·`--dry-run` 은 만들지 않는다) |
| `--forge <forge>` | `github`(기본) 또는 `gitlab` |
| `--lang <lang>` | `ko`(기본) 또는 `en` |
| `--stack <목록>` | 쉼표구분 스택 프리셋. 미지정 시 대화형 프롬프트. 모르는 이름은 오류 |
| `--name <name>` | `{{PROJECT_NAME}}` 치환값. 기본 = 대상 디렉터리명 |
| `--harness <harness>` | `claude`(기본)·`codex`·`agy`·`all` — [하네스](#하네스---harness) 참조 |
| `--with-yd-skills` / `--no-yd-skills` | 한국어 `yd-*` 스킬 14개를 넣거나 뺀다. 기본값은 `ko` 설치에 포함, `en` 설치에 제외 |
| `--with-personal-skills` | 메인테이너 환경 전용 `yd-*` 스킬 9개·에이전트 4개도 설치 |
| `--yes` | 대화형 프롬프트 생략(비대화 모드) |
| `--dry-run` | 아무것도 바꾸지 않는다. 설치·`--update`·`--uninstall` 이 할 일을 출력한다 (아래 참조) |
| `--update` | 이미 부트스트랩된 프로젝트를 최신화 (아래 참조) |
| `--uninstall` | 스캐폴드가 설치했고 사용자가 고치지 않은 파일을 제거 (아래 참조) |
| `--list-stacks` | 쓸 수 있는 스택 프리셋을 한 줄에 하나씩 출력 |
| `--version` | 스캐폴드 버전 출력(`agents-scaffold 1.0.0`) |
| `-h`, `--help` | 사용법 출력 |

값이 필요한 옵션에 값이 없으면 `Error: --stack needs a value` 로, 모르는 옵션은 `Unknown option` 으로 멈춘다.

### 설치 선택 기록 — `.claude/.scaffold.json`

설치와 `--update` 는 사용한 선택을 `.claude/.scaffold.json` 에 쓴다(#104).

```json
{
  "scaffold_version": "1.0.0",
  "name": "my-app",
  "forge": "github",
  "stacks": "nextjs,bun",
  "lang": "en",
  "harness": "claude",
  "yd_skills": "0",
  "personal_skills": "0"
}
```

`--update`·`--uninstall`·`--dry-run` 은 이 파일을 읽어 설치했던 결과를 그대로 다시 만든다. `.claude/` 의 다른
파일과 함께 커밋한다. 파일이 없으면(1.0.0 이전 설치) 프로젝트에서 선택을 추론한다. forge 는 `rules/forge.md`,
스택은 `rules/<stack>.md`, 언어는 `AGENTS.md` 의 제목, 하네스는 있는 디렉터리로 판단한다. 이때 첫 출력 줄에
`(recorded)` 대신 `(inferred)` 가 찍히고, `--update` 가 끝날 때 파일을 쓴다. 명령줄 옵션은 기록보다 우선한다.

### 미리 보기 — `--dry-run`

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/repo --lang en --stack python --dry-run
agents-scaffold/bin/agents-scaffold.sh --update /path/to/repo --dry-run
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --dry-run
```

대상은 아무것도 바뀌지 않는다. 설치 미리 보기는 추가될 파일 수, 이미 같은 파일 수, 이미 있고 내용이 다른 파일을
출력한다. `--update --dry-run` 은 추가되거나 `.new` 로 놓일 파일을, `--uninstall --dry-run` 은 지울 파일과 남길
파일을 보여준다. 대상 디렉터리는 이미 있어야 한다.

### 기존 프로젝트에 다시 설치

일반 설치는 다시 돌려도 안전하다(#104).

- 이미 있는 베이스 파일은 그대로 둔다. forge 프리셋·스택 프리셋·영어 오버레이에서 오는 파일은 다시 쓴다.
- `AGENTS.md` 는 새로 만든다. 기존 파일이 새로 만든 것과 다르면 먼저 `AGENTS.md.bak-<timestamp>` 로 저장한다.
  필요한 내용은 거기서 옮긴다.
- 이미 `pre-commit.sh` 에 들어 있는 스택 게이트는 다시 넣지 않는다.

`AGENTS.md` 를 새로 만들지 않고 갱신만 하려면 `--update` 를 쓴다.

### 원격 원커맨드 설치 (clone 불필요)

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

로컬에 레포가 없는 상태(파이프 실행)로 감지되면 `AGENTS_SCAFFOLD_REPO`(기본
`github.com/leeyudok/agents-scaffold`, env 로 오버라이드) tarball 을 임시 디렉터리에 받아 템플릿 소스로 쓴다.

| 변수 | 뜻 |
|---|---|
| `AGENTS_SCAFFOLD_REPO` | tarball 을 받을 레포 URL. 기본값은 공식 GitHub 레포 |
| `AGENTS_SCAFFOLD_REF` | 받을 브랜치 또는 태그. 기본 `main`. 태그는 1.0.0 부터 동작한다(#106) |
| `AGENTS_SCAFFOLD_SHA256` | 선택. 받은 tarball 의 기대 SHA-256. 다르면 설치를 중단한다 |
| `AGENTS_SCAFFOLD_NO_SYMLINK` | `1` 이면 `.claude/skills` 를 심볼릭 링크 대신 사본으로 만든다 |

릴리스를 고정하고 검증하려면 아래 형식을 쓴다. 릴리스 태그가 생긴 뒤에 쓰는 형식이고, 아직 발행된 태그는 없다
([SECURITY.md](../SECURITY.md#installing-safely) 참조).

```bash
export AGENTS_SCAFFOLD_REF=v1.0.0
export AGENTS_SCAFFOLD_SHA256=<sha256 of that ref's source tarball>
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/v1.0.0/bin/agents-scaffold.sh | bash -s -- --lang en --yes
```

### 갱신 — `--update`

이미 부트스트랩된 프로젝트를 최신화한다. `--update` 는 기록된 선택을 읽고, 그 선택으로 지금 설치하면 나올 결과를
임시 디렉터리에 만든 뒤 프로젝트와 파일 단위로 비교한다(#104). 베이스만이 아니라 전체 결과와 비교하므로 forge·스택
프리셋, 영어 오버레이, `.claude/hooks/pre-commit.sh` 도 비교 대상이다.

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo --dry-run
```

| 프로젝트의 파일 | `--update` 가 하는 일 |
|---|---|
| 새 버전과 같다 | 건너뛴다 |
| 없다 | 추가한다 |
| 다르다 | 그대로 두고 새 버전을 `<file>.new` 로 쓴다 |
| `.claude/memory/MEMORY.md` | 사용자 파일이다. 없을 때만 추가하고 `.new` 는 만들지 않는다 |
| 생성 어댑터(`.codex/`, `.agents/rules`, `.agents/agents`, `.agents/hooks.json`) | 프로젝트의 `.claude/` 에서 다시 생성한다 |

- 끝에 추가·갱신 대기(`.new`)·변경 없음 목록을 요약해 찍는다. `.new` 는 `diff` 로 확인하고 직접 반영한다
  ([TROUBLESHOOTING.md](TROUBLESHOOTING.md#--update-뒤의-new-파일) 참조).
- `AGENTS.md` 도 다른 파일처럼 비교한다. 내용을 채운 뒤에는 업데이트 때마다 `AGENTS.md.new` 가 생긴다.
- 없는 git pre-commit 훅을 연결하고, 기록된 선택을 다시 쓴다.
- 명령줄 옵션은 기록보다 우선한다. `--update --harness all` 은 기존 프로젝트에 Codex·agy 어댑터를 추가하고,
  `--update --stack nextjs,go` 는 다른 스택 조합과 비교한다.
- 이전 버전이 만든 `.gemini/settings.json` 은 건드리지 않는다(남아 있어도 무해).
- 실디렉터리 `.claude/skills` 는 `.agents/skills` 가 없거나 내용이 같을 때만 원본으로 옮기고 링크한다(#61).
  둘 다 있고 내용이 다르면 옮기지 않고 수동 병합을 안내한다. 이전 뒤에는 베이스 스킬도 `.agents/skills`
  쪽으로 갱신한다.

### 제거 — `--uninstall`

```bash
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --dry-run
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --yes
```

기록된 선택으로 설치했을 결과를 다시 만들고, 그것과 아직 같은 파일만 지운다(#106). 사용자가 고친 파일은 남기고
목록으로 보여준다. `.claude/memory/` 와 스캐폴드가 만들지 않은 파일은 지우지 않는다. git pre-commit 훅은
스캐폴드가 만든 한 줄짜리 훅일 때만 지운다. `--yes` 가 없으면 확인을 받고, 물어볼 터미널이 없으면 실행하지 않는다.

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

`.claude/skills/yd-*/` 아래 파일은 치환하지 않는다 — `yd-mobile-web-planner` 템플릿이 `{{PROJECT_NAME}}` 을 산출물용 자리표시자로 쓴다(#78).
