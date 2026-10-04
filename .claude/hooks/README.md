# hooks/ — 자동 실행 규칙 (훅 스크립트)

이벤트(도구 호출 전/후 등)에 harness가 자동 실행. "항상/매번 X" 자동화는 여기 둬야 강제된다.
`settings.json` 의 `hooks` 블록에서 이벤트와 스크립트를 연결한다.

**종료코드 규약**: `exit 2` = 동작 차단(block), `exit 0` = 허용.

동봉: `pre-commit.sh` — 커밋 전 검증 골격. 스택 프리셋(springboot)이 빌드 검증을 append.
스크립트는 실행권한(`chmod +x`) 필요.

## instinct-lite (세션 관찰 → 습관 추출)

ECC continuous-learning-v2 의 경량판. 백그라운드 관찰자 없이 훅 2개로 구성:

- `observe-lite.sh` (PostToolUse, Bash|Edit|Write) — 툴 호출을 `.claude/memory/observations/<session>.jsonl`
  에 압축 기록(시크릿 마스킹, 세션당 2MB 상한, 7일 자동 정리, 비커밋).
- `stop-memory-remind.sh` (Stop) — 세션당 1회 메모리 저장 리마인드. 관찰 로그가 20줄 이상이면
  반복 패턴(에러 반복 해결·사용자 교정·반복 워크플로)을 `instinct_*.md` 메모리로 추출하도록 유도.

instinct 포맷은 [../memory/README.md](../memory/README.md) 참고.

## Codex·agy 훅 어댑터 (#65)

`hook-adapter.py` 가 `settings.json` 의 훅을 Codex `.codex/hooks.json`·agy `.agents/hooks.json` 으로 생성하고(`--harness codex|agy|all`),
실행 때 하네스 입력을 Claude 형식으로 바꿔 이 디렉터리의 스크립트를 그대로 부른다. 그래서 훅은 Claude 형식으로만 쓰면 된다.

- 옮기는 것: `PostToolUse`(Bash·Edit·Write → Codex `Bash`·`apply_patch`, agy `run_command`·`write_to_file` 등), `Stop`.
  Codex 는 `SessionStart`·`UserPromptSubmit` 도 옮긴다.
- 옮기지 않는 것: `PreToolUse`(커밋 게이트는 `.git/hooks`), prompt 타입 훅.
- `python3` 가 필요하다. 프로젝트 경로는 `CLAUDE_PROJECT_DIR` 로 채워 준다.
- Codex 는 프로젝트 신뢰 + 훅 정의 신뢰(`/hooks`) 뒤에만 실행한다. agy 는 신뢰 확인 없이 실행한다.
