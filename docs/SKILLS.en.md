# agents-scaffold — skills

Which skills an install gets, and how to install the skills without the scaffold. Start at the
[README](../README.md). 한국어: [SKILLS.md](SKILLS.md).

## What an install gets

| Install | Skills | Subagents | Contents |
|---|---|---|---|
| `--lang en` | 10 | 7 | The workflow skills, in English |
| `--lang ko` (default) | 24 | 19 | The workflow skills in Korean plus 14 `yd-*` expert skills and their 12 agents |
| either, with `--with-personal-skills` | +9 | +4 | `yd-*` skills tied to the maintainer's environment |

**The 10 workflow skills**: `review`, `status`, `search-first`, `security-precheck`, `docs-sync`, `handoff`,
`memory-factcheck`, `skill-evolve`, `grill-me`, and `example-skill` — a template to copy when you write your own.

**The 14 `yd-*` expert skills**: `yd-pg-expert`, `yd-oracle-expert`, `yd-sqlite-expert`, `yd-db-expert`,
`yd-go-expert`, `yd-react-expert`, `yd-typescript`, `yd-frontend-build`, `yd-cve-check`, `yd-mobile-web-planner`,
`yd-nextjs-implementer`, `yd-blueprint`, `yd-agents-yaml`, `yd-writer-kr`. They are written in Korean and have no
English overlay, which is why `--lang en` leaves them out.

| Option | Effect |
|---|---|
| `--with-yd-skills` | Add the 14 `yd-*` skills (and their agents) to an English install |
| `--no-yd-skills` | Leave them out of a Korean install |
| `--with-personal-skills` | Also install the 9 opt-in skills. They assume a specific GitLab, hosts, ui.doksam.com and FinGuard, so they are not meant for other environments |

The choice is recorded in `.claude/.scaffold.json`, so `--update` keeps the same sets. The per-skill table and the
authoring rules are in [.claude/skills/README.md](../.claude/skills/README.md) (Korean).

Skills live once in `.agents/skills/` (the path Codex and Antigravity read) and Claude Code reads the same files
through the symlink `.claude/skills -> ../.agents/skills`. See
[OPTIONS.en.md](OPTIONS.en.md#harness---harness) for the copy mode used where symlinks are unavailable.

## Install the skills globally as a plugin

Claude Code and Codex read the same `.claude-plugin/marketplace.json`:

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

- `yd-skills` carries the 14 `yd-*` skills plus `handoff`, `docs-sync`, `memory-factcheck` and `skill-evolve`.
  `yd-skills-personal` carries the 9 opt-in ones. Both are Korean.
- In Claude Code, plugin skills are namespaced (`yd-skills:yd-pg-expert`).
- A plugin carries skills only. Project rules, hooks and subagents come from the installer, because Claude Code
  plugins cannot ship rules and Codex plugins cannot ship subagents.
- Each plugin also has an Antigravity manifest (`.antigravity-plugin/plugin.json`), written from the agy docs.
  `agy plugin validate` passes on agy 1.5.0; installation has not been measured.

## Install with the `skills` CLI

[vercel-labs/skills](https://github.com/vercel-labs/skills) finds this repo's skills (`.claude/skills/` plus the
plugin marketplace) and installs the ones you pick into any agent it supports:

```bash
npx skills add LeeYudok/agents-scaffold                            # pick from the 21 general skills
npx skills add LeeYudok/agents-scaffold --skill yd-cve-check -a claude-code
INSTALL_INTERNAL_SKILLS=1 npx skills add LeeYudok/agents-scaffold  # also the scaffold-only and personal ones
```

The 21 are the 7 workflow skills that run on their own plus the 14 `yd-*` skills. `review` and `security-precheck`
need the scaffold's subagents and `example-skill` is a template, so the three are hidden from the CLI
(`metadata.internal`) and come with the installer. `.claude/skills/` holds the Korean originals; the English
versions of the workflow skills come with a `--lang en` install.

## Offline or for development: `install-skills.sh`

Clone this repo and run `scripts/install-skills.sh`. It symlinks the skills into `~/.claude/skills`,
`~/.agents/skills` and `~/.gemini/config/skills`, and supports `--personal`, `--copy` and `--project <dir>`.

For Antigravity globals the two tools use different paths: `skills` 1.7.6 writes to
`~/.gemini/antigravity-cli/skills`, while `install-skills.sh` uses `~/.gemini/config/skills`
([vercel-labs/skills#1483](https://github.com/vercel-labs/skills/pull/1483) would align them).
