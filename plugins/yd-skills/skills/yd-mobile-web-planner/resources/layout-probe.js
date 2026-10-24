/*
 * layout-probe.js — 렌더된 화면설계서의 geometry 를 그대로 뽑아 온다.
 *
 * badge-audit.js 가 "배지가 무엇을 가리키는가"(의미)를 재는 반면, 이쪽은
 * "레이아웃이 깨졌는가"(구조)만 잰다 — 슬라이드 overflow, 배지 이탈, 배지
 * 겹침, 설명 패널 잘림·겹침. 템플릿 CSS 변경의 회귀를 잡는 것이 목적이라
 * 판정 자체는 하지 않고 **원시 좌표만** 돌려준다. 임계값 판정은
 * scripts/check_layout_runtime.py 가 한다 — 그래야 브라우저 없이도 판정
 * 로직을 단위 테스트할 수 있고, 임계값이 파이썬 한 곳에만 존재한다.
 *
 * 사용법: check_layout_runtime.py 가 산출물에 주입해 실행한다. 수동으로는
 * 브라우저 콘솔에 그대로 붙여 넣어도 같은 JSON 을 얻는다.
 */
(() => {
  const R = (n) => Math.round(n * 10) / 10;
  const box = (el) => {
    const r = el.getBoundingClientRect();
    return { top: R(r.top), left: R(r.left), right: R(r.right), bottom: R(r.bottom) };
  };
  // 배지의 좌표 원점이 되는 컨테이너들. mock-body 밖(헤더·푸터·필 탭)에 놓인
  // 배지는 원점이 달라 서로 비교하면 안 된다 — 컨테이너 단위로 묶는다.
  const HOSTS = ".mock-body, .mock-header, .mock-footer, .mock-footer-pill";

  const slides = [...document.querySelectorAll(".ppt-slide")].map((slide, index) => {
    const no = (slide.querySelector(".ppt-top-no")?.textContent || "").trim();

    const containers = [...slide.querySelectorAll(HOSTS)].map((host) => ({
      kind: host.className.split(/\s+/).find((c) => c.startsWith("mock-")) || "unknown",
      rect: box(host),
      // 스크롤 컨테이너(mock-body)는 잘려 보이는 부분이 실제 가시 영역이다.
      clipped: host.scrollHeight > host.clientHeight + 1,
      badges: [...host.querySelectorAll(":scope > .pointer-badge")].map((b) => ({
        label: b.textContent.trim(),
        ...box(b),
      })),
    })).filter((c) => c.badges.length);

    const panels = [...slide.querySelectorAll(".ppt-desc-body")].map((panel) => ({
      clientH: panel.clientHeight,
      scrollH: panel.scrollHeight,
    }));

    const items = [...slide.querySelectorAll(".desc-list > li")].map((li) => ({
      label: (li.querySelector(".desc-num")?.textContent || "").trim(),
      ...box(li),
    }));

    // scrollWidth/Height 는 정수로 반올림된다. 슬라이드 높이가 787.5px 처럼
    // 소수라 그 값만 보면 회귀가 없어도 ±3px 이 흔들린다. 실제로 잘리는지는
    // 자손 rect 가 슬라이드 rect 를 넘는지로 잰다.
    const sr = slide.getBoundingClientRect();
    let overRight = 0;
    let overBottom = 0;
    slide.querySelectorAll("*").forEach((el) => {
      const r = el.getBoundingClientRect();
      if (!r.width && !r.height) return;
      overRight = Math.max(overRight, r.right - sr.right);
      overBottom = Math.max(overBottom, r.bottom - sr.bottom);
    });

    return {
      index,
      no,
      mermaid: slide.querySelectorAll(".mermaid").length,
      slide: {
        w: R(sr.width),
        h: R(sr.height),
        overRight: R(overRight),
        overBottom: R(overBottom),
      },
      containers,
      panels,
      items,
    };
  });

  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    mermaid: {
      total: document.querySelectorAll(".mermaid").length,
      rendered: [...document.querySelectorAll(".mermaid")].filter((m) => m.querySelector("svg")).length,
    },
    slides,
  };
})();
