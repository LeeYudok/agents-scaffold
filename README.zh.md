# agents-scaffold

[English](README.md) | [한국어](README.ko.md) | 简体中文 | [日本語](README.ja.md)

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

**为 AI 编码代理（Claude Code、Codex、Antigravity）设置护栏，由真正的 git pre-commit 门禁强制执行。**

AI 编码代理不守规则。这个工具不是好言相劝，而是直接拦下提交。
一条命令，就把作为项目大脑的 `AGENTS.md`、按路径作用域加载的规则、技能、子代理、钩子以及组合而成的
pre-commit 门禁装进你的仓库。没有框架、没有运行时、没有注册中心 — **你得到的是完全归你所有的普通文件。**

![演示：一条命令完成引导、生成的 .claude/ 目录树，以及 pre-commit 门禁拦截暂存的 .env](docs/assets/demo.gif)

_30 秒演示：一条命令 → 填充完毕的 `.claude/` → 门禁拦截了一次泄露密钥的提交。可用 `vhs docs/assets/demo.tape` 复现。_

## 如果你遇到过这些，就该用它

- 你在**每个会话里重复讲同样的规则** — 昨天告诉代理的，今天又忘了。
- 代理把 `.env` 加进了暂存区，或者带着类型错误就生成了提交。
- 每个同事的 `CLAUDE.md` 都不一样，**结果取决于是谁的会话。**
- 团队混用 Claude Code、Codex 和 Antigravity，你希望**用一套规则管住所有代理。**
- 你在**内网（离线）或 Windows** 上工作，而大多数代理配置对这两者都不支持。

只写在文档里的规则，迟早会被无视。这个脚手架把规则变成
**能拦住提交的门禁**，并把它种进仓库。

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

已经装过？`--update` 会刷新基础文件，并在你改过的文件旁写出 `<file>.new`，
因此你的修改永远不会被覆盖。完整选项见 [docs/OPTIONS.zh.md](docs/OPTIONS.zh.md#usage-1--脚本)。

## 为什么靠得住

| 优势 | 含义 |
|---|---|
| **由 git 强制，而非靠提示词** | `.git/hooks/pre-commit` 会拦截暂存的 `.env`/密钥、失败的构建、类型和 lint 错误。无论你用哪个 AI 工具，乃至人手动提交，它都一样生效。 |
| **一个源头，三个代理** | `AGENTS.md` 是单一事实来源（SSOT），Claude Code、Codex 和 Antigravity 都原生读取它。技能只在 `.agents/skills/` 存放一份；Codex 子代理（`.codex/agents/*.toml`）以及 Antigravity 的规则、子代理和钩子都由 `.claude/` 生成。 |
| **实测，而非假设** | 每一条关于 harness 的说法都有 [docs/harness-matrix.json](docs/harness-matrix.json) 中的实测记录支撑 — Claude Code 和 Antigravity 达到 **full** 级别，Codex 为 **baseline**。实测记录过期时 CI 会失败。 |
| **12 种技术栈预设** | Next.js、Spring Boot、Java web（JSP）、Bun、Python、Go、Rust、Ruby on Rails、.NET、Android、Flutter、ops — 每种都会添加规则和各自的 build/lint/test 门禁。支持 GitHub 或 GitLab forge，输出可选韩文或英文。 |
| **按路径作用域加载的规则** | 规则只在代理触碰匹配文件时才加载，上下文保持精简，而不是一开始就灌入全部约定。 |
| **开箱即用的 24 个技能** | 工作流技能（review、status、handoff、docs-sync、安全预检等）加上 `yd-*` 专家技能：PostgreSQL、Oracle、SQLite、关系型设计、Go、React、TypeScript、Vite/pnpm 构建、移动端界面设计，以及**依赖 CVE 检查**（在线用 `pnpm audit`，离线用 OSV 数据转储）。 |
| **支持内网与 Windows** | 离线包无需网络即可安装；Windows 通过 Git Bash 和 `.cmd` 启动器运行（[docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md)）。 |
| **插件市场** | 这些技能也可以作为 Claude Code / Codex 插件全局安装 — 无需 clone。 |
| **自我改进** | `skill-evolve` / `agent-evolve` 会把真实错误提炼成 "Learned warnings"，写回犯错的那个技能或代理。 |
| **经过测试** | 安装器有 89 个 bats 回归测试，每个技能有契约测试，文档有链接检查器，全部在 CI 中运行。 |

## 装好之后会发生什么

当代理（或人）试图提交密钥时，**提交根本不会发生。**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

这与在文档里写一句"不要提交密钥"完全不同。拦下它的是 git 钩子。

## 你会得到什么

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="一条命令 → 一个归你所有的 .claude/（agents、skills、commands、rules、hooks、memory、AGENTS.md）→ 强制门禁拦截暂存的 .env、失败的构建和不通过的 lint" src="docs/assets/overview-light.svg">
</picture>

安装一分钟后，代理的表现就像一位熟知规则的同事。即使你刚接触 prompt 编写也没关系：

- **工作流即默认行为**：只要说"实现登录功能"，代理就会自行遵循
  issue → 分支 → 实现 → 测试 → PR/MR 的流程（`/fix-issue`；
  `/sdlc-cycle` 由三个职责分离的 agent 无人值守地跑完一个完整周期）。
- **错误由机制拦截**：提交 `.env`/密钥、构建失败/类型错误、新增 JSP
  scriptlet 都会被 pre-commit 钩子拦下，认知复杂度超过 15 的函数会被标记。
- **分级规则**：P0（绝对 — 密钥、破坏性 SQL、force push）、P1（必需 — 关联 issue、测试）、
  P2（推荐）— 在 `AGENTS.md` 中只写一次，凡是工具能强制的地方就强制执行。
- **一键命令**：`/review`（代码评审 + 安全审计）、`/status`、`/knowledge-graph`
  （文档链接检查器）、`/sonar`。
- **需求打磨，三种方式任选**：内置的 **`grill-me`**，或按场景选用两个外部工具 →
  [挑选需求打磨工具](docs/OPTIONS.zh.md#挑选需求打磨工具)。
- **跨会话留存的记忆**：项目经验持续沉淀在 `.claude/memory/` 下，下次会话自动加载，
  并与团队共享。
- **团队/多会话安全**：默认按会话隔离 git worktree，并行的代理互不踩踏。

## 技能

默认安装包含 24 个技能：10 个工作流技能和 14 个 `yd-*` 专家技能（数据库、Go、React、
TypeScript、构建、界面设计、韩文写作、依赖 CVE 检查）。另有 9 个绑定维护者环境的 `yd-*` 技能，
仅在传入 `--with-personal-skills` 时安装。`yd-*` 技能以韩文编写。
完整列表与编写规范见 [.claude/skills/README.md](.claude/skills/README.md)。

**作为插件全局安装技能。** Claude Code 和 Codex 读取同一个 `.claude-plugin/marketplace.json`：

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

`yd-skills` 包含 14 个 `yd-*` 技能以及 `handoff`、`docs-sync`、`memory-factcheck`、`skill-evolve`；
`yd-skills-personal` 包含 9 个可选技能。在 Claude Code 中，插件技能带有命名空间（`yd-skills:yd-pg-expert`）。
插件只携带技能 — 项目规则、钩子和子代理由安装器提供，因为 Claude Code 插件不能携带 rules，
Codex 插件不能携带子代理。每个插件还带有 Antigravity 清单（`.antigravity-plugin/plugin.json`），依据 agy 文档编写，
尚未实测。离线或开发场景下，clone 本仓库并运行 `scripts/install-skills.sh`（在 `~/.claude/skills`、`~/.agents/skills`、
`~/.gemini/config/skills` 下创建符号链接；支持 `--personal`、`--copy`、`--project <dir>`）。

## 对比

| | 手写的 `CLAUDE.md` | 可安装的代理框架 | agents-scaffold |
|---|---|---|---|
| 规则是否真正强制执行 | 否 — 代理可能无视 | 通常在代理运行时内部 | 是 — git 钩子 + CI，独立于任何代理 |
| 跨 Claude Code、Codex、Antigravity 通用 | 否 | 通常只支持一家 | 是 — `AGENTS.md` + 生成的适配器 |
| 需要安装并持续升级的东西 | 无 | 一个运行时或 CLI | 无 — 仓库里的普通文件 |
| 离线 / 内网安装 | 不适用 | 很少支持 | 是 — 离线包 |

## 了解更多

| 文档 | 内容 |
|---|---|
| [docs/OPTIONS.zh.md](docs/OPTIONS.zh.md) | 全部选项 — 12 种技术栈预设、`--forge`、`--harness`、`--lang`、`--update`、`--with-personal-skills`、占位符替换 |
| [docs/INTERNALS.zh.md](docs/INTERNALS.zh.md) | 内部结构 — 生成的完整目录树、仓库布局、关键模式 |
| [docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md) | 内网与 Windows 安装 — 离线包、Git Bash、`.cmd` 启动器、`python3` 设置（英文） |
| [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md) | 技术栈预设格式（韩文） |
| [dotfiles/](dotfiles/README.md) | 维护者的机器 shell 环境配置（zsh、starship、Claude/Codex/agy 状态栏）。与 scaffold 安装无关（韩文） |

## 贡献

工作流见 [CONTRIBUTING.md](CONTRIBUTING.md)，技术栈预设格式见 [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md)。
初来乍到？从
[`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 开始 —
新增一个技术栈预设是最容易上手的任务，因为其结构已完全模板化。

## License

MIT — 见 [LICENSE](LICENSE)。第三方来源（技能、文档）见 [CREDITS.md](CREDITS.md) 和
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)。
