---
name: reference_harness-config-contracts
description: Claude Code / Codex / agy 세 하네스의 설정·디스커버리 계약 실측 결과와 공식문서 위치, 실측 요령 (2026-10-04 세 하네스 실측, 2026-10-14 문서 대조·2026-10-18 claude 2.1.299 재측정)
metadata:
  type: reference
---

이슈 #20 논쟁 중 3자(Claude·GPT/Codex·Antigravity)가 공식문서와 로컬 CLI 로 실측한 계약. 버전이 회전하므로 재사용 전 `--version` 대조할 것.

실측 버전: `claude 2.1.239` / `codex-cli 0.154.0` + `gpt-6-astra` / `agy 1.1.18`
(Codex 2026-09-15, 나머지 2026-08-22, 맥 로컬)
AGENTS.md 로드 항목만 2026-09-21 재측정: `claude 2.1.278` / `codex-cli 0.155.1` / `agy 1.2.7` / `gemini 0.56.0`
2026-10-04 재측정(#60, 리눅스 로컬): `claude 2.1.289` / `codex-cli 0.160.0` + `gpt-6.1-sol` / `agy 1.2.16` — 지원 대상은 이 세 하네스 최신판으로 고정, Gemini CLI 제외
2026-10-14 문서·소스 대조(#72, 실측 아님): 최신 `claude 2.1.299` / `codex-cli 0.162.1`(npm 10-09) / `agy 1.3.5`. 클라우드 세션에선 developers.openai.com·antigravity.google 이 프록시 차단 → Codex 는 소스(rust-v0.162.1), agy 는 공식 CHANGELOG 로만 대조. 2026-10-18 claude 2.1.299 만 재측정(AGENTS.md 단독 정답·대조군 UNKNOWN, 스킬 링크 YES·링크 없는 대조군 NO)

## Claude Code
- 프로젝트 설정 = `.claude/settings.json` (`.claude.json` 은 유저 전역 상태 파일이지 프로젝트 설정 아님)
- **`.claude/rules/*.md` + `paths:` frontmatter 조건부 로딩은 네이티브 기능** — [memory.md § Organize rules with .claude/rules/](https://code.claude.com/docs/en/memory.md#organize-rules-with-claude/rules/). `paths:` 없으면 세션 시작 시 상시 로드
- `@경로` import 최대 4 레벨
- **AGENTS.md 네이티브 로드 — 2.1.278 에서 실측 확인(2026-09-21)**, 공식문서상 v2.1.277+ ([memory § AGENTS.md](https://code.claude.com/docs/en/memory)). 문서 caveat(2026-10-14 대조): Bedrock·텔레메트리 비활성 세션 미적용은 **2.1.281 이전 한정**. 지금 남은 미적용 경우는 2.1.277 미만·`/plugin` 으로 내장 플러그인 비활성·2.1.276 이하에서 올린 직후 첫 세션(일부). `CLAUDE.local.md`·`.claude/CLAUDE.md` 도 "CLAUDE.md 있음"으로 쳐서 AGENTS.md 를 막는다(`~/.claude/CLAUDE.md`·managed·`.claude/rules/` 는 무관). 둘 다 읽히게 하는 `claude-md-and-agents-md` 는 `/config` 의 Project instructions 값(기본 `claude-md-or-agents-md`)인데 **프로젝트·로컬 settings 파일에서는 무시**된다 → 스캐폴드가 켤 수 없으니 CLAUDE.md 를 둘 거면 `@AGENTS.md` import 가 여전히 답. `.claude/AGENTS.md` 도 읽고, 하위 디렉터리 AGENTS.md 는 그 아래 파일을 Read·@-mention 할 때 로드(그 디렉터리에 CLAUDE.md 가 없을 때). AGENTS.md 만 둔 빈 git 디렉터리 + 툴 차단(`--disallowedTools`) 암호어 질의로 검증:
  - AGENTS.md 단독 → 로드됨
  - AGENTS.md 안의 `@경로` import → **처리됨**(import 대상 내용까지 로드)
  - CLAUDE.md 와 공존(CLAUDE.md 에 `@AGENTS.md` 없음) → **CLAUDE.md 만 로드, AGENTS.md 무시**. 병합이 아니라 폴백이다 — CLAUDE.md 를 남길 거면 `@AGENTS.md` import 도 남겨야 한다
  - 2.1.289(2026-10-04) 재확인: AGENTS.md 단독 → 정답, 지침 없음 → UNKNOWN
- repo skills = `.claude/skills` 만 스캔(`.agents/skills` 네이티브 미지원 — 2.1.289 대조군 `NONE`). 단 **`.claude/skills -> ../.agents/skills` 심볼릭 링크는 따라가서 등록**한다(2.1.289 실측) — #61 스킬 SSOT 설계의 근거
- `.claude/commands/` 는 레거시(skills 로 통합), `.claude/workflows/`·`.claude/scripts/` 는 **자동 로드 안 됨**
- `settings.json` 의 `PreToolUse` 훅은 그 세션이 Bash 툴로 커밋할 때만 발동 → **강제선 아님**(조기 피드백). 결정적 강제는 `.git/hooks` + CI
- **훅 타입은 이벤트마다 다르다**([hooks](https://code.claude.com/docs/en/hooks)): `PreCompact`·`PostCompact`·`SessionStart`·`SessionEnd`·`Notification` 등은 `prompt`/`agent` 미지원 → 스캐폴드의 예전 PreCompact prompt 훅은 **한 번도 실행되지 않았다**(#72, SessionStart matcher `compact` command 훅으로 교체 — stdout 이 컨텍스트로 들어간다). prompt/agent 는 Pre/PostToolUse·Stop·UserPromptSubmit 등에서만
- `onFailure: "block"`(v2.1.295+, command·http 훅): 스크립트 경로 오류·크래시 시 기본은 통과(continue) → pre-commit 훅에 걸어 fail-closed(#72). Stop 류에는 효과 없음
- 룰 `paths:` 는 Read·Write·Edit(2.1.293 부터 단일 파일 `cat`/`head` 포함) 때 로드 — 편집 전용 아님. YAML 리스트·쉼표 문자열 둘 다 허용
- 스킬 frontmatter 는 `name`·`description` 외에 `when_to_use`·`disable-model-invocation`·`paths`·`context: fork`·`effort`·`disallowed-tools` 등 지원(미채택). claude.ai·Skills API 업로드 시엔 `name`·`description`·`license`·`compatibility`·`metadata`·`allowed-tools` 외 키가 오류 — `user-invocable`·`argument-hint` 가 걸린다
- 서브에이전트 `model` 별칭에 `fable` 추가, 신규 필드 `disallowedTools`·`permissionMode`·`skills`·`isolation: worktree`·`effort`·`omitClaudeMd` 등. 모르는 필드는 오류 없이 무시(2.1.296 부터 `--debug` 가 이름을 찍는다)
- 2.1.299: `claude -p` 가 settings 검증 오류를 stderr 로 낸다 — 산출물 settings 검증에 쓸 수 있다

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
  - 훅 입력(#65 실측): Claude 와 거의 같다 — `session_id`·`cwd`·`hook_event_name`·`tool_name`·`tool_input`·`tool_response`(문자열). 셸은 `Bash`, 파일 편집은 `apply_patch`(`tool_input.command` 에 `*** Add File:/Update File:` 패치 텍스트). Stop 에 `{"decision":"block","reason"}` 을 내면 한 턴 더 돈다. 훅 cwd = 세션 cwd, 프로젝트 경로 환경변수 없음
  - 서브에이전트 이름에 하이픈(`code-reviewer`)이 되고, `developer_instructions` 를 TOML 리터럴 다중행 문자열(`'''`)로 두면 백슬래시·따옴표가 그대로 전달된다(#64)
  - 2026-10-14 소스 대조(rust-v0.162.1, 실측 아님 #72): 핵심 단언 유효. 훅 이벤트는 12종(SessionStart·SessionEnd·UserPromptSubmit·PreToolUse·PostToolUse·PermissionRequest·PreCompact·PostCompact·Stop·SubagentStart·SubagentStop·Interrupt — 0.160.0 에도 이미 있었음), 핸들러는 command 외 `mcp_tool`·`prompt`·`agent`, `config.toml` 인라인 `[hooks]` 도 가능. 훅 신뢰 해시는 정규화된 정의 기준(TOML·JSON 동일) — `hooks.state.<id>.{enabled,trusted_hash}`. `.codex/agents/` 는 하위 폴더까지 재귀 스캔, `[agents.<name>]` 선언·`[agents]` 설정(`max_depth` 등). 루트는 `project_root_markers`(기본 `.git`), 추가 지침 파일명은 `project_doc_fallback_filenames`. 0.160.0→0.162.1 스키마 diff 상 훅·에이전트·스킬·프로젝트 섹션 변경 없음. 재실측은 #73
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
  - 훅 입력(#65 실측): camelCase — `conversationId`·`workspacePaths`·`toolCall{name,args}`(`run_command`→`args.CommandLine`, `write_to_file` 등→`args.TargetFile`), PostToolUse 에 명령 출력 없음. 훅 cwd 는 hooks.json 이 있는 `.agents/`, 프로젝트 경로 환경변수 없음. Stop 은 `{"decision":"continue","reason"}` 로 한 턴 더(Claude 의 `block` 아님)
  - 산출물에 `.agents/hooks.json`(Stop 메모리 리마인드)이 생긴 뒤로 headless 질의도 한 턴 더 돌며 툴을 써서 "툴 없이 답했나" 판정이 깨진다 — spike 는 기능 측정 동안 hooks.json 을 빼 둔다(#65)
  - 2026-10-14 CHANGELOG 대조(1.3.5, 실측 아님 #72): 전역 위치에 `~/.gemini/config/{AGENTS.md,GEMINI.md,agents/,hooks.json}` 추가, manifest(`rules.json`·`skills.json`·`agents.json`·`plugins.json`)는 cwd→프로젝트 루트 사이 모든 `.agents/` 에서 로드(1.2.16). 1.3.1 부터 마크다운 에이전트가 `skills:`·`plugins:`·`rules:`·`agents:`·`hooks:` 를 받는다 → 위의 "name·description 외 필드면 조용히 미등록"은 Claude 필드(`tools`·`model`·`memory`)에 대해 **재실측 대상**. 1.3.4: headless `--agent` 이름 불일치 시 exit 1 + 목록 출력(예전엔 기본 에이전트로 조용히 실행). 훅 정의에 `enabled` 키, 커뮤니티 예시엔 평면 `{"enabled":true,"PreToolUse":[...]}` 형식도 보여 래퍼 형식과 대조 필요. 1.3.2 플러그인(skills·MCP·subagents·rules·hooks 번들), 공유 설정 `~/.gemini/config/config.json`. 재실측은 #73
  - 하위 `AGENTS.md` 는 cwd 기준으로만 로드 — 공식문서의 "파일을 읽거나 고칠 때 그 폴더부터 올라가며 로드"는 headless 에서 재현되지 않음(읽기·편집·다음 턴 모두 미로드)

## Gemini CLI (지원 대상 제외 — #60)
- 공식문서([gemini-md.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md)): 기본 컨텍스트 파일명은 `GEMINI.md` 뿐. `AGENTS.md` 는 `.gemini/settings.json` 의 `context.fileName` 에 넣어야 읽는다 → 스캐폴드는 #54 부터 이 설정 파일을 emit 하고 `GEMINI.md` 셤은 없앴다
- 0.56.0(2026-09-21): 개인 계정은 `IneligibleTierError`(Gemini Code Assist for individuals 지원 종료, Antigravity 로 이전 안내)로 인증 단계에서 막힘 → 이 머신에선 실측 불가. headless 는 그 전에 trusted-folder 게이트(`GEMINI_CLI_TRUST_WORKSPACE=true` 또는 `--skip-trust`)도 통과해야 한다

## 실측 요령 (2026-10-04 시행착오)
- 레포 `.claude/settings.json` deny 에 `Bash(rm -rf *)` 가 있어, 스크래치 정리용 `rm -rf` 가 섞인 Bash 명령은 **통째로 자동 거부**된다(사용자 거절과 구분 안 됨). 실측 디렉터리는 `mktemp -d` 로 매번 새로 만든다
- CLI 가 셸 함수·alias 로 래핑된 환경에서 `timeout command <cli>` 처럼 builtin 을 넘기면 실행 실패(exit 127)한다. `timeout` 에는 바이너리 절대경로(`command -v` 가 아니라 `which -a` 로 확인)를 준다. bash 스크립트 안에서는 대화형 셸 함수가 없으므로 PATH 의 바이너리가 잡힌다
- 스캐폴드 산출물(`.claude/settings.json` 의 Stop 훅 `stop-memory-remind.sh`)에서 `claude -p` 로 실측하면 훅이 한 턴을 더 돌려 `--output-format json` 의 `result` 가 리마인드 응답으로 덮인다. `--output-format stream-json --verbose` 로 첫 assistant 텍스트를 본다(2026-10-04, #61)

관련: [[project_agents-scaffold-multiagent-review]]
