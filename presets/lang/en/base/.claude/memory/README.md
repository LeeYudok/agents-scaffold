# memory/ — Project memory (SSOT)

This project's **single source of truth** for auto-memory. The system default path is not used — everything lives here.

## Rules

- `MEMORY.md` — the (single) index. One memory = one file; add a one-line pointer to the index.
- Type prefixes:
  - `project_*` — ongoing work, goals, constraints (things not evident from code/git)
  - `feedback_*` — working-style guidance (why + how to apply)
  - `reference_*` — pointers to external resources (URLs, dashboards, tickets)
  - `user_*` — personal memory, **gitignored** (not shared with the team). Everything else is team-shared.
  - `instinct_*` — habits extracted from session observations (instinct-lite). Frontmatter carries
    `trigger`/`confidence` (0.3 tentative ~ 0.9 confident)/`evidence`, with one action in the body.
    Raise confidence when the same habit is re-observed; lower/delete it on contrary evidence.
- Assertive facts (thresholds, active flags) should carry a date and be re-verified against code/DB before acting on them (decay).
- `observations/` — session observation JSONL from the PostToolUse hook (observe-lite.sh). **Gitignored** (not committed),
  auto-pruned after 7 days. The Stop hook uses this log to prompt instinct extraction.
- Freshness auditing (correcting stale entries, archiving dead ones) → run the `memory-factcheck` skill.
  Archived memories move to `archive/` (with `archived:` frontmatter) and leave the index — never delete.
