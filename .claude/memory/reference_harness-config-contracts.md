---
name: reference_harness-config-contracts
description: Claude Code / Codex / agy 세 하네스의 설정·디스커버리 계약 실측 결과와 공식문서 위치 (Codex 2026-09-15 재측정)
metadata:
  type: reference
---

이슈 #20 논쟁 중 3자(Claude·GPT/Codex·Antigravity)가 공식문서와 로컬 CLI 로 실측한 계약. 버전이 회전하므로 재사용 전 `--version` 대조할 것.

실측 버전: `claude 2.1.239` / `codex-cli 0.154.0` + `gpt-6-astra` / `agy 1.1.18`
(Codex 2026-09-15, 나머지 2026-08-22, 맥 로컬)
AGENTS.md 로드 항목만 2026-09-21 재측정: `claude 2.1.278` / `codex-cli 0.155.1` / `agy 1.2.7` / `gemini 0.56.0`

## Claude Code
- 프로젝트 설정 = `.claude/settings.json` (`.claude.json` 은 유저 전역 상태 파일이지 프로젝트 설정 아님)
- **`.claude/rules/*.md` + `paths:` frontmatter 조건부 로딩은 네이티브 기능** — [memory.md § Organize rules with .claude/rules/](https://code.claude.com/docs/en/memory.md#organize-rules-with-claude/rules/). `paths:` 없으면 세션 시작 시 상시 로드
- `@경로` import 최대 4 레벨
- **AGENTS.md 네이티브 로드 — 2.1.278 에서 실측 확인(2026-09-21)**, 공식문서상 v2.1.277+ ([memory § AGENTS.md](https://code.claude.com/docs/en/memory)). 문서 caveat: Bedrock/Vertex·텔레메트리 비활성 세션·업그레이드 직후 첫 세션에선 미적용, `CLAUDE.local.md` 도 "CLAUDE.md 있음"으로 쳐서 AGENTS.md 를 막는다. 둘 다 읽히게 하는 설정(`claude-md-and-agents-md`)이 있다고 문서에 나오나 미실측. AGENTS.md 만 둔 빈 git 디렉터리 + 툴 차단(`--disallowedTools`) 암호어 질의로 검증:
  - AGENTS.md 단독 → 로드됨
  - AGENTS.md 안의 `@경로` import → **처리됨**(import 대상 내용까지 로드)
  - CLAUDE.md 와 공존(CLAUDE.md 에 `@AGENTS.md` 없음) → **CLAUDE.md 만 로드, AGENTS.md 무시**. 병합이 아니라 폴백이다 — CLAUDE.md 를 남길 거면 `@AGENTS.md` import 도 남겨야 한다
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

## agy (Antigravity)
- 공통 `--instructions` 플래그 없음 (`--agent`, `--mode`, `plugin` 등)
- 1.1.17 headless(`-p`) 에서 규칙 미로드 실측 — 원인 미규명. interactive 미검증
- 1.2.7(2026-09-21) 에서도 동일: headless 는 AGENTS.md 단독도, 대조군 GEMINI.md 도 못 읽음 → **headless 로는 AGENTS.md 네이티브 지원 여부를 판정할 수 없다**. interactive 로 확인해야 함

## Gemini CLI
- 공식문서([gemini-md.md](https://github.com/google-gemini/gemini-cli/blob/main/docs/cli/gemini-md.md)): 기본 컨텍스트 파일명은 `GEMINI.md` 뿐. `AGENTS.md` 는 `.gemini/settings.json` 의 `context.fileName` 에 넣어야 읽는다 → 스캐폴드는 #54 부터 이 설정 파일을 emit 하고 `GEMINI.md` 셤은 없앴다
- 0.56.0(2026-09-21): 개인 계정은 `IneligibleTierError`(Gemini Code Assist for individuals 지원 종료, Antigravity 로 이전 안내)로 인증 단계에서 막힘 → 이 머신에선 실측 불가. headless 는 그 전에 trusted-folder 게이트(`GEMINI_CLI_TRUST_WORKSPACE=true` 또는 `--skip-trust`)도 통과해야 한다

관련: [[project_agents-scaffold-multiagent-review]]
