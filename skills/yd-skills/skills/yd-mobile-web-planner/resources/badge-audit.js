/*
 * badge-audit.js — 렌더된 화면설계서에서 pointer-badge 가 실제로 무엇을 가리키는지 잰다.
 *
 * 배지는 `position:absolute; top:<추정>px` 로 놓이는데, 목업은 `transform:scale(0.9)`
 * (목업 1개) 또는 `zoom:0.9`(2개 이상)로 축소되고 콘텐츠 높이는 렌더해야 정해진다.
 * 그래서 인라인 top 값만 보고는 배지가 의도한 요소 옆에 있는지 알 수 없다 —
 * 정적 검사(check_badge_alignment.py)로는 겹침·순서 역전까지가 한계다.
 *
 * 사용법: 산출물 HTML 을 브라우저로 열고(파일 경로 또는 로컬 서버) 개발자도구
 * 콘솔이나 에이전트의 브라우저 실행 도구에 이 파일 내용을 그대로 붙여 실행한다.
 * 반환값의 `misaligned` 가 비어 있어야 한다.
 *
 *   - misaligned[].gap: 배지 상단과 가장 가까운 콘텐츠 블록 상단의 거리(px, 목업
 *     좌표계). 임계값 22px 는 배지 높이(24px)에서 온다 — 그보다 멀면 어떤 블록과도
 *     같은 줄에 있지 않다는 뜻이다.
 *   - fixes[]: 인라인 top 교정 제안. 배지는 타깃 블록 "바로 앞" 에 두는 관례이므로
 *     next sibling 을 타깃으로 보고, **배지 자신의 인라인 top 좌표계**(positioned
 *     ancestor 기준 · scale/zoom 보정)로 환산한 suggestedTop 을 준다. 부분 목업
 *     (바텀시트)처럼 배지의 좌표 원점이 mock-body 상단이 아닌 경우에도 그대로
 *     쓸 수 있는 값이다 — `measured / 0.9` 수동 환산은 이 경우 틀린다 (이슈 #72).
 *
 * 고칠 때는 반환값을 JSON 파일로 저장해 `scripts/apply_badge_audit.py` 에 넘긴다.
 * 인라인 top 을 손으로 되돌리지 않는다.
 */
(() => {
  const GAP_LIMIT = 22;
  const FIX_TOLERANCE = 3; // 이보다 작은 차이는 렌더 오차로 보고 제안하지 않는다
  const misaligned = [];
  const fixes = [];
  const summary = { slides: 0, badges: 0, mermaidRendered: 0, mermaidTotal: 0 };

  document.querySelectorAll(".mermaid").forEach((m) => {
    summary.mermaidTotal += 1;
    if (m.querySelector("svg")) summary.mermaidRendered += 1;
  });

  document.querySelectorAll(".ppt-slide").forEach((slide) => {
    const no = (slide.querySelector(".ppt-top-no")?.textContent || "").trim();
    if (!/^NO\.\s*09\./.test(no)) return;
    summary.slides += 1;
    const slideNo = no.replace(/^NO\.\s*/, "");

    const containers = slide.querySelectorAll(
      ".mock-body, .mock-header, .mock-footer, .mock-footer-pill");
    containers.forEach((body, containerIndex) => {
      const rect = body.getBoundingClientRect();
      // scale(0.9)·zoom(0.9) 모두 rect(시각) / offsetWidth(레이아웃) 비율로 잡힌다.
      const scale = body.offsetWidth ? rect.width / body.offsetWidth : 1;
      // 스크롤된 목업에서도 좌표가 흔들리지 않게 scrollTop 을 더해 문서 좌표로 환산한다.
      const toLocal = (el) =>
        Math.round(el.getBoundingClientRect().top - rect.top + body.scrollTop * scale);

      const blocks = [...body.querySelectorAll("*")]
        .filter((el) => !el.classList.contains("pointer-badge") && el.offsetHeight > 10)
        .map(toLocal);

      body.querySelectorAll(".pointer-badge").forEach((badge) => {
        summary.badges += 1;
        const top = toLocal(badge);
        const gap = blocks.length ? Math.min(...blocks.map((b) => Math.abs(b - top))) : Infinity;
        if (body.classList.contains("mock-body") && gap > GAP_LIMIT) {
          misaligned.push({
            slide: no,
            mock: containerIndex,
            badge: badge.textContent.trim(),
            measuredTop: top,
            gap,
          });
        }

        // ---- 교정 제안 ----
        const styleTop = /top:\s*(-?\d+(?:\.\d+)?)px/.exec(badge.getAttribute("style") || "");
        const target = badge.nextElementSibling;
        if (!styleTop || !target) return;
        const inlineTop = parseFloat(styleTop[1]);
        // 배지→타깃의 시각 거리(rect 차)를 scale 로 되돌리면 인라인 좌표계의 보정량이
        // 된다. 배지와 타깃이 같은 positioned ancestor 아래에 있으므로 원점이 어디든
        // (mock-body 상단이든 바텀시트 내부든) 상대 보정은 항상 옳다.
        const delta = (target.getBoundingClientRect().top - badge.getBoundingClientRect().top) / scale;
        const suggestedTop = Math.round(inlineTop + delta);
        if (Math.abs(suggestedTop - inlineTop) > FIX_TOLERANCE) {
          fixes.push({ slide: slideNo, label: badge.textContent.trim(), inlineTop, suggestedTop });
        }
      });
    });
  });

  return { scale: 0.9, summary, misaligned, fixes };
})();
