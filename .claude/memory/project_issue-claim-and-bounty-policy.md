---
name: issue-claim-and-bounty-policy
description: 외부 기여자의 /attempt·유료 제안 코멘트 대응 — 이 레포엔 바운티 봇도 지불 프로그램도 없다
metadata:
  type: project
---

공개 이슈에 외부 기여자가 남기는 두 종류의 코멘트에 대한 확정 대응(2026-08-29 기준):

- **`/attempt`** — Algora 등 바운티 플랫폼의 클레임 문법. 이 레포엔 그 봇도, 그 명령을
  처리하는 워크플로도 없다(`.github/workflows/` 는 claude-assistant / claude-code-review /
  test 뿐). 자동 assign 되지 않으므로 "코멘트 자체가 클레임"임을 알려주고 CONTRIBUTING.md +
  docs/PRESET_SPEC.md 로 안내한다.
- **유료 작업 제안**(예: "$10 USD 에 해드리겠습니다") — 거절. 선례 답변:
  claude-scaffold#6 comment 5308221548 — "volunteer-based open-source project with no
  bounty/payment program". 이슈 #9 에도 동일 문구로 답한 이력이 있다.

**Why:** 스캐폴드 레포가 공개된 뒤 이 두 패턴이 여러 이슈(#6, #9)에서 반복됐고, 매번 정책을
재발명하면 답변이 흔들린다.

**How to apply:** 클레임은 환영하되 자동화 없음을 명시하고 PR 기한(~1주) 을 걸어 이슈를
묶어두지 않는다. 유료 제안은 위 선례 링크를 인용해 짧게 거절.

관련: [[readme-multilang-sync]]
