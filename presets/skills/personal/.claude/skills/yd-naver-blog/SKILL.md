---
name: yd-naver-blog
description: Playwright MCP 로 네이버 블로그(SmartEditor ONE)에 글을 올리고 관리한다 — 본문 붙여넣기, 태그(최대 30개), 카테고리 만들기·순서 바꾸기, 발행한 글의 카테고리 옮기기, 임시저장·발행. "네이버 블로그에 올려", "블로그 카테고리 만들어", "카테고리 맨 위로", "태그 넣어줘", "글 카테고리 옮겨" 요청에 쓴다. 본문 문장은 yd-writer-kr 가 쓰고 이 스킬은 브라우저 조작만 맡는다.
metadata:
  internal: true
---

# yd-naver-blog

## 역할

네이버 블로그 글쓰기·관리 화면을 Playwright MCP 로 조작한다. 본문 작성과 교정은 `yd-writer-kr` 에 맡긴다.
2026-11-13 블로그 `diablodok` 에서 실측한 순서다(#122).

## 지키는 것

- **로그인은 사용자가 한다.** 로그인 화면이 나오면 멈추고 Playwright 창에서 직접 로그인해 달라고 한다. 아이디·비밀번호를 입력하지 않는다.
- **발행은 사용자 확인 뒤에만 누른다.** 기본 동작은 임시저장이다. 발행 설정 창의 최종 "발행" 버튼은 "발행해", "ㄱㄱ" 같은 명시 지시가 있을 때만 누른다.
- **카테고리 삭제는 사용자가 이름을 짚어 지시할 때만 한다.** 카테고리를 지우면 그 안의 글과 예약 글이 모두 지워진다(삭제 확인창 문구, 2026-11-13 실측). 글이 1개 이상이면 멈추고 글을 먼저 옮길지 묻는다.
- 파일 저장(스크린샷·스냅샷)은 작업 디렉터리와 `.playwright-mcp/` 안에서만 된다. 스크래치패드 경로는 거부된다. 작업이 끝나면 `.playwright-mcp/` 를 지운다.

## 1. 글쓰기 화면 열기

1. `browser_navigate` 로 `https://blog.naver.com/GoBlogWrite.naver` 를 연다.
2. URL 이 `nid.naver.com/nidlogin` 이면 로그인 대기다. 사용자에게 로그인을 부탁하고 턴을 끝낸다.
3. 로그인 뒤 다시 열면 `blog.naver.com/<블로그ID>?Redirect=Write` 로 바뀐다. 에디터는 `iframe#mainFrame` 안에 있다.

## 2. 제목·본문 넣기

에디터는 마크다운을 렌더하지 않는다. 백틱·`#`·`**` 가 그대로 보이므로 빼고 넣는다.
본문은 HTML 클립보드 붙여넣기로 넣는다. `<h2>` 는 소제목으로, `<p><br></p>` 는 빈 줄로 들어간다.

```js
// browser_run_code_unsafe
async (page) => {
  const title = "제목";
  const blocks = [["p", "첫 문단"], ["h2", "소제목"], ["p", "본문"]];
  const esc = s => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const html = blocks.map(([t, s]) => (t === "h2" ? "<p><br></p>" : "") + `<${t}>${esc(s)}</${t}>`).join("");
  const text = blocks.map(([, s]) => s).join("\n\n");
  await page.context().grantPermissions(["clipboard-read", "clipboard-write"], { origin: "https://blog.naver.com" });
  const f = page.frameLocator("#mainFrame");
  const frame = page.frame({ name: "mainFrame" });
  await f.locator(".se-documentTitle .se-text-paragraph").first().click();
  await page.keyboard.press("Meta+A");
  await page.keyboard.press("Backspace");
  await page.keyboard.type(title, { delay: 15 });
  await f.locator(".se-component.se-text .se-text-paragraph").first().click();
  await page.keyboard.press("Meta+A");   // 기존 본문을 지운다
  await page.keyboard.press("Backspace");
  await frame.evaluate(async ({ html, text }) => {
    await navigator.clipboard.write([new ClipboardItem({
      "text/html": new Blob([html], { type: "text/html" }),
      "text/plain": new Blob([text], { type: "text/plain" }),
    })]);
  }, { html, text });
  await page.keyboard.press("Meta+V");
  await page.waitForTimeout(1500);
  const got = await frame.$$eval(".se-component-content .se-text-paragraph",
    els => els.map(e => e.innerText.trim()).filter(Boolean));
  return got;  // [제목, 문단...] — blocks 와 한 줄씩 대조한다
}
```

넣은 뒤 반환값을 원고와 문단 단위로 대조한다. 한 문단이라도 다르면 저장하지 않는다.

붙여넣기로 바뀌는 요소(2026-11-13 실측):

| HTML | 에디터 컴포넌트 |
|---|---|
| `<h2>` | 소제목 |
| `<ul><li>` | 글머리 기호 목록 |
| `<blockquote><p>` | 인용구(`.se-component.se-quotation`). 출처 칸은 비어 있다 |
| `<p><br></p>` | 빈 줄 |

- 인용구 출처는 붙여넣은 뒤 `.se-quotation .se-text-paragraph` 마지막 칸을 눌러 입력한다. 본문 안에 "— 이름" 으로 적지 않는다.
- 여러 줄로 감긴 문단에서 `End` 는 화면상 줄 끝으로만 간다. 문단 끝을 지우려고 `Backspace` 를 반복하면 중간 글자가 지워진다. 문단을 고칠 때는 세 번 클릭(`click({ clickCount: 3 })`)으로 문단을 고른 뒤 다시 입력한다.
- 에디터는 자체 스크롤 영역이다. `window.scrollTo` 는 듣지 않으니 `page.mouse.wheel` 로 움직인다.
- `<b>` 는 굵게로 들어간다. 사진 아래 "사진 설명을 입력하세요." 는 편집 화면의 안내 문구라 발행 글에는 나오지 않는다. 대조할 때는 빼고 센다.
- `browser_run_code_unsafe` 안에서는 `require` 를 쓸 수 없다. 긴 원고는 데이터를 박아 넣은 스크립트 파일을 `.playwright-mcp/` 에 만들고 `filename` 으로 실행한다.

### 사진 넣기 — 구간을 나눠 단계별로

사진은 커서 위치에 들어간다. 원고를 사진 자리에서 구간으로 나누고, 구간마다 아래 세 단계를 반복한다(2026-11-14 실측).

1. `browser_run_code_unsafe`: 직전 구성요소가 사진이면 그 사진을 누르고 `Enter` 로 새 문단을 만든다. 구간 HTML 을 붙여넣는다. 사진 버튼(`button.se-image-toolbar-button`)을 **기다리지 않고** 누른다(`.click().catch(() => {})`).
2. MCP 가 파일 선택 창을 모달로 잡는다. `browser_file_upload` 로 파일 경로를 넘긴다. 경로는 작업 디렉터리 안이어야 한다.
3. 다음 구간으로 간다. 마지막 구간 뒤에는 사진 버튼을 누르지 않는다.

스크립트 안에서 `page.waitForEvent('filechooser')` 로 직접 처리하지 않는다. MCP 가 같은 창을 모달로 잡아 호출이 먼저 반환되고, 스크립트는 뒤에서 계속 돌아 다음 모달을 연다. 결과를 확인할 수 없고 뒤이은 호출이 "modal state" 오류로 막힌다.
끝나면 `.se-component.se-image img` 의 파일 이름 순서로 사진 위치를 확인한다. 첫 사진이 "대표"(썸네일)가 된다.

## 3. 임시저장

- 저장 버튼은 `#mainFrame` 안의 `button[class*="save_btn"]`, 임시저장 개수는 `button[class*="save_count_btn"]` 다.
- 같은 에디터에서 다시 저장하면 새 글이 생기지 않고 같은 임시저장 글을 덮어쓴다. 개수가 그대로인 것이 정상이다.
- 개수 버튼을 누르면 "임시저장 글" 목록이 뜬다. 제목과 저장 시각으로 확인하고 `Escape` 로 닫는다.

## 4. 태그 넣기

1. 상단 "발행" 버튼(`button[class*="publish_btn"]`)을 누르면 발행 설정 창이 열린다. 이 버튼은 발행하지 않는다.
2. 태그 입력칸은 `input[placeholder*="태그"]` 다. 최대 30개다.
3. 태그마다 입력하고 `Enter` 를 누른다. 띄어쓰기 없이 쓴다.

```js
const input = frame.locator('input[placeholder*="태그"]').first();
await input.click();
for (const t of tags) { await page.keyboard.type(t, { delay: 10 }); await page.keyboard.press("Enter"); }
```

넣은 뒤 `#` 로 시작하는 태그 개수를 세어 확인한다.

## 5. 발행

- 발행 설정 창에서 카테고리·주제·공개 설정·발행 시간을 사용자에게 보여 준다. 카테고리 기본값은 마지막에 쓴 카테고리라 의도와 다를 수 있다.
- 사용자 지시가 있으면 `button[class*="confirm_btn"]` 을 누른다. 발행되면 URL 이 `blog.naver.com/<블로그ID>/<글번호>` 로 바뀐다. 이 URL 을 보고한다.

## 6. 카테고리 만들기와 순서 바꾸기

카테고리 관리 화면은 `https://admin.blog.naver.com/<블로그ID>/config/blog` 다. 편집 영역은 `iframe[name=papermain]` 안에 있다.
`AdminMain.naver?Redirect=CategoryManage` 는 기본 설정으로 가므로 쓰지 않는다.

버튼은 글자가 아니라 이미지다. `alt` 가 아니라 클래스로 누른다.

| 동작 | 선택자 |
|---|---|
| 카테고리 추가 | `img._addCategoryView` |
| 구분선 추가 | `img._addLineView` |
| 삭제 | `img._deleteCategoryView` |
| 위 · 아래 | `img._moveUp` · `img._moveDown` |
| 맨위 · 맨아래 | `img._moveFirst` · `img._moveLast` |
| 이름 | 목록 안 `input.cat_input`, 오른쪽 `#category_name` |
| 저장 | 아래쪽 "확인" 버튼 |

순서는 다음과 같다.

1. 목록에서 **"카테고리 전체보기"** 를 먼저 고른다. 다른 카테고리를 고른 채 추가하면 그 하위 카테고리로 들어간다.
2. `img._addCategoryView` 를 누른다. 목록 맨 아래에 "게시판" 이름으로 생긴다.
3. `input.cat_input` 에 이름을 넣고 `Enter` 를 누른다. `#category_name` 값이 같은지 확인한다.
4. "확인" 을 눌러 저장한다. **저장 전에는 정렬 버튼이 듣지 않는다**(아이콘이 `*2.gif` 회색).
5. 새 카테고리를 다시 고르고 `img._moveFirst` 로 맨 위에 올린다. "확인" 을 한 번 더 누른다.
6. 페이지를 다시 열어 목록 순서를 스크린샷으로 확인한다.

잘못 추가했으면 저장 전에 페이지를 새로고침해 버린다. `beforeunload` 확인 창이 뜨면 수락한다. 삭제 버튼보다 안전하다.

카테고리를 지울 때는 다음 순서를 따른다.

1. 목록에서 카테고리를 고르고 이름 옆 글 개수를 읽는다. `(0)` 이 아니면 멈추고 사용자에게 묻는다.
2. `img._deleteCategoryView` 를 누르면 페이지 안 레이어가 뜬다. 브라우저 대화상자가 아니라서 `dialog` 이벤트로 잡히지 않는다.
3. 레이어 문구 "카테고리에 속한 N개의 글이 모두 삭제됩니다" 의 N 을 다시 확인한다. 0 일 때만 레이어 안 "삭제" 를 누른다.
4. 목록에서 사라진 것을 보고 아래쪽 "확인" 으로 저장한다. 페이지를 다시 열어 목록과 "카테고리 전체보기" 글 수를 확인한다.

글쓰기·수정 화면이 열린 탭에서 관리 화면으로 이동하면 고치던 내용이 사라진다. 관리 작업은 `browser_tabs` 로 새 탭을 열어서 한다.

## 7. 발행한 글의 카테고리 옮기기

1. `https://blog.naver.com/PostUpdateForm.naver?blogId=<블로그ID>&logNo=<글번호>` 를 연다. 이 화면은 iframe 없이 최상위 문서에 에디터가 있다.
2. 상단 "발행" 버튼으로 설정 창을 연다.
3. 카테고리 선택 상자(`button[class*="selectbox_button"]`)를 누르고 `[class*="selectbox"] li` 중 원하는 이름을 고른다. 하위 카테고리는 "하위 카테고리\n이름" 으로 읽힌다.
4. 태그는 유지된다. 개수를 세어 확인한 뒤 `button[class*="confirm_btn"]` 을 누른다.
5. 이동한 URL 에 `categoryNo=` 가 붙는다. 글 화면의 카테고리 이름으로 확인한다.

## 에디터 도움말에서 확인한 것

글쓰기·수정 화면 오른쪽 아래 "?" 버튼(`button.se-util-button-guide`)을 누르면 도움말 패널이 열린다. 항목은 27개다.
항목은 `.se-help-content` 안 글자로 열고, 본문은 `.se-help-layer`, 뒤로가기는 `.se-help-layer-button-back` 이다.
2026-11-13 전체를 읽고 자동화에 필요한 것만 옮겼다.

**글자와 문단**
- 제목은 최대 100자다.
- 텍스트 유형은 소제목·본문·인용구 세 가지다. 붙여넣은 `<h2>` 는 소제목이 된다. 이미 넣은 문단은 블록 선택 뒤 속성 도구 막대의 유형 상자에서 바꾼다.
- 인용구에는 "출처" 입력란이 따로 있다. 증권사 연구원 발언처럼 출처가 있는 인용에 쓴다.
- 속성 도구 막대에 "맞춤법" 검사가 있다. 발행 전 점검에 쓸 수 있다.

**자동 변환 — 의도하지 않은 결과가 생길 수 있다**
- 본문에 URL 을 붙여넣으면 링크 카드 컴포넌트가 자동으로 생긴다. 유튜브·네이버TV 주소는 영상으로 임베드된다. 주소만 남기려면 생긴 카드를 지운다.
- 본문에 `#태그명` 을 입력하면 태그가 자동으로 추가된다. 본문에 `#122` 같은 이슈 번호나 `#` 로 시작하는 낱말을 쓰지 않는다. 붙여넣기에도 적용되는지는 확인하지 못했다.
- 추천 템플릿을 고르면 작성 중인 글이 자동 임시저장되고 문서 전체가 템플릿으로 바뀐다. 템플릿 패널은 열지 않는다.

**단축키(macOS)**

| 동작 | 단축키 |
|---|---|
| 임시저장 | `Cmd+Shift+S` |
| 구분선 · 인용구 | `Ctrl+Option+H` · `Ctrl+Option+Q` |
| 사진 첨부 · 템플릿 목록 | `Ctrl+Option+I` · `Ctrl+Option+T` |
| 왼쪽 · 가운데 · 오른쪽 정렬 | `Ctrl+Option+L` · `Ctrl+Option+C` · `Ctrl+Option+R` |
| 굵게 · 실행취소 | `Cmd+B` · `Cmd+Z` |

**발행 설정**
- 공개 범위는 전체·이웃·서로이웃·비공개 네 가지다.
- 발행 설정 항목은 댓글·공감·검색 허용, CCL 표시, 블로그/카페 보내기, 외부 보내기 허용이다.
- 발행 시간은 "현재" 와 "예약" 이다. 예약은 지정한 날짜·시각에 발행한다. "공지사항으로 등록" 도 같은 창에 있다.
- 태그는 입력하고 `Enter` 를 누르면 생기며 최대 30개다.

**검수**
- 오른쪽 아래 "?" 위의 기기 아이콘(`button.__mode-button`)을 누를 때마다 PC → Mobile → Tablet 미리보기로 바뀐다. 현재 모드는 클래스 끝(`-device-desktop`·`-device-mobile`)으로 안다. 발행 전에 모바일 화면을 스크린샷으로 확인한다.
- 수정 화면(`PostUpdateForm`)에는 임시저장 버튼이 없다. 고친 내용은 "발행"을 눌러야 남는다. 사용자 확인 전에는 화면을 닫지 말고 그대로 둔다.
- 임시저장 목록에서 글을 고르면 그 글을 불러온다. 목록에는 "삭제"·"전체삭제" 가 있다. 사용자 지시 없이 누르지 않는다.

## 증시 글을 쓸 때의 데이터 출처

- 지수는 네이버 증권 모바일 API(`m.stock.naver.com/api/index/KOSPI/basic`)가 정규장 값과 같다.
- 같은 API 의 종목 가격은 저녁에 시간외 값을 보여 준다. 2026-11-13 20:20 에 삼성전자는 209,000원(+0.48%)이었다. 기사의 정규장 종가는 20만6000원(-0.96%)이었다. 종목은 정규장 종가를 기사에서 확인한다.
- 투자자별 수급은 출처마다 다르다. 2026-11-13 외국인 순매도는 네이버 화면이 5,419억 원, 파이낸셜뉴스가 7,034억 원이었다. 출처와 시각을 글에 적는다.
- doksamlabs `stock_daily_candles`(yd-stock MCP 원천)에는 지수 코드가 없다. 당일 행은 08:10 장전 수집분이고 `volume=0` 인 자리표시 값이다. 장 마감 요약에 쓰지 않는다.
- 2026-11-14 확인한 네이버 증권 경로(인증 없음, 요청은 몇 건만 보낸다):

| 데이터 | 경로 |
|---|---|
| 지수 1분봉 | `api.stock.naver.com/chart/domestic/index/KOSPI/minute?startDateTime=YYYYMMDD0900&endDateTime=YYYYMMDD1530` |
| 전일·시가·고가·저가·거래대금, 투자자별·프로그램 매매·등락 종목 수 | `m.stock.naver.com/api/index/KOSPI/integration` (`dealTrendInfo`·`programTrendInfo`·`upDownStockInfo`) |
| 미국 지수 일별 마감 | `api.stock.naver.com/index/.INX/price?page=1&pageSize=3` (`.IXIC`·`.DJI` 도 같다) |
| 미국 종목 일별 마감 | `api.stock.naver.com/stock/NVDA.O/price?page=1&pageSize=3` |

## 증시요약 글 형식

2026-11-14 에 정했다(#124). 근거는 네이버 블로그 "증시요약" 정확도순 상위 16개 분석과 네이버 공식 문서 기준이다. 표본이 작고 공감 수는 이웃 수 영향이 커서 인과는 아니다. 본문 문장은 yd-writer-kr 로 쓰고 `--source` 대조를 통과시킨다.

- **문체는 합니다체.** 공감 2개 이상인 글 9개가 모두 합니다체 위주였다. 한다체 위주 4개는 공감 0~1개였다.
- **제목**: `[MM/DD] 증시요약: <핵심 수치>, <핵심 원인>`. 핵심을 앞 25자 안에 둔다. 검색 결과에서 그 뒤는 잘린다(글쓰기 가이드 기준).
- **맨 위**: 세 줄 요약(글머리 목록) → 요약 카드 이미지. 카드에는 지수·환율·외국인 수급을 둔다. 첫 사진이 대표 사진이 되니 카드를 맨 앞에 둔다.
- **소제목**은 명사구로 짧게 쓴다. 예: "수급: 외국인 장중 매도 전환". 3~4문단마다 하나씩 둔다.
- **굵게**는 핵심 수치에만, 문단당 1~2곳.
- **사진 4~6장.** 공감 2개 이상인 글은 모두 6~9장이었다. 차트는 수집한 데이터로 직접 그린다. 네이버 증권 차트 이미지는 쓰지 않는다. 모바일 본문 폭에서도 읽히게 글씨를 키운다.
- **이모지는 쓰지 않는다.** 16개 중 11개가 쓰지 않았다.
- **출처 목록**에는 데이터 출처와 기사 시각만 적는다. "차트는 직접 그렸다" 같은 제작 과정 메모는 넣지 않는다(2026-11-13 사용자 지시).
- **네이버 "나쁜 문서" 기준**: 기계적으로 생성한 내용만으로 된 글, 같은 내용을 반복하는 도배성 글. 정기 글이라도 그날 데이터로 쓴 고유 분석 문장을 넣고, 사람이 확인한 뒤 발행한다.

## 완료 보고

- 글 URL, 카테고리 이름, 태그 개수, 공개 설정을 보고한다.
- 임시저장만 했으면 "발행 안 함" 을 분명히 쓴다.
- `.playwright-mcp/` 를 지웠는지 적는다.
