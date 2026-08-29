# agents-scaffold

[English](README.md) | 한국어 | [简体中文](README.zh.md) | [日本語](README.ja.md)

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI 코딩 에이전트가 규칙을 안 지키는 문제를, 커밋을 막아서 해결한다.**

명령 한 번이면 `.claude/` 구성과 pre-commit 게이트가 레포에 깔린다. 프레임워크도 런타임도
설치할 레지스트리도 없다 — 결과물은 전부 **당신이 소유하는 평범한 파일**이다.

![데모: 원커맨드 부트스트랩 → 생성된 .claude/ 트리 → pre-commit 게이트가 .env 커밋을 차단](docs/assets/demo.gif)

_30초 데모: 명령 한 번 → `.claude/` 완성 → 시크릿 커밋은 게이트가 차단. 재현은 `vhs docs/assets/demo.tape`._

## 이런 적 있으면 이 도구다

- AI 에게 같은 규칙을 **매 세션 다시 설명**하고 있다 — 어제 말한 걸 오늘 또 모른다.
- 에이전트가 `.env` 를 스테이징하거나, 타입 에러가 있는 채로 커밋을 만들었다.
- 팀원마다 `CLAUDE.md` 가 제각각이라 **누구 세션이냐에 따라 결과가 다르다.**

규칙을 문서에만 적어두면 AI 는 언젠가 무시한다. 이 스캐폴드는 규칙을 **커밋을 막는
게이트**로 바꿔 레포에 심는다.

## 퀵스타트

```bash
# clone 없이 원커맨드
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# 또는 로컬 clone 에서 (옵션 생략 시 대화형 프롬프트)
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

결과물은 채워진 `.claude/` 디렉터리(agents·skills·hooks·paths 스코프 rules·memory),
`AGENTS.md` 프로젝트 브레인, 합성된 pre-commit 게이트 하나 — 전부 직접 소유하는 평범한
파일이다. 전체 옵션은 [사용법](docs/OPTIONS.md#사용법-1--스크립트) 참조.

## 설치 직후 이런 일이 벌어진다

에이전트가(또는 사람이) 시크릿을 커밋하려 하면 **커밋 자체가 안 된다.**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

문서에 "시크릿 커밋하지 마세요"라고 적어두는 것과 다르다. `.git/hooks/pre-commit` 이
막기 때문에 **어떤 AI 도구를 쓰든, 사람이 터미널에서 직접 커밋하든 똑같이 걸린다.**

## 무엇을 얻나 — 입문자 기준

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="한 명령 → 직접 소유하는 .claude/ (agents·skills·commands·rules·hooks·memory·AGENTS.md) → 강제 게이트(.env·빌드 깨짐·린트 실패 커밋 차단)" src="docs/assets/overview-light.svg">
</picture>

설치 1분 뒤부터 Claude 가 "규칙을 아는 팀원"처럼 움직인다. 프롬프트를 잘 몰라도:

- **워크플로가 기본값**: "로그인 기능 만들어줘" 한 마디에 이슈 등록 → 브랜치 → 구현 →
  테스트 동반 → PR/MR 까지 스스로 따른다 (`/fix-issue`, `/sdlc-cycle` 은 역할 분리
  에이전트 3개가 무인 사이클).
- **실수는 기계가 차단**: `.env`/시크릿 커밋, 타입에러·빌드 깨진 커밋, 신규 JSP
  스크립틀릿은 pre-commit 훅이 막고, 복잡도 15 초과 함수는 경고한다 — Claude 가
  깜빡해도 걸리는 강제 게이트.
- **명령 한 방 시리즈**: `/review`(코드리뷰+보안감사 이중), `/status`,
  `/knowledge-graph`(문서 링크 검사), `/sonar`.
- **요구사항 다지기는 셋 중 골라서**: 동봉된 **`grill-me`** 외에 외부 도구 둘을 상황에
  맞게 붙일 수 있다 → [요구사항 다지기 도구 고르기](docs/OPTIONS.md#요구사항-다지기-도구-고르기).
- **세션이 끝나도 기억**: `.claude/memory/` 에 프로젝트 러닝이 쌓여 다음 세션에 자동
  로드되고 팀과 공유된다.
- **스스로 진화**: skill-evolve/agent-evolve 가 실패 피드백으로 스킬·에이전트 정의를
  직접 고친다 — 쓸수록 프로젝트에 맞게 좋아진다.
- **팀/멀티세션 안전**: 세션마다 git worktree 격리 규칙이 기본이라 병렬 작업이 서로를
  덮어쓰지 않는다.

## 왜 agents-scaffold 인가

대형 설치형 프레임워크나 에이전트/스킬 카탈로그와 달리, agents-scaffold 은 런타임도 플러그인
시스템도 동기화할 중앙 레지스트리도 없다 — `.claude/` 디렉터리 골격 + 스택 프리셋 몇 개를
레포에 한 번 복사하면 그걸로 끝이고, 이후 업그레이드할 대상 자체가 없다. fork 해서
placeholder 를 채우고 안 쓰는 걸 지우면, 결과는 레포의 다른 코드와 똑같이 버전 관리되는
평범한 파일들이다.

- **선언이 아니라 강제** — P0/P1/P2 티어가 훅(pre-commit 게이트·deny 규칙·CC 경고)에
  물려 있다. 문서에만 적힌 규칙이 아님.
- **paths 스코프 룰** — 매칭 파일을 만질 때만 룰이 로드돼 컨텍스트가 가볍다.
- **자기개선** — `skill-evolve`/`agent-evolve` 가 실수에서 "Learned warnings" 를
  스킬/에이전트에 축적한다.
- **테스트됨** — 부트스트랩 스크립트는 bats 회귀 스위트, 문서는 지식그래프 링크 체커가
  게이트한다.

## 더 보기

| 문서 | 내용 |
|---|---|
| [docs/OPTIONS.md](docs/OPTIONS.md) | 전체 옵션 — 스택 프리셋 12종, `--forge`, `--harness`, `--lang`, 사용법, 치환 플레이스홀더, 요구사항 다지기 도구 선택 |
| [docs/INTERNALS.md](docs/INTERNALS.md) | 내부 구조 — 생성되는 `.claude/` 전체 트리, 주요 패턴 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 기여 가이드 |

## Contributing

워크플로는 [CONTRIBUTING.md](CONTRIBUTING.md), 스택 프리셋 규격은 [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) 참조.
처음이라면 [`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 라벨부터 — 새 스택 프리셋 추가가 구조가 정형화돼 있어 가장 만만하다.

## License

MIT — see [LICENSE](LICENSE). 서드파티 유래(스킬·문서)는 [CREDITS.md](CREDITS.md) 참조.
