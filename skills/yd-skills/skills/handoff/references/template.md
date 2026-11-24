# 핸드오프 템플릿

### 본문 — 스크래치 파일 → 이슈/코멘트 본문, 인프라 없으면 `HANDOFF.md`

````markdown
# HANDOFF — <한 줄 요약>

- 이슈: <URL>  (트래커가 없으면 "없음 — 이 파일이 원본")
- 작성: <YYYY-MM-DD HH:MM:SS.mmm>
- 작업 이슈/PR: #<N> · #<M> (<상태>)
- 브랜치: `<branch>`  ·  워크트리: `<path>` (없으면 "없음 — 새로 만들 것")
- HEAD: `<sha>` (<push 여부>)

## 지금 어디까지

<끝난 것 / 안 끝난 것을 사실로. "대체로 됨" 금지.>

## 검증 결과 (원문)

```
<테스트·빌드·게이트의 마지막 실행 결과 그대로. 안 돌렸으면 "안 돌림">
```

## 실행 중인 것

| 대상 | 주소 | 어떻게 띄웠나 |
| --- | --- | --- |
| <로컬 서버> | <http://127.0.0.1:포트> | <명령 + 실행 디렉터리> |
| <터널/프록시> | <127.0.0.1:포트> | <스크립트 경로, pid> |

## 미결 판단

<사람이 정해야 하는 것. 선택지와 각 선택의 결과까지.>

## 다음에 칠 명령

```bash
# 복붙 가능한 형태로, 실행 디렉터리 포함
cd <절대경로>
<command>
```

## 함정

<이번에 밟은 것. 도구·플랫폼 차이, 잘못 읽기 쉬운 신호 등.>

## 기계 판독용 상태

```yaml
schema_version: "1"
meta:
  written_at: "<YYYY-MM-DD HH:MM:SS.mmm>"
  location: "<작업 디렉터리 절대경로>"
  issue: "<이슈 URL 또는 없음>"
  branch: "<branch>"
  head: "<sha>"
  read_first: ["<먼저 읽을 파일>"]
state:
  <재개에 필요한 서비스·포트·리비전 — 프로젝트별 키>
last_verification:
  - check: "<무엇을 확인했나>"
    result: "<결과 원문, 안 돌렸으면 안 돌림>"
    verified_after_fix: false
next_steps:
  - id: "1"
    do: "<할 일>"
    check: "<대조할 명령>"
    needs_user_confirmation: false
open_decisions: []
cautions: []
```
````

### 예전 포인터 형식 — 읽기·삭제 판단용 (2026-10-06 부터 새로 만들지 않는다)

```markdown
# HANDOFF (포인터)

세션 인계 본문은 <트래커> 이슈에 있다. 이 파일은 그 위치만 가리킨다.

- 현재 핸드오프: <이슈 URL>
- 작성: <YYYY-MM-DD HH:MM:SS.mmm>
- 요약: <한 줄 — 무엇이 막혀 있고 뭘 기다리는지>
- 전체 목록: <handoff 라벨 이슈 목록 URL>
```
