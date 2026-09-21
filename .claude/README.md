# `.claude/` — Claude Code 협업 자산

루트 `AGENTS.md`(프로젝트 브레인 — 하네스가 네이티브로 로드)와 함께 동작한다.

```
.claude/
├── agents/        AI 팀원 — 서브에이전트 정의
├── commands/      커스텀 슬래시 커맨드
├── hooks/         Claude가 반드시 따르는 규칙 — 훅 스크립트(exit 2 = block)
├── memory/        프로젝트 메모리 SSOT — MEMORY.md 인덱스 + 타입접두 파일
├── rules/         맥락 인지 룰 — paths frontmatter로 조건부 자동로드(네이티브)
├── skills/        상황별 지능 — <name>/SKILL.md
├── workflows/     저장형 Workflow 오케스트레이션 스크립트(*.js)
├── scripts/       레포 로컬 헬퍼 스크립트(knowledge_graph.py 등)
└── settings.json  컨트롤 센터 — permissions/hooks/model
```

- **memory/** 가 auto-memory SSOT. 시스템 기본 경로 미사용(`memory/README.md`).
- **rules/** 는 `paths:` frontmatter 매칭 파일 작업 시 자동 로드, paths 없으면 세션 시작 시 로드.
- skill/agent 신규 생성 시 프로젝트 prefix 네임스페이스로 전역 충돌 방지.
- `/knowledge-graph` 로 이 생태계를 그래프로 렌더링하고 깨진 링크를 점검할 수 있다.

각 하위 폴더 `README.md` 에 용도·작성 골격을 둔다.
