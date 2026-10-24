---
name: quality-fix-at-contract-level
description: 스킬 산출물 품질 이슈는 산출물 땜질이 아니라 계약 레벨 3층위로 고치고 콜드 재생성으로 재현성을 실증한다
metadata:
  type: feedback
---

`yd-mobile-web-planner` 산출물(생성된 HTML)에서 렌더 품질 문제가 나오면 그 파일을 고치는 것으로 끝내지 않는다. 보장 강도 순으로 계약에 넣는다:

1. **template.html CSS** — 렌더 자체를 강제 (재량 0). 예: desc-num 칩·nowrap, `:has()` 항목 수 감지 자동 압축.
2. **validate_storyboard.py 기계 판정** — 위반 시 exit 1 이라 어떤 세션이 만들어도 통과 전엔 미완료. 예: 목업↔캡션 수 대조, 원문자 감지.
3. **SKILL.md 지침/자체점검** — 기계로 못 재는 것만 (예: 항목 12개 초과 시 슬라이드 분할).

**Why**: 사용자가 "다시 질의해도 이런 품질로 나오는 거지?"를 명시적으로 확인함 (2026-07-28). 지침만 고치면 재생성 시 회귀한다 — 실제로 원문자 금지가 자체점검에만 있어 구멍이었고 기계 판정으로 승격함.

**How to apply**: 품질 픽스 후에는 ① 기존 산출물 패치 + ② 계약 3층위 반영 + ③ **완전 새 세션 콜드 재생성으로 재현 실증**까지가 한 세트. 사용자에게는 전후·재생성 비교를 [로컬 HTML 렌더 QA](reference_local-html-render-qa.md) 방식으로 나란히 보여준다.

(2026-10-24 LeeYudok/doksam-skills 에서 이식, #78)
