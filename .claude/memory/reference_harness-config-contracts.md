---
name: reference_harness-config-contracts
description: Claude Code / Codex / agy 세 하네스의 설정·디스커버리 계약 실측 결과와 공식문서 위치, 실측 요령 (2026-10-04 세 하네스 최신판 재측정)
metadata:
  type: reference
---

이슈 #20 논쟁 중 3자(Claude·GPT/Codex·Antigravity)가 공식문서와 로컬 CLI 로 실측한 계약. 버전이 회전하므로 재사용 전 `--version` 대조할 것.

실측 버전: `claude 2.1.239` / `codex-cli 0.154.0` + `gpt-6-astra` / `agy 1.1.18`
(Codex 2026-09-15, 나머지 2026-08-22, 맥 로컬)
AGENTS.md 로드 항목만 2026-09-21 재측정: `claude 2.1.278` / `codex-cli 0.155.1` / `agy 1.2.7` / `gemini 0.56.0`
2026-10-04 재측정(#60, 리눅스 로컬): `claude 2.1.289` / `codex-cli 0.160.0` + `gpt-6.1-sol` / `agy 1.2.16` — 지원 대상은 이 세 하네스 최신판으로 고정, Gemini CLI 제외

## Claude Code
- 프로젝트 설정 = `.claude/settings.json` (`.claude.json` 은 유저 전역 상태 파일이지 프로젝트 설정 아님)
- **`.claude/rules/*.md` + `paths:` frontmatter 조건부 로딩은 네이티브 기능** — [memory.md § Organize rules with .claude/rules/](https://code.claude.com/docs/en/memory.md#organize-rules-with-claude/rules/). `paths:` 없으면 세션 시작 시 상시 로드
- `@경로` import 최대 4 레벨
- **AGENTS.md 네이티브 로드 — 2.1.278 에서 실측 확인(2026-09-21)**, 공식문서상 v2.1.277+ ([memory § AGENTS.md](https://code.claude.com/docs/en/memory)). 문서 caveat: Bedrock/Vertex·텔레메트리 비활성 세션·업그레이드 직후 첫 세션에선 미적용, `CLAUDE.local.md` 도 "CLAUDE.md 있음"으로 쳐서 AGENTS.md 를 막는다. 둘 다 읽히게 하는 설정(`claude-md-and-agents-md`)이 있다고 문서에 나오나 미실측. AGENTS.md 만 둔 빈 git 디렉터리 + 툴 차단(`--disallowedTools`) 암호어 질의로 검증:
  - AGENTS.md 단독 → 로드됨
  - AGENTS.md 안의 `@경로` import → **처리됨**(import 대상 내용까지 로드)
  - CLAUDE.md 와 공존(CLAUDE.md 에 `@AGENTS.md` 없음) → **CLAUDE.md 만 로드, AGENTS.md 무시**. 병합이 아니라 폴백이다 — CLAUDE.md 를 남길 거면 `@AGENTS.md` import 도 남겨야 한다
  - 2.1.289(2026-10-04) 재확인: AGENTS.md 단독 → 정답, 지침 없음 → UNKNOWN
- repo skills = `.claude/skills` 만 스캔(`.agents/skills` 네이티브 미지원 — 2.1.289 대조군 `NONE`). 단 **`.claude/skills -> ../.agents/skills` 심볼릭 링크는 따라가서 등록**한다(2.1.289 실측) — #61 스킬 SSOT 설계의 근거
- `.claude/commands/` 는 레거시(skills 로 통합), `.claude/workflows/`·`.claude/scripts/` 는 **자동 로드 안 됨**
- `settings.json` 의 `PreToolUse` 훅은 그 세션이 Bash 툴로 커밋할 때만 발동 → **강제선 아님**(조기 피드백). 결정적 강제는 `.git/hooks` + CI

## Codex
- instructions = `AGENTS.md` + nested `AGENTS.override.md` 계층, **합산 기본 한도 32KiB** (`project_doc_max_bytes`)
- repo skills = `.agents/skills/*/SKILL.md` (CWD→repo root 스캔). `.claude/skills` 는 발견 경로 아님.
  2026-09-15 `gpt-6-astra` 명시 통제실험에서 `.agents/skills`만 등록됨을 재확인
- 프로젝트 설정 = `.codex/config.toml`, hooks = `.codex/hooks.json`, subagents = `.codex/agents/*.toml`
- **trust boundary**: `.codex/` 레이어는 프로젝트를 신뢰한 경우에만 로드 → "파일 생성 = 활성화"가 아님
- hook 은 정의 **hash 에 신뢰가 묶임** → 정의 변경 시 재승인 전까지 skip
- `.codex/rules/*.rules` 는 **명령 실행 정책**(prefix_rule allow/prompt/forbidden)이지 Claude 의 `paths:` 코딩 가이던스와 다름. experimental
- 공통 `--instructions` 플래그 없음
- **2026-10-04 실측(0.160.0, #60)** — 재현은 `scripts/spike-codex-contract.sh --dynamic`
  - 서브에이전트 `.codex/agents/*.toml`(`name`·`description`·`developer_instructions`): 신뢰 프로젝트에서만 등록, 위임 시 `collab_tool_call` 로 developer_instructions 대로 응답
  - 훅 `.codex/hooks.json`(`{"hooks":{"<Event>":[{"hooks":[{"type":"command","command":...}]}]}}`): 신뢰 프로젝트 + 훅 정의 신뢰(`/hooks` 검토) 또는 `--dangerously-bypass-hook-trust` 일 때만 실행. 미신뢰 프로젝트는 우회 플래그로도 미실행
  - 하위 `AGENTS.md` 는 cwd 기준으로만 로드(루트에서 하위 파일을 읽어도 미로드) — 파일 경로 조건부 지침 없음
  - 서브에이전트 이름에 하이픈(`code-reviewer`)이 되고, `developer_instructions` 를 TOML 리터럴 다중행 문자열(`'''`)로 두면 백슬래시·따옴표가 그대로 전달된다(#64)
  - 함정: `codex exec` 는 stdin 이 열려 있으면 `Reading additional input from stdin...` 에서 멈춘다 → `</dev/null`. 사용자 config 를 안 건드리고 신뢰를 주려면 `-c 'projects={"<abs>"={trust_level="trusted"}}'`(인라인 테이블). `-c 'projects."<abs>".trust_level=...'` 는 "unrecognized configuration" 으로 무시된다

## agy (Antigravity)
- 공식문서 [Rules](https://antigravity.google/docs/rules/): 워크스페이스 `AGENTS.md`/`GEMINI.md`, `.agents/AGENTS.md`, `.agents/rules/*.md`(직계 자식만) 를 파일 위치→워크스페이스 루트로 올라가며 로드. 전역은 `~/.gemini/AGENTS.md`·`~/.gemini/config/rules/*.md`, CLI 전용 `~/.gemini/antigravity-cli/rules/*.md`
- 공식문서 [Skills](https://antigravity.google/docs/skills): 워크스페이스 `.agents/skills/<name>/`(레거시 `.agent/skills` 호환), CLI 전역 `~/.gemini/antigravity-cli/skills/`. CLI 설정은 `~/.gemini/antigravity-cli/settings.json` — 워크스페이스 `.gemini/settings.json` 은 agy 와 무관
- **1.2.16 headless(`-p`) 에서 AGENTS.md 로드 확인**(2026-10-04): AGENTS.md 단독 → 암호어 정답, GEMINI.md 대조군 → 정답, 없음 → UNKNOWN. `scripts/spike-agy-contract.sh --dynamic` 으로 스택 P0 인라인·`.agents/skills` 만 등록(`.claude/skills` 미등록)·.env 게이트 exit 2 까지 pass
- 1.1.17·1.2.7 headless 는 AGENTS.md·GEMINI.md 모두 미로드였다(원인 미규명, 1.2.16 에서 해소)
- `-p --output-format stream-json` 의 `step_update.step_type` 으로 툴 호출 여부를 판정할 수 있다(`user_input`·`agent_response` 외 단계 = 툴 사용)
- 공통 `--instructions` 플래그 없음 (`--agent`, `--mode`, `plugin` 등)
- **2026-10-04 실측(1.2.16 headless, #60)** — 재현은 `scripts/spike-agy-contract.sh --dynamic`
  - 서브에이전트 `.agents/agents/<name>.md`(frontmatter `name`·`description`): 툴 없이 목록에 등록, `--agent <name>` 으로 고르면 본문 지시대로 응답. `agy agents` 서브커맨드는 출력이 비어 판정에 못 쓴다
  - frontmatter 에 Claude 의 `tools: Read, Grep`·`model: sonnet`·`memory` 가 있으면 그 에이전트는 **조용히 미등록**(로그에도 이유 없음) → 스캐폴드는 `name`·`description` 만 생성한다(#64)
  - frontmatter 는 **엄격한 YAML** — 따옴표 없는 값 안의 `: ` 는 파싱 실패로 그 스킬·에이전트가 조용히 빠진다(로그 `--log-file` 에만 `mapping values are not allowed`). search-first 가 이렇게 빠졌다(#67, `tests/test_frontmatter.py` 가 막음). 사용자 전역 스킬(`~/.gemini/config/skills/*`)도 같은 이유로 빠질 수 있다. codex 는 관대해서 증상이 안 보인다
  - 훅 `.agents/hooks.json`: `{"<hook-name>":{"PreToolUse":[{"matcher":"...","hooks":[{...}]}],"PreInvocation":[{"type":"command","command":"..."}],...}}` — 툴 이벤트(Pre/PostToolUse)만 matcher+hooks, Pre/PostInvocation·Stop 은 핸들러 배열. 틀리면 `--log-file` 에만 `command hook must specify 'command'` 가 남고 조용히 무시된다. **신뢰 확인 없이 headless 에서도 실행**된다(보안 주의 — security-audit 대상)
  - 룰 `.agents/rules/*.md` `trigger: glob`: 일치 파일 접근 뒤에만 로드. `globs` 는 `**/sub2/**` 처럼 `**/` 접두가 필요하고 `sub2/**` 는 미일치. `trigger: always_on` 은 상시 로드
  - glob 패턴 세부(#63 실측): 슬래시 없는 패턴(`Dockerfile`·`*.py`)은 파일 이름에 일치(루트·하위 모두), `**/*.py` 는 루트 파일에도 일치. 여러 패턴은 `"a,b"` 처럼 **공백 없는 쉼표** — 공식문서 예시 `"*.ts, *.tsx"` 처럼 쉼표 뒤에 공백을 두면 두 번째 패턴이 일치하지 않는다. YAML 리스트(`globs:` 아래 `- ...`)는 응답이 비거나 엉뚱해져 쓰지 않는다. 스캐폴드는 `.claude/rules` 에서 이 형식으로 생성한다(`emit_agy_rules`)
  - 하위 `AGENTS.md` 는 cwd 기준으로만 로드 — 공식문서의 "파일을 읽거나 고칠 때 그 폴더부터 올라가며 로드"는 headless 에서 재현되지 않음(읽기·편집·다음 턴 모두 미로드)

## Gemini CLI (지원 대상 제외 — #60)
- 공식문서([gemini-md.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md)): 기본 컨텍스트 파일명은 `GEMINI.md` 뿐. `AGENTS.md` 는 `.gemini/settings.json` 의 `context.fileName` 에 넣어야 읽는다 → 스캐폴드는 #54 부터 이 설정 파일을 emit 하고 `GEMINI.md` 셤은 없앴다
- 0.56.0(2026-09-21): 개인 계정은 `IneligibleTierError`(Gemini Code Assist for individuals 지원 종료, Antigravity 로 이전 안내)로 인증 단계에서 막힘 → 이 머신에선 실측 불가. headless 는 그 전에 trusted-folder 게이트(`GEMINI_CLI_TRUST_WORKSPACE=true` 또는 `--skip-trust`)도 통과해야 한다

## 실측 요령 (2026-10-04 시행착오)
- 레포 `.claude/settings.json` deny 에 `Bash(rm -rf *)` 가 있어, 스크래치 정리용 `rm -rf` 가 섞인 Bash 명령은 **통째로 자동 거부**된다(사용자 거절과 구분 안 됨). 실측 디렉터리는 `mktemp -d` 로 매번 새로 만든다
- CLI 가 셸 함수·alias 로 래핑된 환경에서 `timeout command <cli>` 처럼 builtin 을 넘기면 실행 실패(exit 127)한다. `timeout` 에는 바이너리 절대경로(`command -v` 가 아니라 `which -a` 로 확인)를 준다. bash 스크립트 안에서는 대화형 셸 함수가 없으므로 PATH 의 바이너리가 잡힌다
- 스캐폴드 산출물(`.claude/settings.json` 의 Stop 훅 `stop-memory-remind.sh`)에서 `claude -p` 로 실측하면 훅이 한 턴을 더 돌려 `--output-format json` 의 `result` 가 리마인드 응답으로 덮인다. `--output-format stream-json --verbose` 로 첫 assistant 텍스트를 본다(2026-10-04, #61)

관련: [[project_agents-scaffold-multiagent-review]]
