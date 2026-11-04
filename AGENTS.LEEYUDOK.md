# AGENTS.LEEYUDOK.md — 메인테이너 개인 추가 지침

이 파일은 [AGENTS.md](AGENTS.md) 위에 얹는 **개인 레이어**다. 메인테이너(LeeYudok)가 이 저장소에서 에이전트에게
시키는 일에만 적용한다. 다른 사용자는 이 파일을 켜지 않는 한 영향을 받지 않는다.

- **세션 사용자가 LeeYudok 인지 확인한 뒤에만 따른다.** 세션 첫 응답에서 누구인지 묻고, LeeYudok 이면
  `.claude/scripts/personal-layer.sh use LEEYUDOK` 을 실행한다. 답을 받기 전이나 다른 사람이면 이 파일 전체를 무시한다.
  `personal-gate` 훅이 확인 전 툴 호출을 막는다(AGENTS.md 의 개인 레이어 규칙, #94).
- AGENTS.md 에 **더하기만** 한다. P0/P1 을 약하게 만들거나 예외를 두지 않는다. 충돌하면 AGENTS.md 가 이긴다.
- 켜기: `.claude/scripts/personal-layer.sh on LEEYUDOK` · 끄기: `off` · 상태·낡은 사본 확인: `status`
- 자기 레이어를 만들려면 이 파일을 `AGENTS.<NAME>.md` 로 복사해 고친 뒤 `on <NAME>` 을 실행한다.

## 하네스별 사용 가능성

`on` 은 하네스마다 지침 파일을 하나 더 읽게 하는 생성물을 만든다. 생성물은 `.git/info/exclude` 에 들어가 커밋되지 않는다.

| 하네스 | 실측 버전 | 생성물 | 로드 | 주의 |
|---|---|---|---|---|
| Claude Code | 2.1.318 | `CLAUDE.local.md` = `@AGENTS.md` + `@AGENTS.LEEYUDOK.md` | 된다 | `CLAUDE.local.md` 가 있으면 AGENTS.md 를 건너뛰므로 `@AGENTS.md` 를 함께 import 한다. 개인 import 만 두면 기본 지침이 빠진다(실측) |
| Codex | codex-cli 0.166.0 | `AGENTS.override.md` = AGENTS.md + 이 파일을 이어 붙인 사본 | 된다(신뢰 여부 무관) | override 는 같은 폴더의 AGENTS.md 를 대신한다. 원본을 고치면 `on` 을 다시 돌린다. 합산 32 KiB 한도 |
| agy | 1.5.0 | `.agents/rules/personal-leeyudok.md` (`trigger: always_on`) | 된다 | 내용이 사본이라 원본을 고치면 `on` 을 다시 돌린다 |

실측(2026-11-04, #92): 빈 git 폴더에 기본 암호어(AGENTS.md)와 개인 암호어(개인 파일)를 두고 툴 없이 물었다.
세 하네스 모두 두 값을 함께 답했다. Codex 는 모델 호출 없이 `codex debug prompt-input` 출력으로 확인했다.

사용자 확인 게이트(#94, 2026-11-04): 스캐폴드 산출물에 개인 파일을 두고 "notes.txt 를 읽어 줘" 를 물었다.

| 하네스 | 확인 전 | `use <NAME>` 뒤 |
|---|---|---|
| Claude Code 2.1.318 | 파일을 읽지 않고 누구인지 물었다 | `use` 실행 → 게이트 열림 → 파일 읽기, 개인 지침 적용 |
| agy 1.5.0 | 같다 | 같다. 확정 컨텍스트에 개인 파일 본문을 실어야 개인 지침을 따랐다 |
| Codex 0.166.0 | 단위 시험만(입력·출력 형식) | 모델 호출 미실측 — 로그인 토큰 폐기 |

이 세션(대화형 Claude Code)도 게이트가 켜지자마자 툴이 막혔고, 사용자 확인 질문 → `use LEEYUDOK` 뒤에 풀렸다.

## 소통

- 대화(설명·상태 보고)는 가벼운 구어체로 짧게 한다. 코드·커밋·이슈·PR 본문·문서는 표준 문체로 쓴다.
- 영어 IT 용어는 처음 나올 때 한글 풀이를 붙인다. 코드 식별자·명령은 원문 그대로 둔다.
- 완료·머지·생성을 보고할 때는 결과물 URL(PR·이슈·CI 실행)을 함께 준다.
- 상태 질문에는 예/아니오와 짧은 근거로 답한다.

## git

- 사람이 직접 하지 않은 작업의 커밋 작성자는 에이전트 계정이다 — `git -c user.name=claude-ai -c user.email=claude-ai@doksam.com commit`
  (Codex `codex-ai`, agy `agy-ai`). 전역 git config 는 바꾸지 않는다.
- 커밋·PR 제목은 `[<모델명>] <type>: <설명> (#N)` 이다. 예: `[Claude Opus 5.5] docs: ... (#90)`.
  `Co-Authored-By` 와 `Generated with ...` 줄은 넣지 않는다.
- PR 본문에 `Closes #N` 을 넣는다. 머지는 merge commit 으로 한다(squash 금지).
- push·머지는 요청을 받으면 바로 한다. force push·`reset --hard` 는 확인을 받는다.

## 작업 환경

`dotfiles/install.sh` 로 맞춘 macOS 머신의 실측값이다. 다시 뽑으려면 `dotfiles/scripts/versions.sh --md` 를 실행해 이 표를 바꾼다.
버전이 다른 머신에서는 이 표가 아니라 그 머신의 출력이 맞다.

측정: 2026-11-04, macOS(Apple Silicon)

| 구분 | 도구 | 버전 | 상태 |
|---|---|---|---|
| 셸 | zsh | 5.9 | 사용 가능 |
| 셸 | starship | 1.26.0 | 사용 가능 |
| 셸 | zsh-autosuggestions | 0.7.1 | 사용 가능 |
| 셸 | zsh-syntax-highlighting | 0.8.0 | 사용 가능 |
| CLI 도구 | eza | 0.23.4 | 사용 가능 |
| CLI 도구 | bat | 0.26.1 | 사용 가능 |
| CLI 도구 | zoxide | 0.9.9 | 사용 가능 |
| CLI 도구 | fzf | 0.74.4 | 사용 가능 |
| CLI 도구 | fd | 10.4.2 | 사용 가능 |
| CLI 도구 | jq | 1.7.1 | 사용 가능 |
| 폰트 | JetBrainsMono Nerd Font | - | 설치됨 |
| 폰트 | D2Coding Nerd Font | - | 설치됨 |
| 하네스 | Claude Code | 2.1.318 | 사용 가능 |
| 하네스 | Codex CLI | 0.166.0 | 사용 가능 |
| 하네스 | agy (Antigravity) | 1.5.0 | 사용 가능 |
| 필수 런타임 | python3 | 3.12.10 | 사용 가능 |
| 필수 런타임 | git | 2.54.0 | 사용 가능 |
| 필수 런타임 | curl | 8.7.1 | 사용 가능 |
| 필수 런타임 | unzip | 6.00 | 사용 가능 |
| 필수 런타임 | brew | 7.0.11 | 사용 가능 |
| 개발·시험 | node | 26.7.0 | 사용 가능 |
| 개발·시험 | npm | 11.19.0 | 사용 가능 |
| 개발·시험 | pnpm | 11.9.0 | 사용 가능 |
| 개발·시험 | bun | 1.4.2 | 사용 가능 |
| 개발·시험 | pyenv | 2.8.5 | 사용 가능 |
| 개발·시험 | gh | 2.96.0 | 사용 가능 |
| 개발·시험 | bats | 1.13.0 | 사용 가능 |

- 폰트는 install.sh 가 Nerd Fonts 최신 릴리스를 받아 깔고 버전을 남기지 않아서 "설치됨" 으로만 나온다.
- agy 는 스스로 업데이트한다. 버전을 고정할 수 없으니 하네스 판정은 [docs/harness-matrix.json](docs/harness-matrix.json) 을 본다.
