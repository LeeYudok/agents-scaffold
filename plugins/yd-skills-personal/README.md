# yd-skills-personal

agents-scaffold 메인테이너 환경 전용 스킬 묶음이다(`--with-personal-skills` 와 같은 9개). git-sync·git-ship·
claude-auth-sync·finguard·doksam-ui·script-editor·sdlc-orchestrator·session-recording·agents-mem 을 담고,
특정 서버·계정·사내 도구를 전제하는 내용이 있어 범용 묶음과 나눴다. 스킬 본문은 한국어다.

```bash
claude plugin install yd-skills-personal@agents-scaffold
codex plugin add yd-skills-personal@agents-scaffold
```

`skills/` 는 원본 `presets/skills/personal/.claude/skills/` 에서 `scripts/dev/build-plugins.py` 가 생성한 사본이다.
여기를 직접 고치지 말고 원본을 고친 뒤 다시 생성한다(CI 가 드리프트를 막는다).
