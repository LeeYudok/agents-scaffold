---
name: doksam-skills 원본은 이 레포
description: 2026-10-24 부터 doksam-skills 스킬·에이전트의 SSOT 는 이 레포 — 2026-11-25 skills/{core,yd-skills,yd-skills-personal}/ 단일 원본화로 plugins/·.claude/skills/ 이중 사본 제거
metadata:
  type: project
---

# doksam-skills 원본(SSOT) = agents-scaffold (#78)

- 2026-10-24 `LeeYudok/doksam-skills@67e5948` 을 옮겨 왔고 이 레포를 원본으로 확정했다. 옛 레포는 보관용 — 고치지 않는다(보관 처리는 사람 몫).
- 2026-11-25 구조 개편(2/3): `.claude/skills/`, `presets/skills/personal/.claude/skills/`, `plugins/` 이중 사본을 제거하고 `skills/` 로 단일화했다:
  - `skills/core/` — 스캐폴드 기본 워크플로 스킬
  - `skills/yd-skills/skills/` — 범용 15 + 병합 4 (플러그인 `yd-skills@agents-scaffold` 직접 소스)
  - `skills/yd-skills-personal/skills/` — 개인 옵트인 12 (플러그인 `yd-skills-personal@agents-scaffold` 직접 소스)
- 에이전트는 `.claude/agents/yd-*.md` · `presets/skills/personal/.claude/agents/*.md` 실파일 하나가 원본 — 스킬 안 `agents/{codex.toml,antigravity.md}` 는 두지 않는다.
  Codex·agy 판은 설치기 `emit_agents`, 전역 설치는 `scripts/install-skills.sh` 가 생성한다.
- 함정: 설치기 `{{PROJECT_NAME}}` 치환은 `*/skills/yd-*/` 를 건너뛴다(planner 템플릿 자리표시자 보존).
  `.skills-dist/` 항목은 심링크라 그 안에 쓰면 원본이 바뀐다 — 복사는 `cp -RL`.
