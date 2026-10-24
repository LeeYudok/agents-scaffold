/*
 * desc-measure.js — 렌더된 화면 상세 슬라이드에서 Description 패널을 실측한다.
 *
 * export_deck.py 의 --editable-desc 가 쓴다. 설명 패널을 PPT 텍스트 상자로
 * 얹으려면 각 항목의 배지 칩과 본문이 슬라이드 안 어디에 있는지 알아야 하는데,
 * 그 위치는 렌더해야 정해진다 (본문 길이에 따라 항목 높이가 달라지고, 항목이
 * 8개를 넘으면 템플릿이 목록을 자동 압축한다).
 *
 * 좌표는 슬라이드 좌상단 기준 px 다. export_deck.py 가 EMU 로 환산한다.
 * 반환값은 슬라이드 하나에 대한 것이며, 설명 패널이 없으면 items 가 빈 배열이다.
 */
(() => {
  const slide = document.querySelector(".ppt-slide");
  if (!slide) return { error: "ppt-slide 없음" };
  const base = slide.getBoundingClientRect();
  const rel = (el) => {
    const r = el.getBoundingClientRect();
    return {
      x: r.left - base.left,
      y: r.top - base.top,
      w: r.width,
      h: r.height,
    };
  };

  // 설명 항목의 본문은 <b>제목</b><br>줄<br>줄 구조다. <br> 로 끊어 줄 배열을
  // 만들고, 첫 줄이 제목인지(=<b> 로 시작하는지)를 함께 돌려준다. <code> 는
  // 컴포넌트명 표기라 본문 줄로 합친다.
  const linesOf = (node) => {
    const out = [];
    let buf = "";
    let boldFirst = false;
    let seenText = false;
    node.childNodes.forEach((child) => {
      if (child.nodeName === "BR") {
        out.push(buf.trim());
        buf = "";
        return;
      }
      const text = (child.textContent || "").replace(/\s+/g, " ");
      if (!seenText && text.trim()) {
        seenText = true;
        boldFirst = child.nodeName === "B" || child.nodeName === "STRONG";
      }
      buf += text;
    });
    if (buf.trim()) out.push(buf.trim());
    return { lines: out.filter(Boolean), boldFirst };
  };

  const items = [];
  slide.querySelectorAll(".ppt-desc-panel .desc-list > li").forEach((li) => {
    const chip = li.querySelector(".desc-num");
    const body = li.querySelector("div");
    if (!chip || !body) return;
    const { lines, boldFirst } = linesOf(body);
    items.push({
      label: chip.textContent.trim(),
      badge: rel(chip),
      text: rel(body),
      lines,
      boldFirst,
    });
  });

  const panel = slide.querySelector(".ppt-desc-panel");
  return {
    slide: { w: base.width, h: base.height },
    hasPanel: Boolean(panel),
    items,
  };
})();
