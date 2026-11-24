// 네이버 블로그 에디터(SmartEditor ONE)에서 글자 범위에 굵게·색·크기를 입힌다.
// 쓰는 법: `const ITEMS = [];` 줄의 빈 배열을 항목 JSON 으로 바꾼 사본을 .playwright-mcp/ 에 만들고 browser_run_code_unsafe 의 filename 으로 실행한다.
// ITEMS = [{para, text, bold?, color?, size?}] — para 는 그 문단에만 있는 글귀, text 는 강조할 글자.
//   color 는 색상표에 있는 값(예 "#ff0010"), size 는 11·13·15·16·19·24·28·30·34·38 중 하나.
// 반환값의 failed 가 빈 배열이어야 한다. 남으면 그 항목만 담아 다시 돌린다(이미 된 속성은 건너뛴다).
// 에디터는 document.getSelection() 이 비어 있어 Range 의 화면 좌표로 마우스 드래그해 고른다.
// 이미 적용된 속성은 건너뛴다(굵게는 토글이라 두 번 누르면 풀린다). 끝나면 항목마다 읽은 값을 돌려준다.
// 도구 막대 버튼은 본문 위 속성 막대(se-property-toolbar-*)의 것을 누른다. 같은 클래스의 떠 있는 막대 버튼이 따로 있다.
// 글자 크기 선택지는 글자가 "19\n19" 로 읽혀 글자로 못 고른다. data-value="fs19" 로 고른다.
async (page) => {
  const ITEMS = [];
  const f = page.frameLocator("#mainFrame");
  const frame = page.frame({ name: "mainFrame" });
  const hex = (rgb) => { const m = /(\d+),\s*(\d+),\s*(\d+)/.exec(rgb || ""); return m ? "#" + [1, 2, 3].map(i => (+m[i]).toString(16).padStart(2, "0")).join("") : ""; };
  const locate = (it, scroll) => frame.evaluate(({ para, text, scroll }) => {
    const p = [...document.querySelectorAll(".se-component-content .se-text-paragraph")].find(e => e.innerText.includes(para));
    if (!p) return { err: "문단 없음" };
    if (scroll) p.scrollIntoView({ block: "center" });
    const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let acc = ""; const nodes = [];
    while (w.nextNode()) { nodes.push([w.currentNode, acc.length]); acc += w.currentNode.data; }
    const i = acc.indexOf(text); if (i < 0) return { err: "글자 없음" };
    const loc = (pos) => { for (let k = nodes.length - 1; k >= 0; k--) if (pos >= nodes[k][1]) return [nodes[k][0], pos - nodes[k][1]]; };
    const [sn, so] = loc(i), [en0, eo0] = loc(i + text.length - 1);
    const rg = document.createRange(); rg.setStart(sn, so); rg.setEnd(en0, eo0 + 1);
    const rs = [...rg.getClientRects()].filter(x => x.width > 0); const a = rs[0], b = rs[rs.length - 1];
    // 범위 안 모든 글자 노드의 표시 속성을 모은다(중간에 서식이 갈리면 여러 값이 나온다)
    const seen = [];
    for (const [n, start] of nodes) {
      if (start + n.data.length <= i || start >= i + text.length) continue;
      const cs = getComputedStyle(n.parentElement);
      seen.push([cs.color, +cs.fontWeight >= 600, Math.round(parseFloat(cs.fontSize))]);
    }
    return { x1: a.left + 1, y1: a.top + a.height / 2, x2: b.right - 1, y2: b.top + b.height / 2, seen, whole: acc.trim() === text.trim() };
  }, { para: it.para, text: it.text, scroll });
  const select = async (it) => {
    await locate(it, true); await page.waitForTimeout(200);
    const r = await locate(it, false); if (r.err) return r;
    if (r.whole) {
      // 문단 전체는 끝까지 드래그하면 고르기가 풀릴 때가 있다. 세 번 클릭으로 문단을 고른다.
      await page.mouse.click(r.x1 + 15, r.y1, { clickCount: 3 });
    } else {
      await page.mouse.move(r.x1, r.y1); await page.mouse.down();
      await page.mouse.move(r.x2, r.y2, { steps: 10 }); await page.mouse.up();
    }
    await page.waitForTimeout(150);
    return r;
  };
  const state = (r) => ({
    bold: r.seen.every(s => s[1]), colors: [...new Set(r.seen.map(s => hex(s[0])))], sizes: [...new Set(r.seen.map(s => s[2]))],
  });
  const out = [];
  for (const it of ITEMS) {
    let r = await select(it);
    if (r.err) { out.push({ text: it.text.slice(0, 16), err: r.err }); continue; }
    let st = state(r);
    if (it.color && !(st.colors.length === 1 && st.colors[0] === it.color.toLowerCase())) {
      await f.locator("button.se-font-color-toolbar-button.se-property-toolbar-color-picker-button").first().click();
      await f.locator(`.se-property-color-picker-container button[data-color="${it.color}"]`).first().click();
      await page.waitForTimeout(200); r = await select(it);
    }
    if (it.size && !(st.sizes.length === 1 && st.sizes[0] === it.size)) {
      await f.locator("button.se-font-size-code-toolbar-button.se-property-toolbar-label-select-button").first().click();
      await f.locator(`button.se-toolbar-option-text-button[data-value="fs${it.size}"]`).first().click();
      await page.waitForTimeout(200); r = await select(it);
    }
    if (it.bold && !st.bold) {
      await f.locator("button.se-bold-toolbar-button.se-property-toolbar-toggle-button").first().click();
      await page.waitForTimeout(200);
    }
    await page.keyboard.press("ArrowRight");
    const fin = await locate(it, false); const s2 = state(fin);
    const ok = (!it.bold || s2.bold) && (!it.color || (s2.colors.length === 1 && s2.colors[0] === it.color.toLowerCase())) && (!it.size || (s2.sizes.length === 1 && s2.sizes[0] === it.size));
    out.push({ text: it.text.slice(0, 16), ok, ...(ok ? {} : s2) });
  }
  return { total: out.length, failed: out.filter(o => !o.ok), ok: out.filter(o => o.ok).length };
}
