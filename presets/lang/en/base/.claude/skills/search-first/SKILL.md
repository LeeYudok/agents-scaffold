---
name: search-first
description: 'A workflow that searches for an existing solution (this repo → internal mirrors → package registries → MCP/skills → GitHub) before writing new code. Triggers right before adding a new feature/utility/dependency, or the moment a "add feature X" request tempts you to jump straight to code. (Origin: the search-first skill from [affaan-m/ECC](https://github.com/affaan-m/ECC), MIT — ported and adapted)'
allowed-tools: Bash, Read, Grep, Glob, WebSearch, WebFetch
---

# search-first — search before you build

A workflow to avoid reinventing the wheel. Custom code is the **last resort when the search comes up empty**.

## When it triggers

- The moment you're about to build a new feature/utility/helper that likely already has an existing solution
- Right before adding a dependency or integration (external API, parser, client, etc.)
- The moment you receive an "add feature X" request and are about to jump straight to code

## Search order (inner → outer)

| Order | Channel | Method |
|---|---|---|
| 1 | **This repo** | Sweep related modules/tests with `rg` — it may already exist and simply be unnoticed |
| 2 | **Internal mirrors** | Check `<your-git-host>/mirrors/` group first (mirrors of OSS agents/skills/icons, etc.). Bring external originals in via the mirror rather than referencing them directly. Skip if there's no mirror group |
| 3 | **Package registries** | npm / PyPI / crates.io / etc., whichever fits the project's stack |
| 4 | **MCP / skills** | Check whether an already-connected MCP server provides the feature, or whether the same skill exists under `.claude/skills/` |
| 5 | **GitHub / web** | Search for a maintained OSS implementation or template. If adopted, fork it into mirrors before use |

If a channel is unavailable (offline, no auth, etc.), **don't silently skip it** — state explicitly which channel could not be checked.

## Evaluate → decide

Evaluate candidates on feature fit / maintenance status (recent commits, issue responsiveness) / license / dependency weight.

| Signal | Decision |
|---|---|
| Exact fit + well maintained + MIT/Apache | **Adopt** — install and use as-is |
| Partial fit + good foundation | **Extend** — install + thin wrapper |
| Several weak candidates | **Combine** — compose 2-3 small packages |
| Nothing usable | **Build from scratch** — but informed by the designs seen during the search |

## Delegate non-trivial features to a subagent

```
Agent(subagent_type="general-purpose", model="sonnet", prompt="
  Investigate existing solutions for the following feature: [description]
  Language/framework: [stack], constraints: [if any]
  Search: this repo → internal mirrors (<your-git-host>/mirrors) → npm/PyPI → MCP → GitHub
  Return: a candidate comparison table + a recommendation to adopt/extend/build from scratch
")
```

## Anti-patterns

- **Straight to code**: writing a utility from scratch without searching
- **Ignoring mirrors**: referencing a GitHub original directly (the rule is to bring it into the internal mirror first, then use it)
- **Silent skipping**: reporting "nothing found" when a search channel was actually unreachable
- **Over-wrapping**: wrapping a library so heavily that its advantages are lost
- **Dependency bloat**: pulling in a massive package for one small feature
