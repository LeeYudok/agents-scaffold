# Contributing to agents-scaffold

Thanks for considering a contribution! agents-scaffold is a minimal `.claude/`
bootstrap template, not a running application — most contributions are Markdown
(rules, agent/skill definitions) and small shell scripts (hooks,
`bin/agents-scaffold.sh`, `presets/*/.claude/hooks/pre-commit.partial.sh`).
The easiest way to make a first contribution is a **new stack preset** — see
the section below and the issues labeled
[`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## Workflow (GitHub)

1. **Issue first.** Open a GitHub issue before starting work, except for
   trivial typo fixes. Note the issue number — it should appear in the branch
   name, commits, and the pull request.
2. **Fork & branch**: `type/issue-<N>-<slug>`, where `type` is one of
   `feat`, `fix`, `chore`, `docs`. Example: `docs/issue-14-contributing-spec`.
3. **Commit messages** include the issue number, e.g.
   `docs: add preset spec (#14)`. Keep unrelated changes in separate commits.
4. **Run the tests locally** before opening a PR:

   ```bash
   # bats (bootstrap script + presets); install: https://bats-core.readthedocs.io
   bats tests/agents-scaffold.bats

   # python unit tests (hook/link-checker helpers)
   python3 -m unittest discover -s tests
   ```

   The same suite runs in CI on every PR — a green run is required to merge.
5. **Pull request** against `main` with `Closes #<N>` in the description.
   Merging auto-closes the issue.
6. **Review.** Changes to `bin/agents-scaffold.sh`, `.claude/hooks/pre-commit.sh`,
   or any `pre-commit.partial.sh` get extra scrutiny — these are load-bearing
   for every repo that bootstraps from this template.

## What to change where

- **Core skeleton** (`.claude/agents/`, `.claude/commands/`, `.claude/hooks/`,
  `.claude/rules/common.md`, `.claude/skills/`, `AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`): applies to every consuming repo regardless of stack. Changes
  here have the widest blast radius — keep them stack-agnostic.
- **Stack presets** (`presets/<stack>/`): opt-in, applied only when a repo
  selects that stack via `bin/agents-scaffold.sh --stack <name>`. See
  [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) for the required layout.
- **English overlay** (`presets/lang-en/`): the English mirror of the Korean
  originals. If you change a Korean rule/agent/skill, mirror the change in
  `presets/lang-en/` in the same PR (and vice versa). Executable scripts are
  written in English once and shared — do not duplicate them into the overlay.
- **Bootstrap script** (`bin/agents-scaffold.sh`): the only piece of logic that
  copies files, applies presets, and substitutes placeholders. Changes here
  affect every mode of consumption — test them with the bats suite.

## Contributing a new stack preset

1. Read [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) in full — it defines the
   required directory layout, `paths:` frontmatter rules, and the
   `pre-commit.partial.sh` contract (in particular: **never call `exit 0`**
   inside a partial — see the "Why partials must not `exit 0`" section, which
   documents a real regression).
2. Create `presets/<stack>/.claude/rules/<stack>.md` and, if the stack has an
   automatable build/lint/test step, `presets/<stack>/.claude/hooks/pre-commit.partial.sh`.
   A preset without a meaningful automated gate (e.g. `ops`) may omit the
   partial entirely.
3. Add the English rule file at `presets/lang-en/stacks/<stack>/.claude/rules/<stack>.md`.
4. Add a row to the stack preset table in `docs/OPTIONS.md` and `docs/OPTIONS.en.md`
   (rule file + pre-commit gate description).
5. Bootstrap a scratch repo with `bin/agents-scaffold.sh /tmp/scratch --stack
   <your-stack> --name scratch` and confirm:
   - the rule file lands at `.claude/rules/<stack>.md` with correct
     frontmatter `paths:`,
   - the partial is appended into `.claude/hooks/pre-commit.sh` after the
     `# --- STACK CHECKS` marker,
   - a deliberate build/lint failure in the scratch repo makes
     `git commit` exit non-zero, and a passing build commits cleanly,
   - combining your new stack with at least one existing stack still runs
     both gates.
6. Open an issue, then a branch/PR per the workflow above.

## Style

- Documentation is written in standard, professional Korean (`README.ko.md` and
  the Korean originals) or English (`README.md` and `presets/lang-en/`) —
  no emoji as icons or decoration, per this project's visual conventions.
  Contributing in English only is fine — maintainers will help with the
  Korean side if you can't.
- Shell scripts: `set -euo pipefail` at the top, POSIX-compatible where
  practical since presets run under whatever shell the consuming repo's CI
  provides.
