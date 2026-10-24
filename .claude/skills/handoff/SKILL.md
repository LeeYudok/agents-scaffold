---
name: handoff
description: 세션을 끊고 다음 세션에 넘긴다 — 협업 인프라(GitHub·GitLab·Forgejo·Jira·Plane·Slack)가 있으면 재개 가능한 상태를 그 트래커 이슈 본문으로 남기고 이슈 URL 하나로 건넨다 — 이때 레포에 HANDOFF.md 를 만들지 않는다(포인터 파일도 두지 않는다). 트래커가 없는 폴더에서만 HANDOFF.md 자체에 전체 내용을 적어 그 파일로 끝낸다. 작업 이슈를 닫은 경계에서는 전용 이슈 대신 다음 작업 이슈에 코멘트 하나로 남긴다. 넘겨받은 쪽은 이슈 URL 이나 파일을 읽고 적힌 단언을 실제와 대조한 뒤 이어서 착수하고, 끝나면 결과를 남기고 닫는다. 컨텍스트가 40~50% 에 닿았을 때, "여기서 끊자 / 상태 남겨 / 이어받아 / 재개" 라고 하거나 핸드오프 URL·파일 경로를 붙여넣었을 때 쓴다.
---

# 세션 핸드오프

핸드오프는 **요약이 아니라 재개 가능한 상태**다. 다음 세션이 이것만 읽고 같은
자리에서 다음 명령을 칠 수 있어야 한다. "뭘 했는지" 보다 **"지금 어디에 서 있고
다음에 뭘 치는지"** 가 본체다.

컨텍스트 사용량이 40~50% 에 닿으면 하던 걸 멈추고 이 스킬을 부른다. compaction 은
모델이 뭘 버릴지 스스로 고르므로 안전망일 뿐이다.

## 어디에 남기나 — 상황당 한 곳

재개 상태를 **두 군데에 나눠 적지 않는다.** 나눠 적으면 어느 쪽도 혼자서는 재개
가능한 상태가 아니게 되고, 다음에 쓸 때 한쪽 내용이 조용히 빠진다(2026-09-21 실측,
이슈 #152 — 함정·기동 명령은 핸드오프 이슈에만, 새로 확정된 패턴은 다음 이슈
메모에만 있었다).

| 상황 | 남기는 곳 | 다음 세션이 받는 것 |
| --- | --- | --- |
| **이슈 도중** — 작업 이슈가 아직 열려 있다(컨텍스트 40~50% 등) | 전용 핸드오프 이슈(레포에 `HANDOFF.md` 는 만들지 않는다, 아래 "두 갈래") | 핸드오프 이슈 URL |
| **이슈 경계** — 작업 이슈를 닫았고 **다음 작업 이슈가 이미 있다** | **다음 작업 이슈에 코멘트 하나** (1-6) — 전용 핸드오프 이슈는 만들지 않는다 | 다음 작업 이슈 URL |
| 인프라 없음(트래커 없는 폴더) | `HANDOFF.md` | 파일 경로 |

이슈 경계인데 다음 작업 이슈가 아직 없으면 그 이슈를 먼저 만든다. 다음에 할 일이
정해지지 않았다면 경계가 아니라 그냥 끝난 것이므로 핸드오프를 쓰지 않는다.

## 두 갈래, 인프라 있으면 원본은 이슈

| | 하는 일 | `HANDOFF.md` | 다음 세션이 받는 것 |
| --- | --- | --- | --- |
| **인프라 있음** | 본문을 스크래치 파일에 쓰고 **그 내용으로 이슈/티켓/스레드를 만든다** | **만들지 않는다**(포인터 파일도 두지 않는다) | **전체 URL** |
| **인프라 없음** | `HANDOFF.md` 에 전체 내용을 쓴다 | **본문 그대로 = 원본** | **파일 경로** |

이슈 도중에 끊을 때 본문은 **항상** 만든다. 인프라가 있으면 그 본문은 이슈에
들어가고 레포에는 파일을 남기지 않는다 — 레포에 재개 상태를 평문으로 남기지
않고, 다음 세션은 사용자가 붙여넣는 이슈 URL 하나(또는 `handoff` 라벨 이슈 목록)로
어디로 가야 하는지 안다. 인프라가 없으면 갈 곳이 없으므로 본문 자체가 `HANDOFF.md`
에 남는다(파일 모드) — 절차가 멈추지 않는다.

2026-10-06 전에는 인프라가 있어도 레포에 `HANDOFF.md` 를 남겼다.
거기엔 **포인터만**(이슈 URL·작성 시각·요약·목록 링크) 적었다. 이제는 만들지 않는다. 레포에 그런 포인터 파일이 남아 있으면 2-1 대로 읽고,
가리키는 이슈에 내용이 다 있는지 확인한 뒤 그 레포의 이슈·MR 로 파일을 지운다.

## `HANDOFF.yaml` — 기계 판독용 짝

본문은 사람이 읽기엔 좋지만, 다음 세션이 서비스 주소·리비전·검증 결과·다음 명령을 뽑아 쓰려면 매번
마크다운을 파싱해야 한다. 같은 상태를 키로 적은 `HANDOFF.yaml` 을 **본문과 함께** 쓴다.
둘은 같은 사실을 가리키므로 함께 갱신한다. 한쪽만 고치면 검사기(`--pair`)가 어긋남을 잡는다.

| 상황 | yaml 을 두는 곳 |
| --- | --- |
| 인프라 없음(파일 모드) | 레포 루트 `HANDOFF.yaml` — `HANDOFF.md` 옆 |
| 인프라 있음 | 이슈 본문 끝의 `## 기계 판독용 상태` 섹션 안 ```yaml 블록 하나. 레포에는 `HANDOFF.yaml` 을 만들지 않는다 |

인프라 있음에서 첨부 대신 본문 안에 두는 이유는, 트래커마다 첨부 지원이 달라(Jira·Plane·Slack) 첨부를
쓰면 원본이 둘로 갈라지기 때문이다. 본문 하나가 곧 원본이라는 원칙이 그대로 유지된다.

- 스키마는 아래 본문 템플릿의 `## 기계 판독용 상태` 가 원본이다. 프로젝트별 키는 `state` 밑에 더한다.
- 필수 키는 `schema_version`·`meta`·`state`·`last_verification`·`next_steps` 다.
- **날짜·시각·버전은 항상 따옴표로 감싼다.** 따옴표가 없으면 YAML 이 `2026-10-05` 를 날짜로, `1.10` 을 `1.1` 로, `yes` 를 불리언으로 조용히 바꾼다.
  소수는 키 이름에 `version`·`release`·`revision`·`tag` 가 들어간 값만 따옴표를 요구한다. 진짜 소수 값(`progress: 0.5`)은 그대로 쓴다.
- 목록은 블록 스타일(`- `)로 적는다. 같은 키를 두 번 쓰지 않는다. 검사기는 어휘 수준이라 한 줄 흐름 스타일 목록은 항목으로 세지 못하고, 파서는 중복 키의 마지막 값을 쓴다.
- `## 기계 판독용 상태` 섹션이 있으면 닫힌 ```yaml 블록이 있어야 한다. 본문 안 yaml 은 같은 본문의 `작성`·`브랜치`·`HEAD` 와 맞춰 본다.
- `next_steps` 항목마다 대조할 명령(`check`)을 적는다.
- 값에 시크릿을 넣지 않는다. 키 이름·경로까지만 적는다.
- 검사기는 어휘 수준(필수 키·형 변환 위험·탭)을 보고, PyYAML 이 있으면 실제로 파싱한다.

## 모드

| 호출 | 하는 일 |
| --- | --- |
| `/handoff` (인자 없음) | **작성** — 이슈 도중이면 인프라 있을 때 이슈만 만들고(레포 파일 없음), 인프라 없으면 `HANDOFF.md` 에 전체 내용; 이슈 경계면 다음 작업 이슈 코멘트 → URL 또는 파일 경로 출력 |
| `/handoff <URL · #N · 파일경로>` | **재개** — 내용을 읽고 단언을 검증한 뒤 이어서 착수 |
| `/handoff done` | **종료** — 결과를 남기고 닫는다(이슈) / 파일에 적는다(파일 모드) |

사용자가 URL 이나 `HANDOFF.md` 경로만 붙여넣어도(설명 없이) 재개 모드로 본다. 레포에 남은 예전 포인터 파일을 받았을 때도 같다.

---

## 0. 트래커 판별 (제일 먼저, 추측 금지)

**"이 레포는 GitLab 이니까" 같은 추정으로 명령을 고르지 않는다.** 아래를 순서대로
확인하고, 처음 성립하는 것을 쓴다.

```bash
# 1) 레포 문서가 트래커를 지정했는가 (가장 강한 신호)
grep -riE 'jira|plane|linear|이슈는|트래커' AGENTS.md CLAUDE.md README.md 2>/dev/null | head -5

# 2) git 포지
git remote get-url origin

# 3) 인증이 실제로 되는가 (설치돼 있다 ≠ 쓸 수 있다)
gh auth status 2>&1 | tail -2
glab auth status 2>&1 | tail -2

# 4) 포지 밖 트래커의 자격증명이 있는가 — 이름만 본다, 값은 출력하지 않는다
env | grep -oE '^(JIRA|PLANE|SLACK|LINEAR)_[A-Z_]+' | sort -u
```

MCP 도구 목록에 Jira·Plane·Slack 도구가 있으면 그쪽을 **CLI 보다 먼저** 쓴다
(자격증명을 셸로 꺼낼 일이 없다).

| 판별 결과 | 쓰는 것 | 프로젝트 지정 |
| --- | --- | --- |
| `github.com/<owner>/<repo>` | `gh` | `--repo <owner>/<repo>` |
| GitLab (self-hosted 포함) | `glab` | `projects/<owner>%2F<repo>` (슬래시는 `%2F`) |
| Forgejo / Gitea | `curl` + 토큰 | `/api/v1/repos/<owner>/<repo>/issues` |
| Jira | MCP 도구 또는 REST | `/rest/api/3/issue` · 프로젝트 키 필요 |
| Plane | MCP 도구 또는 REST | `/api/v1/workspaces/<ws>/projects/<id>/issues/` |
| Slack (티켓 없이 채널로 협업) | MCP 도구 또는 `curl` | 채널 ID · 스레드 permalink 가 URL |
| 아무것도 없음 | **파일 모드** | `HANDOFF.md` 경로가 곧 주소 |

**애매하면 파일 모드로 내려간다.** 잘못된 트래커에 이슈를 만드는 것보다,
파일 하나를 정확히 남기고 사용자에게 "트래커를 쓰려면 알려달라" 고 하는 게 낫다.
권한이 없어 이슈 생성이 실패한 경우도 마찬가지 — 실패를 삼키지 말고 파일 모드로
끝낸 뒤 **실패 사실과 원인을 한 줄로 알린다**.

---

## 1. 작성

### 1-1. 상태를 모은다 (추측 금지, 전부 실측)

```bash
git branch --show-current && git status --short
git log --oneline -5
git worktree list

# 열린 작업 — 트래커에 맞는 것만
gh pr list && gh issue list --label handoff --state open      # GitHub
glab mr list -P 10 && glab issue list --label handoff -P 5    # GitLab

# 띄워 둔 로컬 서버 — 포트는 이 레포 것으로 바꿔 적는다
lsof -nP -iTCP -sTCP:LISTEN | grep -E '<앱이름>|<포트>' || true
```

검증 게이트를 돌렸다면 **결과 원문**(통과/실패 줄)을 그대로 옮긴다. 안 돌렸으면
"안 돌림" 이라고 적는다 — 돌린 척이 제일 위험하다.

### 1-2. 본문을 스크래치 파일에 쓴다 (템플릿은 아래)

레포의 `HANDOFF.md` 에 바로 쓰지 않는다 — 인프라가 있으면 이 본문은 이슈로 가고
레포에는 아무 파일도 남기지 않기 때문이다. 세션 스크래치 디렉터리(또는 `/tmp`) 에 임시
파일로 아래 "본문 템플릿" 전 항목을 채워 쓴다.

인프라가 전혀 없을 때만(0번 판별 결과 "아무것도 없음") 이 본문을 그대로 레포
루트 `HANDOFF.md` 에 쓴다 — 이미 있으면 **덮어쓴다**. 핸드오프는 항상 "지금
상태" 한 장이고, 과거 이력은 트래커와 그 레포의 작업 로그 파일
(`CURRENT_TASK.md` 등)이 갖는다. 레포가 이 파일을 추적하지 않는다면
(`.gitignore`) 커밋 대신 **절대경로**를 알린다.

본문을 다 쓰면 **게시 전에 검사기를 돌린다.** `exit 0` 이어야 게시한다. 비워 둔 항목·남은
자리표시자·ISO 8601 시각·시크릿 모양을 잡고, 시크릿은 줄 번호만 알려 준다. `exit 2` 는 입력이나 git 을 쓸 수 없었다는 뜻이며 통과가 아니다.

```bash
python3 <스킬경로>/scripts/check_handoff.py <본문파일>.md
```

파일 모드의 `HANDOFF.yaml` 은 짝인 `HANDOFF.md` 와 함께 본다. 이슈 본문 안 yaml 블록은 위 본문 검사가
같이 본다.

```bash
python3 <스킬경로>/scripts/check_handoff.py HANDOFF.yaml --yaml --pair HANDOFF.md
```

### 1-3. 인프라가 있으면 이슈를 만든다

본문은 인라인 `--body "$(...)"` 나 `jq --arg` 말고 **파일 경유** — fenced code·표·
백슬래시가 들어가면 escape 가 깨지고, 큰 본문은 ARG_MAX 를 넘겨 빈 요청이 된다.
아래 `<본문파일>` 은 1-2 에서 쓴 스크래치 파일이다(레포의 `HANDOFF.md` 가 아니다).

```bash
# GitHub
gh issue create --title "핸드오프: <한 줄 요약> (<YYYY-MM-DD>)" \
  --label handoff --body-file <본문파일>.md

# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues" \
  -F "title=핸드오프: <한 줄 요약> (<YYYY-MM-DD>)" \
  -F "labels=handoff" \
  -F "description=@<본문파일>.md" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['iid'], d['web_url'])"

# Forgejo / Gitea — payload 를 파일로 만든 뒤 넘긴다(본문에 백틱·표가 들어가므로)
python3 -c "
import json;json.dump({'title':'핸드오프: <요약>','body':open('<본문파일>.md').read()}, open('payload.json','w'))"
curl -s -X POST "$FORGEJO_URL/api/v1/repos/<owner>/<repo>/issues" \
  -H "Authorization: token $FORGEJO_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['number'], d['html_url'])"
```

**Jira / Plane / Slack 은 MCP 도구가 있으면 그것을 쓴다.** 없을 때만 REST:

```bash
# Jira — description 은 ADF 가 기본이지만 대부분 wiki/plain 도 받는다. 프로젝트 키 필수.
curl -s -X POST "$JIRA_URL/rest/api/3/issue" \
  -H "Authorization: Bearer $JIRA_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['key'])"
# → URL 은 $JIRA_URL/browse/<KEY>

# Plane
curl -s -X POST "$PLANE_URL/api/v1/workspaces/$PLANE_WS/projects/$PLANE_PROJECT/issues/" \
  -H "X-API-Key: $PLANE_TOKEN" -H 'Content-Type: application/json' \
  --data-binary @payload.json \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['id'], d.get('sequence_id'))"

# Slack — 티켓 대신 채널 스레드로 협업하는 팀. 본문이 길면 스니펫 업로드가 낫다.
#   메시지 1건 → permalink 를 URL 로 쓴다 (chat.getPermalink).
```

payload 는 셸에 인라인하지 말고 **파일로 만든 뒤 `--data-binary @`** 로 넘긴다
(위 두 명령의 `payload.json`). 토큰은 같은 줄에서 변수로만 쓰고 `-v`/`--trace` 를
붙이지 않는다 — verbose 메타라인이 마스킹을 우회한다.

`handoff` 라벨(또는 그에 해당하는 Jira/Plane 라벨)이 없으면 먼저 만든다. 라벨이
있어야 다음 세션이 "열린 핸드오프" 를 한 번에 찾는다.

### 1-4. 레포에는 파일을 남기지 않는다 (파일 모드만 커밋)

인프라가 있으면 레포에 `HANDOFF.md` 를 만들지 않는다 — 포인터 파일도 두지 않는다.
재개 상태는 1-3 의 이슈에만 있고, 다음 세션은 그 URL 이나 `handoff` 라벨 이슈 목록으로
찾는다. 레포에 작업 로그 파일(`CURRENT_TASK.md` 등)이 원래 있으면 맨 위에 이슈 URL 한
줄을 남기는 것은 괜찮다(그 파일의 원래 용도 안에서).

레포에 예전 포인터 `HANDOFF.md` 가 남아 있으면 스크래치 파일의 본문을 옮기지 않는다 —
가리키는 이슈에 내용이 다 있는지 확인한 뒤 그 레포의 이슈·MR 로 파일을 지운다. 지우기
전에 상태를 볼 때는 `python3 <스킬경로>/scripts/check_handoff.py HANDOFF.md --as-file` 를 쓴다.
트래커 이슈가 있는데 `HANDOFF.md` 에 본문이 남아 있으면 이 검사가 실패한다.

파일 모드(인프라 없음)면 1-2 에서 이미 전체 본문을 `HANDOFF.md` 에 썼다. 파일 맨 위에
"트래커 없음 — 이 파일이 원본" 이라고 적는다. 그 폴더가 git 이면 커밋한다.

```bash
git add HANDOFF.md && git commit -m "docs: 세션 핸드오프 (파일 모드)"
```

브랜치에 커밋 중이면 **푸시까지** 한다 — 새 세션이 다른 워크트리에서 이어받을 수 있어야 한다.

### 1-5. 사용자에게는 한 줄

인프라가 있으면 **전체 URL**, 없으면 **파일 절대경로**. `/clear` 후 그것만
붙여넣으면 이어진다고 알린다. 파일 모드였다면 "트래커를 붙이면 다음부터 이슈로
만든다" 도 한 줄 덧붙인다.

### 1-6. 이슈 경계 — 다음 작업 이슈에 코멘트 하나

작업 이슈를 닫은 직후라면 1-2~1-4 대신 이 절차를 밟는다. 상태 수집(1-1)과 사용자
안내(1-5)는 같다.

1. **직전 핸드오프·착수 메모를 다시 읽는다.** 방금 닫은 작업 이슈의 코멘트, 그 세션이
   이어받았던 핸드오프 이슈·`HANDOFF.md` 가 대상이다. 항목마다 **유효 / 소멸**을
   가른다 — 함정·검증 환경 기동 명령·미결 판단은 대부분 다음 이슈에서도 유효하다.
2. **템플릿 전 항목을 채운 코멘트 본문을 파일로 쓴다**(아래 "본문 템플릿" 그대로,
   제목만 `## 착수 메모 — <YYYY-MM-DD>`). 유효한 항목은 **옮겨 적는다.** "이전 이슈·MR 을
   본다" 로 떠넘기지 않는다 — 링크는 출처 표시일 뿐 내용을 대신하지 못한다. 이번
   세션에서 새로 확정된 것과 물려받은 것을 구분해 적으면 다음 경계에서 다시 가르기 쉽다.
3. **자기완결 점검.** 게시 전에 묻는다: 이 코멘트 밖의 다른 이슈·MR 을 열어야만 알 수
   있는 것이 있는가? 있으면 옮겨 적는다. 다음 작업 이슈 **본문**에 이미 있는 것(범위·
   설계·검증 기준)은 되풀이하지 않는다 — 본문과 코멘트를 합쳐 한 장이면 된다.
4. **코멘트 하나로 게시한다**(본문은 파일 경유 — 1-3 과 같은 이유).

```bash
# GitHub
gh issue comment <다음 N> --body-file <메모파일>.md
# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues/<다음 N>/notes" -F "body=@<메모파일>.md"
# Jira / Plane / Slack — MCP 도구로 해당 티켓·스레드에 댓글
```

게시한 뒤 빠진 것을 발견하면 코멘트를 **하나 더 달지 말고 그 코멘트를 고친다** —
읽을 곳이 둘이 되는 순간 같은 문제가 다시 생긴다. 이 세션이 이어받았던 핸드오프
이슈가 열려 있으면 3장대로 닫고, 닫는 코멘트에 다음 작업 이슈 URL 을 적는다.

`HANDOFF.md` 는 이 갈래에서 쓰지 않는다. 레포에 예전 포인터가 남아 있으면 덧쓰지
말고 1-4 대로 지운다 — 낡은 파일은 최신으로 오해된다.

---

## 2. 재개

### 2-1. 내용을 읽는다

인프라가 있으면 사용자가 준 **이슈 URL** 을 연다(없으면 `handoff` 라벨 이슈 목록에서
열린 것을 찾는다). 레포에 예전 포인터 `HANDOFF.md` 가 있으면 적힌 이슈 URL 만 얻고
파일 자체를 재개 상태로 쓰지 않는다 — 다 읽은 뒤 1-4 대로 지운다. 인프라가 없으면
파일 자체가 본문 전체다.

```bash
cat HANDOFF.md   # 파일 모드: 이 파일이 본문 전체 (인프라 있는 레포의 예전 포인터면 이슈 URL 만 얻는다)

# GitHub
gh issue view <N> --comments
# GitLab
glab issue view <N>
glab api "projects/<owner>%2F<repo>/issues/<N>/notes" | python3 -c "
import json,sys
for n in json.load(sys.stdin): print('---', n['author']['username'], n['created_at']); print(n['body'])"   # 자르지 않는다 — 다음에 칠 명령·함정은 대개 뒤쪽에 있다
# Jira / Plane / Slack — MCP 도구로 본문과 댓글/스레드 답글을 함께 읽는다
```

**코멘트가 본문보다 최신일 수 있다** — 이슈 모드면 항상 둘 다 읽는다. 받은 URL 이
핸드오프 이슈가 아니라 **작업 이슈**여도 절차는 같다(이슈 경계 갈래로 넘겨받은 경우):
본문이 범위·검증 기준이고 착수 메모 코멘트가 재개 상태다. 파일 모드는
파일 하나가 전부이지만, 그만큼 **git log 로 언제 갱신됐는지**를 같이 본다
(`git log -1 --format='%ci' -- HANDOFF.md`).

yaml 짝이 있으면 먼저 읽는다 — 파일 모드는 `HANDOFF.yaml`, 인프라 있음은 본문 끝 `## 기계 판독용 상태`
블록이다. yaml 이 없는 옛 핸드오프(md only)는 그대로 읽는다.

### 2-2. 단언을 검증한다 (본문도 decay 한다)

yaml 이 있으면 `next_steps[0].check` 와 `meta.branch`·`meta.head` 를 아래 표처럼 실제와 대조하고,
어긋나면 보고한 뒤 착수한다.

적힌 것 중 **행동을 바꾸는 단언 1~2개**는 실제와 대조한 뒤 움직인다. 실전에서
"열려 있다" 던 PR 이 이미 머지돼 있던 적이 있다.

| 적혀 있는 것 | 확인 |
| --- | --- |
| 브랜치/워크트리 | `git worktree list`, `git branch -a --contains <sha>` |
| PR/MR 상태 | `gh pr view <N>` / `glab mr view <N>` — 이미 머지됐을 수 있다 |
| 이슈/티켓 상태 | `gh issue view <N>` / `glab issue view <N>` / Jira·Plane 조회 — 이미 닫혔을 수 있다 |
| 띄워 둔 서버 | `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:<port>/` |
| 배포된 버전 | 서비스의 `/version`·`/healthz` 를 직접 친다 |
| 다음 명령 | 경로·스크립트가 아직 있는지 (`ls`, `git show --stat`) |

브랜치와 HEAD 단언은 검사기가 읽기 전용으로 대조한다. 본문(또는 파일 모드의 `HANDOFF.md`)을
파일로 저장해 돌린다. 기록한 HEAD 보다 브랜치가 앞서 있으면 경고, 기록한 HEAD 가 브랜치의
조상이 아니면 위반이다.

```bash
python3 <스킬경로>/scripts/check_handoff.py <본문파일>.md --verify-git <레포 경로>
```

충돌하면 **실제 상태를 믿고** 이슈에 코멘트로(파일 모드면 파일에) 교정한다.

### 2-3. 이어서 착수

- 워크트리가 남아 있으면 그 안에서, 없으면 `git worktree add ../<repo>-<n> <branch>`.
- 정식 클론에서는 `checkout`/`switch` 금지(pull·읽기만) — 다른 세션의 발밑이 바뀐다.
- 핸드오프는 **작업 이슈가 아니다** — 실제 작업 이슈 번호가 적혀 있으면 그걸
  브랜치/커밋/PR 에 박는다. 핸드오프는 세션 사이를 잇는 표식일 뿐이다.

---

## 3. 종료

이어받은 작업이 끝나면(또 다른 핸드오프를 쓰는 경우 포함) 핸드오프를 닫는다.

```bash
# GitHub
gh issue comment <N> --body-file <결과파일>.md && gh issue close <N>
# GitLab
glab api --method POST "projects/<owner>%2F<repo>/issues/<N>/notes" -F "body=@<결과파일>.md"
glab issue close <N>
# Jira / Plane — MCP 도구로 댓글 + 상태를 Done/Completed 로
# Slack — 같은 스레드에 결과를 답글로 달고 해결 이모지 등 팀 규약을 따른다
```

파일 모드면 `HANDOFF.md` 맨 위에 **`# 종료 — <날짜>`** 와 결과를 적고 커밋한다.
다음 핸드오프를 쓰는 경우라면 그 파일을 새 내용으로 덮어쓰는 것이 종료다.

이슈 경계 갈래로 받은 세션은 닫을 핸드오프 이슈가 없다 — 작업 이슈의 통상 종료(결과
코멘트 + 클로즈)가 곧 종료이고, 다음 작업이 이어지면 1-6 으로 그 이슈에 메모를 남긴다.

닫을 때 한 줄: 무엇이 끝났고, 다음 핸드오프가 있으면 그 URL/경로.
열린 핸드오프가 둘 이상 쌓이면 어느 게 최신인지 모른다 — **동시에 하나만** 연다.

---

## 템플릿

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

---

## doksam GitLab 에서 쓸 때

doksam self-hosted GitLab 은 에이전트마다 계정이 따로 있다. 핸드오프 이슈·코멘트는
**자기 계정**으로 남긴다. 토큰은 `~/workspace/.env.toml` 의 자기 섹션을 쓰는 명령과
같은 줄에서만 읽고, 따로 출력하지 않는다.

| 에이전트 | 섹션 |
|---|---|
| Claude Code | `gitlab_claude_ai` |
| Codex | `gitlab_codex_ai` |
| Antigravity | `gitlab_agy_ai` |

```bash
export GITLAB_TOKEN=$(python3 -c 'import tomllib,os;print(tomllib.load(open(os.path.expanduser("~/workspace/.env.toml"),"rb"))["gitlab_claude_ai"]["token"])')
glab api -X POST "projects/<ns>%2F<repo>/labels" -f name=handoff -f color='#6699cc' >/dev/null 2>&1   # 라벨이 없으면 만든다
```

- `glab issue create -R <ns>/<repo>` 는 404 가 날 수 있다. 레포 폴더 안에서 `-R` 없이 실행한다.
- 시각은 `YYYY-MM-DD HH:MM:SS.mmm`(KST)로 적는다. ISO 8601 의 `T`·`+09:00` 은 쓰지 않는다.
- 핸드오프를 쓰기 전에 메모리에 남길 사실은 레포 메모리에 먼저 반영하고 푸시한다. 이슈 본문은 decay 하지만 메모리는 다음 세션이 자동으로 읽는다.
- 이어받은 쪽은 이슈에 `재개: <에이전트>` 코멘트를 먼저 남긴다. 두 에이전트가 같은 핸드오프를 동시에 집는 것을 막는다.

---

## 원칙

- **인프라 있으면 원본은 이슈이고 레포에는 `HANDOFF.md` 를 만들지 않는다. 인프라 없으면 원본은 파일**.
  트래커가 없거나 실패해도 핸드오프는 완성된다.
- **상황당 한 곳**. 이슈 도중이면 핸드오프 이슈, 이슈 경계면 다음 작업 이슈의 코멘트
  하나. 둘 다 쓰지 않고, 어느 쪽이든 그것만 읽고 시작할 수 있어야 한다.
- **yaml 은 본문의 짝이다**. 같은 사실을 키로 적고 함께 갱신한다. 인프라가 있으면 이슈 본문 안에, 없으면 `HANDOFF.md` 옆에 둔다.
- **사실만**. 날짜·이슈번호·수치는 실측으로 채우고, 모르면 "모름" 이라고 쓴다.
- **명령은 복붙 가능하게**. 실행 디렉터리 포함, 상대경로 금지.
- **큰 tool output 은 붙여넣지 않는다** — 파일로 남기고 경로와 마지막 몇 줄만.
- 본문에 `.env` 값·토큰·비밀번호를 넣지 않는다. 키 **이름**까지만. 트래커가 공개
  채널이면 내부 호스트명·경로도 한 번 더 걸러 본다.
- 한 세션 = 한 작업 이슈. 핸드오프는 그 경계를 넘기는 장치지, 한 세션을 늘리는 장치가 아니다.

## Learned warnings

- (2026-10-06) 트래커가 있는 레포에 `HANDOFF.md` 포인터를 커밋하지 않는다. 사용자 지시는 "HANDOFF.md 는 삭제해 깃없을때만 이용이라" 였다. 그래서 jbb/ews#250 에서 루트·`newtech/` 의 파일을 지웠다. 인계는 핸드오프 이슈 URL 이나 다음 작업 이슈 코멘트로 한다. 파일은 트래커 없는 폴더에서만 쓴다 (#217).
