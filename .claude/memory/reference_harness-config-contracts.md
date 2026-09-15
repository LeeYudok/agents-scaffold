---
name: reference_harness-config-contracts
description: Claude Code / Codex / agy 세 하네스의 설정·디스커버리 계약 실측 결과와 공식문서 위치 (Codex 2026-09-15 재측정)
metadata:
  type: reference
---

이슈 #20 논쟁 중 3자(Claude·GPT/Codex·Antigravity)가 공식문서와 로컬 CLI 로 실측한 계약. 버전이 회전하므로 재사용 전 `--version` 대조할 것.

실측 버전: `claude 2.1.239` / `codex-cli 0.154.0` + `gpt-6-astra` / `agy 1.1.18`
(Codex 2026-09-15, 나머지 2026-08-22, 맥 로컬)

## Claude Code
- 프로젝트 설정 = `.claude/settings.json` (`.claude.json` 은 유저 전역 상태 파일이지 프로젝트 설정 아님)
- **`.claude/rules/*.md` + `paths:` frontmatter 조건부 로딩은 네이티브 기능** — [memory.md § Organize rules with .claude/rules/](https://code.claude.com/docs/en/memory.md#organize-rules-with-claude/rules/). `paths:` 없으면 세션 시작 시 상시 로드
- `@경로` import 최대 4 레벨. **AGENTS.md 는 네이티브로 안 읽음** — `CLAUDE.md` 의 `@AGENTS.md` import 에 의존
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

관련: [[project_agents-scaffold-multiagent-review]]
