---
name: local-html-render-qa
description: 생성 HTML 렌더 검수·전후 비교 방법 — claude-in-chrome은 file:// 불가·확장 미연결이 잦아 headless Chrome + mongoose 조합을 쓴다
metadata:
  type: reference
---

`yd-mobile-web-planner` 산출물(스토리보드 HTML) 렌더 품질을 눈으로 검수할 때 쓰는 로컬 파이프라인 (2026-07-28 실증):

1. **서빙**: `mongoose -d <산출물 디렉터리> -l http://0.0.0.0:8899` — claude-in-chrome 확장은 `file://` URL을 거부하고, 확장 자체가 미연결인 경우도 잦다.
2. **슬라이드 추출**: 전체 문서를 `'<div class="ppt-slide">'` 로 split 해서 head(공통 CSS/mermaid) + 대상 슬라이드 1장만 담은 단독 HTML을 만든다 — 슬라이드별 스크린샷용.
3. **스크린샷**: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --window-size=1480,920 --screenshot=<out.png> <mongoose URL>` → Read 툴로 이미지 판독.
4. **사용자 리뷰**: 전후/버전 비교는 BEFORE·AFTER 이미지를 나란히 놓은 비교 HTML을 만들어 `open <mongoose URL>` 로 브라우저에 띄워준다 — 로컬 파일 경로만 던지지 않는다(전역 지침).

**주의**: 검증기(`validate_storyboard.py`) 통과 ≠ 렌더 정상. 잘림·줄바꿈 깨짐·표기 불일치는 스크린샷으로만 잡힌다 — [계약 레벨 품질 수정](feedback_quality-fix-at-contract-level.md) 의 세 이슈 모두 검증기 0건 상태에서 사용자 눈으로 발견됐다.

(2026-10-24 LeeYudok/doksam-skills 에서 이식, #78)
