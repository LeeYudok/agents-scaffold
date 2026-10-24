# scripts/ — repo-local helper scripts

Helper scripts shipped with the template and invoked by commands/skills (these are
**not** hooks — hooks live in `../hooks/` and are wired via `settings.json`).

Included:
- `knowledge_graph.py` — generates `docs/knowledge-graph.html` from the `.claude`
  ecosystem; `--check` mode is a broken-link gate (see the `/knowledge-graph` command).

Conventions: stdlib-only Python (no third-party imports, no xml/pyexpat) or POSIX shell;
keep scripts runnable from the repo root; new scripts get descriptive names.
