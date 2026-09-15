# agents-scaffold — 全部选项

`bin/agents-scaffold.sh` 的全部选项。概览请见 [README](../README.zh.md)。

## 技术栈预设

| 预设 | 规则文件 | pre-commit 门禁 |
|--------|-----------|-----------------|
| `nextjs` | nextjs.md (paths: app/**, components/**) | `tsc --noEmit` |
| `springboot` | springboot.md (paths: src/main/java/**) | `./gradlew build` |
| `javaweb` | javaweb.md (paths: src/main/java/**, **/*.jsp) | maven/gradle/ant compile（自动检测） |
| `bun` | bun.md (paths: **/*.ts) | `bunx tsc --noEmit` |
| `python` | python.md (paths: **/*.py) | `ruff check` + `mypy` |
| `go` | go.md (paths: **/*.go) | `go build ./...` + `vet` + `golangci-lint` |
| `rust` | rust.md (paths: src/**/*.rs, **/*.rs) | `cargo check` + `clippy` |
| `android` | android.md (paths: **/*.kt) | `./gradlew ktlintCheck detekt` |
| `flutter` | flutter.md (paths: **/*.dart, pubspec.yaml) | `dart format` + `flutter analyze` + `test` |
| `ruby-rails` | ruby-rails.md (paths: app/**/*.rb, config/**/*.rb, Gemfile) | `rubocop` + `rspec` |
| `dotnet` | dotnet.md (paths: **/*.cs, **/*.csproj, appsettings*.json) | `dotnet build` + `format --verify-no-changes` + `test` |
| `ops` | ops.md (paths: Dockerfile, docker-compose*, quadlet/**, ansible/**) | — |

## Forge 预设（`--forge`）

注入与你所用 forge 匹配的 issue/PR 工作流。在技术栈预设之前合并。

| 预设 | CLI | PR/MR | issue 关闭 |
|--------|-----|-------|-------------|
| `github`（默认） | `gh` | PR | 合并时通过 `Closes #N` **自动关闭** |
| `gitlab` | `glab` | MR | `Closes #N` 自动关闭有效 —— 合并后需确认，仍处于 open 时才手动关闭 |

注入的文件：`.claude/rules/forge.md`（始终加载），以及
`.claude/commands/fix-issue.md` 和 `sdlc-cycle.md` 的 forge 变体（覆盖基础版本）。
基础文件保持 forge 中立（"issue / PR·MR"）。

## 挑选需求打磨工具

实现之前打磨需求的手段有三种，**性质各不相同，按任务挑选**。内置的只有 `grill-me`，另外两个需单独安装。

| | `grill-me` | superpowers | Ouroboros |
|---|---|---|---|
| **范围** | 仅拷问 | 覆盖整个工作流 | 拷问 → 规格 → 执行 → 评估 循环 |
| **状态** | 止于对话之内 | 对话 + 文件产物 | 由 MCP 服务器持久管理 |
| **重量** | 轻 | 中 | 重 — 每个问题都会 fanout 子代理 |
| **安装** | **内置**（`.claude/skills/grill-me/`） | 插件 [obra/superpowers](https://github.com/obra/superpowers) | 市场 [Q00/ouroboros](https://github.com/Q00/ouroboros)（附带 MCP 服务器） |

**选择标准**

- 方向已定的功能，想找出规格中的漏洞 → **`grill-me`**。无需安装，一轮对话即可。
- 一张白纸需要发散再收敛，并留下文档产物 → **superpowers 的 `brainstorming`**。
- 需求模糊的大型工作，需要**先规格化，再以循环方式执行与评估** → **Ouroboros**。会话中断后状态仍在，但 token 成本三者中最高。

按重量逐级升级，且**只向上走** — 轻量方案够用的任务上动用 Ouroboros 只会推高成本。三者即便都已安装也不会自动触发，由使用者按任务选定。

## Harness（`--harness`）

| 取值 | 目标 | 行为 |
|---|---|---|
| `claude`（默认） | Claude Code | 完整安装 — 含 settings.json 钩子绑定、子代理、斜杠命令、workflows |
| `codex` | Codex | 安装 `AGENTS.md`、原生 `.agents/skills` 与共享 rules/hooks/memory，并移除 Claude 专用层 |
| `all` | 混合团队 | 同时安装 `.claude/skills` 与 Codex 原生 `.agents/skills` |

**保障分为两级（#21）** — 不是"支持/不支持"的二分法。

| 级别 | 成立的内容 | 适用 harness |
|---|---|---|
| **baseline** | `AGENTS.md` 正文中的 P0/P1（含所选技术栈的 P0）+ **真正的 `.git/hooks/pre-commit` 门禁** + CI | **全部 harness，与 `--harness` 取值无关。** 无论 harness 读取什么，也无论是否由人在终端直接提交，门禁都会生效 |
| **full** | baseline + 该 harness 的原生层（子代理、skills、斜杠命令、按路径的条件加载、lifecycle 钩子） | 仅限适配器经过实测验证的 harness |

git 钩子**与 harness 无关，始终接入**（#21）。Claude Code 的 `PreToolUse` 钩子只在该会话通过 Bash 工具提交时触发，因此它属于早期反馈层而非强制线 — 决定性的强制线放在 harness 之外（`.git/hooks` + CI）。已存在的 `.git/hooks/pre-commit` 不会被覆盖，只会给出警告。

所选技术栈的 P0 会**直接插入 `AGENTS.md` 正文**，不依赖 `.claude/rules/` 引用链接，因此在不加载 `.claude/` 的 harness 上同样可达。未选择的技术栈不会被插入（Codex 指令合计默认上限为 32KiB — 以避免 context flooding）。

### 实测验证（2026-09-15）

| Harness | 实测版本 | baseline | full 层已确认 / 未确认的内容 |
|---|---|---|---|
| Claude Code | 2.1.239 | 成立 | `.claude/rules/*.md` 的 `paths:` 条件加载、子代理、skills、`settings.json` 钩子 — 均已对照[官方文档](https://code.claude.com/docs/en/memory.md)确认 |
| Codex | codex-cli 0.154.0 / GPT-6 Astra | 成立 | 已实测 `AGENTS.md`、内联技术栈 P0、`.agents/skills` 与 `.env` 门禁 |
| Antigravity | agy **1.1.18**（未重测） | 成立 | 1.1.17 上实测 **headless（`-p`）不加载规则** — 原因未查明。1.1.18 与交互模式均未重测 |

Codex（codex-cli 0.154.0，`gpt-6-astra`）会自动加载 `codex` 模式产物中的 AGENTS.md 与内联技术栈 P0，并发现 `.agents/skills` 下的仓库 skills；`.claude/skills` 不会被发现。即使模型遗漏规则，git 钩子仍会以 exit 2 拦截已暂存的 `.env`。

支持状态的单一真实来源是 [`docs/harness-matrix.json`](harness-matrix.json)。本表会与该 manifest 对照，并由 CI 中的 `scripts/check-harness-matrix.py` 检查 — 若某个 `full` 等级超过 90 天未重新实测，或某项判定缺少证据，**构建将失败**。重新实测请运行 `scripts/spike-codex-contract.sh --dynamic`。

`--harness codex` 会把仓库 skills 安装到 Codex 原生的 `.agents/skills` 路径；`--harness all` 同时保留 Claude/Antigravity 使用的 `.claude/skills` 与 Codex 使用的 `.agents/skills`。Codex 子代理、路径条件规则和 lifecycle 钩子尚未验证，因此整体等级仍为 baseline。

另有两项 Codex 约束影响设计：

- **指令合计默认上限 32KiB**（`project_doc_max_bytes`），因此只把所选技术栈的 P0 内联进 `AGENTS.md`（`--stack javaweb` 实测 6,869 B — 占上限的 21%）。
- **`.codex/` 层仅在项目受信任时加载。** 生成文件并不等于生效，因此决定性的强制线放在 `.git/hooks` + CI。

## 语言（`--lang`）

基础目录树（agents、rules、skills、commands、`AGENTS.md`、钩子/settings
消息）**默认为韩语**（#36 反转——韩语是事实来源，英语是翻译出的覆盖层）。
`--lang en` 会把英文翻译叠加在最上层，且最后应用——在基础复制、forge 预设、
技术栈预设之后——用 `presets/lang-en/base` +
`presets/lang-en/forge-<forge>` + `presets/lang-en/stacks/<stack>` 的内容
覆盖同名文件。

```bash
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --lang en --forge github --stack bun
```

`.claude/hooks/pre-commit.sh` 永远不会被 `--lang` 覆盖（它是技术栈片段
拼接进去的文件——消息只有单一语言，代码不受语言影响）。`--update`
只刷新韩语基础文件；若需要重新应用英文覆盖层，请在其后再带
`--lang en` 运行一次。

## Usage 1 — 脚本

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
# --forge 默认为 github；GitLab 仓库请用 --forge gitlab
agents-scaffold/bin/agents-scaffold.sh /path/to/new-repo --forge github --stack nextjs,bun --name my-app
```

省略 `--forge`/`--stack`/`--name` 即进入交互模式——脚本会依次询问
（forge 默认为 github）。

### 选项

| 选项 | 说明 |
|---|---|
| `<target-dir>` | 目标目录。默认 `.` |
| `--forge <forge>` | `github`（默认）或 `gitlab` |
| `--lang <lang>` | `ko`（默认）或 `en` |
| `--stack <list>` | 逗号分隔的技术栈预设列表。省略时进入交互式提问 |
| `--name <name>` | `{{PROJECT_NAME}}` 的替换值。默认 = 目标目录名 |
| `--yes` | 跳过交互式提问（非交互模式） |
| `--update` | 刷新已引导项目的基础文件（见下文） |

### 远程一键安装（无需 clone）

```bash
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/main/bin/agents-scaffold.sh | bash -s -- --stack nextjs --yes
```

当脚本检测到自己并非从本地检出运行时（例如管道执行），会将
`AGENTS_SCAFFOLD_REPO` 的 tarball（默认：
`github.com/leeyudok/agents-scaffold`，可通过环境变量覆盖）下载到临时目录，
并将其作为模板来源。用 `AGENTS_SCAFFOLD_REF` 固定分支/标签
（默认 `main`）。

### 更新基础文件 — `--update`

将最新的基础文件（`.claude/`、`AGENTS.md`、`CLAUDE.md`、
`GEMINI.md`）应用到已完成引导的项目。

```bash
agents-scaffold/bin/agents-scaffold.sh --update /path/to/existing-repo
```

- `.claude/hooks/pre-commit.sh` 始终被跳过——技术栈片段已被拼接
  进去，需要手动合并。
- 其他基础文件内容相同时跳过；有差异时保留现有文件，新版本写为
  `<file>.new`（占位符替换同样作用于 `.new` 文件）。
- 结束时打印新增 / 待更新 / 跳过 / 未变更文件的汇总——用 `diff`
  查看 `.new` 文件后手动应用。

## Usage 2 — GitLab 模板

若想在创建新项目时自动应用这套配置，
请参阅 **[docs/GITLAB_TEMPLATE.md](GITLAB_TEMPLATE.md)**。

> 注意：该工作流假定使用自托管 GitLab 实例。在 **GitLab CE** 上，
> 原生的自定义项目模板属于 Premium 功能、不可用——
> 请改用 **Import by URL + `bin/agents-scaffold.sh`** 或**仅用脚本**。
> 创建/导入后运行一次 `bin/agents-scaffold.sh .`，即可应用所选
> 技术栈、替换占位符，并自清理 `bin/`/`presets/`/`docs/superpowers/`。

## 占位符替换

| 令牌 | 值 |
|---|---|
| `{{PROJECT_NAME}}` | `--name` 的值，或目标目录名 |
| `{{JAVA_VERSION}}` | `1.8`（springboot 预设默认值） |
