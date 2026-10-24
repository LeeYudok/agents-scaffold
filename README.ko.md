# agents-scaffold

[English](README.md) | 한국어 | [简体中文](README.zh.md) | [日本語](README.ja.md)

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

**Claude Code·Codex·Antigravity 를 위한 AI 코딩 에이전트 가드레일. 실제 git pre-commit 게이트가 강제한다.**

AI 코딩 에이전트는 규칙을 어긴다. 이 도구는 부탁하지 않고 커밋을 막는다.
명령 한 번이면 `AGENTS.md` 프로젝트 브레인, paths 스코프 룰, 스킬, 서브에이전트, 훅, 합성된
pre-commit 게이트가 레포에 깔린다. 프레임워크도 런타임도 레지스트리도 없다 — 결과물은 전부 **당신이 소유하는 평범한 파일**이다.

![데모: 원커맨드 부트스트랩 → 생성된 .claude/ 트리 → pre-commit 게이트가 .env 커밋을 차단](docs/assets/demo.gif)

_30초 데모: 명령 한 번 → `.claude/` 완성 → 시크릿 커밋은 게이트가 차단. 재현은 `vhs docs/assets/demo.tape`._

## 이런 적 있으면 이 도구다

- AI 에게 같은 규칙을 **매 세션 다시 설명**하고 있다 — 어제 말한 걸 오늘 또 모른다.
- 에이전트가 `.env` 를 스테이징하거나, 타입 에러가 있는 채로 커밋을 만들었다.
- 팀원마다 `CLAUDE.md` 가 제각각이라 **누구 세션이냐에 따라 결과가 다르다.**
- 팀이 Claude Code·Codex·Antigravity 를 섞어 쓰고, **규칙은 하나로 통일하고 싶다.**
- **폐쇄망이나 Windows** 에서 일하는데, 에이전트 세팅 대부분이 둘 다 고려하지 않는다.

규칙을 문서에만 적어두면 언젠가 무시된다. 이 스캐폴드는 규칙을 **커밋을 막는
게이트**로 바꿔 레포에 심는다.

## 퀵스타트

```bash
# one command, no clone required
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# or from a local clone (prompts interactively when options are omitted)
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app

# Codex or Antigravity too: --harness codex | agy | all
agents-scaffold/bin/agents-scaffold.sh /path/to/repo --harness all --stack python --yes
```

이미 설치했다면 `--update` 로 베이스 파일을 갱신한다. 직접 고친 파일은 덮어쓰지 않고 옆에
`<file>.new` 를 만든다. 전체 옵션은 [사용법](docs/OPTIONS.md#사용법-1--스크립트) 참조.

## 왜 믿을 만한가

| 강점 | 의미 |
|---|---|
| **프롬프트가 아니라 git 이 강제** | `.git/hooks/pre-commit` 이 스테이징된 `.env`/시크릿, 빌드 깨짐, 타입·린트 에러를 막는다. 어떤 AI 도구를 쓰든, 사람이 직접 커밋하든 똑같이 걸린다. |
| **원본 하나, 에이전트 셋** | `AGENTS.md` 가 단일 진실원천이고, Claude Code·Codex·Antigravity 모두 이를 네이티브로 읽는다. 스킬은 `.agents/skills/` 에 한 벌만 둔다. Codex 서브에이전트(`.codex/agents/*.toml`)와 Antigravity 룰·서브에이전트·훅은 `.claude/` 에서 생성한다. |
| **가정이 아니라 실측** | 하네스에 관한 주장은 모두 [docs/harness-matrix.json](docs/harness-matrix.json) 의 실측으로 뒷받침된다 — Claude Code 와 Antigravity 는 **full** 등급, Codex 는 **baseline** 등급. 실측이 만료되면 CI 가 실패한다. |
| **스택 프리셋 12종** | Next.js, Spring Boot, Java web(JSP), Bun, Python, Go, Rust, Ruby on Rails, .NET, Android, Flutter, ops — 각각 룰과 자체 build/lint/test 게이트를 더한다. forge 는 GitHub 또는 GitLab, 출력 언어는 한국어 또는 영어. |
| **paths 스코프 룰** | 에이전트가 매칭 파일을 만질 때만 룰이 로드된다. 모든 컨벤션을 미리 싣지 않으니 컨텍스트가 가볍다. |
| **기본 스킬 24개** | 워크플로(review, status, handoff, docs-sync, 보안 사전점검 등)와 `yd-*` 전문 스킬: PostgreSQL, Oracle, SQLite, 관계형 설계, Go, React, TypeScript, Vite/pnpm 빌드, 모바일 화면설계, **의존성 CVE 점검**(온라인은 `pnpm audit`, 오프라인은 OSV 덤프). |
| **폐쇄망·Windows 지원** | 오프라인 번들은 네트워크 없이 설치된다. Windows 는 Git Bash 와 `.cmd` 런처로 돌아간다([docs/OFFLINE_INSTALL.md](docs/OFFLINE_INSTALL.md)). |
| **플러그인 마켓플레이스** | 스킬은 Claude Code / Codex 플러그인으로도 전역 설치된다 — clone 이 필요 없다. |
| **자기개선** | `skill-evolve` / `agent-evolve` 가 실제 실수를, 그 실수를 낸 스킬·에이전트의 "Learned warnings" 로 바꾼다. |
| **테스트됨** | 설치 스크립트 bats 회귀 테스트 89개, 스킬별 계약 테스트, 문서 링크 체커가 모두 CI 에서 돈다. |

## 설치 직후 이런 일이 벌어진다

에이전트가(또는 사람이) 시크릿을 커밋하려 하면 **커밋 자체가 안 된다.**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

문서에 "시크릿 커밋하지 마세요"라고 적어두는 것과 다르다. 막는 것은 git 훅이다.

## 무엇을 얻나

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="한 명령 → 직접 소유하는 .claude/ (agents·skills·commands·rules·hooks·memory·AGENTS.md) → 강제 게이트(.env·빌드 깨짐·린트 실패 커밋 차단)" src="docs/assets/overview-light.svg">
</picture>

설치 1분 뒤부터 에이전트가 "규칙을 아는 팀원"처럼 움직인다. 프롬프트를 잘 몰라도:

- **워크플로가 기본값**: "로그인 기능 만들어줘" 한 마디에 이슈 등록 → 브랜치 → 구현 →
  테스트 → PR/MR 까지 스스로 따른다 (`/fix-issue`, `/sdlc-cycle` 은 역할 분리
  에이전트 3개가 무인 사이클).
- **실수는 기계가 차단**: `.env`/시크릿 커밋, 타입에러·빌드 깨진 커밋, 신규 JSP
  스크립틀릿은 pre-commit 훅이 막고, 인지 복잡도 15 초과 함수는 경고한다.
- **티어별 규칙**: P0(절대 — 시크릿, 파괴적 SQL, force push), P1(필수 — 이슈 연결, 테스트),
  P2(권장). `AGENTS.md` 에 한 번 적고, 도구로 강제할 수 있는 곳에서는 강제한다.
- **명령 한 방 시리즈**: `/review`(코드리뷰+보안감사), `/status`,
  `/knowledge-graph`(문서 링크 검사), `/sonar`.
- **요구사항 다지기는 셋 중 골라서**: 동봉된 **`grill-me`** 외에 외부 도구 둘을 상황에
  맞게 붙일 수 있다 → [요구사항 다지기 도구 고르기](docs/OPTIONS.md#요구사항-다지기-도구-고르기).
- **세션이 끝나도 기억**: `.claude/memory/` 에 프로젝트 러닝이 쌓여 다음 세션에 자동
  로드되고 팀과 공유된다.
- **팀/멀티세션 안전**: 세션마다 git worktree 격리가 기본이라 병렬 에이전트가 서로의 작업을
  덮어쓰지 않는다.

## 스킬

기본 설치에 스킬 24개가 들어간다 — 워크플로 스킬 10개와 DB·Go·React·TypeScript·빌드·화면설계·한국어 글쓰기·
의존성 CVE 점검을 다루는 `yd-*` 전문 스킬 14개다. 메인테이너 환경 전용 `yd-*` 9개는 `--with-personal-skills` 를
줄 때만 설치된다. `yd-*` 스킬은 한국어로 쓰여 있다. 목록과 작성 규약은
[.claude/skills/README.md](.claude/skills/README.md) 참조.

**플러그인으로 전역 설치.** Claude Code 와 Codex 가 같은 `.claude-plugin/marketplace.json` 을 읽는다.

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

`yd-skills` 에는 `yd-*` 14개와 `handoff`·`docs-sync`·`memory-factcheck`·`skill-evolve` 가, `yd-skills-personal` 에는
옵트인 9개가 들어 있다. Claude Code 에서는 플러그인 스킬 이름 앞에 플러그인 이름이 붙는다(`yd-skills:yd-pg-expert`).
플러그인은 스킬만 싣는다. Claude Code 플러그인은 rules 를, Codex 플러그인은 서브에이전트를 싣지 못하므로 프로젝트 규칙·훅·
서브에이전트는 설치 스크립트가 맡는다. 각 플러그인에는 Antigravity 용 매니페스트
(`.antigravity-plugin/plugin.json`)도 있는데, agy 문서를 보고 만들었고 아직 실측하지 않았다. 폐쇄망이나 개발용으로는
이 레포를 clone 해 `scripts/install-skills.sh` 를 실행한다(`~/.claude/skills`·`~/.agents/skills`·
`~/.gemini/config/skills` 에 심링크, `--personal`·`--copy`·`--project <dir>` 지원).

## 비교

| | 직접 쓴 `CLAUDE.md` | 설치형 에이전트 프레임워크 | agents-scaffold |
|---|---|---|---|
| 규칙이 실제로 강제되나 | 아니오 — 에이전트가 무시할 수 있다 | 대개 에이전트 런타임 안에서 | 예 — git 훅 + CI, 어떤 에이전트와도 무관 |
| Claude Code·Codex·Antigravity 공용 | 아니오 | 대개 한 벤더 전용 | 예 — `AGENTS.md` + 생성 어댑터 |
| 설치·업그레이드할 대상 | 없음 | 런타임이나 CLI | 없음 — 레포 안의 평범한 파일 |
| 오프라인 / 폐쇄망 설치 | 해당 없음 | 드묾 | 예 — 오프라인 번들 |

## 더 보기

| 문서 | 내용 |
|---|---|
| [docs/OPTIONS.md](docs/OPTIONS.md) | 전체 옵션 — 스택 프리셋 12종, `--forge`, `--harness`, `--lang`, `--update`, `--with-personal-skills`, 치환 플레이스홀더 |
| [docs/INTERNALS.md](docs/INTERNALS.md) | 내부 구조 — 생성되는 전체 트리, 레포 구성, 주요 패턴 |
| [docs/OFFLINE_INSTALL.md](docs/OFFLINE_INSTALL.md) | 폐쇄망·Windows 설치 — 오프라인 번들, Git Bash, `.cmd` 런처, `python3` 설정 |
| [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) | 스택 프리셋 규격 |
| [dotfiles/](dotfiles/README.md) | 메인테이너의 머신 셸 환경(zsh·starship·Claude/Codex/agy statusline). scaffold 설치와는 별개다 |

## Contributing

워크플로는 [CONTRIBUTING.md](CONTRIBUTING.md), 스택 프리셋 규격은 [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) 참조.
처음이라면 [`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 라벨부터 —
새 스택 프리셋 추가가 구조가 정형화돼 있어 가장 만만하다.

## License

MIT — [LICENSE](LICENSE) 참조. 서드파티 유래(스킬·문서)는 [CREDITS.md](CREDITS.md) 와
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) 에 있다.
