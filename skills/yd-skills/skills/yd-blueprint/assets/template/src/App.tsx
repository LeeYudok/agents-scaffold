import { useEffect, useMemo, useState } from "react";
import type { JSX } from "react";
import { parseBlueprint, summarize } from "./blueprint";
import type { Blueprint, EdgeType, Priority, State } from "./blueprint";
import { Diagram } from "./Diagram";

const files = import.meta.glob("../data/*.jsonl", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;
const parsed = parseBlueprint(
  Object.entries(files).map(([name, text]) => ({ name: name.replace("../", ""), text })),
);

const stateLabel: Record<State, string> = {
  done: "구현",
  partial: "부분",
  missing: "미구현",
};

// 화면의 CSS 변수 값과 svg 규칙을 박아 넣어, 내려받은 파일을 따로 열어도 같은 모양이 되게 한다.
function exportSvg(title: string) {
  const svg = document.querySelector<SVGSVGElement>(".diagram-wrap svg");
  if (!svg) return;
  const root = getComputedStyle(document.documentElement);
  const tokens = ["--background", "--foreground", "--card", "--muted-foreground", "--primary", "--border", "--success", "--warning", "--destructive", "--write"]
    .map((name) => `${name}:${root.getPropertyValue(name).trim()}`)
    .join(";");
  const rules = [...document.styleSheets]
    .flatMap((sheet) => {
      try {
        return [...sheet.cssRules];
      } catch {
        return [];
      }
    })
    .filter((rule): rule is CSSStyleRule => rule instanceof CSSStyleRule && rule.selectorText.startsWith("svg "))
    .map((rule) => rule.cssText)
    .join("\n");
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const view = svg.viewBox.baseVal;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  clone.setAttribute("width", String(view.width));
  clone.setAttribute("height", String(view.height));
  clone.removeAttribute("style");
  const style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = `svg{${tokens};background:var(--background);font-family:system-ui,sans-serif}\n${rules}`;
  clone.prepend(style);
  const url = URL.createObjectURL(
    new Blob([new XMLSerializer().serializeToString(clone)], { type: "image/svg+xml" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title}.svg`;
  link.click();
  URL.revokeObjectURL(url);
}

const lineLabel: Record<EdgeType | "group", string> = {
  flow: "흐름",
  write: "쓰기",
  boundary: "경계 · 미연결",
  group: "배포 경계",
};

// 맨 위 수치 한 줄. 데이터에서 세고, 0 인 항목은 적지 않는다.
function Stats({ blueprint }: { blueprint: Blueprint }) {
  const { states, open } = summarize(blueprint);
  const parts: JSX.Element[] = [];
  if (blueprint.nodes.length) {
    const detail = (["done", "partial", "missing"] as State[])
      .filter((state) => states[state])
      .map((state) => `${stateLabel[state]} ${states[state]}`)
      .join(" · ");
    parts.push(
      <a key="nodes" href="#architecture">
        구성요소 <strong>{blueprint.nodes.length}</strong> <span>{detail}</span>
      </a>,
    );
  }
  if (blueprint.gaps.length) {
    const total = open.P0 + open.P1 + open.P2;
    const detail = (["P0", "P1", "P2"] as Priority[])
      .filter((priority) => open[priority])
      .map((priority) => `${priority} ${open[priority]}`)
      .join(" · ");
    parts.push(
      <a key="gaps" href="#gaps">
        남은 작업 {total ? <strong>{total}</strong> : <strong>없음</strong>} {detail && <span>{detail}</span>}
      </a>,
    );
  }
  return parts.length ? <p className="stats">{parts}</p> : null;
}

// 도면에 실제로 쓰인 선·상자 종류만 보인다.
function LineLegend({ blueprint }: { blueprint: Blueprint }) {
  const kinds = new Set<EdgeType | "group">(blueprint.edges.map((edge) => edge.type || "flow"));
  if (blueprint.groups.length) kinds.add("group");
  const order: (EdgeType | "group")[] = ["flow", "write", "boundary", "group"];
  return (
    <>
      {order
        .filter((kind) => kinds.has(kind))
        .map((kind) => (
          <span key={kind} className={`line ${kind}`}>
            {lineLabel[kind]}
          </span>
        ))}
    </>
  );
}

function Badge({ state }: { state: State }) {
  return <span className={`badge state-${state}`}>{stateLabel[state]}</span>;
}

function useHashEffects(blueprint: Blueprint, select: (id: string) => void) {
  useEffect(() => {
    const reveal = () => {
      const id = decodeURIComponent(location.hash.slice(1));
      if (!id) return;
      const target = document.getElementById(id);
      if (target instanceof HTMLDetailsElement) target.open = true;
      if (id.startsWith("node-") && blueprint.nodes.some((n) => `node-${n.id}` === id))
        select(id.slice(5));
    };
    reveal();
    window.addEventListener("hashchange", reveal);
    return () => window.removeEventListener("hashchange", reveal);
  }, [blueprint, select]);
  // 인쇄는 종이 모드로 접힌 상세를 모두 펼친다.
  useEffect(() => {
    let restore: { paper: string | undefined; open: boolean[] } | null = null;
    const before = () => {
      restore = {
        paper: document.documentElement.dataset.paper,
        open: [...document.querySelectorAll("details")].map((d) => d.open),
      };
      document.documentElement.dataset.paper = "true";
      document.querySelectorAll("details").forEach((d) => (d.open = true));
    };
    const after = () => {
      if (!restore) return;
      document.documentElement.dataset.paper = restore.paper || "false";
      const saved = restore;
      document.querySelectorAll("details").forEach((d, index) => (d.open = saved.open[index]));
    };
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);
}

function Sheet({ blueprint }: { blueprint: Blueprint }) {
  // 처음에는 아무것도 고르지 않는다. 첫 상자를 미리 고르면 굵은 테두리가 상태 강조처럼 읽힌다.
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [paper, setPaper] = useState(true);
  useHashEffects(blueprint, setSelected);
  useEffect(() => {
    document.title = blueprint.meta.title;
  }, [blueprint]);
  useEffect(() => {
    document.documentElement.dataset.paper = String(paper);
  }, [paper]);
  const dimmed = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return new Set<string>();
    return new Set(
      blueprint.nodes.filter((n) => !JSON.stringify(n).toLowerCase().includes(q)).map((n) => n.id),
    );
  }, [blueprint, query]);
  const node = blueprint.nodes.find((n) => n.id === selected);
  const sections = [
    blueprint.nodes.length > 0 && { id: "architecture", title: "전체 구조" },
    blueprint.flow.length > 0 && { id: "flow", title: "기록 흐름" },
    blueprint.features.length > 0 && { id: "matrix", title: "구현 현황" },
    blueprint.gaps.length > 0 && { id: "gaps", title: "남은 작업" },
    blueprint.docs.length > 0 && { id: "reference", title: "운영 규칙" },
  ].filter((section): section is { id: string; title: string } => Boolean(section));
  const number = (id: string) => String(sections.findIndex((s) => s.id === id) + 1).padStart(2, "0");
  return (
    <>
      <div className="top">
        <nav aria-label="청사진 목차">
          {sections.map((section) => (
            <a key={section.id} href={`#${section.id}`}>
              {section.title}
            </a>
          ))}
          {(blueprint.meta.links || []).map((link) => (
            <a key={link.href} href={link.href} className="out">
              {link.label}
            </a>
          ))}
        </nav>
        <button type="button" aria-pressed={paper} onClick={() => setPaper((value) => !value)}>
          {paper ? "도면 모드" : "종이 모드"}
        </button>
      </div>
      <main>
        <header>
          {blueprint.meta.eyebrow && <span className="eyebrow">{blueprint.meta.eyebrow}</span>}
          <h1>{blueprint.meta.title}</h1>
          {blueprint.meta.summary && <p>{blueprint.meta.summary}</p>}
          <p className="meta">
            {[...(blueprint.meta.badges || []), `${blueprint.meta.asOf} 기준`, blueprint.meta.basis].filter(Boolean).join(" · ")}
          </p>
          <Stats blueprint={blueprint} />
        </header>
        {blueprint.nodes.length > 0 && (
          <section id="architecture">
            <h2>{number("architecture")} / 전체 구조</h2>
            <div className="toolbar">
              <input
                type="search"
                aria-label="구성요소 검색"
                placeholder="구성요소 검색"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
              <button type="button" className="quiet" onClick={() => setQuery("")}>
                전체 보기
              </button>
              <button type="button" className="quiet" onClick={() => exportSvg(blueprint.meta.title)}>
                SVG 저장
              </button>
              <button type="button" className="quiet" onClick={() => window.print()}>
                인쇄 · PDF
              </button>
              <span className="legend">
                <span>
                  테두리 <span className="state-partial">부분</span> · <span className="state-missing">미구현</span>
                </span>
                <LineLegend blueprint={blueprint} />
              </span>
              <span role="status">
                {query ? `${blueprint.nodes.length - dimmed.size}개 일치` : `${blueprint.nodes.length}개 구성요소`}
              </span>
            </div>
            <div className="workspace">
              <Diagram blueprint={blueprint} selected={selected} dimmed={dimmed} onSelect={setSelected} />
              <aside className="detail" aria-live="polite" aria-atomic="true">
                <small className="muted">선택한 구성요소</small>
                {!node && <p className="muted">도면에서 상자를 고르면 역할과 근거 코드가 여기에 나온다.</p>}
                {node && (
                  <>
                    <h3>
                      {node.title} <Badge state={node.state} />
                    </h3>
                    <p>{node.summary}</p>
                    {node.paths && (
                      <dl>
                        <dt>근거 코드</dt>
                        {node.paths.map((path) => (
                          <dd className="path" key={path}>
                            {path}
                          </dd>
                        ))}
                      </dl>
                    )}
                    {node.next && (
                      <dl>
                        <dt>한계·남은 일</dt>
                        <dd>{node.next}</dd>
                      </dl>
                    )}
                    {node.gap && <a href={`#gap-${node.gap}`}>관련 작업 {node.gap}</a>}
                  </>
                )}
              </aside>
            </div>
          </section>
        )}
        {blueprint.flow.length > 0 && (
          <section id="flow">
            <h2>{number("flow")} / 기록이 만들어지는 순서</h2>
            <ol className="flow">
              {blueprint.flow.map((step) => (
                <li key={step.title}>
                  <strong>{step.title}</strong> {step.body}
                </li>
              ))}
            </ol>
          </section>
        )}
        {blueprint.features.length > 0 && (
          <section id="matrix">
            <h2>{number("matrix")} / 구현 현황</h2>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>기능</th>
                    <th>상태</th>
                    <th>현재 동작</th>
                    <th>남은 범위</th>
                  </tr>
                </thead>
                <tbody>
                  {blueprint.features.map((feature) => (
                    <tr key={feature.name}>
                      <td>{feature.name}</td>
                      <td>
                        <Badge state={feature.state} />
                      </td>
                      <td>{feature.now}</td>
                      <td>{feature.remaining}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
        {blueprint.gaps.length > 0 && (
          <section id="gaps">
            <h2>{number("gaps")} / 남은 작업과 완료 기준</h2>
            {blueprint.gaps.map((gap) => (
              <details key={gap.id} id={`gap-${gap.id}`}>
                <summary>
                  <span className="badge prio">{gap.priority}</span> {gap.id} · {gap.title} <Badge state={gap.state} />
                </summary>
                <dl>
                  <dt>지금</dt>
                  <dd>{gap.now}</dd>
                  <dt>할 일</dt>
                  <dd>{gap.todo}</dd>
                  <dt>완료 기준</dt>
                  <dd>{gap.done}</dd>
                  {gap.paths && (
                    <>
                      <dt>대상</dt>
                      {gap.paths.map((path) => (
                        <dd className="path" key={path}>
                          {path}
                        </dd>
                      ))}
                    </>
                  )}
                </dl>
              </details>
            ))}
          </section>
        )}
        {blueprint.docs.length > 0 && (
          <section id="reference">
            <h2>{number("reference")} / 운영 규칙과 명세</h2>
            {blueprint.docs.map((doc) => (
              <details key={doc.id} id={`doc-${doc.id}`}>
                <summary>{doc.title}</summary>
                {doc.paragraphs.map((paragraph, index) => (
                  <p key={index}>{paragraph}</p>
                ))}
              </details>
            ))}
          </section>
        )}
      </main>
    </>
  );
}

export function App() {
  if (!parsed.blueprint)
    return (
      <main>
        <h1>청사진 데이터 오류</h1>
        <p>data/*.jsonl 을 고친 뒤 저장하면 다시 읽습니다. 같은 검사를 <code>bun run check</code> 로도 할 수 있습니다.</p>
        <ul className="errors">
          {parsed.errors.map((error) => (
            <li key={error}>
              <code>{error}</code>
            </li>
          ))}
        </ul>
      </main>
    );
  return <Sheet blueprint={parsed.blueprint} />;
}
