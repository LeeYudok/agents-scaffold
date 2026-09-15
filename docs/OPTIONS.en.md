# agents-scaffold — all options

Every option of `bin/agents-scaffold.sh`. Start at the [README](../README.md).

## Stack presets

| Preset | Rule file | pre-commit gate |
|--------|-----------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `./gradlew build` |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant compile (auto-detect) |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check` + `mypy` |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

## Forge presets (`--forge`)

Injects the issue/PR workflow for your forge. Merged before stack presets.

| Preset | CLI | PR/MR | Issue close |
|--------|-----|-------|-------------|
| `github` (default) | `gh` | PR | **auto-closed** on merge via `Closes #N` |
| `gitlab` | `glab` | MR | `Closes #N` auto-close works — verify post-merge, manual only if still open |

Injected files: `.claude/rules/forge.md` (always loaded) plus forge variants of
`.claude/commands/fix-issue.md` and `sdlc-cycle.md` (overwrite the base). Base
files stay forge-neutral ("issue / PR·MR").

## Picking a requirements-hardening tool

Three tools harden requirements before implementation, and **they differ enough that you pick per
task.** Only `grill-me` is bundled; the other two install separately.

| | `grill-me` | superpowers | Ouroboros |
|---|---|---|---|
| **Scope** | interrogation only | the whole workflow | interrogate → spec → run → evaluate loop |
| **State** | stays in the conversation | conversation + file artifacts | an MCP server keeps it persistently |
| **Weight** | light | medium | heavy — fans out a subagent per question |
| **Install** | **bundled** (`.claude/skills/grill-me/`) | plugin, [obra/superpowers](https://github.com/obra/superpowers) | marketplace, [Q00/ouroboros](https://github.com/Q00/ouroboros) (ships an MCP server) |

**How to choose**

- A feature that already has direction, and you want the holes in its spec found → **`grill-me`**.
  Nothing to install, one conversation and you're done.
- A blank page you need to diverge and converge on, with a document to keep → **superpowers'
  `brainstorming`**.
- A large, vaguely specified job that has to be **turned into a spec and then run and evaluated in
  a loop** → **Ouroboros**. State survives a dropped session, at the highest token cost of the three.

Escalate by weight, and **only upward** — reaching for Ouroboros where the light option would do
just costs more. None of them fire automatically, even with all three installed; you pick per task.

## Harness (`--harness`)

| Value | Target | What it does |
|---|---|---|
| `claude` (default) | Claude Code | Full install — settings.json hook bindings, subagents, slash commands, workflows |
| `codex` | Codex | Installs `AGENTS.md`, native `.agents/skills`, and shared rules/hooks/memory; drops Claude-only layers |
| `all` | Mixed teams | Installs both `.claude/skills` and Codex-native `.agents/skills` |

**Support comes in two tiers (#21)** — not a binary "supported / unsupported".

| Tier | What holds | Which harnesses |
|---|---|---|
| **baseline** | The P0/P1 tiers in the `AGENTS.md` body (including the selected stack's P0) + a **real `.git/hooks/pre-commit` gate** + CI | **Every harness, whatever `--harness` you passed.** It holds no matter what the harness reads, and it holds when a human commits straight from the terminal |
| **full** | baseline + that harness's native layers (subagents, skills, slash commands, path-scoped rule loading, lifecycle hooks) | Only harnesses whose adapter has been measured |

The git hook is **always wired, regardless of harness** (#21). Claude Code's `PreToolUse` hook only fires when that session commits through the Bash tool, so it is an early-feedback layer, not the enforcement line — the deterministic line lives outside the harness (`.git/hooks` + CI). An existing `.git/hooks/pre-commit` is never overwritten; you get a warning instead.

The selected stack's P0 rules are **inlined into the `AGENTS.md` body**, so they do not depend on a `.claude/rules/` reference link and stay reachable on harnesses that never load `.claude/`. Stacks you did not select are not inlined (Codex caps combined instructions at 32KiB by default — this avoids context flooding).

### Verified (2026-09-15)

| Harness | Measured version | baseline | What is / isn't confirmed on the full tier |
|---|---|---|---|
| Claude Code | 2.1.239 | holds | `paths:`-scoped loading of `.claude/rules/*.md`, subagents, skills, `settings.json` hooks — all confirmed against the [official docs](https://code.claude.com/docs/en/memory.md) |
| Codex | codex-cli 0.154.0 / GPT-6 Astra | holds | `AGENTS.md`, inlined stack P0, `.agents/skills`, and the `.env` gate were measured |
| Antigravity | agy **1.1.18** (not re-measured) | holds | On 1.1.17, **headless (`-p`) measurably did not load rules** — root cause unknown. Neither 1.1.18 nor interactive mode has been re-measured |

Codex (codex-cli 0.154.0, `gpt-6-astra`) auto-loads the `codex`-mode AGENTS.md and its
inlined stack P0, and discovers repository skills under `.agents/skills`. It does not discover
`.claude/skills`. If a model misses a rule, the git hook still blocks a staged `.env` with exit 2.

The single source of truth for support status is [`docs/harness-matrix.json`](harness-matrix.json).
This table is checked against that manifest by `scripts/check-harness-matrix.py` in CI — if a `full`
tier has gone 90 days without re-measurement, or a verdict carries no evidence, **the build fails**.
Re-measure with `scripts/spike-codex-contract.sh --dynamic`.

`--harness codex` installs repository skills in Codex's native `.agents/skills` path.
`--harness all` keeps `.claude/skills` for Claude/Antigravity and also emits `.agents/skills`
for Codex. Codex subagents, path-scoped rules, and lifecycle hooks remain unverified, so its
overall tier remains baseline.

Two further Codex constraints shape the design:

- **Combined instructions are capped at 32KiB by default** (`project_doc_max_bytes`), which is why
  only the selected stack's P0 is inlined into `AGENTS.md` (measured 6,869 B with `--stack javaweb`
  — 21% of the cap).
- **The `.codex/` layer only loads for a trusted project.** Emitting a file does not guarantee it is
  active, which is why the deterministic enforcement line lives in `.git/hooks` + CI.

## Language (`--lang`)

The base tree (agents, rules, skills, commands, `AGENTS.md`, hook/settings
messages) is **Korean by default** (#36 inversion — Korean is the source of
truth, English is the translated overlay). `--lang en` layers the English
translation on top, applied last — after the base copy, forge preset, and
stack presets — so it overrides the same files with `presets/lang-en/base` +
`presets/lang-en/forge-<forge>` + `presets/lang-en/stacks/<stack>` content.

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`.claude/hooks/pre-commit.sh` is never overlaid by `--lang` (it's the file
stack partials get spliced into — single-language messages, code unaffected
by language). `--update` only refreshes the Korean base; re-run with
`--lang en` on top if you need the English overlay reapplied.

## Usage 1 — script

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge defaults to github; use --forge gitlab for GitLab repos
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

Omit `--forge`/`--stack`/`--name` to run interactively — the script will prompt
(forge defaults to github).

### Options

| Option | Description |
|---|---|
| `<target-dir>` | Target directory. Default `.` |
| `--forge <forge>` | `github` (default) or `gitlab` |
| `--lang <lang>` | `ko` (default) or `en` |
| `--stack <list>` | Comma-separated stack presets. Prompts interactively when omitted |
| `--name <name>` | `{{PROJECT_NAME}}` substitution value. Default = target directory name |
| `--yes` | Skip interactive prompts (non-interactive mode) |
| `--update` | Refresh base files of an already-bootstrapped project (see below) |

### Remote one-command install (no clone)

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

When the script detects it is not running from a local checkout (e.g. piped
execution), it downloads the `AGENTS_SCAFFOLD_REPO` tarball (default:
`github.com/leeyudok/agents-scaffold`, override via env) into a temporary directory and
uses it as the template source. Pin a branch/tag with `AGENTS_SCAFFOLD_REF`
(default `main`).

### Updating the base — `--update`

Applies the latest base files (`.claude/`, `AGENTS.md`, `CLAUDE.md`,
`GEMINI.md`) to an already-bootstrapped project.

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
```

- `.claude/hooks/pre-commit.sh` is always skipped — stack partials were spliced
  into it, so it needs manual merging.
- Other base files are skipped when identical; when they differ, the existing
  file is preserved and the new version is written as `<file>.new`
  (placeholder substitution applies to `.new` files too).
- A summary of added / pending-update / skipped / unchanged files is printed at
  the end — review `.new` files with `diff` and apply manually.

## Usage 2 — GitLab template

To have this configuration applied automatically when creating a new project,
see **[docs/GITLAB_TEMPLATE.md](GITLAB_TEMPLATE.md)**.

> Note: this workflow assumes a self-hosted GitLab instance. On **GitLab CE**,
> native custom project templates are a Premium feature and unavailable —
> use **Import by URL + `bin/agents-scaffold.sh`** or **the script alone** instead.
> After creating/importing, run `bin/agents-scaffold.sh .` once to apply the
> chosen stacks, substitute placeholders, and self-clean `bin/`/`presets/`/`docs/superpowers/`.

## Placeholder substitution

| Token | Value |
|---|---|
| `{{PROJECT_NAME}}` | `--name` value, or the target directory name |
| `{{JAVA_VERSION}}` | `1.8` (springboot preset default) |
