---
name: reference_hwpx-plan-v2-traps
description: hwpx 플러그인(automation 7.3.4) document_plan v2 표·글머리·출력 경로 함정 — 검증기는 통과하는데 내용이 깨진다
metadata:
  type: reference
---

hwpx-plugin 2.4.0(automation 7.3.4, python-hwpx 6.8.0)으로 `create_document_from_plan` 을 쓸 때 실측한 함정(2026-11-15).

- **v2 표는 `header`(배열) + `rows`(배열의 배열)** 만 받는다. v1 식 `columns`+`rows`(키-값 객체)를 v2 `sections` 안에 넣으면
  `validate_document_plan` 은 `ok:true` 인데 셀에 값 대신 **키 이름**(`k`, `v`, `number`)이 찍힌다. 생성 후 `get_table_text` 로 반드시 읽어 본다.
- v2 표는 `caption` 을 **무시**한다. 표 제목은 앞에 별도 문단/heading 으로 둔다. 지원 키: `header`·`rows`·`merges`(`"A3:A5"`)·`headerShading`·`columnWidths`.
- `bullets` 의 `style`(circle/square/note)은 **government_report 프리셋에서만** 먹는다. `genre:operating_plan` 에선 레벨 0 이 `-` 로 나오고
  header.xml 에 `head:bullets` 스키마 경고가 붙는다. ○·※ 는 문단 텍스트 앞에 직접 넣는 편이 확실하다.
- `compose_section_chip` box 칩은 셀 글꼴이 표 본문 크기(10.5pt)라 제목이 작다. 장 제목은 heading level 1 이 낫다(자동 번호 안 붙음).
- `render_preview` 는 표 테두리·글머리 번호를 그리지 않는다. 테두리 유무는 section0.xml 의 `borderFillIDRef` → header.xml `borderFill` 로 확인.
- MCP 샌드박스 루트가 세션 cwd 하나뿐이라 다른 폴더에 바로 못 쓴다. cwd 아래 임시 폴더에 만들고 `mv` 한다.

관련: [[reference_local-html-render-qa]]
