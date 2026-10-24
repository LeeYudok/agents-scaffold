# agents-scaffold

English | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md)

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

**Guardrails for AI coding agents — Claude Code, Codex and Antigravity — enforced by a real git pre-commit gate.**

AI coding agents break your rules. This blocks the commit instead of asking nicely.
One command installs an `AGENTS.md` project brain, path-scoped rules, skills, subagents, hooks and a composed
pre-commit gate into your repo. No framework, no runtime, no registry — **plain files you own outright.**

![Demo: one-command bootstrap, the generated .claude/ tree, and the pre-commit gate blocking a staged .env](docs/assets/demo.gif)

_30-second demo: one command → a filled `.claude/` → the gate blocks a secret commit. Reproduce with `vhs docs/assets/demo.tape`._

## You want this if

- You **re-explain the same rules every session** — what you told the agent yesterday is gone today.
- An agent staged your `.env`, or produced a commit with type errors still in it.
- Every teammate has a different `CLAUDE.md`, so **results depend on whose session it was.**
- Your team mixes Claude Code, Codex and Antigravity, and you want **one set of rules for all of them.**
- You work on an **air-gapped network or Windows** and most agent setups assume neither.

Rules that live only in a document get ignored eventually. This scaffold turns them into a
**gate that blocks the commit**, and plants it in the repo.

## Quickstart

```bash
# one command, no clone required
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# or from a local clone (prompts interactively when options are omitted)
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app

# Codex or Antigravity too: --harness codex | agy | all
agents-scaffold/bin/agents-scaffold.sh /path/to/repo --harness all --stack python --yes
```

Already installed? `--update` refreshes the base files and writes `<file>.new` next to anything you changed,
so your edits are never overwritten. Full options: [docs/OPTIONS.en.md](docs/OPTIONS.en.md#usage-1--script).

## Why it holds up

| Strength | What it means |
|---|---|
| **Enforced by git, not by prompts** | `.git/hooks/pre-commit` blocks staged `.env`/secrets, broken builds, type and lint errors. It holds whichever AI tool you use — and when a human commits by hand. |
| **One source, three agents** | `AGENTS.md` is the single source of truth; Claude Code, Codex and Antigravity all read it natively. Skills live once in `.agents/skills/`; Codex subagents (`.codex/agents/*.toml`), Antigravity rules, subagents and hooks are generated from `.claude/`. |
| **Measured, not assumed** | Every harness claim is backed by a live measurement in [docs/harness-matrix.json](docs/harness-matrix.json) — Claude Code and Antigravity at the **full** tier, Codex at **baseline**. CI fails when a measurement expires. |
| **12 stack presets** | Next.js, Spring Boot, Java web (JSP), Bun, Python, Go, Rust, Ruby on Rails, .NET, Android, Flutter, ops — each adds rules and its own build/lint/test gate. GitHub or GitLab forge, Korean or English output. |
| **Path-scoped rules** | A rule loads only while the agent touches matching files, so context stays lean instead of front-loading every convention. |
| **24 skills out of the box** | Workflow (review, status, handoff, docs-sync, security pre-check, ...) plus `yd-*` expert skills: PostgreSQL, Oracle, SQLite, relational design, Go, React, TypeScript, Vite/pnpm builds, mobile screen design, and **dependency CVE checks** (`pnpm audit` online, OSV dump offline). |
| **Air-gapped and Windows ready** | An offline bundle installs with no network; Windows runs through Git Bash with a `.cmd` launcher ([docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md)). |
| **Plugin marketplace** | The skills also install globally as a Claude Code / Codex plugin — no clone needed. |
| **Self-improving** | `skill-evolve` / `agent-evolve` turn real mistakes into "Learned warnings" in the skill or agent that made them. |
| **Tested** | 89 bats regression tests for the installer, per-skill contract tests, a link checker for the docs, all in CI. |

## What happens the moment it's installed

When an agent — or a person — tries to commit a secret, **the commit does not happen.**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

This is not the same as writing "don't commit secrets" in a doc. A git hook is what stops it.

## What you get

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="One command → a .claude/ you own (agents, skills, commands, rules, hooks, memory, AGENTS.md) → enforced gates blocking staged .env, broken builds, failing lint" src="docs/assets/overview-light.svg">
</picture>

One minute after install, the agent behaves like a teammate who knows the rules — even if you're new to prompting:

- **The workflow is the default**: say "build the login feature" and the agent follows
  issue → branch → implementation → tests → PR/MR on its own (`/fix-issue`;
  `/sdlc-cycle` runs an unattended cycle with three role-separated agents).
- **Mistakes are blocked by machinery**: committing `.env`/secrets, broken builds/type errors, or new JSP
  scriptlets is stopped by the pre-commit hook, and functions over cognitive complexity 15 get flagged.
- **Tiered rules**: P0 (absolute — secrets, destructive SQL, force push), P1 (required — issue links, tests),
  P2 (recommended) — written once in `AGENTS.md`, enforced where a tool can enforce them.
- **One-shot commands**: `/review` (code review + security audit), `/status`, `/knowledge-graph`
  (doc link checker), `/sonar`.
- **Requirements hardening, your pick of three**: the bundled **`grill-me`**, or two external tools depending on
  the job → [Picking a requirements-hardening tool](docs/OPTIONS.en.md#picking-a-requirements-hardening-tool).
- **Memory that survives sessions**: project learnings accumulate under `.claude/memory/`, load automatically
  next session, and are shared with the team.
- **Team and multi-session safe**: per-session git worktree isolation is the default, so parallel agents never
  trample each other's work.

## Skills

The default install ships 24 skills: 10 workflow skills and 14 `yd-*` expert skills (databases, Go, React,
TypeScript, builds, screen design, Korean writing, dependency CVE checks). 9 more `yd-*` skills tied to the
maintainer's environment install only with `--with-personal-skills`. The `yd-*` skills are written in Korean.
The full list and authoring rules are in [.claude/skills/README.md](.claude/skills/README.md).

**Install the skills globally as a plugin.** Claude Code and Codex read the same `.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

`yd-skills` carries the 14 `yd-*` skills plus `handoff`, `docs-sync`, `memory-factcheck` and `skill-evolve`;
`yd-skills-personal` carries the 9 opt-in ones. In Claude Code, plugin skills are namespaced (`yd-skills:yd-pg-expert`).
A plugin carries skills only — project rules, hooks and subagents come from the installer, because Claude Code
plugins cannot ship rules and Codex plugins cannot ship subagents. Each plugin also has an Antigravity manifest
(`.antigravity-plugin/plugin.json`), written from the agy docs and not yet measured. Offline or for development,
clone this repo and run `scripts/install-skills.sh` (symlinks into `~/.claude/skills`, `~/.agents/skills` and
`~/.gemini/config/skills`; supports `--personal`, `--copy` and `--project <dir>`).

## How it compares

| | A hand-written `CLAUDE.md` | Installable agent frameworks | agents-scaffold |
|---|---|---|---|
| Rules actually enforced | No — the agent may ignore them | Often inside the agent runtime | Yes — git hook + CI, outside any agent |
| Works across Claude Code, Codex, Antigravity | No | Usually one vendor | Yes — `AGENTS.md` + generated adapters |
| Something to install and keep upgrading | Nothing | A runtime or CLI | Nothing — plain files in your repo |
| Offline / air-gapped install | n/a | Rarely | Yes — offline bundle |

## Going further

| Doc | What's in it |
|---|---|
| [docs/OPTIONS.en.md](docs/OPTIONS.en.md) | Every option — 12 stack presets, `--forge`, `--harness`, `--lang`, `--update`, `--with-personal-skills`, placeholder substitution |
| [docs/INTERNALS.en.md](docs/INTERNALS.en.md) | Internals — the full generated tree, repository layout, key patterns |
| [docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md) | Air-gapped and Windows install — offline bundle, Git Bash, `.cmd` launcher, `python3` setup |
| [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) | Stack preset format (Korean) |
| [dotfiles/](dotfiles/README.md) | The maintainer's machine shell setup (zsh, starship, Claude/Codex/agy status lines). Separate from the scaffold install (Korean) |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) for the
stack preset format. New here? Start with a
[`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) —
adding a new stack preset is the most approachable one, since the layout is fully templated.

## License

MIT — see [LICENSE](LICENSE). Third-party origins (skills, docs) are listed in [CREDITS.md](CREDITS.md) and
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
