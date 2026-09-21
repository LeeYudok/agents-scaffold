# rules/ — context-aware rules (native)

Development rules auto-injected when AI agents (Claude Code, etc.) work in this repo.
Each file is one markdown document.

## How loading works

- **Scoped load**: with a frontmatter `paths:` (glob array), the file is injected **only when
  editing/creating matching files**.
- **Always loaded**: without `paths:`, the file loads at session start (like AGENTS.md).
- Each file's exact globs live in **its frontmatter — the single source of truth**; the table below is an overview.

```markdown
---
paths:
  - "src/api/**/*.ts"
---
# API Rules
- Input validation is required on every endpoint
```

## Rule mapping

| Rule file | Scope (overview) | Main content |
| :--- | :--- | :--- |
| **[common.md](common.md)** | *always loaded* | priority tiers, workflow, secrets handling, communication |
| **[security.md](security.md)** | backend + frontend source, config files | secrets/auth P0, public-env secrets ban, lockout |
| **[testing.md](testing.md)** | test files | 1 test per feature (P1), mock-first units, user-perspective assertions |
| **[data.md](data.md)** | `data/` scripts | no bulk-data staging (P0), explicit encodings, OOM prevention |
| forge preset adds **forge.md** | *always loaded* | issue/PR-MR procedure per forge |
| stack presets add **`<stack>.md`** | stack source globs | stack-specific conventions |

## Rule-authoring principles

1. **Never create a new file with the same `paths` scope** — same scope loads together anyway
   (zero gain from splitting). Add a section to the existing file instead.
2. **Verify scope with real work** — check that the files needing the rule actually match the
   globs. A glob that only catches one package silently skips the related controllers/mappers.
3. **Keep rules short; cite evidence as issue numbers** — one line per rule + `(#N)` instead of
   prose. Shorter rules get followed more.
4. **Standard P0 (absolute) / P1 (required) / P2 (recommended) headers** — violation handling is
   defined in AGENTS.md.
5. On add/remove, **update the AGENTS.md mapping and the table above together**.
6. **Enforcement tags** — attach `[auto-enforced: <tool>]` only to rules a tool genuinely
   verifies. **Untagged = discipline (agent/human judgment) is the default** — spell out
   `[discipline]` only where a rule is easily mistaken for auto-enforced (e.g. a test rule the
   hook only partially gates). No tag spam. For partial enforcement, state the limit inline.
7. **Incident-origin rules link the retrospective memory** — next to the rule: `(#N)` + a
   relative link labeled `[incident memory]` pointing at `../memory/<file>.md`, so "why" is one
   click away. Links must resolve to real files (no placeholders — the link checker
   `.claude/scripts/knowledge_graph.py --check` gates them).
