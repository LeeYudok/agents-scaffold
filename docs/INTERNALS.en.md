# agents-scaffold — internals

The generated `.claude/` tree and the design patterns behind it. Start at the [README](../README.md).

## What's inside

```
.claude/
  agents/
    security-audit.md   12-item P0/P1 security grep scan
    db-migration.md      DDL safety check + rollback SQL generation
    sdlc-developer.md    minimal-scope implementation agent (SDLC role split)
    sdlc-tester.md        AC/TC test-writing agent
    sdlc-verifier.md      pipeline execution + report agent
    agent-evolve.md       self-improving meta agent — refines agents/*.md from run feedback
    yd-*.md               12 agents for the yd-* skills (#78) — real source files; Codex/agy versions are generated from them
  commands/              (legacy on Claude Code — slash commands merged into skills)
    sonar.md             SonarQube analysis (CE task polling, sqp_/squ_ token handling)
    sdlc-cycle.md         5-stage SDLC automation
    knowledge-graph.md    regenerate the .claude knowledge graph + broken-link check
  hooks/
    pre-commit.sh         pre-commit gate skeleton (stack partial entry point)
    post-edit-format.sh   PostToolUse(Edit|Write) → auto-format
    post-test-notify.sh   PostToolUse(Bash, *test*) → terminal notification
    stop-memory-remind.sh Stop hook → once-per-session memory reminder
    compact-remind.sh     SessionStart(compact) hook → re-entry reminder right after compaction
    cc-check.py            PostToolUse(Bash, git commit) → warn if CC > 15
  memory/
    MEMORY.md              auto-memory index (SSOT)
    README.md               memory type/usage rules
  rules/
    common.md               P0/P1/P2 priority tiers + common workflow (always loaded)
    security.md              secrets/auth P0 + lockout/admin-seeding rules (paths-scoped)
    testing.md               test-per-feature, mock-first units, user-perspective assertions
    data.md                  data-script rules — no bulk staging, explicit encodings
    README.md                paths-scoped loading + rule-authoring principles
  skills/
    skill-evolve/            self-improving meta skill ("Learned warnings" pattern)
    status/                   multi-stack status check
    review/                   code-reviewer + security-audit wrapper
    memory-factcheck/         memory fact-check — verify claims against code/DB/issues, correct stale
    security-precheck/        pre-audit security sweep → issues → parallel fixes
    docs-sync/                doc currency — claim-by-claim verification + parallel-language sync
    handoff/                  session handoff — issue body when a tracker exists, HANDOFF.md otherwise
    yd-*/                     14 general skills — 13 moved from doksam-skills + yd-cve-check (#79) (DB, Go, React, TS, builds, screen design, writing, CVE checks; Korean only)
  workflows/             (not auto-loaded — invoked explicitly)
    rules-audit.js           stored Workflow example — scan/verify/repair with human merge gate
  scripts/               (not auto-loaded — invoked explicitly)
    knowledge_graph.py       .claude ecosystem graph + --check broken-link gate
  settings.json               hook wiring + default deny rules
AGENTS.md                 project brain — rule SSOT (P0/P1/P2 + workflow)
presets/                  preset fragments (copy-overwrite model)
  forge-github/           GitHub forge — gh, PRs, `Closes #N` auto-close
  forge-gitlab/           GitLab forge — glab, MRs, `Closes #N` auto-close (verify after merge)
  nextjs/ bun/ ...        per-stack fragments (rules + pre-commit.partial.sh + AGENTS.partial.md)
  lang-en/                English overlay (base/forge-*/stacks/*) — see `--lang` below
  skills-personal/        opt-in bundle: 9 yd-* skills + 4 agents, merged only with `--with-personal-skills` (#78)
bin/                      agents-scaffold.sh bootstrap script
scripts/                  install-skills.sh (global skill install), run-skill-tests.sh (per-skill tests) — self-cleaned after install
tests/                    bats regression suite for the bootstrap script
```

## Key patterns

- **P0/P1/P2 priority tiers**: defined in `common.md` + `AGENTS.md`. P0 = security/secrets/data destruction, no exceptions.
- **SDLC role split**: developer/tester/verifier agents + the `/sdlc-cycle` automation command.
- **skill-evolve / agent-evolve**: a self-improvement pattern that appends "Learned warnings" from mistakes. `skill-evolve` targets `.claude/skills/*.md`, `agent-evolve` targets `.claude/agents/*.md`.
- **Memory SSOT**: `.claude/memory/` (the system default path is not used). Type prefixes: `project_`/`feedback_`/`reference_`/`user_`.
- **Paths-scoped rules**: frontmatter `paths:` auto-loads a rule only while working on matching files.
- **Multi-agent isolation**: when parallel subagents may touch the same file concurrently, use `isolation: "worktree"`.
- **Install order**: base copy → forge preset → stack presets → (`--with-personal-skills`) `presets/skills-personal` → `--lang en` overlay → `{{PROJECT_NAME}}` substitution (skips `*/skills/yd-*/*` to keep the planner template's placeholder) → move to `.agents/skills` and link `.claude/skills` → emit Codex/agy agents.
- **Skill tests**: each skill carries `tests/test_*.py` and `tests/claims.json`. `scripts/run-skill-tests.sh` runs them per skill; `tests/test_skill_contracts.py` checks the claims format, referenced paths and trigger overlap.
