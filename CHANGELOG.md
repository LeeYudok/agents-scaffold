# Changelog

Notable changes to agents-scaffold. Versions follow [Semantic Versioning](https://semver.org/); the version is
`SCAFFOLD_VERSION` in `bin/agents-scaffold.sh` and matches the release tag.

## 1.0.0 — unreleased

First tagged release. Everything before it shipped from `main` without a version.

### Added
- `--version`, `--list-stacks`, `--dry-run` and `--uninstall`.
- `.claude/.scaffold.json` records the choices made at install time (forge, stacks, language, harness, skill sets).
- `--with-yd-skills` / `--no-yd-skills`. English installs (`--lang en`) no longer receive the Korean-only `yd-*` skills by default.
- An install summary with next steps (fill in `AGENTS.md`, check the gate, commit).
- `AGENTS_SCAFFOLD_REF` accepts tags; `AGENTS_SCAFFOLD_SHA256` verifies the downloaded template.
- `SECURITY.md`, `CODE_OF_CONDUCT.md`, a release workflow that publishes the offline bundle with `SHA256SUMS`.

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
