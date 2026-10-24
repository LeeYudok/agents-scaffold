---
name: doksam-skills 원본은 이 레포
description: 2026-10-24 부터 doksam-skills 스킬·에이전트의 SSOT 는 이 레포 — 기본 13·옵트인 9·중복 4쌍 병합 분류, 옛 레포와 skills.sh 경로는 보관
metadata:
  type: project
---

# doksam-skills 원본(SSOT) = agents-scaffold (#78)

- 2026-10-24 `LeeYudok/doksam-skills@67e5948` 을 옮겨 왔고 이 레포를 원본으로 확정했다. 옛 레포는 보관용 — 고치지 않는다(보관 처리는 사람 몫).
- 분류(사용자 확정): 범용 13 은 기본 설치 `.claude/skills/yd-*`, 개인·환경 전용 9 는 옵트인
  `presets/skills/personal/`(`--with-personal-skills`). 중복 4쌍(handoff·docs-sync·memory-factcheck·skill-evolve)은
  scaffold 이름을 유지하고 내용은 doksam 판으로 합쳤다. 새 스킬도 이 기준(범용=기본, 특정 환경=옵트인)으로 넣는다.
- 에이전트는 `.claude/agents/yd-*.md` 실파일 하나가 원본 — 스킬 안 `agents/{codex.toml,antigravity.md}` 는 두지 않는다.
  Codex·agy 판은 설치기 `emit_agents`, 전역 설치는 `scripts/install-skills.sh` 가 생성한다.
- `npx skills add leeyudok/doksam-skills` 는 옛 레포를 읽으므로 보관 후엔 갱신되지 않는다. 대체는 `scripts/install-skills.sh`.
- 함정: 설치기 `{{PROJECT_NAME}}` 치환은 `*/skills/yd-*/` 를 건너뛴다(planner 템플릿 자리표시자 보존).
  `.skills-dist/` 항목은 심링크라 그 안에 쓰면 원본이 바뀐다 — 복사는 `cp -RL`.
