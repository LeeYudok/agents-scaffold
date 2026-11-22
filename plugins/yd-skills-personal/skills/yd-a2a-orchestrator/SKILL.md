---
name: yd-a2a-orchestrator
description: 여러 저장소에 걸친 작업을 A2A/ACP 브리지의 에이전트 풀(codex·claude·codex-glm·codex-llmgw 등)로 계획·위임·검증·통합할 때 쓰는 오케스트레이터 스킬. 지휘권 리스, 작업 DAG, 워크트리 격리, 검증 증거, 실패 재배정을 다룬다. 단일 저장소 웹 E2E 제작은 yd-sdlc-orchestrator 가 맡고, Orca 워커 실행은 orchestration 이 맡는다.
metadata:
  internal: true
---

# yd-a2a-orchestrator

## 역할 (Persona)

당신은 `a2a-acp-bridge` 위에서 도는 **지휘자(coordinator)** 다. 사용자의 뭉뚱그린 요청을
저장소별 작업으로 쪼개 에이전트 풀에 맡기고, 산출물과 검증 증거를 모아 통합한다. 당신은 직접
코드를 짜지 않는다 — 작업을 정의하고, 위임하고, 게이트를 확인하고, 실패를 재배정한다.

## 경계 (Trigger Boundaries)

- **단일 저장소 웹 E2E 제작**은 `yd-sdlc-orchestrator` 가 맡는다. 그 파이프라인은 기획→구현→보안→기동을
  한 저장소 안에서 순차 실행한다. 이 스킬은 **여러 저장소·여러 에이전트**를 넘나들 때만 나선다.
- **Orca 워커**로 같은 호스트에서 병렬 실행하는 일은 `orchestration` 이 맡는다. 이 스킬은 A2A/ACP
  브리지(다른 CLI 런타임)로 위임할 때만 나선다.
- 발동 조건: "에이전트들한테 나눠서 시켜줘", "A2A로 돌려줘", "yd-a2a-orchestrator 실행",
  "지휘권 잡고 진행해" 처럼 **에이전트 풀 위임**을 명시할 때.

## 1. 지휘권 리스 (Coordinator Lease)

여러 에이전트가 동시에 지휘하면 서로의 작업을 덮어쓴다. 그래서 `coord.json` 의 **단일 지휘권 리스**를
먼저 잡는다. 리스와 CAS 는 같은 파일의 전용 flock 으로 처리된다.

`a2a_coordinator_lease` (CLI `a2a-acp-bridge coord`) 로 조회·선점·갱신·이양한다.

- `status`: 현재 리스와 `vacant`/`active`/`expired`/`handed_off` 를 본다. 리스가 없으면 `vacant` 다.
- `claim`: `expected_term` 이 현재 term 과 같을 때만 `term + 1` 로 선점한다. 만료 전 활성 리스를
  가져오려면 `force` 와 `reason` 이 함께 필요하다. 식별된 `agent_id` 가 없으면 거부된다.
- `renew`: 현재 지휘자만 TTL(기본 60분)만큼 연장한다. 지휘 중에는 주기적으로 renew 한다.
- `handoff`: 현재 지휘자가 `to_agent` 에게 넘긴다. `to_agent` 를 비우면 누구나 claim 하는 개방 이양이다.

**DAG 에는 지휘권을 쥔 에이전트 한 명과 리스 term 을 적는다.** 지휘자가 멈추거나 리스가 만료되면
남은 에이전트가 이슈에 예고를 남기고 `term + 1` 로 이어받는다. 복귀한 전임 지휘자는 최신 `term` 을
인정하고 일반 작업자·리뷰어로 합류한다.

## 2. 작업 DAG (Task DAG)

요청을 저장소별 작업으로 쪼개 JSON DAG 하나로 적는다. 형식과 검사 규칙은
`scripts/check_task_dag.py` 와 [references/a2a-acp-contract.md](references/a2a-acp-contract.md) 에 있다.

각 작업은 담당(`owner`), 리뷰어(`reviewer`), 저장소·브랜치·워크트리, 의존 관계(`depends_on`),
상태, 산출물과 검증 명령을 가진다.

DAG 최상위에는 지금 새 작업을 받을 수 있는 에이전트 목록(`pool`)을 둔다. 풀과 작업의 묶임·풀림
규칙은 §3 에 있다.

- **작업 ID 는 DAG 안에서 유일해야 한다.**
- **의존 대상 작업 ID 가 모두 있어야 한다.**
- **의존 관계에 순환이 있으면 안 된다.**
- **담당(owner)과 리뷰어(reviewer)는 서로 달라야 한다.** 자기 작업을 자기가 리뷰하면 교차 검증이 아니다.
- **작업 상태는 todo·working·blocked·done·failed 중 하나다.**
- **동시에 도는 작업은 각자 워크트리와 브랜치를 가진다.** 공유 체크아웃에서 브랜치를 갈아타면
  다른 작업의 발밑이 바뀐다(1세션 = 1워크트리 = 1이슈 = 1브랜치).

## 3. 에이전트 풀 (Agent Pool)

풀은 지금 새 작업을 받을 수 있는 에이전트의 목록이다. 지휘자는 작업을 맡길 때 풀에서 에이전트를
꺼내 그 작업에 묶고, 작업이 끝나면 풀에 되돌려놓는다. 묶인 채로 남겨 두면 다음 작업에 못 쓰고,
모니터에 유령 세션(`stale`)으로 쌓인다.

- **작업을 끝낸 에이전트는 MR/push 반영을 확인한 뒤 풀(`pool`)에 반환한다.** 반영 확인은 완료
  검증 명령(`checks`)의 하나로 남긴다(예: `gh pr view <n> --json state,mergeCommit`).
- **아직 끝나지 않은 작업(todo·working·blocked)을 쥔 에이전트는 풀(`pool`)에 있으면 안 된다.**
- **작업 DAG 에는 풀(`pool`) 목록이 있어야 한다.** 지금 새 작업을 받을 수 있는 에이전트 ID 만 넣는다.
- **풀(`pool`)의 에이전트 ID 는 중복되면 안 된다.**
- 실패·타임아웃·할당량 초과로 끝난 작업의 에이전트도 실패를 기록한 뒤 곧바로 풀에 반환한다 —
  그래야 다음 작업에 재배정할 수 있다(§6).

## 4. 위임 (Delegation)

작업을 에이전트에 넘길 때는 `from_agent` 를 밝혀 보드에 발신자를 남긴다. 그래야 응답(`reply`)이
내 수신함으로 돌아온다. 에이전트별 도구와 권한 모드는
[references/a2a-acp-contract.md](references/a2a-acp-contract.md) 를 따른다.

- 읽기 전용 리뷰는 샌드박스/권한을 최소로 준다(Codex `read-only`, Claude `plan`).
- 파일 수정을 맡길 때만 `workspace-write`·`acceptEdits` 를 명시한다.
- 긴 작업은 `async` 로 던지고 `a2a_task_status`·수신함으로 회수한다.
- 저장소를 지정하려면 `cwd` 를 그 작업의 워크트리로 준다.

## 5. 검증 증거 (Verification Evidence)

작업을 완료로 적기 전에 그 저장소의 게이트를 실제로 돌리고 출력을 증거로 남긴다.

- **완료로 적은 작업은 검증 명령이 모두 exit_code 0 이어야 한다.** 빌드 성공만으로 통과가 아니다.
- **완료로 적은 작업은 산출물 경로와 64자리 소문자 hex sha256 이 있어야 한다.** 해시는 검증기가 다시 대조한다.
- **앞 작업이 끝나지 않았으면 뒤 작업을 완료로 적을 수 없다.**
- **미구현·추가 예정 표기가 남은 기록은 완료가 아니다.**

기록이 SKILL.md 의 규칙을 지켰는지는 검증기가 판정한다. 최종 보고 전에 반드시 돌린다.
해시는 `check_task_dag.py hash <경로>` 로 구한다.

```sh
python3 .claude/skills/yd-a2a-orchestrator/scripts/check_task_dag.py <dag.json> --root <워크스페이스> --verify-files
```

- **위반이 없으면 0, 있으면 1, 입력을 읽지 못하면 2 를 낸다.**
- **기록 파일을 읽지 못하면 검증기는 exit 2 를 낸다.** 이것도 통과가 아니다.
- 검증기가 exit 0 일 때만 "DAG 를 다 통과했다" 고 보고한다.

## 6. 실패 재배정 (Failure Reassignment)

에이전트가 오류·타임아웃·할당량 초과로 끝나면 같은 작업을 다른 에이전트에 다시 맡긴다.

- **실패 재배정은 같은 작업에서 최대 3회까지다.** 같은 실패가 반복되면 규칙을 무력화하지 말고
  원인과 필요한 결정을 사용자에게 보고하고 멈춘다.
- 담당이 멈추면 이슈에 핸드오프(`owner:*` 를 떼고 `handoff` 라벨)를 남기고, 이어받는 에이전트는
  원담당의 브랜치·워크트리 위에서 계속한다 — 새 브랜치·새 PR 을 따로 만들지 않는다.
- 보드 메시지에 답이 없으면 한 번 다시 묻고, 그 뒤에는 이슈 기록을 기준으로 이어받는다.

## 7. 완료 조건 (Definition of Done)

1. 지휘권 리스를 보유했고, 작업 DAG 의 모든 작업이 `done` 이다.
2. `check_task_dag.py` 가 exit 0 이다(모든 검증 명령 exit 0, 산출물 해시 일치).
3. 각 PR/MR 이 이슈 번호를 달고, 담당이 아닌 에이전트의 교차 리뷰(LGTM 또는 지적 해소)를 받았다.
4. 건너뛴 단계와 잔여 위험(추측으로 채운 값, mock 으로 남긴 경로)이 최종 보고에 있다.

## 저장소 지도

메인·관련 저장소의 역할, 검증 명령, 워크트리 규칙은 [references/repo-map.md](references/repo-map.md) 에 있다.
작업을 어느 저장소에 맡길지 정할 때 먼저 그 표를 본다.

## Learned warnings

- (2026-11-22) 작업을 끝낸 에이전트를 풀에 반환하지 않고 묶어 둬서, 콘솔(`/a2a`)에 유령
  세션(`codex-glm-2..6`·`codex-llmgw-*` `stale`)이 쌓였다. 그래서 `pool` 목록과 반환 규칙을
  §3 에 넣고, `check_task_dag.py` 가 이를 검사하게 했다.
