# skills/ — 상황별 지능 (스킬)

특정 상황에서 발동하는 절차적 지식. 각 스킬 = 디렉터리 1개 + `SKILL.md`
(frontmatter `name`/`description`(+`user-invocable`) + 본문 절차). description 트리거에
맞으면 Claude가 로드해 그대로 따른다. `user-invocable: true` 면 수동 호출도 가능.

```
skills/
└── <name>/
    ├── SKILL.md      # 본문은 짧게 — 트리거·핵심 절차만
    ├── scripts/      # (옵션) 스킬이 실행하는 스크립트
    └── resources/    # (옵션) 무거운 참조 자료 — 본문에서 링크, 필요할 때만 로드
```

원칙은 progressive disclosure(점진적 공개): SKILL.md 는 항상 로드되므로 짧게 유지하고,
긴 원문·표·예시는 `resources/` 파일로 빼서 필요할 때만 읽게 한다.

동봉: `example-skill/`, `review/`, `status/`, `search-first/`, `skill-evolve/`,
`memory-factcheck/`(메모리 사실 검증), `security-precheck/`(감사 대비 보안 사전점검),
`docs-sync/`(문서 현행화 — 주장별 사실 대조 + 다국어 짝 파일 동시 갱신),
`handoff/`(세션 핸드오프 — 재개 가능한 상태를 `HANDOFF.md`/이슈로 넘기고 이어받기),
`grill-me/`(적대적 요구사항 심문 — 대화 안에서 끝나는 가장 가벼운 선택지. 더 무거운
superpowers `brainstorming`·Ouroboros 와 작업마다 택일하며, 비교는 README 의
"요구사항 다지기 도구 고르기" 참조).
신규는 `{{PROJECT_NAME}}-sk-*` prefix 권장.

설치된 프로젝트에서 스킬 원본은 `.agents/skills/`(Codex·agy 네이티브 경로)이고, `.claude/skills` 는
그 디렉터리를 가리키는 심볼릭 링크다(#61) — 어느 경로로 고쳐도 같은 파일이다. 링크를 만들 수 없는
환경(Windows Git Bash 기본값 등)에서는 `.claude/skills` 가 사본이므로 `.agents/skills` 만 고치고
사본을 다시 떠 둘 다 스테이징한다. 스테이징된 사본이 원본과 다르면 pre-commit 게이트가 차단한다.
