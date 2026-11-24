# Markup

## 화면 상세 (09.x) — 좌우 분할

```html
<div class="ppt-slide">

  <div class="ppt-top-bar">
    <div class="ppt-top-no">NO. 09.1</div>
    <div class="ppt-top-title">Main Home</div>
    <div class="ppt-head-label">화면 Type</div>
    <div class="ppt-head-value">MOBILE WEB</div>
    <div class="ppt-head-label">요구사항 ID</div>
    <div class="ppt-head-value">-</div>
    <!-- Page 박스는 CSS 가 자동으로 붙는다. ppt-top-proj 는 두지 않는다(푸터와 중복) -->
  </div>

  <div class="ppt-meta-bar">
    <div class="ppt-meta-label">화면 ID</div>
    <div class="ppt-meta-id">DTC-MAIN-001</div>
    <div class="ppt-meta-label">Location</div>
    <div class="ppt-meta-value">홈</div>
    <div class="ppt-meta-label" style="margin-left:auto;">작업자</div>
    <div class="ppt-meta-value">UX 기획</div>
  </div>

  <div class="ppt-content">

    <div class="ppt-wireframe">
      <div class="mock">
        <div class="mock-screen">
          <div class="mock-status"></div> <!-- 빈 div 하나 — 9:41·배터리는 CSS 가 그린다 -->
          <div class="mock-header"><span><span style="font-size:20px; font-weight:400; margin-right:8px;">&lsaquo;</span>메인 홈</span></div>
          <div class="mock-body" style="position:relative; background:#f2f4f6;">
            <span class="pointer-badge" style="position:absolute; top:20px; left:2px; z-index:10;">1</span>
            <!-- 목업 내용. 세부 스타일은 인라인 style 로. 카드는 아래 "목업 밀도" 스니펫 참조 -->
          </div>
          <div class="mock-footer-pill">
            <!-- 탭 바 있는 화면의 기본형. 배지는 여기(position:relative)에 얹는다 -->
            <span class="pointer-badge" style="position:absolute; top:10px; left:2px; z-index:10;">4</span>
            <div style="display:flex; align-items:center; gap:6px; background:rgba(255,255,255,0.22); border:1px solid rgba(255,255,255,0.3); border-radius:17px; padding:6px 11px; box-shadow:inset 0 1px 2px rgba(255,255,255,0.35), 0 2px 8px rgba(0,0,0,0.25);">
              <svg class="icon" viewBox="0 0 256 256" style="fill:#fff; width:14px; height:14px;"><path d="M218.83,103.77l-80-75.48a1.14,1.14,0,0,1-.11-.11,16,16,0,0,0-21.53,0l-.11.11L37.17,103.77A16,16,0,0,0,32,115.55V208a16,16,0,0,0,16,16H96a16,16,0,0,0,16-16V160h32v48a16,16,0,0,0,16,16h48a16,16,0,0,0,16-16V115.55A16,16,0,0,0,218.83,103.77ZM208,208H160V160a16,16,0,0,0-16-16H112a16,16,0,0,0-16,16v48H48V115.55l.11-.1L128,40l79.9,75.43.11.1Z"/></svg>
              <span style="font-size:11px; font-weight:800; color:#fff;">홈</span>
            </div>
            <svg class="icon" viewBox="0 0 256 256" style="fill:rgba(255,255,255,0.75); width:14px; height:14px;"><path d="M229.66,218.34l-50.07-50.06a88.11,88.11,0,1,0-11.31,11.31l50.06,50.07a8,8,0,0,0,11.32-11.32ZM40,112a72,72,0,1,1,72,72A72.08,72.08,0,0,1,40,112Z"/></svg>
          </div>
        </div>
        <div class="mock-caption">메인 홈 (DTC-MAIN-001)</div>
      </div>
    </div>

    <div class="ppt-desc-panel">
      <div class="ppt-desc-header">Description (화면설명)</div>
      <div class="ppt-desc-body">
        <ul class="desc-list">
          <li><span class="desc-num">1</span> <div><b>배너 영역</b><br>주요 속보 롤링 (Max. 5개)<br>탭: 공지 상세로 이동 (DTC-NOTICE-002)<br><code>Banner</code></div></li>
          <li><span class="desc-num">2</span> <div><b>네비게이션</b><br>탭: 해당 카테고리 목록 전환<br>스와이프: 인접 탭 이동<br><code>Tabs</code></div></li>
        </ul>
      </div>
    </div>

  </div>

  <div class="ppt-footer">
    {{PROJECT_NAME}} | Ver.{{VERSION}}
  </div>

</div>
```

## 화면 상세 — 목업 2개 (상태 비교)

좌측 패널에 `mock` 을 나란히 두고 각각 `mock-caption` 으로 라벨을 붙인다. 배지 번호는 2단이다 — 첫 목업이 `1-1`·`1-2`, 두 번째 목업이 `2-1`. 축소율과 간격은 템플릿이 처리하므로 인라인으로 크기를 주지 않는다. 캡션에는 라벨과 함께 그 목업의 화면 ID 를 적어 두 번째 화면의 ID 도 문서 안에 정의된다.

```html
<div class="ppt-wireframe">

  <div class="mock">
    <div class="mock-screen">
      <div class="mock-status"></div>
      <div class="mock-header">필터</div>
      <div class="mock-body" style="position:relative;">
        <span class="pointer-badge" style="position:absolute; top:20px; left:2px; z-index:10;">1-1</span>
        <!-- 선택 전 목록 -->
        <span class="pointer-badge" style="position:absolute; top:200px; left:2px; z-index:10;">1-2</span>
        <!-- 적용 버튼 (비활성) -->
      </div>
    </div>
    <div class="mock-caption">필터 기본 (DTC-FILTER-001)</div>
  </div>

  <div class="mock">
    <div class="mock-screen">
      <div class="mock-status"></div>
      <div class="mock-header">필터</div>
      <div class="mock-body" style="position:relative;">
        <span class="pointer-badge" style="position:absolute; top:20px; left:2px; z-index:10;">2-1</span>
        <!-- 선택된 칩이 강조된 목록 -->
      </div>
    </div>
    <div class="mock-caption">필터 선택됨 (DTC-FILTER-002)</div>
  </div>

</div>

<div class="ppt-desc-panel">
  <div class="ppt-desc-header">Description (화면설명)</div>
  <div class="ppt-desc-body">
    <ul class="desc-list">
      <li><span class="desc-num">1-1</span> <div><b>필터 목록 (기본 상태)</b><br>미선택 시 전체 조건 노출 <code>ChipGroup</code></div></li>
      <li><span class="desc-num">1-2</span> <div><b>적용 버튼 (기본 상태)</b><br>선택 0건이면 비활성 <code>Button (disabled)</code></div></li>
      <li><span class="desc-num">2-1</span> <div><b>필터 목록 (선택됨)</b><br>선택 항목 Primary 강조, 상단 고정 <code>ChipGroup (selected)</code></div></li>
    </ul>
  </div>
</div>
```

## 표지·이력·목차·IA·화면목록·흐름도·시퀀스·공통규칙 — 통짜 (화면 상세 제외 전부)

```html
<div class="ppt-slide">
  <div class="ppt-top-bar">
    <div class="ppt-top-no">NO. 04</div>
    <div class="ppt-top-title">Information Architecture</div>
    <div class="ppt-top-proj">{{PROJECT_NAME}}</div>
  </div>
  <div class="ppt-content">
    <div class="ppt-body-full">
      <!-- 텍스트, 표, 또는 <div class="mermaid"> 다이어그램 -->
    </div>
  </div>
  <div class="ppt-footer">
    {{PROJECT_NAME}} | Ver.{{VERSION}}
  </div>
</div>
```
