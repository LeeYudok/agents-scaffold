# hooks/ — 자동 실행 규칙 (훅 스크립트)

이벤트(도구 호출 전/후 등)에 harness가 자동 실행. "항상/매번 X" 자동화는 여기 둬야 강제된다.
`settings.json` 의 `hooks` 블록에서 이벤트와 스크립트를 연결한다.

**종료코드 규약**: `exit 2` = 동작 차단(block), `exit 0` = 허용.

동봉: `pre-commit.sh` — 커밋 전 검증 골격. 스택 프리셋(springboot)이 빌드 검증을 append.
스크립트는 실행권한(`chmod +x`) 필요.

- `pre-commit.sh` 훅에는 `"onFailure": "block"`(Claude Code v2.1.295+)이 걸려 있다 — 스크립트 경로 오류·크래시 때
  커밋을 통과시키지 않고 막는다. 그래도 하네스 훅은 조기 피드백이고, 강제선은 `.git/hooks` + CI 다 (#72).
- `compact-remind.sh` (SessionStart, matcher `compact`) — 컨텍스트 압축 직후 재진입 사실 정리·메모리 기록을 유도한다.
  stdout 이 모델 컨텍스트에 들어간다. `PreCompact` 는 prompt 타입 훅을 지원하지 않아 예전 PreCompact prompt 훅은
  실행된 적이 없다 (#72).
- `personal-gate.sh` → `personal-gate.py` (SessionStart·UserPromptSubmit·PreToolUse·PostToolUse) — 루트에 `AGENTS.<NAME>.md` 가
  있으면 매 세션 사용자 확인을 강제한다. 확인 전에는 질문 도구와 `.claude/scripts/personal-layer.sh use <NAME|none>` 외
  툴을 막고, 확인 뒤에는 다른 사람의 개인 파일 수정을 막는다. 세션 마커는 `.claude/state/personal-gate/`(비커밋).
  개인 파일이 없으면 셸에서 바로 통과한다. ews ai-sdlc 의 사번 게이트를 옮겼다 (#94).

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
- 옮기지 않는 것: `PreToolUse`(커밋 게이트는 `.git/hooks`), prompt 타입 훅, matcher 가 걸린 비-툴 이벤트(`SessionStart` `compact` 등, #72).
- `personal-gate` 훅은 래퍼를 거치지 않고 하네스 고유 이벤트(Codex `SessionStart`·`UserPromptSubmit`·`PreToolUse`·`PostToolUse`,
  agy `SessionStart`·`PreInvocation`·`PreToolUse`·`PostToolUse`)로 바로 건다. agy 1.5.0 은 PreToolUse 출력 `{}` 를 거부로 읽어서
  허용은 `{"decision":"allow"}` 로 낸다 (#94).
- `python3` 가 필요하다. 프로젝트 경로는 `CLAUDE_PROJECT_DIR` 로 채워 준다.
- Codex 는 프로젝트 신뢰 + 훅 정의 신뢰(`/hooks`) 뒤에만 실행한다. agy 는 신뢰 확인 없이 실행한다.
