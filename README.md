# agents-scaffold

English | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md)

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI coding agents break your rules. This blocks the commit instead of asking nicely.**

One command drops a `.claude/` setup and a pre-commit gate into your repo. No framework, no
runtime, no registry to install from — what you get is **plain files you own outright.**

![Demo: one-command bootstrap, the generated .claude/ tree, and the pre-commit gate blocking a staged .env](docs/assets/demo.gif)

_30-second demo: one command → a filled `.claude/` → the gate blocks a secret commit. Reproduce with `vhs docs/assets/demo.tape`._

## You want this if

- You **re-explain the same rules every session** — what you told the agent yesterday is gone today.
- An agent staged your `.env`, or produced a commit with type errors still in it.
- Every teammate has a different `CLAUDE.md`, so **results depend on whose session it was.**

Rules that live only in a document get ignored eventually. This scaffold turns them into a
**gate that blocks the commit**, and plants it in the repo.

## Quickstart

```bash
# one command, no clone required
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# or from a local clone (prompts interactively when options are omitted)
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

You get a filled-in `.claude/` directory (agents, skills, hooks, paths-scoped
rules, memory), an `AGENTS.md` project brain, and a single composed pre-commit
gate — plain files you own outright. Full options: see [Usage](docs/OPTIONS.en.md#usage-1--script).

## What happens the moment it's installed

When an agent — or a person — tries to commit a secret, **the commit does not happen.**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

This is not the same as writing "don't commit secrets" in a doc. `.git/hooks/pre-commit` is what
stops it, so **it holds whichever AI tool you use, and it holds when a human commits by hand.**

## What you get — for beginners

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="One command → a .claude/ you own (agents, skills, commands, rules, hooks, memory, AGENTS.md) → enforced gates blocking staged .env, broken builds, failing lint" src="docs/assets/overview-light.svg">
</picture>

One minute after install, Claude behaves like a teammate who knows the rules. Even if
you're new to prompting:

- **The workflow is the default**: say "build the login feature" and Claude follows
  issue → branch → implementation → tests → PR/MR on its own (`/fix-issue`;
  `/sdlc-cycle` runs an unattended cycle with three role-separated agents).
- **Mistakes are blocked by machinery**: committing `.env`/secrets, broken
  builds/type errors, or new JSP scriptlets is stopped by the pre-commit hook, and
  functions over complexity 15 get flagged — gates that catch things even when
  Claude forgets.
- **One-shot commands**: `/review` (code review + security audit), `/status`,
  `/knowledge-graph` (doc link checker), `/sonar`.
- **Requirements hardening, your pick of three**: beyond the bundled **`grill-me`**, two
  external tools plug in depending on the job →
  [Picking a requirements-hardening tool](docs/OPTIONS.en.md#picking-a-requirements-hardening-tool).
- **Memory that survives sessions**: project learnings accumulate under
  `.claude/memory/`, auto-load next session, and are shared with the team.
- **Self-evolving**: skill-evolve/agent-evolve rewrite skill/agent definitions from
  failure feedback — it gets better the more you use it.
- **Team/multi-session safe**: per-session git worktree isolation is the default, so
  parallel work never tramples each other.

## Why agents-scaffold

Unlike large installable frameworks or agent/skill catalogs, agents-scaffold ships
no runtime, no plugin system, and no central registry to keep in sync — it is
a `.claude/` directory skeleton plus a handful of stack presets that you copy
into a repo once and then own outright. There is nothing to upgrade later:
you fork it, fill in the placeholders, delete what you don't need, and the
result is plain files under version control like any other code in the repo.

- **Enforced, not aspirational** — the P0/P1/P2 tiers are wired into hooks
  (pre-commit gate, deny rules, CC warnings), not just written down in prose.
- **Paths-scoped rules** — a rule loads only while you touch matching files,
  so context stays lean instead of front-loading every convention.
- **Self-improving** — `skill-evolve`/`agent-evolve` append "Learned warnings"
  to skills and agents from real mistakes.
- **Tested** — the bootstrap script ships with a bats regression suite, and a
  knowledge-graph link checker gates the docs.

## Going further

| Doc | What's in it |
|---|---|
| [docs/OPTIONS.en.md](docs/OPTIONS.en.md) | Every option — 12 stack presets, `--forge`, `--harness`, `--lang`, usage, placeholder substitution, picking a requirements-hardening tool |
| [docs/INTERNALS.en.md](docs/INTERNALS.en.md) | Internals — the full generated `.claude/` tree, key patterns |
| [docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md) | Air-gapped & Windows install — offline bundle, Git Bash required, `.cmd` launcher, `python3` setup |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and
[docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) for the stack preset format.
New here? Start with a [`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) —
adding a new stack preset is the most approachable one, since the layout is fully templated.

## License

MIT — see [LICENSE](LICENSE). Third-party origins (skills/docs) are listed in [CREDITS.md](CREDITS.md).
