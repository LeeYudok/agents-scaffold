---
name: reference_naver-blog-playwright
description: 네이버 블로그 게시·카테고리 편집 절차는 옵트인 스킬 yd-naver-blog(#122)에 있다 — 2026-11-13 실측 함정 요약
metadata:
  type: reference
---

네이버 블로그 게시 절차의 원본은 옵트인 스킬 `presets/skills/personal/.claude/skills/yd-naver-blog/SKILL.md` 다(#122, PR #123).
여기에는 다시 찾기 어려운 함정만 요약한다. 2026-11-13 블로그 `diablodok` 에서 실측했다.

- 카테고리 추가는 선택된 카테고리의 하위로 들어간다. "카테고리 전체보기"를 먼저 고른다.
- 새 카테고리는 저장 전에는 정렬 버튼이 듣지 않는다. 저장 → 다시 선택 → 맨위 → 저장 순서다.
- 본문은 HTML 클립보드 붙여넣기로 넣어야 소제목이 유지된다. 마크다운은 렌더하지 않는다.
- 네이버 증권 모바일 API 의 저녁 종목 시세는 시간외 값이다. doksamlabs `stock_daily_candles` 의 당일 행은 08:10 장전 자리표시 값이다.
- `yd-news`·`yd-stock` 은 HTTP MCP(`news.mcp.doksam.com`·`stock.mcp.doksam.com`, GitLab OAuth)다. 2026-11-13 이 맥의 Claude Code 에는 등록돼 있지 않았다.
