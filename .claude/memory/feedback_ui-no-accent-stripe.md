---
name: ui-no-accent-stripe
description: 카드·도면 상자 한쪽 가장자리에 색 띠(accent stripe)를 넣지 않는다 — 사용자가 "AI 냄새"로 싫어한다. 상태는 테두리 색·배지 글자로 보인다
metadata:
  type: feedback
---

카드·도면 상자·목록 항목의 왼쪽(또는 한쪽) 가장자리에 굵은 색 띠를 넣어 상태를 표시하지 않는다.

**Why:** 2026-10-11 yd-blueprint 도면 상자의 왼쪽 상태 색 띠를 보고 사용자가 "ai냄새 밤티야"라고 했다. 이모지 아이콘(전역 지침)과 같은 부류로, AI 생성 UI 특유의 장식으로 읽힌다.

**How to apply:**
- 상태는 상자 테두리 색(정상은 기본 테두리, 주의·미완만 색)이나 배지 글자로 보인다. yd-blueprint 템플릿이 이 방식이다(LeeYudok/doksam-skills#236, `assets/template/src/style.css`).
- 새 UI·템플릿을 만들 때 `border-left: 3px solid <색>` 류 패턴을 쓰지 않는다. 위쪽 색 줄(요약 타일)은 사용자가 참고하라고 한 ews 청사진에도 있어 아직 지적받지 않았다 — 판단이 서지 않으면 물어본다.
- 관련: [계약 레벨 품질 수정](feedback_quality-fix-at-contract-level.md)

(2026-10-24 LeeYudok/doksam-skills 에서 이식, #78)
