# Changelog

Notable changes to agents-scaffold. Versions follow [Semantic Versioning](https://semver.org/); the version is
`SCAFFOLD_VERSION` in `bin/agents-scaffold.sh` and matches the release tag.

## 1.0.0 — unreleased

First tagged release. Everything before it shipped from `main` without a version.

### Added
- `yd-a2a-orchestrator`: coordinates multi-repo work across the A2A/ACP agent pool — a single coordinator
  lease with CAS failover, a task DAG validated by `scripts/check_task_dag.py` (unique IDs, dependency
  existence, cycle detection, owner ≠ reviewer, evidence hashes), worktree isolation, cross-agent
  verification evidence and bounded failure reassignment. It defers single-repo web E2E to
  `yd-sdlc-orchestrator` and same-host Orca workers to `orchestration` (#161).
- `yd-visual-brief`: builds a one-page, diagram-first brief (HTML) for business plans and approval documents from a
  single `brief.json` — a layered architecture diagram, a metro-style flow map, comparison rows, a schedule and decision
  cards drawn as SVG, three curated palettes, and `check_brief.py` for contrast, hue count, text size and missing
  diagrams (#153).
- `yd-writer-kr`: warning-level and per-sentence count rules drawn from five more style guides, notation profiles
  (`--profile`, `references/profiles/`), an OpenAI-compatible endpoint for proofreading and summaries
  (`WRITER_LLM_BASE_URL`), and prebuilt `check-writing` binaries for Windows, Linux and macOS on each release (#137).
- `yd-writer-kr`: twelve writing tasks (issue, notice, incident report, meeting summary) with a scorer and a blind
  comparison sheet, to measure whether text written with the skill is better than text written without it (#139).
- `yd-writer-kr`: `references/flow.yaml` maps every step, branch, tool option and environment variable of the skill;
  `scripts/flow_map.py --check` fails when a section, option, variable or file is missing from the map, and
  `--write` renders `references/flow.md` (Mermaid diagrams and step tables) from it (#143).
- `--version`, `--list-stacks`, `--dry-run` and `--uninstall`.
- `.claude/.scaffold.json` records the choices made at install time (forge, stacks, language, harness, skill sets).
- `--with-yd-skills` / `--no-yd-skills`. English installs (`--lang en`) no longer receive the Korean-only `yd-*` skills by default.
- An install summary with next steps (fill in `AGENTS.md`, check the gate, commit).
- `AGENTS_SCAFFOLD_REF` accepts tags; `AGENTS_SCAFFOLD_SHA256` verifies the downloaded template.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, a release workflow that publishes the offline bundle with `SHA256SUMS`.
- Contract tests for the agentskills limits: `name` equals the directory and is at most 64 characters, `description` is at most
  1024 characters, `SKILL.md` stays under 500 lines. `handoff` and `yd-mobile-web-planner` moved their templates to `references/`.
- `yd-writer-kr` checker: paragraph and list rules (repeated sentence endings, sentence-initial conjunctions, a colon
  opening a list, bound nouns, bold-prefixed list items), a third severity `참고` that never changes the exit code, and an
  optional `--morph` pass that runs only when kiwipiepy is installed.
- Trigger queries (`tests/triggers.json`) for the 21 visible skills and `scripts/dev/eval-skill-triggers.py`, a manual runner
  that scores them with `claude plugin eval`.

### Changed
- `--update` replays the recorded choices (or infers them for older installs) and compares against that result,
  so forge/stack presets, the English overlay and `pre-commit.sh` are compared instead of being skipped or reverted.
- An unknown `--stack` is an error that lists the available stacks. It used to warn and exit 0.
- The git hook is written where git actually runs it: worktrees, submodules and `core.hooksPath` are handled,
  and `--update` wires a missing hook.
- The generated `settings.json` denies more variants (`rm -fr`, `git push -f`, nested `.env`, editing `.env`)
  and asks before `git reset --hard` and `git push --force-with-lease`.

### Fixed
- Re-running the installer overwrote an edited `AGENTS.md`. It is now saved as `AGENTS.md.bak-<timestamp>`.
- Re-running the installer spliced each stack gate into `pre-commit.sh` again, so it ran twice per commit.
- An option without its value printed `unbound variable`.
