---
name: 스킬 bash 스니펫의 조용한 실패
description: SKILL.md 명령 예시가 `2>/dev/null || true`·`a | tail || b` 로 에러를 삼켜 고장을 숨긴다 — 스킬 점검 시 억제 없이 실행해 검증
type: feedback
---

# 스킬 bash 스니펫의 조용한 실패 (#57)

스킬 본문의 명령 예시는 "없으면 조용히 건너뛰기"용으로 `2>/dev/null || true` 를 붙이는 경우가
많은데, 이게 **잘못된 플래그·깨진 폴백까지 같이 숨긴다.** 테스트 스위트는 SKILL.md 를
실행하지 않으므로 어떤 게이트에도 안 걸린다.

실제 사례 (2026-09-25, status 스킬):
- `bunx tsc … | tail -5 || npx tsc …` — 파이프 종료코드는 `tail` 것이라 폴백이 절대 안 돈다.
- `glab issue list --state=opened -P 1 --per-page 5` — 존재하지 않는 `--state` + 중복 `-P`.
  에러가 `2>/dev/null` 에 묻혀 수개월간 "오픈 이슈 없음"처럼 보였다.

**How to apply:** 스킬 점검·수정 시 스니펫을 `bash -n` 으로 문법 검사하고, 억제(`2>/dev/null`,
`|| true`)를 떼고 한 번 실행해 실제 에러를 본다. 폴백은 `a | tail || b` 대신 `command -v` 로
러너를 먼저 고른다. CLI 플래그는 `<cmd> --help` 로 대조한다(기억 금지).
