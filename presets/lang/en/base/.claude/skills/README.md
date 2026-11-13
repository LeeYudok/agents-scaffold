# skills/ — situational intelligence (skills)

Procedural knowledge triggered in specific situations. Each skill = 1 directory + `SKILL.md`
(frontmatter `name`/`description` (+`user-invocable`) + procedural body). When the description
trigger matches, Claude loads it and follows it as-is. `user-invocable: true` also allows manual
invocation.

```
skills/
└── <name>/
    ├── SKILL.md      # keep the body short — trigger + core procedure only
    ├── scripts/      # (optional) scripts the skill executes
    └── resources/    # (optional) heavy reference material — linked from the body, loaded only when needed
```

The principle is progressive disclosure: SKILL.md is always loaded, so keep it short and
move long source texts, tables, and examples into `resources/` files read only when needed.

Included: `example-skill/`, `review/`, `status/`, `search-first/`, `skill-evolve/`,
`memory-factcheck/` (memory fact-check vs code/DB/issues), `security-precheck/` (pre-audit security sweep),
`docs-sync/` (doc currency — claim-by-claim verification and parallel-language sync),
`handoff/` (session handoff — pass resumable state through the tracker issue body, or `HANDOFF.md` when there is no tracker, and pick it up),
`grill-me/` (adversarial requirements interrogation — the lightest option, staying inside the
conversation. Picked per task against the heavier superpowers `brainstorming` and Ouroboros; see
"Picking a requirements-hardening tool" in the README for the comparison).
New skills should use the `{{PROJECT_NAME}}-sk-*` prefix.

## `yd-*` skills (#78)

Moved over from [LeeYudok/doksam-skills](https://github.com/LeeYudok/doksam-skills); this repo is now their source.
The `yd-*` skills are **Korean only**, so an English install (`--lang en`) leaves them out unless you pass
`--with-yd-skills` (#105). Installation does not substitute `{{PROJECT_NAME}}` inside them. Skills marked ○ also have a named agent in `agents/yd-<name>.md`.

**Installed with `--lang ko`, or with `--with-yd-skills` (14)**

| Skill | Agent | Use when |
|---|---|---|
| `yd-mobile-web-planner` | ○ | Producing IA, a screen-design deck (HTML slides) and Business Rules for a mobile web/app |
| `yd-nextjs-implementer` | ○ | Turning the screen design into Next.js or Vite + React code |
| `yd-blueprint` | ○ | Recording structure, implementation status and remaining work as JSONL and rendering a blueprint view |
| `yd-frontend-build` | ○ | pnpm/Vite builds, dependencies, bundle size, offline self-hosting |
| `yd-typescript` | — | Reviewing type boundaries, async UI and DOM access |
| `yd-react-expert` | ○ | React 19 components, state, effects, accessibility, render performance |
| `yd-go-expert` | ○ | Writing or reviewing Go 1.22+ (errors, concurrency, `net/http`, `go:embed`) |
| `yd-db-expert` | ○ | Engine-neutral relational design (normalization, keys, constraints, indexes, transactions, migrations) |
| `yd-pg-expert` | ○ | PostgreSQL-specific behavior (locking ALTERs, `CONCURRENTLY`, VACUUM, plans) |
| `yd-oracle-expert` | ○ | Oracle-specific issues (empty string NULL, DATE time part, VARCHAR2 bytes, ROWNUM) |
| `yd-sqlite-expert` | ○ | SQLite-specific issues (read-only queries, WAL, locking, dynamic table names) |
| `yd-agents-yaml` | — | Setting up or updating `AGENTS.md` + `AGENTS.yaml` + validator |
| `yd-writer-kr` | ○ | Writing or editing Korean issues, PRs, docs and announcements |
| `yd-cve-check` | ○ | Checking and fixing pnpm dependencies against known CVE/GHSA/malicious-package data (online `pnpm audit`, offline OSV dump, #79) |

doksam-skills' `yd-handoff`, `yd-doc-sync`, `yd-memory-factcheck` and `yd-skill-evolve` were merged into
`handoff`, `docs-sync`, `memory-factcheck` and `skill-evolve`, which do the same jobs.

**Opt-in (10)** — these assume the maintainer's environment (a specific GitLab, hosts, ui.doksam.com, FinGuard).
Their source is `presets/skills/personal/.claude/skills/` in this repo, and they are installed only with
`--with-personal-skills`: `yd-sdlc-orchestrator`, `yd-finguard`, `yd-doksam-ui`, `yd-script-editor` (with agents),
`yd-agents-mem`, `yd-git-ship`, `yd-git-sync`, `yd-claude-auth-sync`, `yd-session-recording`, `yd-naver-blog`.

## Authoring rules

- Frontmatter requires `name` (same as the folder) and `description` (concrete trigger conditions).
- Put testable assertions in `tests/claims.json` as `{id, kind, rule, test}`. Each `rule` must appear
  **verbatim** in SKILL.md or `references/*.md`, and `test` must be a test that unittest actually collects.
- Skill tests live in `tests/test_*.py`. Run them from the repo root with `scripts/dev/run-skill-tests.sh [skill]`.
- `tests/test_skill_contracts.py` checks the claims format, that script paths named in the docs exist, and that
  description triggers do not overlap between skills. When they overlap, state the boundary in the description
  ("X is handled by Y").
- (In the agents-scaffold repo) after changing a `yd-*` skill or handoff, docs-sync, memory-factcheck or skill-evolve,
  regenerate the plugin copies (`plugins/*/skills/`) with `python3 scripts/dev/build-plugins.py` and commit them together
  (#82; CI blocks drift).
- Skills that need the scaffold's subagents, templates and personal skills carry `metadata:` / `  internal: true` in their
  frontmatter, which hides them from `npx skills add` (#102, `tests/test_skill_visibility.py`).

In an installed project the skill source is `.agents/skills/` (the Codex/agy native path) and
`.claude/skills` is a symlink to it (#61) — editing through either path changes the same file. Where
a symlink cannot be created (e.g. Windows Git Bash defaults) `.claude/skills` is a copy: edit
`.agents/skills` only, copy the same file into the copy, and stage both paths by name
(`git add -- .agents/skills/<path> .claude/skills/<path>`). The pre-commit gate blocks a staged copy that
differs from the source and lists the differing files.
