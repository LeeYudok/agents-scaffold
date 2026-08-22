# agents-scaffold

[English](README.md) | [한국어](README.ko.md) | 简体中文 | [日本語](README.ja.md)

[![tests](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml/badge.svg)](https://github.com/leeyudok/agents-scaffold/actions/workflows/test.yml)
**[leeyudok.github.io/agents-scaffold](https://leeyudok.github.io/agents-scaffold/)**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**AI 编码代理不守规则。这个工具不是好言相劝，而是直接拦下提交。**

一条命令，就把 `.claude/` 配置和 pre-commit 门禁装进你的仓库。没有框架、没有运行时、没有要接入的注册中心 — 你得到的是**完全归你所有的普通文件。**

![演示：一条命令完成引导、生成的 .claude/ 目录树，以及 pre-commit 门禁拦截暂存的 .env](docs/assets/demo.gif)

_30 秒演示：一条命令 → 填充完毕的 `.claude/` → 门禁拦截了一次泄露密钥的提交。可用 `vhs docs/assets/demo.tape` 复现。_

## 如果你遇到过这些，就该用它

- 你在**每个会话里重复讲同样的规则** — 昨天说过的，今天又不认识了。
- 代理把 `.env` 加进了暂存区，或者带着类型错误就生成了提交。
- 每个同事的 `CLAUDE.md` 都不一样，**结果取决于是谁的会话。**

只写在文档里的规则，AI 迟早会无视。这个脚手架把规则变成**能拦住提交的门禁**，并把它种进仓库。

## Quickstart

```bash
# 一条命令，无需 clone
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes

# 或从本地克隆运行（省略选项时会进入交互式提问）
git clone https://github.com/leeyudok/agents-scaffold.git
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

你将得到一个填充完毕的 `.claude/` 目录（agents、skills、hooks、按路径作用域加载的
规则、memory）、一份作为项目大脑的 `AGENTS.md`，以及一个组合而成的 pre-commit
门禁——全部是完全归你所有的普通文件。完整选项见 [Usage](docs/OPTIONS.zh.md#usage-1--脚本)。

## 装好之后会发生什么

当代理（或人）试图提交密钥时，**提交根本不会发生。**

```console
$ bash agents-scaffold.sh . --stack python --name payments --yes
$ echo 'DB_PASSWORD=hunter2' > .env
$ git add -f .env app.py && git commit -m "feat: add config"
Blocked: a .env-type file is staged. Commit is not allowed.
```

这与在文档里写一句"不要提交密钥"完全不同。拦下它的是 `.git/hooks/pre-commit`，因此**无论你用哪个 AI 工具，也无论是人在终端手动提交，都一样会被拦住。**

## 你会得到什么 — 写给新手

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/overview-dark.svg">
  <img alt="一条命令 → 一个归你所有的 .claude/（agents、skills、commands、rules、hooks、memory、AGENTS.md）→ 强制门禁拦截暂存的 .env、失败的构建和不通过的 lint" src="docs/assets/overview-light.svg">
</picture>

安装一分钟后，Claude 的表现就像一位熟知团队规则的同事。即使你刚接触
prompt 编写也没关系：

- **工作流即默认行为**：只要说"实现登录功能"，Claude 就会自行遵循
  issue → 分支 → 实现 → 测试 → PR/MR 的流程（`/fix-issue`；
  `/sdlc-cycle` 由三个职责分离的 agent 无人值守地跑完一个完整周期）。
- **错误由机制拦截**：提交 `.env`/密钥、构建失败/类型错误、新增 JSP
  scriptlet 都会被 pre-commit 钩子拦下，认知复杂度超过 15 的函数会被
  标记——即使 Claude 忘了规则，门禁也能兜底。
- **一键命令**：`/review`（代码评审 + 安全审计）、`/status`、
  `/knowledge-graph`（文档链接检查器）、`/sonar`。
- **需求打磨，三种方式任选**：除内置的 **`grill-me`** 外，还可按场景接入两个外部工具 →
  [挑选需求打磨工具](docs/OPTIONS.zh.md#挑选需求打磨工具)。
- **跨会话留存的记忆**：项目经验持续沉淀在 `.claude/memory/` 下，
  下次会话自动加载，并与团队共享。
- **自我进化**：skill-evolve/agent-evolve 会根据失败反馈重写 skill/agent
  定义——用得越多越好用。
- **团队/多会话安全**：默认按会话隔离 git worktree，并行工作互不
  踩踏。

## 为什么选择 agents-scaffold

与大型可安装框架或 agent/skill 目录不同，agents-scaffold 不附带运行时、
不带插件系统、也没有需要保持同步的中心化 registry——它只是一个 `.claude/`
目录骨架加上几个技术栈预设，复制进仓库一次之后就完全归你所有。日后没有
任何东西需要升级：fork 它、填好占位符、删掉不需要的部分，最终得到的就是
和仓库里其他代码一样纳入版本控制的普通文件。

- **强制执行，而非纸上谈兵** —— P0/P1/P2 分级接入了钩子机制
  （pre-commit 门禁、deny 规则、CC 警告），不只是写在文档里。
- **按路径作用域加载的规则** —— 规则只在你触碰匹配文件时才加载，
  上下文保持精简，而不是一开始就灌入全部约定。
- **自我改进** —— `skill-evolve`/`agent-evolve` 会把真实错误提炼成
  "Learned warnings" 追加到 skill 和 agent 里。
- **经过测试** —— 引导脚本附带 bats 回归测试套件，知识图谱链接
  检查器为文档把关。

## 了解更多

| 文档 | 内容 |
|---|---|
| [docs/OPTIONS.zh.md](docs/OPTIONS.zh.md) | 全部选项 — 10 种技术栈预设、`--forge`、`--harness`、`--lang`、用法、占位符替换、需求打磨工具的挑选 |
| [docs/INTERNALS.zh.md](docs/INTERNALS.zh.md) | 内部结构 — 生成的完整 `.claude/` 目录树、关键模式 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |

## 贡献

工作流见 [CONTRIBUTING.md](CONTRIBUTING.md)，
技术栈预设格式见 [docs/PRESET_SPEC.md](docs/PRESET_SPEC.md)。
初来乍到？从 [`good first issue`](https://github.com/LeeYudok/agents-scaffold/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) 开始——
新增一个技术栈预设是最容易上手的任务，因为其结构已完全模板化。

## License

MIT —— 见 [LICENSE](LICENSE)。第三方来源（技能/文档）见 [CREDITS.md](CREDITS.md)。
