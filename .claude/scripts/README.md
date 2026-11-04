# scripts/ — 레포 로컬 헬퍼 스크립트

템플릿에 동봉되어 커맨드/스킬이 호출하는 헬퍼 스크립트 (**훅 아님** — 훅은 `../hooks/`
에 있고 `settings.json` 으로 연결된다).

동봉:
- `knowledge_graph.py` — `.claude` 생태계에서 `docs/knowledge-graph.html` 생성;
  `--check` 모드는 깨진 링크 게이트 (`/knowledge-graph` 커맨드 참고).
- `personal-layer.sh` — 개인 추가 지침 `AGENTS.<NAME>.md` 를 Claude Code·Codex·agy 에 켜고 끈다
  (`on <NAME>`·`off`·`status`). 생성물은 `.git/info/exclude` 에 넣는다 (#92). `use <NAME|none>` 은 세션 사용자 확인
  명령이다 — `personal-gate` 훅이 이 명령을 기다린다 (#94).

컨벤션: stdlib 전용 Python(외부 라이브러리·xml/pyexpat 금지) 또는 POSIX shell;
레포 루트에서 실행 가능하게 유지; 신규 스크립트는 서술적 이름 사용.
