# yd-skills

agents-scaffold 의 범용 스킬 묶음이다. DB(공통·PostgreSQL·Oracle·SQLite), Go, React, TypeScript, 프런트 빌드,
모바일 화면설계와 구현, 한국어 글쓰기, 의존성 CVE 점검(`yd-cve-check`), 그리고 `handoff`·`docs-sync`·
`memory-factcheck`·`skill-evolve` 를 담는다. 스킬 본문은 한국어다.

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

이 디렉터리의 `skills/` 는 원본 `.claude/skills/` 에서 `scripts/dev/build-plugins.py` 가 생성한 사본이다.
여기를 직접 고치지 말고 원본을 고친 뒤 다시 생성한다(CI 가 드리프트를 막는다). 프로젝트 규칙·훅·서브에이전트는
플러그인으로 배포되지 않는다 — 프로젝트에는 `bin/agents-scaffold.sh` 로 설치한다.
