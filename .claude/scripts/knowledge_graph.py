#!/usr/bin/env python3
""".claude knowledge-ecosystem graph generator — stdlib only (no xml/pyexpat; keep it that way).

Scans AGENTS.md + .claude/{rules,memory,agents,skills,commands,workflows} and extracts
nodes (files) plus three kinds of edges into a self-contained HTML dashboard:
  1. Markdown relative links [text](path) — explicit references ("broken link" if the target is missing)
  2. Wiki links [[name]]                 — memory-to-memory links (matched by frontmatter name/filename)
  3. Shared issue numbers #N             — two or more files mentioning the same issue connect via an issue node

Usage:
  python3 .claude/scripts/knowledge_graph.py            # writes docs/knowledge-graph.html
  python3 .claude/scripts/knowledge_graph.py --check    # exit 1 on broken links (link checker)
  python3 .claude/scripts/knowledge_graph.py --out <path>
"""
import argparse
import html
import json
import os
import re
import sys

# this script lives at .claude/scripts/ — repo root is two levels up
REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# scan targets: (repo-relative directory, node type)
SCAN_DIRS = [
    (".claude/rules", "rule"),
    (".claude/memory", "memory"),
    (".claude/agents", "agent"),
    (".claude/skills", "skill"),
    (".claude/commands", "command"),
    (".claude/workflows", "workflow"),
]
ROOT_DOCS = [("AGENTS.md", "root")]

MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")
WIKI_LINK = re.compile(r"\[\[([a-z0-9-]+)\]\]")
ISSUE_REF = re.compile(r"#(\d{2,4})\b")
PERSONAL_MEMORY = re.compile(r"^user_.*\.md$")  # gitignored per-developer memory
FRONT_NAME = re.compile(r"^name:\s*(\S+)", re.M)
FRONT_DESC = re.compile(r"^description:\s*(.+)$", re.M)


def rel(path):
    return os.path.relpath(path, REPO).replace(os.sep, "/")


def collect_files():
    """List of scan-target files as [(relative path, type)]."""
    files = []
    for root_doc, typ in ROOT_DOCS:
        p = os.path.join(REPO, root_doc)
        if os.path.exists(p):
            files.append((root_doc, typ))
    for d, typ in SCAN_DIRS:
        base = os.path.join(REPO, d)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in ("observations", "archive", ".git")]
            for fn in sorted(filenames):
                if fn.endswith((".md", ".js")):
                    files.append((rel(os.path.join(dirpath, fn)), typ))
    return files


def memory_subtype(path):
    base = os.path.basename(path)
    for prefix in ("project", "feedback", "reference", "user", "instinct"):
        if base.startswith(prefix + "_"):
            return prefix
    return "memory"


def build_graph():
    files = collect_files()
    known = {p for p, _ in files}
    nodes, edges, broken = [], [], []
    issue_mentions = {}  # issue -> set(path)
    name_to_path = {}    # frontmatter name -> path

    texts = {}
    for path, typ in files:
        try:
            with open(os.path.join(REPO, path), encoding="utf-8") as f:
                texts[path] = f.read()
        except OSError:
            texts[path] = ""

    for path, typ in files:
        m = FRONT_NAME.search(texts[path][:400])
        if m:
            name_to_path[m.group(1)] = path

    for path, typ in files:
        text = texts[path]
        desc_match = FRONT_DESC.search(text[:600])
        label = os.path.basename(path)
        # SKILL.md / README.md filenames are tautological — label with the directory name
        if re.sub(r"\.(md|js)$", "", label) in ("SKILL", "README"):
            parent = os.path.basename(os.path.dirname(path))
            label = parent if label.startswith("SKILL") else f"{parent}/README"
        subtype = memory_subtype(path) if typ == "memory" else typ
        nodes.append({
            "id": path,
            "label": re.sub(r"\.(md|js)$", "", label),
            "type": subtype,
            "desc": html.unescape(desc_match.group(1).strip().strip('"')) if desc_match else "",
        })

        # 1. markdown relative links (after stripping code spans and HTML comments)
        stripped = re.sub(r"```.*?```", "", text, flags=re.S)
        stripped = re.sub(r"`[^`\n]*`", "", stripped)
        stripped = re.sub(r"<!--.*?-->", "", stripped, flags=re.S)
        for lm in MD_LINK.finditer(stripped):
            target = lm.group(2).split("#")[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = rel(os.path.normpath(os.path.join(REPO, os.path.dirname(path), target)))
            if resolved in known:
                edges.append({"from": path, "to": resolved, "kind": "link"})
            elif os.path.exists(os.path.join(REPO, resolved)):
                continue  # a real file outside the graph (code etc.) — skip, no node
            elif PERSONAL_MEMORY.match(os.path.basename(resolved)):
                # user_*.md is gitignored per-developer memory (see .claude/.gitignore).
                # MEMORY.md links to it legitimately; its absence is by design, not breakage.
                continue
            else:
                broken.append({"from": path, "target": target})

        # 2. wiki links
        for wm in WIKI_LINK.finditer(stripped):
            target = name_to_path.get(wm.group(1))
            if target and target != path:
                edges.append({"from": path, "to": target, "kind": "wiki"})

        # 3. issue mentions
        for im in ISSUE_REF.finditer(text):
            issue_mentions.setdefault(im.group(1), set()).add(path)

    # issue nodes: only when shared by two or more files (noise control)
    for issue, paths in sorted(issue_mentions.items(), key=lambda x: int(x[0])):
        if len(paths) < 2:
            continue
        nid = f"issue:{issue}"
        nodes.append({"id": nid, "label": f"#{issue}", "type": "issue", "desc": f"issue shared by {len(paths)} documents"})
        for p in sorted(paths):
            edges.append({"from": p, "to": nid, "kind": "issue"})

    # de-duplicate edges
    seen, uniq = set(), []
    for e in edges:
        key = (e["from"], e["to"], e["kind"])
        if key not in seen:
            seen.add(key)
            uniq.append(e)
    return nodes, uniq, broken


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{PROJECT_NAME}} .claude knowledge graph</title>
<style>
  :root { --bg:#fafafa; --fg:#1a1a1a; --muted:#6b7280; --panel:#ffffff; --border:#e5e7eb; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#111418; --fg:#e5e7eb; --muted:#9ca3af; --panel:#1a1f26; --border:#2d333c; }
  }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--fg); font:14px/1.5 -apple-system,sans-serif; display:flex; height:100vh; overflow:hidden; }
  #canvas { flex:1; cursor:grab; }
  #side { width:320px; border-left:1px solid var(--border); background:var(--panel); padding:16px; overflow-y:auto; }
  h1 { font-size:15px; margin-bottom:4px; }
  .sub { color:var(--muted); font-size:12px; margin-bottom:12px; }
  .legend { display:flex; flex-wrap:wrap; gap:6px 12px; margin-bottom:14px; font-size:12px; }
  .legend span { display:inline-flex; align-items:center; gap:5px; color:var(--muted); }
  .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
  #detail { border-top:1px solid var(--border); padding-top:12px; font-size:13px; }
  #detail .path { font-family:ui-monospace,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  #detail .desc { margin-top:8px; }
  #detail ul { margin:8px 0 0 16px; font-size:12px; color:var(--muted); }
  .broken { margin-top:14px; border-top:1px solid var(--border); padding-top:10px; font-size:12px; }
  .broken b { color:#dc2626; }
</style>
</head>
<body>
<canvas id="canvas"></canvas>
<aside id="side">
  <h1>{{PROJECT_NAME}} .claude knowledge graph</h1>
  <div class="sub">__STATS__ · drag to pan, wheel to zoom, click a node for details</div>
  <div class="legend">__LEGEND__</div>
  <div id="detail"><span class="sub">Click a node.</span></div>
  <div class="broken">__BROKEN__</div>
</aside>
<script>
const DATA = __DATA__;
const COLORS = {rule:'#2563eb', reference:'#059669', feedback:'#d97706', project:'#7c3aed',
  user:'#6b7280', instinct:'#0d9488', memory:'#059669', agent:'#db2777', skill:'#0891b2', command:'#ca8a04',
  workflow:'#dc2626', root:'#111827', issue:'#9ca3af'};
const ROOTCOLOR = matchMedia('(prefers-color-scheme: dark)').matches ? '#e5e7eb' : '#111827';
COLORS.root = ROOTCOLOR;
const cv = document.getElementById('canvas'), ctx = cv.getContext('2d');
let W, H, scale = 1, ox = 0, oy = 0;
function resize(){ W = cv.width = cv.clientWidth * devicePixelRatio; H = cv.height = cv.clientHeight * devicePixelRatio; }
addEventListener('resize', () => { resize(); });
const nodes = DATA.nodes.map((n,i) => ({...n,
  x: Math.cos(i*2.399963)* (120+8*Math.sqrt(i)), y: Math.sin(i*2.399963)*(120+8*Math.sqrt(i)), vx:0, vy:0,
  r: n.type==='issue'?5:(n.type==='root'?12:8)}));
const byId = Object.fromEntries(nodes.map(n=>[n.id,n]));
const edges = DATA.edges.filter(e=>byId[e.from]&&byId[e.to]);
const deg = {}; edges.forEach(e=>{deg[e.from]=(deg[e.from]||0)+1; deg[e.to]=(deg[e.to]||0)+1;});
nodes.forEach(n=>{ if(n.type!=='issue') n.r = Math.min(14, 7 + (deg[n.id]||0)*0.6); });
let selected = null, dragging = null, panning = false, px=0, py=0;
function step(){
  for(let i=0;i<nodes.length;i++) for(let j=i+1;j<nodes.length;j++){
    const a=nodes[i], b=nodes[j]; let dx=b.x-a.x, dy=b.y-a.y;
    let d2=dx*dx+dy*dy||1; if(d2<90000){ const f=1800/d2; const d=Math.sqrt(d2);
      dx/=d; dy/=d; a.vx-=dx*f; a.vy-=dy*f; b.vx+=dx*f; b.vy+=dy*f; } }
  edges.forEach(e=>{ const a=byId[e.from], b=byId[e.to];
    const dx=b.x-a.x, dy=b.y-a.y, d=Math.sqrt(dx*dx+dy*dy)||1, f=(d-90)*0.004;
    a.vx+=dx/d*f; a.vy+=dy/d*f; b.vx-=dx/d*f; b.vy-=dy/d*f; });
  nodes.forEach(n=>{ n.vx-=n.x*0.0008; n.vy-=n.y*0.0008;
    if(n!==dragging){ n.x+=n.vx*=0.85; n.y+=n.vy*=0.85; } });
}
function draw(){
  ctx.setTransform(1,0,0,1,0,0); ctx.clearRect(0,0,W,H);
  ctx.setTransform(scale*devicePixelRatio,0,0,scale*devicePixelRatio,
    W/2+ox*devicePixelRatio, H/2+oy*devicePixelRatio);
  edges.forEach(e=>{ const a=byId[e.from], b=byId[e.to];
    ctx.strokeStyle = e.kind==='issue' ? 'rgba(150,150,150,0.18)' :
      e.kind==='wiki' ? 'rgba(5,150,105,0.4)' : 'rgba(37,99,235,0.35)';
    ctx.lineWidth = e.kind==='issue'?0.6:1.1;
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke(); });
  nodes.forEach(n=>{ ctx.fillStyle = COLORS[n.type]||'#888';
    ctx.beginPath(); ctx.arc(n.x,n.y,n.r,0,7); ctx.fill();
    if(n===selected){ ctx.strokeStyle=ROOTCOLOR; ctx.lineWidth=2; ctx.stroke(); }
    if(scale>0.55 || n.type==='root' || n===selected){
      ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('color');
      ctx.font = (n.type==='root'?'bold 11px':'9.5px') + ' sans-serif';
      ctx.textAlign='center'; ctx.fillText(n.label, n.x, n.y+n.r+11); } });
}
function loop(){ step(); draw(); requestAnimationFrame(loop); }
function pick(mx,my){ const x=(mx*devicePixelRatio-W/2-ox*devicePixelRatio)/(scale*devicePixelRatio),
  y=(my*devicePixelRatio-H/2-oy*devicePixelRatio)/(scale*devicePixelRatio);
  return nodes.find(n=>{const dx=n.x-x,dy=n.y-y;return dx*dx+dy*dy<(n.r+4)**2;}); }
cv.addEventListener('mousedown',e=>{ const n=pick(e.offsetX,e.offsetY);
  if(n){ dragging=n; select(n);} else { panning=true; } px=e.offsetX; py=e.offsetY; });
addEventListener('mousemove',e=>{ const dx=e.offsetX-px, dy=e.offsetY-py; px=e.offsetX; py=e.offsetY;
  if(dragging){ dragging.x+=dx/scale; dragging.y+=dy/scale; }
  else if(panning){ ox+=dx; oy+=dy; } });
addEventListener('mouseup',()=>{ dragging=null; panning=false; });
cv.addEventListener('wheel',e=>{ e.preventDefault(); scale=Math.max(0.25,Math.min(3,scale*(e.deltaY<0?1.1:0.9))); },{passive:false});
function select(n){ selected=n; const d=document.getElementById('detail');
  const out = edges.filter(e=>e.from===n.id).map(e=>byId[e.to].label);
  const inn = edges.filter(e=>e.to===n.id).map(e=>byId[e.from].label);
  d.innerHTML = '<b>'+n.label+'</b> <span class="sub">('+n.type+')</span>'+
    '<div class="path">'+n.id+'</div>'+
    (n.desc?'<div class="desc">'+n.desc+'</div>':'')+
    (out.length?'<div style="margin-top:8px">→ references '+out.length+'</div><ul><li>'+out.join('</li><li>')+'</li></ul>':'')+
    (inn.length?'<div style="margin-top:8px">← referenced by '+inn.length+'</div><ul><li>'+inn.join('</li><li>')+'</li></ul>':''); }
resize(); loop();
</script>
</body>
</html>
"""

TYPE_LABELS = [
    ("root", "root (AGENTS/CLAUDE)"), ("rule", "rules"), ("reference", "memory:reference"),
    ("feedback", "memory:feedback"), ("project", "memory:project"), ("instinct", "memory:instinct"),
    ("agent", "agents"), ("skill", "skills"), ("command", "commands"), ("workflow", "workflows"),
    ("issue", "issue hubs"),
]
LEGEND_COLORS = {
    "root": "#111827", "rule": "#2563eb", "reference": "#059669", "feedback": "#d97706",
    "project": "#7c3aed", "instinct": "#0d9488", "agent": "#db2777", "skill": "#0891b2",
    "command": "#ca8a04", "workflow": "#dc2626", "issue": "#9ca3af",
}


def render_html(nodes, edges, broken):
    present = {n["type"] for n in nodes}
    legend = "".join(
        f'<span><i class="dot" style="background:{LEGEND_COLORS[t]}"></i>{label}</span>'
        for t, label in TYPE_LABELS if t in present
    )
    stats = f"{len(nodes)} nodes · {len(edges)} edges"
    if broken:
        items = "".join(f"<li>{html.escape(b['from'])} → {html.escape(b['target'])}</li>" for b in broken)
        broken_html = f"<b>{len(broken)} broken links</b><ul>{items}</ul>"
    else:
        broken_html = '<span class="sub">no broken links</span>'
    return (HTML_TEMPLATE
            .replace("__DATA__", json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False))
            .replace("__STATS__", stats)
            .replace("__LEGEND__", legend)
            .replace("__BROKEN__", broken_html))


def main():
    parser = argparse.ArgumentParser(description="generate the .claude knowledge graph")
    parser.add_argument("--out", default=os.path.join(REPO, "docs", "knowledge-graph.html"))
    parser.add_argument("--check", action="store_true", help="exit 1 on broken links (no HTML output)")
    args = parser.parse_args()

    nodes, edges, broken = build_graph()
    if args.check:
        for b in broken:
            print(f"broken link: {b['from']} -> {b['target']}")
        print(f"{len(nodes)} nodes · {len(edges)} edges · {len(broken)} broken links")
        sys.exit(1 if broken else 0)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render_html(nodes, edges, broken))
    print(f"wrote {rel(args.out)} — {len(nodes)} nodes · {len(edges)} edges · {len(broken)} broken links")


if __name__ == "__main__":
    main()
