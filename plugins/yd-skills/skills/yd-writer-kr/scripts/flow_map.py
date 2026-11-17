#!/usr/bin/env python3
"""yd-writer-kr 흐름 지도 검증기 (#143).

references/flow.yaml 이 전체 흐름의 원본이다. 이 스크립트는 지도에 빠진 것이 없는지 보고
(--check), 사람이 읽을 references/flow.md 를 지도에서 만든다(--write).

검증하는 것:
  - 모든 단계가 시작에서 닿고 끝으로 이어진다. 갈림에는 조건이 있다.
  - SKILL.md 의 모든 절이 어느 단계에 연결돼 있다.
  - 스크립트의 모든 옵션과 환경변수가 지도에 있다.
  - 스킬 폴더의 모든 파일이 지도에 있고 어느 단계에서 쓰인다.
  - 검사 모드의 절 목록이 금지 표현 파일·Go 엔진과 같다.
  - flow.md 가 지도에서 만든 결과와 같다.

표준 라이브러리만 쓴다. 폐쇄망에서 YAML 라이브러리 없이 돌아야 해서 YAML 의 일부만 읽는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"start": "시작", "step": "단계", "decision": "갈림", "tool": "도구", "gate": "관문", "end": "끝"}
SHELL_VARS = {"HOME", "BASH_SOURCE", "PATH"}  # 셸이 주는 값이라 스킬의 설정이 아니다
RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "~"}


class FlowError(ValueError):
    """flow.yaml 을 읽을 수 없다."""


# ── YAML 일부 읽기 ────────────────────────────────────────


def scalar(text: str, where: str):
    text = text.strip()
    if text.startswith('"'):
        try:
            return json.loads(text)
        except ValueError as e:
            raise FlowError(f"{where}: 큰따옴표 문자열을 읽을 수 없다 ({e})") from e
    if text.startswith("[") and text.endswith("]"):
        return [scalar(part, where) for part in split_commas(text[1:-1]) if part.strip()]
    if not text:
        raise FlowError(f"{where}: 값이 비었다")
    if ": " in text or " #" in text or text[0] in "[{&*!|>%@`'" or text.lower() in RESERVED or text.endswith(":"):
        raise FlowError(f"{where}: 큰따옴표로 감싸야 하는 값이다: {text}")
    return text


def split_commas(text: str) -> list[str]:
    parts, current, quoted, escaped = [], "", False, False
    for ch in text:
        if quoted:
            current += ch
            quoted = escaped or ch != '"'
            escaped = ch == "\\" and not escaped
        elif ch == ",":
            parts.append(current)
            current = ""
        else:
            quoted = ch == '"'
            current += ch
    return [*parts, current]


def split_pair(text: str):
    """'키: 값' 을 가른다. 맵 항목이 아니면 None."""
    if text.startswith('"'):
        end = re.match(r'"(?:[^"\\]|\\.)*"', text)
        if not end or not text[end.end():].startswith(":"):
            return None
        return json.loads(end.group()), text[end.end() + 1:].strip()
    if text.endswith(":"):
        return text[:-1], ""
    key, sep, value = text.partition(": ")
    return (key, value.strip()) if sep else None


def parse_yaml(text: str):
    lines = []
    for number, raw in enumerate(text.splitlines(), 1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise FlowError(f"{number}행: 들여쓰기에 탭을 쓰지 않는다")
        if raw.strip() and not raw.lstrip().startswith("#"):
            lines.append((len(raw) - len(raw.lstrip()), raw.strip(), number))
    value, index = parse_block(lines, 0, lines[0][0] if lines else 0)
    if index != len(lines):
        raise FlowError(f"{lines[index][2]}행: 들여쓰기가 맞지 않는다")
    return value


def parse_block(lines, index, indent):
    if lines[index][1].startswith("- "):
        return parse_list(lines, index, indent)
    return parse_map(lines, index, indent)


def parse_list(lines, index, indent):
    out = []
    while index < len(lines) and lines[index][0] == indent and lines[index][1].startswith("- "):
        _, text, number = lines[index]
        rest = text[2:].strip()
        if split_pair(rest) is None:
            out.append(scalar(rest, f"{number}행"))
            index += 1
            continue
        # '- 키: 값' 은 맵 항목이다. 첫 쌍을 두 칸 안쪽의 줄로 보고 맵으로 읽는다.
        lines[index] = (indent + 2, rest, number)
        item, index = parse_map(lines, index, indent + 2)
        out.append(item)
    return out, index


def parse_map(lines, index, indent):
    out = {}
    while index < len(lines) and lines[index][0] == indent and not lines[index][1].startswith("- "):
        _, text, number = lines[index]
        pair = split_pair(text)
        if pair is None:
            raise FlowError(f"{number}행: '키: 값' 꼴이 아니다")
        key, value = pair
        if key in out:
            raise FlowError(f"{number}행: 키가 겹친다: {key}")
        index += 1
        if value:
            out[key] = scalar(value, f"{number}행")
        elif index < len(lines) and lines[index][0] > indent:
            out[key], index = parse_block(lines, index, lines[index][0])
        else:
            raise FlowError(f"{number}행: {key} 의 값이 없다")
    if index < len(lines) and lines[index][0] > indent:
        raise FlowError(f"{lines[index][2]}행: 들여쓰기가 맞지 않는다")
    return out, index


# ── 실제 스킬에서 읽는 값 ─────────────────────────────────


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def headings(text: str, levels=(2, 3)) -> dict[str, int]:
    """코드 블록 밖의 절 제목과 그 절의 점검 항목(- [ ]) 수."""
    out, fenced, current = {}, False, None
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif fenced:
            continue
        elif (m := re.match(r"(#{1,6}) (.+)", line)):
            current = m.group(2).strip() if len(m.group(1)) in levels else None
            if current:
                out[current] = 0
        elif current and line.startswith("- [ ]"):
            out[current] += 1
    return out


def script_options(path: Path) -> set[str]:
    text = read(path)
    if path.suffix == ".go":
        return set(re.findall(r'arg == "(-[^"]*)"', text))
    found = set()
    for call in re.findall(r"add_argument\(([^\n]*)", text):
        found.update(re.findall(r'"(-[^"]+)"', re.split(r"\b\w+=", call)[0]))
    return found


def script_env(path: Path) -> set[str]:
    text = read(path)
    if path.suffix == ".go":
        return set(re.findall(r'os\.Getenv\("([A-Z0-9_]+)"\)', text))
    if path.suffix == ".py":
        return set(re.findall(r'os\.environ(?:\.get\(|\[)\s*"([A-Z0-9_]+)"', text))
    return set(re.findall(r"\$\{?([A-Z][A-Z0-9_]+)", text)) - SHELL_VARS


def tool_sources(root: Path, tool: dict) -> list[Path]:
    """도구의 옵션과 환경변수를 읽을 파일. source 가 Go 파일이면 같은 폴더의 엔진 파일을 모두 본다."""
    paths = [root / tool["path"]]
    if source := tool.get("source"):
        folder = (root / source).parent
        paths += sorted(p for p in folder.glob("*.go") if not p.name.endswith("_test.go"))
    return paths


def skill_files(root: Path) -> list[str]:
    out = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        hidden = any(part.startswith(".") or part == "__pycache__" for part in rel.parts)
        if path.is_file() and not hidden and path.suffix != ".pyc":
            out.append(rel.as_posix())
    return out


def covers(key: str, file: str) -> bool:
    return file.startswith(key) if key.endswith("/") else file == key


# ── 검증 ──────────────────────────────────────────────────


def load(root: Path = ROOT) -> dict:
    path = root / "references" / "flow.yaml"
    if not path.is_file():
        raise FlowError(f"{path}: 파일이 없다")
    data = parse_yaml(path.read_text(encoding="utf-8"))
    for key in ("flows", "nodes", "tools", "modes", "files"):
        if not isinstance(data.get(key), dict):
            raise FlowError(f"flow.yaml: {key} 맵이 없다")
    return data


def edges(node: dict) -> list[dict]:
    return node.get("next", [])


def reach(starts, step) -> set[str]:
    seen, queue = set(), list(starts)
    while queue:
        current = queue.pop()
        if current not in seen:
            seen.add(current)
            queue.extend(step(current))
    return seen


def graph_problems(data: dict) -> list[str]:
    nodes, flows, out = data["nodes"], data["flows"], []
    stage_flow = {stage: fid for fid, flow in flows.items() for stage in flow.get("stages", [])}
    for nid, node in nodes.items():
        kind, links = node.get("kind"), edges(node)
        if not node.get("title"):
            out.append(f"{nid}: title 이 없다")
        if kind not in KINDS:
            out.append(f"{nid}: kind 는 {'/'.join(KINDS)} 가운데 하나다")
        if node.get("stage") not in stage_flow:
            out.append(f"{nid}: stage '{node.get('stage')}' 가 flows 의 stages 에 없다")
        for edge in links:
            if edge.get("to") not in nodes:
                out.append(f"{nid}: 없는 단계로 간다: {edge.get('to')}")
            if len(links) > 1 and not edge.get("when"):
                out.append(f"{nid}: 갈림인데 {edge.get('to')} 로 가는 조건(when)이 없다")
        if kind == "end" and links:
            out.append(f"{nid}: 끝 단계에 next 가 있다")
        if kind != "end" and not links:
            out.append(f"{nid}: 다음 단계가 없다")
        if kind == "decision" and len(links) < 2:
            out.append(f"{nid}: 갈림인데 갈 곳이 하나다")
        if kind == "gate" and not node.get("pass"):
            out.append(f"{nid}: 관문에 통과 조건(pass)이 없다")
        if kind == "tool" and not set(node.get("uses", [])) & set(data["tools"]):
            out.append(f"{nid}: 도구 단계인데 uses 에 도구가 없다")
    starts = []
    for fid, flow in flows.items():
        start = flow.get("start")
        if nodes.get(start, {}).get("kind") != "start":
            out.append(f"flows.{fid}: start '{start}' 가 시작 단계가 아니다")
        else:
            starts.append(start)
    forward = reach(starts, lambda n: [e["to"] for e in edges(nodes[n]) if e.get("to") in nodes])
    back = {nid: [] for nid in nodes}
    for nid, node in nodes.items():
        for edge in edges(node):
            if edge.get("to") in nodes:
                back[edge["to"]].append(nid)
    finishing = reach([n for n, node in nodes.items() if node.get("kind") == "end"], lambda n: back[n])
    out += [f"{nid}: 어느 시작에서도 닿지 않는다" for nid in nodes if nid not in forward]
    out += [f"{nid}: 끝으로 이어지지 않는다" for nid in nodes if nid not in finishing]
    return out


def doc_problems(data: dict, root: Path) -> list[str]:
    real = headings(read(root / "SKILL.md"))
    mapped = {title: nid for nid, node in data["nodes"].items() for title in node.get("doc", [])}
    out = [f"{nid}: SKILL.md 에 없는 절이다: {title}" for title, nid in mapped.items() if title not in real]
    out += [f"SKILL.md 의 절이 어느 단계에도 없다: {title}" for title in real if title not in mapped]
    return out


def tool_problems(data: dict, root: Path) -> list[str]:
    tools, out = data["tools"], []
    used = {name for node in data["nodes"].values() for name in node.get("uses", [])}
    for tid, tool in tools.items():
        if not (root / tool.get("path", "")).is_file():
            out.append(f"tools.{tid}: path 가 없다: {tool.get('path')}")
            continue
        if not tool.get("run") or not isinstance(tool.get("exit"), dict):
            out.append(f"tools.{tid}: run 과 exit 를 적는다")
        if tid not in used:
            out.append(f"tools.{tid}: 어느 단계에서도 쓰지 않는다")
        sources = tool_sources(root, tool)
        for ref in ("options_from", "env_from"):
            if ref in tool and tool[ref] not in tools:
                out.append(f"tools.{tid}: {ref} 가 없는 도구를 가리킨다: {tool[ref]}")
        if "options_from" not in tool:
            real = set().union(*(script_options(p) for p in sources))
            listed = set(tool.get("options", {}))
            out += [f"tools.{tid}: 지도에 없는 옵션: {name}" for name in sorted(real - listed)]
            out += [f"tools.{tid}: 스크립트에 없는 옵션: {name}" for name in sorted(listed - real)]
        if "env_from" not in tool:
            real = set().union(*(script_env(p) for p in sources))
            listed = set(tool.get("env", {}))
            out += [f"tools.{tid}: 지도에 없는 환경변수: {name}" for name in sorted(real - listed)]
            out += [f"tools.{tid}: 스크립트에 없는 환경변수: {name}" for name in sorted(listed - real)]
    return out


def file_problems(data: dict, root: Path) -> list[str]:
    files, tools, out = data["files"], data["tools"], []
    real = skill_files(root)
    out += [f"files: 지도에 없는 파일: {name}" for name in real if not any(covers(key, name) for key in files)]
    out += [f"files: 없는 파일이다: {key}" for key in files if not any(covers(key, name) for name in real)]
    used = set()
    for nid, node in data["nodes"].items():
        for name in node.get("uses", []):
            if name in tools:
                used.update(v for k, v in tools[name].items() if k in ("path", "source"))
            elif name in files:
                used.add(name)
            else:
                out.append(f"{nid}: uses 가 도구도 파일도 아니다: {name}")
    out += [f"files: 어느 단계에서도 쓰지 않는다: {key}" for key in files
            if not any(covers(key, name) for name in used)]
    return out


def mode_problems(data: dict, root: Path) -> list[str]:
    modes, out = data["modes"], []
    engine = read(root / "go" / "engine.go")
    sections = [h for h in headings(read(root / "references" / "banned-expressions.md"), levels=(2,))
                if h != "참고 문헌"]
    if modes.get("sections") != sections:
        out.append("modes.sections 가 금지 표현 파일의 절 제목과 다르다")
    prose = re.search(r"proseSections = \[\]string\{([^}]*)\}", engine)
    if modes.get("prose_only") != (re.findall(r'"([^"]+)"', prose.group(1)) if prose else None):
        out.append("modes.prose_only 가 Go 엔진의 proseSections 와 다르다")
    noun = re.search(r'nounEnding\s*=\s*"([^"]+)"', engine)
    if modes.get("chat_skips") != [s for s in sections if noun and s.startswith(noun.group(1))]:
        out.append("modes.chat_skips 가 Go 엔진이 채팅에서 건너뛰는 절과 다르다")
    profile = read(root / "go" / "profile.go")
    kinds = re.search(r"var notationChecks = [^{]*\{[^}]*\}\{(.*)\}", profile)
    names = dict(re.findall(r'(kind\w+)\s*=\s*"([^"]+)"', profile))
    real = [names.get(k) for k in re.findall(r"\{(kind\w+),", kinds.group(1))] if kinds else None
    if modes.get("notation") != real:
        out.append("modes.notation 이 Go 엔진의 내장 표기 검사와 다르다")
    return out


def problems(root: Path = ROOT) -> list[str]:
    data = load(root)
    out = graph_problems(data)
    if not out:  # 그래프가 깨지면 아래 검사의 메시지가 뜻을 잃는다
        out += doc_problems(data, root) + tool_problems(data, root) + file_problems(data, root)
        out += mode_problems(data, root)
        if not out and read(root / "references" / "flow.md") != render(data, root):
            out.append("references/flow.md 가 지도와 다르다. flow_map.py --write 로 다시 만든다")
    return out


# ── flow.md 만들기 ────────────────────────────────────────

SHAPES = {"start": '(["{}"])', "end": '(["{}"])', "step": '["{}"]', "decision": '{{"{}"}}',
          "tool": '[["{}"]]', "gate": '{{{{"{}"}}}}'}


def mid(nid: str) -> str:
    # 접두사를 붙인다. style·end 같은 단계 이름은 Mermaid 예약어와 겹친다.
    return "n_" + nid.replace("-", "_")


def label(text: str) -> str:
    return text.replace('"', "#quot;")


def cell(text: str) -> str:
    return text.replace("|", "\\|")


def mermaid(data: dict, fid: str) -> list[str]:
    nodes, flows = data["nodes"], data["flows"]
    flow = flows[fid]
    mine = [nid for nid, node in nodes.items() if node["stage"] in flow["stages"]]
    out = ["```mermaid", "flowchart TD"]
    for number, stage in enumerate(flow["stages"]):
        out.append(f'  subgraph {fid}_{number}["{label(stage)}"]')
        for nid, node in nodes.items():
            if node["stage"] == stage:
                out.append("    " + mid(nid) + SHAPES[node["kind"]].format(label(f"{nid}<br/>{node['title']}")))
        out.append("  end")
    outside = {}
    for nid in mine:
        for edge in edges(nodes[nid]):
            target = edge["to"]
            if target not in mine:
                other = next(f["title"] for f in flows.values() if nodes[target]["stage"] in f["stages"])
                outside[target] = f'  {mid(target)}(["{label(other)}<br/>{target}"])'
            arrow = f'-->|"{label(edge["when"])}"|' if edge.get("when") else "-->"
            out.append(f"  {mid(nid)} {arrow} {mid(target)}")
    return [*out[:2], *sorted(outside.values()), *out[2:], "```"]


def uses_text(data: dict, node: dict) -> str:
    return "<br>".join(f"`{data['tools'][u]['path']}`" if u in data["tools"] else f"`{u}`"
                       for u in node.get("uses", []))


def next_text(node: dict) -> str:
    return "<br>".join(f"`{e['to']}`" + (f" — {e['when']}" if e.get("when") else "") for e in edges(node))


def render(data: dict, root: Path = ROOT) -> str:
    nodes, tools, modes = data["nodes"], data["tools"], data["modes"]
    checks = headings(read(root / "SKILL.md"))
    out = [
        "# yd-writer-kr 흐름 지도", "",
        "<!-- flow_map.py --write 가 flow.yaml 에서 만든 파일이다. 손으로 고치지 않는다. -->", "",
        "요청을 받아 결과를 돌려줄 때까지 거치는 단계를 모두 적었다. 원본은 `flow.yaml` 이다.",
        "단계를 건너뛰지 않으려면 시작 단계부터 화살표를 따라간다. 갈림에서는 조건에 맞는 화살표 하나만 고른다.",
        "", "| 모양 | 뜻 |", "|---|---|",
        "| 둥근 상자 | 시작과 끝 |", "| 네모 | 사람이나 에이전트가 하는 단계 |", "| 마름모 | 갈림. 조건을 보고 한쪽으로 간다 |",
        "| 겹네모 | 스크립트를 돌리는 단계 |", "| 육각형 | 관문. 통과 조건을 채워야 다음으로 간다 |", "",
        f"흐름은 {len(data['flows'])}개, 단계는 {len(nodes)}개다.", "",
    ]
    for fid, flow in data["flows"].items():
        out += [f"## {flow['title']}", "", f"시작 단계는 `{flow['start']}` 다.", "", *mermaid(data, fid), ""]
        for stage in flow["stages"]:
            out += [f"### {stage}", "", "| 단계 | 할 일 | 문서 절 | 쓰는 것 | 다음 |", "|---|---|---|---|---|"]
            for nid, node in nodes.items():
                if node["stage"] != stage:
                    continue
                todo = list(node.get("do", []))
                if node.get("pass"):
                    todo.append(f"**통과 조건**: {node['pass']}")
                docs = [f"{d} ({checks[d]}항목)" if checks.get(d) else d for d in node.get("doc", [])]
                out.append("| " + " | ".join(cell(c) for c in (
                    f"`{nid}`<br>{node['title']}<br>({KINDS[node['kind']]})", "<br>".join(todo),
                    "<br>".join(docs), uses_text(data, node), next_text(node))) + " |")
            out.append("")
    out += ["## 도구", ""]
    for tid, tool in tools.items():
        out += [f"### {tool['title']} — `{tool['path']}`", "", "```bash", tool["run"], "```", ""]
        options = tools[tool["options_from"]]["options"] if "options_from" in tool else tool.get("options", {})
        env = tools[tool["env_from"]]["env"] if "env_from" in tool else tool.get("env", {})
        rows = [("옵션", f"`{k}`", v) for k, v in options.items()]
        rows += [("환경변수", f"`{k}`", v) for k, v in env.items()]
        if "key_file" in tool:
            rows.append(("키 파일", f"`{tool['key_file']}`", "환경변수에 키가 없을 때 읽는다"))
        rows += [("종료 코드", f"`{k}`", v) for k, v in tool["exit"].items()]
        out += ["| 구분 | 이름 | 뜻 |", "|---|---|---|", *("| " + " | ".join(cell(c) for c in row) + " |" for row in rows), ""]
    out += [
        "## 검사기가 모드마다 보는 것", "", "| 절 | 기본 | `--chat` | `--prose` |", "|---|---|---|---|",
        *(f"| {s} | 본다 | {'건너뛴다' if s in modes['chat_skips'] else '본다'} | "
          f"{'본다' if s in modes['prose_only'] else '건너뛴다'} |" for s in modes["sections"]),
        *(f"| 표기 검사: {n} | 프로필이 정한다 | 프로필이 정한다 | 프로필이 정한다 |" for n in modes["notation"]),
        "| 긴 문장 경고 | 본다 | 본다 | 건너뛴다 |", "",
        "`--source` 를 주면 원문 대조를 더한다.", "",
        "| 구분 | 내용 |", "|---|---|",
        f"| 오류 | {cell(modes['source']['errors'])} |", f"| 경고 | {cell(modes['source']['warnings'])} |",
        f"| 줄 수 | {cell(modes['source']['lines'])} |", "",
        "## 파일", "", "| 경로 | 구실 |", "|---|---|",
        *(f"| `{k}` | {cell(v)} |" for k, v in data["files"].items()), "",
        "## 지도를 고칠 때", "",
        "1. `flow.yaml` 을 고친다.",
        "2. `python3 <스킬경로>/scripts/flow_map.py --write` 로 이 파일을 다시 만든다.",
        "3. `python3 <스킬경로>/scripts/flow_map.py --check` 로 빠진 것이 없는지 본다.",
        "",
        "검증은 다음 가운데 하나라도 어긋나면 실패한다.", "",
        "- `SKILL.md` 의 절이 어느 단계에도 연결되지 않았다.",
        "- 스크립트에 있는 옵션이나 환경변수가 지도에 없다.",
        "- 스킬 폴더에 지도가 모르는 파일이 있다.",
        "- 시작에서 닿지 않거나 끝으로 이어지지 않는 단계가 있다.",
        "- 검사 모드의 절 목록이 금지 표현 파일이나 Go 엔진과 다르다.",
        "- 이 파일이 `flow.yaml` 과 다르다.",
    ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="yd-writer-kr 흐름 지도 검증과 flow.md 생성")
    ap.add_argument("--check", action="store_true", help="지도에 빠진 것이 없는지 검증한다 (기본)")
    ap.add_argument("--write", action="store_true", help="flow.yaml 에서 flow.md 를 다시 만든다")
    args = ap.parse_args(argv)
    try:
        if args.write:
            (ROOT / "references" / "flow.md").write_text(render(load(ROOT), ROOT), encoding="utf-8")
        found = problems(ROOT)
    except FlowError as e:
        print(f"flow_map: {e}", file=sys.stderr)
        return 2
    for line in found:
        print(line)
    print(f"흐름 지도: 문제 {len(found)}건")
    return 1 if found else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
