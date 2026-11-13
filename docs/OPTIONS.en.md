# agents-scaffold — all options

Every option of `bin/agents-scaffold.sh`. Start at the [README](../README.md).

## Stack presets

| Preset | Rule file | pre-commit gate |
|--------|-----------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `gradle testClasses` / `mvn test-compile` (full tests with `SPRINGBOOT_GATE_TESTS=1`) |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant compile (auto-detect) |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check`; `mypy` when the project configures it |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `php-laravel` | php-laravel.md (paths: app/**/*.php, routes/**/*.php, composer.json) | `composer validate` + `pint --test` + `phpunit` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

`--list-stacks` prints these names, one per line. A name that is not in the list is an error (exit 1) that prints the
available stacks, and nothing is installed — it used to be a warning.

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
| `codex` | Codex | Installs `AGENTS.md`, skills, and shared rules/hooks/memory; generates `.codex/agents` TOML (#64) and `.codex/hooks.json` (#65); drops Claude-only layers (commands, workflows) |
| `agy` | Antigravity | The shared `codex` layout, plus `.agents/rules` (`trigger: glob`, #63), `.agents/agents` (#64) and `.agents/hooks.json` (#65) generated from `.claude/` |
| `all` | Mixed teams | Everything from `claude` plus every adapter (agy rules, Codex and agy subagents and hooks). The skill layout does not depend on the harness (#61) |

**Skills have a single source (#61).** Whatever the harness, skills live once in `.agents/skills/`
(the Codex/agy native path) and Claude Code reads the same files through the symlink
`.claude/skills -> ../.agents/skills` (measured on claude 2.1.318 — with `.agents/skills` alone and no
link, Claude Code finds no skills). Two copies can no longer drift apart, and adding another harness
later needs no reinstall.

- Where a symlink cannot be created (e.g. Windows Git Bash defaults), or with
  `AGENTS_SCAFFOLD_NO_SYMLINK=1`, `.claude/skills` is a copy. The pre-commit gate blocks a commit whose
  staged copy differs from the staged source (an index comparison, so untracked files such as
  `__pycache__` do not count). Whether a symlink works can vary with the environment (e.g. policy on
  network-separated PCs) — see step 6 of [OFFLINE_INSTALL.en.md](OFFLINE_INSTALL.en.md).
- A Git for Windows checkout with `core.symlinks=false` turns the link into a plain file holding the
  path. Claude Code then finds no skills and the gate warns — run `git config core.symlinks true` and
  check it out again.
- A real `.claude/skills` that existed before install is moved into `.agents/skills` and linked. If a
  path's content differs from `.agents/skills`, `.agents/skills` stays the source and the old directory
  is kept as `.claude/skills.pre-ssot-<timestamp>/`.
- Rules and subagents are not linked: `.codex/rules` is a command-execution policy, agy's
  `.agents/rules` does not understand Claude's `paths:` scoping, and Claude `.md` and Codex `.toml`
  subagents use different formats. They are generated in each harness's format at install and `--update`
  instead (#63, #64).

All three harnesses read the root `AGENTS.md` natively, so no `CLAUDE.md`/`GEMINI.md` pointer or
`.gemini/settings.json` shim is emitted (#54, #60). Supported targets are the latest Claude Code,
Codex and Antigravity; Gemini CLI is no longer a target.

**Support comes in two tiers (#21)** — not a binary "supported / unsupported".

| Tier | What holds | Which harnesses |
|---|---|---|
| **baseline** | The P0/P1 tiers in the `AGENTS.md` body (including the selected stack's P0) + a **real `.git/hooks/pre-commit` gate** + CI | **Every harness, whatever `--harness` you passed.** It holds no matter what the harness reads, and it holds when a human commits straight from the terminal |
| **full** | baseline + that harness's native layers (subagents, skills, slash commands, path-scoped rule loading, lifecycle hooks) | Only harnesses whose adapter has been measured |

The git hook is **always wired, regardless of harness** (#21). Claude Code's `PreToolUse` hook only fires when that session commits through the Bash tool, so it is an early-feedback layer, not the enforcement line — the deterministic line lives outside the harness (`.git/hooks` + CI). An existing pre-commit hook is never overwritten; you get a warning with the one line to add to it. The hook is written where git actually runs it — a worktree, a submodule (`.git` is a file) and a `core.hooksPath` directory such as `.husky` are handled — and `--update` wires a hook that is missing (#106). See [TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md#an-existing-pre-commit-hook-or-husky).

The selected stack's P0 rules are **inlined into the `AGENTS.md` body**, so they do not depend on a `.claude/rules/` reference link and stay reachable on harnesses that never load `.claude/`. Stacks you did not select are not inlined (Codex caps combined instructions at 32KiB by default — this avoids context flooding).

### Verified (2026-11-04)

| Harness | Measured version | Tier | baseline | What is / isn't confirmed on the full tier |
|---|---|---|---|---|
| Claude Code | 2.1.318 | **full** | holds | `paths:`-scoped loading of `.claude/rules/*.md`, subagents, skills, `settings.json` hooks — all confirmed against the [official docs](https://code.claude.com/docs/en/memory.md) |
| Codex | codex-cli 0.166.0 | **baseline** | holds | Measured: `AGENTS.md`, inlined stack P0, `.agents/skills`, the `.env` gate, `.codex/agents` subagents (trusted projects only), `.codex/hooks.json` hooks (project and hook-definition trust required), and subdirectory `AGENTS.md` by cwd. No file-path-scoped instructions |
| Antigravity | agy 1.5.0 | **baseline** | holds | Measured in headless (`-p`) mode: `AGENTS.md`, inlined stack P0, `.agents/skills`, the `.env` gate, `.agents/agents` subagents, and `.agents/hooks.json` hooks (run without a trust prompt). **`trigger: glob` rules in `.agents/rules` do not load on 1.5.0 even after a matching file is read** (passed through 1.4.2; `always_on` still works, #90). Subdirectory `AGENTS.md` loads by cwd only |

Codex (codex-cli 0.166.0) and agy (1.5.0) auto-load their mode's AGENTS.md and
its inlined stack P0 without any tool call, and discover repository skills under `.agents/skills`
only — neither discovers `.claude/skills`. agy 1.2.7 headless loaded neither `AGENTS.md` nor
`GEMINI.md`; that is fixed in 1.2.16. If a model misses a rule, the git hook still blocks a staged
`.env` with exit 2.

The single source of truth for support status is [`docs/harness-matrix.json`](harness-matrix.json).
This table is checked against that manifest by `scripts/dev/check-harness-matrix.py` in CI — a verdict
without evidence or a version mismatch **fails the build**. A `full` tier that has gone 90 days without
re-measurement fails the weekly `harness-matrix` workflow; pull requests only warn, from 14 days before expiry.
Re-measure with `scripts/dev/spike-codex-contract.sh --dynamic` and `scripts/dev/spike-agy-contract.sh --dynamic`.

**agy rules adapter (#63).** With `--harness agy|all`, `.claude/rules/*.md` is generated as `.agents/rules/*.md`.
`paths:` becomes `trigger: glob` + `globs:`; without `paths:` it becomes `trigger: always_on`. Patterns are converted as
measured on agy 1.2.16: a relative pattern containing a slash (`src/**`) becomes `**/src/**`, while a pattern without a
slash (`Dockerfile`, `*.py`) matches the file name and is kept. Patterns are joined with commas and no spaces (a space
after a comma becomes part of the next pattern, which then never matches). `.claude/rules` stays the source; `--update`
regenerates (an existing project gets its first generation with `--update --harness agy`) and removes generated files whose source is gone. A same-named file without the generated marker
(user-owned) is left untouched.

**Subagent adapters (#64).** `.claude/agents/*.md` is generated as `.codex/agents/<name>.toml` for Codex
(`--harness codex|all`) and as `.agents/agents/<name>.md` for agy (`--harness agy|all`). Codex gets `name`, `description` and
`developer_instructions` (the body verbatim as a TOML literal string `'''`); a body containing `'''` is skipped with a
warning. agy gets only `name` and `description` — with Claude's `tools`, `model` or `memory` in the frontmatter, agy 1.2.16
silently drops the agent (measured). Tools and model fall back to each harness's defaults, and Claude-specific instructions
in the body stay as written. `.claude/agents` is the source, so codex/agy modes keep it. Codex loads the `.codex/` layer
only for trusted projects, so generating the files does not activate them by itself. Update rules match the rules
adapter (`--update` regenerates, generated files whose source is gone are removed, user files without the marker are kept,
and an existing project gets its first generation with `--update --harness codex|agy|all`).

**Hook adapters (#65).** Hooks are authored in Claude format (`hooks` in `.claude/settings.json` + `.claude/hooks/*`).
`.claude/hooks/hook-adapter.py` generates `.codex/hooks.json` for Codex (`--harness codex|all`) and `.agents/hooks.json` for
agy (`--harness agy|all`). At run time the same adapter converts the harness input to Claude format, calls the original
script, and converts the reply back (measured 2026-10-04):

- Codex input is almost Claude's. Shell is `Bash`; file edits are `apply_patch` (split per file from the patch text and passed
  as `Edit`). Codex accepts Stop's `{"decision":"block"}` as-is and runs another turn. Hooks run only with project trust plus
  hook-definition trust (`/hooks` review).
- agy input is camelCase (`conversationId`, `toolCall`). `run_command` becomes `Bash`, `write_to_file` and friends become
  `Write`/`Edit`, and Stop's `block` becomes agy's `continue`. Command output is not passed, so test-result notifications
  cannot judge pass/fail. **Hooks run without a trust prompt** (cloning is enough to run the repo's `.claude/hooks/*` —
  `security-audit` scans them).
- Not carried over: the PreToolUse commit gate (`.git/hooks` owns it) and prompt-type hooks, and non-tool events with a matcher (the SessionStart `compact` reminder, #72).
- The adapter needs `python3` (generation is skipped without it). `.claude/settings.json` is the hook source, so codex/agy
  modes keep it.
- The Stop hook (memory reminder) runs one more turn in headless mode (`-p`, `exec`) too. If that is unwanted in automation,
  remove it from `settings.json` and run `--update`. Update rules match the other adapters.

The scaffold generates subagents (#64) and hooks (#65) for both harnesses and path-scoped rules (#63) for agy, each
measured end to end. agy was full through 1.4.2, but **on 1.5.0 glob rules no longer load, so agy is now baseline** (#90) —
the generator stays as is, and agy returns to full once a fixed release passes the re-measurement. **Codex stays baseline**: it has no
file-path-scoped instructions, so `.claude/rules` `paths:` rules cannot reach it (subdirectory `AGENTS.md` loads by cwd only). As with Claude Code, hooks are early feedback, not the enforcement line. agy
runs a repo's `.agents/hooks.json` without a trust prompt, so check that file before running agy in a
foreign repo (the `security-audit` agent scans it).

Two further Codex constraints shape the design:

- **Combined instructions are capped at 32KiB by default** (`project_doc_max_bytes`), which is why
  only the selected stack's P0 is inlined into `AGENTS.md` (measured 6,869 B with `--stack javaweb`
  — 21% of the cap).
- **The `.codex/` layer only loads for a trusted project.** Emitting a file does not guarantee it is
  active, which is why the deterministic enforcement line lives in `.git/hooks` + CI.

## Skill bundles (`--with-yd-skills`, `--no-yd-skills`, `--with-personal-skills`)

| Install | Skills | Subagents |
|---|---|---|
| `--lang ko` (default) | 24 — 10 workflow skills + 14 `yd-*` | 19 — 7 + 12 `yd-*` |
| `--lang en` | 10 — the workflow skills | 7 |
| with `--with-personal-skills` | +10 | +4 |

The 10 workflow skills are `review`, `status`, `search-first`, `security-precheck`, `docs-sync`, `handoff`,
`memory-factcheck`, `skill-evolve`, `grill-me` and the `example-skill` template. The 14 `yd-*` skills are the 13 moved
over from [LeeYudok/doksam-skills](https://github.com/LeeYudok/doksam-skills) (DB, Go, React, TypeScript, builds,
screen design, Korean writing, ...) plus `yd-cve-check` for dependency CVE checks (#79); their 12 agents
(`.claude/agents/yd-*.md`) travel with them (#78).

| Option | Effect |
|---|---|
| `--with-yd-skills` | Install the 14 `yd-*` skills and their agents. The default for `--lang ko` |
| `--no-yd-skills` | Leave them out. The default for `--lang en`, because the `yd-*` skills are written in Korean and have no English overlay (#105) |
| `--with-personal-skills` | Also merge the opt-in bundle `presets/skills/personal/` after the stack presets |

The opt-in bundle is 10 skills (`yd-agents-mem`, `yd-claude-auth-sync`, `yd-git-sync`, `yd-git-ship`, `yd-doksam-ui`,
`yd-finguard`, `yd-sdlc-orchestrator`, `yd-script-editor`, `yd-session-recording`, `yd-naver-blog`) and 4 agents. They assume a
specific GitLab, hosts, ui.doksam.com and FinGuard, so they are not meant for other environments.

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --stack go --with-yd-skills
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --stack go --with-personal-skills
```

- The choice is recorded in `.claude/.scaffold.json` (`yd_skills`, `personal_skills`), and `--update` keeps the same
  sets. For an install without that file, `--update` treats the `yd-*` set as installed when `yd-db-expert` is
  present, and the opt-in bundle as installed when the target has any of its skills.
- Running `--update` on a default install does not add the opt-in bundle. `--update --with-yd-skills` adds the
  `yd-*` set to an existing install. `--update --no-yd-skills` only changes the record — skills that are already
  installed are not deleted.
- Installing the skills without the scaffold (plugin, `npx skills`, `install-skills.sh`): [SKILLS.en.md](SKILLS.en.md).

## Language (`--lang`)

The base tree (agents, rules, skills, commands, `AGENTS.md`, hook/settings
messages) is **Korean by default** (#36 inversion — Korean is the source of
truth, English is the translated overlay). `--lang en` layers the English
translation on top, applied last — after the base copy, forge preset, and
stack presets — so it overrides the same files with `presets/lang/en/base` +
`presets/lang/en/forge/<forge>` + `presets/lang/en/stacks/<stack>` content.

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`--lang en` also leaves out the Korean-only `yd-*` skills unless you pass `--with-yd-skills`
(see [Skill bundles](#skill-bundles---with-yd-skills---no-yd-skills---with-personal-skills)).

`.claude/hooks/pre-commit.sh` is never overlaid by `--lang` (it's the file
stack partials get spliced into — one copy for both languages, code unaffected
by language). The language is recorded in `.claude/.scaffold.json`, and `--update`
compares against an install in that language — an English install is no longer offered
Korean files.

## Usage 1 — script

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge defaults to github; use --forge gitlab for GitLab repos
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

Omit `--forge`/`--stack`/`--lang` to run interactively — the script will prompt
(forge defaults to github, language to ko). A target directory that does not exist is created.

The install ends with a summary — the version, the number of rule files, skills and subagents, and the gate —
followed by the next steps: fill in the empty sections of `AGENTS.md`, check that the gate blocks a staged `.env`,
and commit the result.

### Options

| Option | Description |
|---|---|
| `<target-dir>` | Target directory. Default `.`. Created when it does not exist (not with `--update`, `--uninstall` or `--dry-run`) |
| `--forge <forge>` | `github` (default) or `gitlab` |
| `--lang <lang>` | `ko` (default) or `en` |
| `--stack <list>` | Comma-separated stack presets. Prompts interactively when omitted. An unknown name is an error |
| `--name <name>` | `{{PROJECT_NAME}}` substitution value. Default = target directory name |
| `--harness <harness>` | `claude` (default), `codex`, `agy` or `all` — see [Harness](#harness---harness) |
| `--with-yd-skills` / `--no-yd-skills` | Install or leave out the 14 Korean `yd-*` skills. Default: in for `ko`, out for `en` |
| `--with-personal-skills` | Also install the 10 `yd-*` skills and 4 agents tied to the maintainer's environment |
| `--yes` | Skip interactive prompts (non-interactive mode) |
| `--dry-run` | Change nothing. Print what an install, `--update` or `--uninstall` would do (see below) |
| `--update` | Refresh an already-bootstrapped project (see below) |
| `--force` | With `--update`, replace changed files after saving unique `.bak-*` backups. Preview with `--dry-run` |
| `--uninstall` | Remove what the scaffold installed and you did not change (see below) |
| `--list-stacks` | Print the available stack presets, one per line |
| `--version` | Print the scaffold version (`agents-scaffold 1.0.0`) |
| `-h`, `--help` | Print the usage text |

An option that needs a value and gets none stops with `Error: --stack needs a value`, and an unknown option stops
with `Unknown option`.

### Recorded choices — `.claude/.scaffold.json`

Every install and `--update` writes the choices it used to `.claude/.scaffold.json` (#104):

```json
{
  "scaffold_version": "1.0.0",
  "name": "my-app",
  "forge": "github",
  "stacks": "nextjs,bun",
  "lang": "en",
  "harness": "claude",
  "yd_skills": "0",
  "personal_skills": "0"
}
```

`--update`, `--uninstall` and `--dry-run` read it to rebuild exactly what was installed. Commit it with the rest of
`.claude/`. When the file is missing — an install from before 1.0.0 — the choices are inferred from the project
(forge from `rules/forge.md`, stacks from `rules/<stack>.md`, language from the `AGENTS.md` headings, harness from the
directories present), the first output line says `(inferred)` instead of `(recorded)`, and the file is written at the
end of `--update`. Options on the command line override the recorded values.

### Preview — `--dry-run`

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/repo --lang en --stack python --dry-run
agents-scaffold/bin/agents-scaffold.sh --update /path/to/repo --dry-run
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --dry-run
```

Nothing in the target is changed. An install preview prints how many files would be added, how many are already
identical, and which existing files differ. `--update --dry-run` lists what would be added or staged as `.new`, and
`--uninstall --dry-run` lists what would be removed and kept. The target directory must already exist.

### Installing over an existing project

Running a normal install again is safe to repeat (#104):

- Base files that already exist are kept. Files that come from a forge preset, a stack preset or the English overlay
  are written again.
- `AGENTS.md` is regenerated. If yours differed from the generated one, it is saved first as
  `AGENTS.md.bak-<timestamp>` — merge what you need back.
- A stack gate that is already in `pre-commit.sh` is not spliced in a second time.

To refresh an install without regenerating `AGENTS.md`, use `--update`.

### Remote one-command install (no clone)

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

When the script detects it is not running from a local checkout (e.g. piped
execution), it downloads the `AGENTS_SCAFFOLD_REPO` tarball (default:
`github.com/leeyudok/agents-scaffold`, override via env) into a temporary directory and
uses it as the template source.

| Variable | Meaning |
|---|---|
| `AGENTS_SCAFFOLD_REPO` | Repository URL the tarball is downloaded from. Default: the official GitHub repository |
| `AGENTS_SCAFFOLD_REF` | Branch or tag to download. Default `main`. Tags work as of 1.0.0 (#106) |
| `AGENTS_SCAFFOLD_SHA256` | Optional. Expected SHA-256 of the downloaded tarball; the install aborts on a mismatch |
| `AGENTS_SCAFFOLD_NO_SYMLINK` | `1` makes `.claude/skills` a copy instead of a symlink |

To pin a release and verify it (the form to use once a release tag exists — no tag has been published yet;
see [SECURITY.md](../SECURITY.md#installing-safely)):

```bash
export AGENTS_SCAFFOLD_REF=v1.0.0
export AGENTS_SCAFFOLD_SHA256=<sha256 of that ref's source tarball>
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/v1.0.0/bin/agents-scaffold.sh | bash -s -- --lang en --yes
```

### Updating — `--update`

Refreshes an already-bootstrapped project. `--update` reads the recorded choices, builds the install those choices
produce today in a temporary directory, and compares the project against it file by file (#104). Because the
comparison is against the full result and not only the base, forge and stack presets, the English overlay and
`.claude/hooks/pre-commit.sh` are compared too.

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo --dry-run
```

| File in the project | What `--update` does |
|---|---|
| Identical to the new version | Skipped |
| Missing | Added |
| Different | Left alone; the new version is written as `<file>.new` |
| `.claude/memory/MEMORY.md` | Yours — added only when missing, never given a `.new` |
| Generated adapters (`.codex/`, `.agents/rules`, `.agents/agents`, `.agents/hooks.json`) | Regenerated from the project's `.claude/` |

- A summary of added / pending (`.new`) / unchanged files is printed at the end. Review each `.new` with `diff` and
  apply it by hand — see [TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md#new-files-after---update).
- `AGENTS.md` is compared like any other file, so once you have filled it in, each update writes `AGENTS.md.new`.
- A missing git pre-commit hook is wired, and the recorded choices are written back.
- Options on the command line override the record: `--update --harness all` adds the Codex and agy adapters to an
  existing project, `--update --stack nextjs,go` compares against a different stack set.
- A `.gemini/settings.json` left by an earlier version is not touched (harmless if it stays).
- A real `.claude/skills` is moved into the source `.agents/skills` and linked only when `.agents/skills`
  does not exist or has the same content (#61). If both exist and differ, nothing is moved and a manual
  merge is suggested. Once migrated, base skills are refreshed on the `.agents/skills` side.

### Removing — `--uninstall`

```bash
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --dry-run
agents-scaffold/bin/agents-scaffold.sh --uninstall /path/to/repo --yes
```

Rebuilds what the recorded choices installed and removes the files that are still identical to it (#106). Files
you changed are kept and listed. `.claude/memory/` is never removed, and neither is anything the scaffold did not
create. The git pre-commit hook is removed only when it is the scaffold's own one-line hook. Without `--yes` it asks
for confirmation, and it refuses to run when there is no terminal to ask on.

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

Files under `.claude/skills/yd-*/` are not substituted — the `yd-mobile-web-planner` template uses `{{PROJECT_NAME}}` as a placeholder for its own output (#78).
