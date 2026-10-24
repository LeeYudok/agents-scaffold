# /knowledge-graph — regenerate & view the .claude knowledge graph

Renders the connection structure of the AGENTS.md ecosystem
(rules · memory · agents · skills · commands · workflows) as a single dashboard.
For onboarding and doc-consistency checks.

## Procedure

1. **Generate**:
   ```bash
   python3 .claude/scripts/knowledge_graph.py
   ```
   Updates `docs/knowledge-graph.html` (reports node/edge/broken-link counts on stdout).

2. **View** — serve locally:
   ```bash
   python3 -m http.server -d docs 8899
   ```
   → http://localhost:8899/knowledge-graph.html (pan/zoom/drag; click a node for
   references / referenced-by details)

3. **Link consistency only** (exit 1 on broken links — usable as a CI gate):
   ```bash
   python3 .claude/scripts/knowledge_graph.py --check
   ```

## Notes

- The HTML is a snapshot — after restructuring docs, regenerate and commit it together.
- The refresh commit needs no issue, but never commit directly to main (branch + PR/MR).
