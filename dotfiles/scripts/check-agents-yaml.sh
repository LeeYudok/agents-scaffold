#!/bin/sh
# Validate AGENTS.yaml: structure, YAML implicit-type traps, graph integrity, paths.
# Generic version from the agents-yaml skill - copy it to <repo>/scripts/ unchanged.
# Repo-specific top-level keys go under an "x-" prefix instead of editing this file.
#
# Usage: scripts/check-agents-yaml.sh [path/to/AGENTS.yaml]
# Exit code 0 = OK, 1 = problems found. Requires python3 + PyYAML.

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)
FILE="${1:-${BASE_DIR}/AGENTS.yaml}"

exec python3 - "$FILE" "$BASE_DIR" <<'EOF'
import datetime
import os
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("[FAIL] PyYAML is not installed (pip install pyyaml)")
    sys.exit(1)

path, base = sys.argv[1], sys.argv[2]
errors = []

try:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
except (OSError, yaml.YAMLError) as e:
    print(f"[FAIL] cannot load {path}: {e}")
    sys.exit(1)

if not isinstance(doc, dict):
    print("[FAIL] top level must be a mapping")
    sys.exit(1)

# 1. Top-level keys: an indentation slip usually surfaces as an unknown key here.
#    Repo-specific sections use an "x-" prefix (x-deliverables, x-catalog ...).
TOP_KEYS = {
    "schema_version", "meta", "team", "environments", "nodes", "edges", "ports",
    "commands", "secret_files", "secret_facts", "env_keys", "policies",
    "known_issues", "docs", "runtime_facts", "verifications", "corrections",
    "procedures",
}
REQUIRED = {"schema_version", "meta", "nodes", "edges"}
for k in sorted(set(doc) - TOP_KEYS):
    if not str(k).startswith("x-"):
        errors.append(f"unknown top-level key '{k}' (indentation slip? use an x- prefix for custom sections)")
for k in sorted(REQUIRED - set(doc)):
    errors.append(f"missing top-level key '{k}'")

# 2. Implicit-type traps: unquoted dates/versions silently change type
#    (2026-09-24 -> date, 1.10 -> float 1.1, 0600 -> int).
STRING_KEYS = {
    "schema_version", "updated", "recorded", "version", "sha256", "id", "from",
    "to", "rel", "type", "path", "summary", "source", "rule", "mode", "date",
    "checked", "verified", "verified_at", "schedule",
}

def walk(node, where):
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{where}.{k}" if where else str(k)
            if isinstance(v, (datetime.date, datetime.datetime)):
                errors.append(f"{here}: parsed as date ({v}); quote it")
            elif k in STRING_KEYS and v is not None and not isinstance(v, str):
                errors.append(f"{here}: expected string, got {type(v).__name__} ({v!r}); quote it")
            walk(v, here)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, (datetime.date, datetime.datetime)):
                errors.append(f"{where}[{i}]: parsed as date ({v}); quote it")
            walk(v, f"{where}[{i}]")

walk(doc, "")

# 3. Graph integrity: unique node ids, every edge endpoint is a node.
nodes = [n for n in (doc.get("nodes") or []) if isinstance(n, dict)]
ids = [n.get("id") for n in nodes]
for n in nodes:
    if not n.get("id"):
        errors.append(f"node without id: {n.get('label') or n}")
for dup in sorted({i for i in ids if i and ids.count(i) > 1}):
    errors.append(f"duplicate node id '{dup}'")
id_set = set(ids)
for i, e in enumerate(doc.get("edges") or []):
    for side in ("from", "to"):
        if e.get(side) not in id_set:
            errors.append(f"edges[{i}].{side}: unknown node '{e.get(side)}'")

# 4. Ports must be integers.
for n in nodes:
    if "port" in n and not isinstance(n["port"], int):
        errors.append(f"node '{n.get('id')}': port must be int")
for i, p in enumerate(doc.get("ports") or []):
    if isinstance(p, dict) and not isinstance(p.get("port"), int):
        errors.append(f"ports[{i}]: port must be int")

# 5. Repo-relative paths must exist. Absolute, home (~), URL, placeholder and
#    descriptive values (spaces, parentheses) are skipped.
def is_repo_path(p):
    return (isinstance(p, str) and p and not p.startswith(("/", "~", "-"))
            and "://" not in p and " " not in p and "(" not in p and "<" not in p
            and "*" not in p)

def ignored(p):
    """Build outputs, venvs and local installs are gitignored and only exist
    after a build. They are legitimate references, so they are not required."""
    try:
        return subprocess.run(["git", "-C", base, "check-ignore", "-q", "--no-index", p],
                              capture_output=True).returncode == 0
    except OSError:
        return False

def check_path(p, where):
    if is_repo_path(p) and not os.path.exists(os.path.join(base, p)) and not ignored(p):
        errors.append(f"{where}: path not found '{p}'")

PATH_KEYS = {"path", "module", "files", "unit", "seed", "migrations", "static_docs",
             "llm_entry", "rules", "script", "version_file", "decisions_log",
             "confidential_subdir", "validator", "reuses", "source_paths"}

def walk_paths(node, where, in_node):
    if isinstance(node, dict):
        for k, v in node.items():
            here = f"{where}.{k}"
            if in_node and k in PATH_KEYS:
                for p in (v if isinstance(v, list) else [v]):
                    check_path(p, here)
            else:
                walk_paths(v, here, in_node)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_paths(v, f"{where}[{i}]", in_node)

for n in nodes:
    walk_paths(n, f"node '{n.get('id')}'", True)
walk_paths(doc.get("meta") or {}, "meta", True)
for sf in doc.get("secret_files") or []:
    if isinstance(sf, dict) and sf.get("host", "local") == "local":
        check_path(sf.get("path"), "secret_files")
for key in ("policies", "known_issues"):
    for item in doc.get(key) or []:
        if isinstance(item, dict):
            check_path(item.get("source"), f"{key} '{item.get('id')}'.source")
            for p in item.get("files") or []:
                check_path(p, f"{key} '{item.get('id')}'.files")
for d in doc.get("docs") or []:
    check_path(d.get("path") if isinstance(d, dict) else d, "docs")

# 6. Commands: when the program is a repo file (its first path segment is a
#    top-level entry of the repo), that file must exist.
top_entries = set(os.listdir(base))

def walk_cmds(node, where):
    if isinstance(node, dict):
        for k, v in node.items():
            walk_cmds(v, f"{where}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_cmds(v, f"{where}[{i}]")
    elif isinstance(node, str):
        words = node.split()
        if not words:
            return
        tok = words[1] if words[0] in ("python3", "python", "node", "sh", "bash", "uv") and len(words) > 1 else words[0]
        tok = tok[2:] if tok.startswith("./") else tok
        if "/" in tok and tok.split("/")[0] in top_entries:
            check_path(tok, f"commands{where}")

walk_cmds(doc.get("commands") or {}, "")

if errors:
    for e in errors:
        print(f"[FAIL] {e}")
    print(f"{len(errors)} problem(s) in {path}")
    sys.exit(1)
print(f"[OK] {path}: {len(ids)} nodes, {len(doc.get('edges') or [])} edges, "
      f"{len(doc.get('ports') or [])} ports, {len(doc.get('policies') or [])} policies")
EOF
