# A2A/ACP 운영 계약 (a2a-acp-bridge)

이 문서는 `yd-a2a-orchestrator` 가 지휘할 때 따르는 `a2a-acp-bridge` 의 실제 동작 계약을 적는다.
원본은 브리지 레포의 `README.md`(절 번호로 인용)와 `AGENTS.md` 이며, 여기에는 지휘자가 매번
확인해야 하는 사실만 추린다. 브리지 바이너리·레포가 바뀌면 원본을 먼저 본다.

레포: `/Users/dok123/workspace/github.com/LeeYudok/a2a-acp-bridge` (Go 1.22 표준 라이브러리만).
빌드: `go build -o ~/.local/bin/a2a-acp-bridge ./cmd/a2a-acp-bridge`.

## 1. 지휘권 리스 (coord.json)

여러 에이전트가 동시에 지휘하면 서로의 작업을 덮어쓴다. 그래서 `coord.json` 에 **단일 지휘권
리스**를 두고, 모든 변경은 `coord.json.lock` flock 아래 `expected_term` 을 비교(CAS)한 뒤에만
반영한다. 보드(`a2a_board.json`)와 리스(`coord.json`)는 서로 다른 flock 을 쓴다.

MCP 도구 `a2a_coordinator_lease`, CLI `a2a-acp-bridge coord` 로 조회·선점·갱신·이양한다.

- `status`: 리스와 `vacant`·`active`·`expired`·`handed_off` 중 하나를 돌려준다. 리스가 없으면
  `coordinator: null`, `status: "vacant"` 다.
- `claim`: `expected_term` 이 현재 term 과 같을 때만 `term + 1` 로 선점한다. 활성 리스를 만료
  전에 가져오려면 `force` 와 `reason` 이 함께 필요하다.
- `renew`: 현재 지휘자만 `ttl_seconds`(CLI `-ttl`, 기본 60분)만큼 연장한다.
- `handoff`: 현재 지휘자가 `to_agent` 에게 넘긴다. `to_agent` 를 비우면 누구나 claim 하는 개방
  이양이 된다.
- 변경에는 식별된 `agent_id` 가 필요하다. `agent_id` 가 없거나 `user` 면 claim·renew·handoff 를
  거부한다. 실패 사유는 term 불일치, 활성 리스, 만료된 리스 갱신·이양, 개방 이양 재이양,
  지휘자 아님, 사유 없는 force, 잘못된 ID, 익명 변경자다.

CLI 예:

```sh
a2a-acp-bridge coord status
a2a-acp-bridge coord claim -agent codex -expected-term 6
a2a-acp-bridge coord renew -agent codex -ttl 60m
a2a-acp-bridge coord handoff -agent codex -to codex-glm
```

**지휘자가 멈추거나 리스가 만료되면 남은 에이전트가 이슈에 예고를 남기고 `term + 1` 로
이어받는다.** 복귀한 전임 지휘자는 최신 `term` 을 인정하고 일반 작업자·리뷰어로 합류한다.

## 2. 에이전트 풀과 발신자

에이전트 정의는 `~/.local/share/a2a-acp-bridge/agents.json`(`A2A_AGENTS_FILE`)에 있고, 내장
3종(`agy`·`codex`·`claude`)에 동적 에이전트가 더해진다. 같은 ID 면 내장 카드를 덮어쓴다.
`agents.json` 을 읽지 못하면 내장 3종으로 계속 동작하고 `registry_warnings` 에 오류를 남긴다.

풀은 지금 새 작업을 받을 수 있는 에이전트의 목록이다. 작업을 맡길 때 풀에서 에이전트를 꺼내
그 작업에 묶고, 작업이 끝나면 풀에 되돌려놓는다.

- **작업을 끝낸 에이전트는 MR/push 반영을 확인한 뒤 풀(`pool`)에 반환한다.** 반영 확인은 완료
  검증 명령(`checks`)의 하나로 남긴다(예: `gh pr view <n> --json state,mergeCommit`).
  완료 작업의 `checks`에 MR/push 반영 확인 명령이 없으면 `check_task_dag.py` 가 위반으로 판정한다.
- **아직 끝나지 않은 작업(todo·working·blocked)을 쥔 에이전트는 풀(`pool`)에 있으면 안 된다.**
- **작업 DAG 에는 풀(`pool`) 목록이 있어야 한다.** 지금 새 작업을 받을 수 있는 에이전트 ID 만 넣는다.
- **풀(`pool`)의 에이전트 ID 는 중복되면 안 된다.**
- 실패·타임아웃·할당량 초과로 끝난 작업의 에이전트도 실패를 기록한 뒤 곧바로 풀에 반환한다.
- **동시에 도는 작업(todo·working·blocked)끼리는 같은 저장소 안에서 워크트리나 브랜치가 겹치면
  안 된다.** 각 작업 레코드에는 `repo`·`branch`·`worktree`를 빈 값 없이 적는다.
- **각 작업은 `attempts`(시도 횟수, 최초 1회부터)를 적는다.** 최초 시도가 1이고 재배정은 최대
  3회이므로 `attempts`는 1~4다.

발신자는 `from_agent`(CLI `-from`) → 환경변수 `A2A_AGENT_ID` → MCP `clientInfo.name` 추정 →
`user` 순으로 정한다. **발신자를 밝혀 위임하면 응답(`reply`)이 그 발신자의 수신함으로 돌아온다.**

동적 에이전트 ID(`codex-glm`·`codex-deepseek` 등)는 `agents.json` 발견·보드 메시지·수신함에는
참여하지만, MCP/CLI 위임 도구가 그 ID를 직접 실행 대상으로 받는 것은 아니다. 현재 위임 도구는
`agy`·`codex`·`claude` 세 런타임 경로를 제공한다. 동적 Codex 래퍼를 실제로 실행하려면 CLI에서
`A2A_CODEX_COMMAND=codex-deepseek ask-codex ...` 처럼 명령을 재정의한다. 이 호출의 결과는
`agent: codex` 로 반환되므로, 작업 DAG와 검증 증거에는 반환된 `codex`와 실제 래퍼
`codex-deepseek`를 구분해 기록한다.

## 3. 위임 도구와 권한 모드

| 도구 | CLI | 런타임 | 기본 권한 |
| :--- | :--- | :--- | :--- |
| `acp_delegate_to_agy` | `ask-agy` | `agy acp` 상주 세션 풀 | `-mode auto` (상주, `session/cancel`·`set_mode`·`set_model`) |
| `a2a_delegate_to_codex` | `ask-codex` | `codex exec --json` | 새 실행 `workspace-write`, 재개 `read-only` |
| `a2a_delegate_to_claude` | `ask-claude` | `claude -p --output-format json` | `plan`(읽기 전용) |

**읽기 전용 리뷰는 샌드박스/권한을 최소로 준다** — Codex `read-only`, Claude `plan`.
**파일 수정을 맡길 때만 `workspace-write`·`acceptEdits` 를 명시한다.**

- `cwd` 를 주지 않고 `-s` 로 명명 세션을 이어가면 그 세션을 만든 디렉터리에서 실행한다.
  Claude Code·ACP 세션은 프로젝트 디렉터리에 묶여 있어 다른 디렉터리에서는 이어지지 않는다.
  **저장소를 지정하려면 `cwd` 를 그 작업의 워크트리로 준다.**
- `-no-wait`(`async: true`)는 태스크를 `working` 으로 두고 즉시 `task_id` 를 돌려준다. 끝나면
  `reply` 와 `completed` 가 기록된다. CLI 는 백그라운드 작업이 끝날 때까지 종료하지 않는다.
- 호출자와 대상 Codex 의 `CODEX_HOME` 이 다르면 `A2A_CODEX_HOME` 으로 대상 홈을 지정한다.
- Claude Code 위임은 호출마다 비용이 든다. 응답의 `cost_usd` 로 확인한다.

## 4. 공유 보드·수신함·태스크 상태

보드는 태스크·메시지·명명 세션을 `a2a_board.json` 에 저장한다. 파일별 flock + `os.CreateTemp` →
`os.Rename` 원자 교체(권한 `0600`)로 직렬화한다.

- 위임 한 번은 `delegate` 메시지와 `task_id` 를 만든다. 동기 호출은 끝나면 `reply` 를 발신자
  수신함에 남기고 태스크를 `completed`/`failed` 로 바꾼다.
- `a2a_task_status`(CLI `task_status`)로 태스크 상태를 확인한다.
- `a2a_receive_messages`(CLI `inbox <id>`)로 수신함을 읽는다. 기본은 안 읽은 메시지 최대 20건을
  읽음 처리한다. 남의 수신함을 확인만 할 때는 `-peek` 을 쓴다.
- `send`(MCP `a2a_send_message`)의 `intent` 는 `delegate`·`review`·`reply`·`chat`·`sync` 다.
- `watch` 는 보드를 폴링해 새 메시지·읽음·태스크 상태·지휘권 리스 변화를 JSON 이벤트로 출력하고
  저장소를 바꾸지 않는다.

**보드 메시지에 답이 없으면 한 번 다시 묻고, 그 뒤에는 이슈 기록을 기준으로 이어받는다.**

## 5. 모니터와 A2A HTTP

`a2a-acp-bridge serve-a2a -addr 127.0.0.1:8765` 로 HTTP 서버를 띄운다. 기본 주소를 바꾸지 않는다
(인증이 없고 위임 도구가 로컬 에이전트를 실행한다).

- `GET /monitor/snapshot`: 콘솔용 읽기 전용 스냅샷. 에이전트 상태·최근 태스크·명명 세션·지휘권
  리스만 돌려주고 본문·`cwd`·실제 세션 ID 는 넣지 않는다. `working` 태스크가 5분 넘게 갱신되지
  않으면 `stale` 로 표시한다.
- 콘솔: `https://console.doksam.com/a2a`.
- `POST /a2a` JSON-RPC `method` 매핑: `acp/agy`·`acp/control`·`a2a/codex`·`a2a/claude`·
  `tasks/send`·`tasks/get`.

## 6. 실패 재배정과 핸드오프

에이전트가 오류·타임아웃·할당량 초과로 끝나면 같은 작업을 다른 에이전트에 다시 맡긴다.

- **실패 재배정은 같은 작업에서 최대 3회까지다.** 같은 실패가 반복되면 규칙을 무력화하지 말고
  원인과 필요한 결정을 사용자에게 보고하고 멈춘다.
- 담당이 멈추면 이슈에 핸드오프(`owner:*` 를 떼고 `handoff` 라벨)를 남기고, 이어받는 에이전트는
  원담당의 브랜치·워크트리 위에서 계속한다 — 새 브랜치·새 PR 을 따로 만들지 않는다.

## 7. 저장소 파일과 환경변수

| 환경변수 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `A2A_BRIDGE_STORE` | `~/.local/share/a2a-acp-bridge/a2a_board.json` | 보드 저장소. 리스는 같은 디렉터리 `coord.json` |
| `A2A_AGENTS_FILE` | `~/.local/share/a2a-acp-bridge/agents.json` | 동적 에이전트 정의 |
| `A2A_AGENT_ID` | (없음) | 이 프로세스의 발신자 ID |
| `A2A_CODEX_HOME` | (없음) | 자식 Codex 에만 적용할 `CODEX_HOME` |
| `A2A_ACP_COMMAND` | `agy acp --dangerously-skip-permissions` | ACP 워커 명령 재정의 |
| `A2A_CODEX_COMMAND` | `codex` | Codex 위임 명령 재정의 |
| `A2A_CLAUDE_COMMAND` | `claude` | Claude Code 위임 명령 재정의 |
