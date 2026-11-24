---
name: yd-agents-yaml
description: 저장소의 에이전트 지침을 사람용 AGENTS.md + 기계 판독용 AGENTS.yaml + 검증기 scripts/check-agents-yaml.sh 세 파일로 세팅하거나 갱신한다. AGENTS.yaml 이 없는 저장소에서 작업을 시작할 때, 구성요소·포트·경로·명령·환경변수가 바뀌어 AGENTS.yaml 을 고쳐야 할 때, "AGENTS.yaml 만들어줘 / ews 처럼 세팅해줘 / 에이전트 지침 정리해줘" 요청에 사용한다.
---

# yd-agents-yaml

에이전트가 저장소를 파악하는 데 드는 탐색을 줄이려고, 저장소의 구조적 사실을
**`AGENTS.yaml`** 한 파일에 모은다. 사람이 읽는 규칙과 배경은 `AGENTS.md` 에 남기고,
`AGENTS.yaml` 은 구성요소 그래프·명령·시크릿 위치·정책 요약·알려진 함정처럼
**파싱해서 쓰는 사실**만 담는다. 검증기가 YAML 의 조용한 타입 변환과 부패한 경로를 잡는다.

| 파일 | 역할 |
|---|---|
| `AGENTS.md` | 사람용 지침(SoT). 맨 위에 AGENTS.yaml 안내 한 단락 |
| `AGENTS.yaml` | 기계 판독용 사실. 서술이 충돌하면 AGENTS.md 와 실제 코드가 이긴다 |
| `scripts/check-agents-yaml.sh` | 이 스킬의 `scripts/` 에서 **수정 없이** 복사 |

## 언제 쓰나

- AGENTS.yaml 이 없는 저장소에서 작업을 시작할 때 — 그 저장소 작업의 첫 chore 이슈로 세팅한다
- 구성요소·포트·경로·명령·환경변수가 바뀐 MR — 같은 MR 에서 AGENTS.yaml 도 고치고 검증기를 돌린다
- AGENTS.yaml 과 실제가 어긋난 걸 발견했을 때 — 실제(코드·파일시스템)를 확인해 둘 다 고친다

## 세팅 절차

1. **조사** — 아래를 실제로 확인한다. 추측으로 채우지 않는다.
   - 진입점·패키지 구조 (`ls`, 모듈 파일, 서브커맨드 분기)
   - 코드가 읽는 환경변수 **이름**: `grep -rhoE 'Getenv\("[A-Z0-9_]+"' --include='*.go'` / `os.environ` / `process.env` 등
   - 배포 단위(컨테이너·유닛·타이머·CI job)와 그 EnvironmentFile 경로
   - 외부 의존(DB·LLM·API·소켓)과 어느 코드가 부르는지
   - 시크릿 파일의 **키 이름만**: `grep -oE '^[A-Z_]+=' <file>` — 값이 출력되는 명령(`cat`, `env`, `inspect`)은 쓰지 않는다
   - 기존 메모리·README 의 함정(known issues)
2. **AGENTS.yaml 작성** — [`assets/AGENTS.yaml`](assets/AGENTS.yaml) 뼈대에서 시작한다. 섹션 규칙은 아래.
3. **검증기 설치** — `cp <skill>/scripts/check-agents-yaml.sh <repo>/scripts/ && chmod +x`. 저장소에 맞게 고치지 않는다(아래 "확장").
4. **AGENTS.md 연결** — 맨 위에 다음 단락을 넣는다.
   > **기계 판독용 정보는 `AGENTS.yaml`** — 구성요소 그래프(`nodes`/`edges`), `commands`, `secret_files`(경로·키 이름만), `policies`, `known_issues` 등. 작업 전 이 파일을 먼저 읽고, 구성요소·경로·명령·환경변수가 바뀌면 이 문서와 **함께** 갱신한다. 두 파일이 어긋나면 실제 코드·파일시스템을 확인해 둘 다 고친다. 고친 뒤엔 `scripts/check-agents-yaml.sh` 로 검증한다. 날짜·버전 값은 항상 따옴표로 감싼다.
5. **검증** — `scripts/check-agents-yaml.sh` 가 `[OK]` 인지, 그리고 일부러 망가뜨린 사본(따옴표 뺀 날짜, 없는 노드로 가는 엣지, 없는 경로)을 잡는지 한 번 확인한다.
6. 이슈 → 브랜치 → MR 로 올린다. `AGENTS.yaml`, 검증기, `AGENTS.md` 를 한 MR 에.

## 섹션 규칙

| 섹션 | 필수 | 내용 |
|---|---|---|
| `schema_version` | O | `'1.0'` (따옴표) |
| `meta` | O | 이름·설명·저장소/이슈 URL·브랜치 전략·`updated: 'YYYY-MM-DD'` |
| `nodes` | O | 구성요소. `id`(유일)·`type`·`label`·`path`(저장소 상대). 외부 의존도 노드로 둔다 |
| `edges` | O | `{from, to, rel}` + 해당 연결이 읽는 `env: [키 이름]` |
| `environments` | | local / prod / ci 실행 환경 |
| `ports` | | `{port: 정수, service, scope}` |
| `commands` | | 그룹별 실행 명령. 첫 토큰이 저장소 파일이면 검증기가 존재를 확인한다 |
| `secret_files` | | `{host, path, keys: [이름만], used_by}`. **값은 절대 넣지 않는다** |
| `env_keys` | | 컴포넌트별 코드가 읽는 환경변수 이름 |
| `policies` | | `{id, rule: 한 줄, source: 상세 문서 경로}` — 상세는 source 가 SoT |
| `known_issues` | | `{id, summary, source, files}` — 한 번 밟은 함정 |
| `docs` | | 문서 포인터 |
| `x-*` | | 저장소 고유 섹션 (예: `x-deliverables`, `x-catalog`) |

다른 레포에서 쓰는 `runtime_facts`·`verifications`·`corrections`·`procedures`·`secret_facts` 도 허용한다.

작성 규칙:
- 날짜·버전·해시는 **항상 따옴표**. `2026-09-24` 는 date, `1.10` 은 float `1.1` 로 조용히 바뀐다.
- 서술형 값(공백·괄호 포함)은 경로 검사에서 빠진다. 경로는 공백 없이 저장소 상대로 적는다.
- gitignore 된 경로(빌드 산출물, venv, 로컬 설치)는 존재하지 않아도 통과한다.
- 수치·키 이름은 실측값만. 실측 날짜를 note 에 남긴다 (`키 이름 실측 2026-09-24`).

## 확장: AGENTS.md 표를 YAML 에서 생성

모델 카탈로그처럼 표가 크고 자주 바뀌면, AGENTS.md 안의
`<!-- BEGIN GENERATED: <name> -->` ~ `<!-- END GENERATED: <name> -->` 구간을
스크립트가 AGENTS.yaml 에서 렌더링하게 하고, CI 에서 `--check` 로 드리프트를
막는다. 이때는 AGENTS.yaml 이 그 표의 SoT 가 된다. 표가 작으면 쓰지 않는다.

## 하지 않는 것

- 검증기를 저장소마다 고치지 않는다. 새 최상위 섹션은 `x-` 접두사로.
- AGENTS.md 의 서술을 AGENTS.yaml 에 복사하지 않는다. yaml 은 한 줄 요약 + `source` 포인터.
- 시크릿 값, 토큰, 개인 이메일을 넣지 않는다.
