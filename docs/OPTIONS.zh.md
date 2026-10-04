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
| `codex` | Codex | 安装 `AGENTS.md`、skills 与共享 rules/hooks/memory，并移除 Claude 专用层 |
| `agy` | Antigravity | 在 `codex` 布局之外，把 `.claude/rules` 生成为 agy 的 `.agents/rules`（`trigger: glob`）（#63） |
| `all` | 混合团队 | `claude` 的全部内容 + 生成的 agy 规则。skills 布局与 harness 无关（#61） |

**skills 只有一个源（#61）。** 无论使用哪个 harness，skills 只存放在 `.agents/skills/`（Codex、agy 的原生路径）一处，Claude Code 通过符号链接 `.claude/skills -> ../.agents/skills` 读取同一份文件（claude 2.1.289 实测 — 只有 `.agents/skills` 而没有链接时，Claude Code 找不到任何 skill）。两份副本不会再分叉，日后加入其他 harness 也无需重新安装。

- 无法创建符号链接的环境（如 Windows Git Bash 默认设置），或设置了 `AGENTS_SCAFFOLD_NO_SYMLINK=1` 时，`.claude/skills` 为副本。已暂存的副本与源不一致时，pre-commit 门禁会拦截提交（基于索引比较，`__pycache__` 等未跟踪文件不计入）。能否创建链接可能因环境而异（如网络隔离 PC 的策略）— 见 [OFFLINE_INSTALL.en.md](OFFLINE_INSTALL.en.md) 第 6 步。
- Git for Windows 在 `core.symlinks=false` 下检出时，链接会变成内含路径字符串的普通文件。此时 Claude Code 找不到 skills，门禁会给出警告 — 执行 `git config core.symlinks true` 后重新检出。
- 安装前已存在的真实目录 `.claude/skills` 会被移入 `.agents/skills` 并改为链接。若同一路径的内容与 `.agents/skills` 不同，则以 `.agents/skills` 为源，旧目录保留为 `.claude/skills.pre-ssot-<时间戳>/`。
- rules 与子代理不做链接：`.codex/rules` 是命令执行策略，agy 的 `.agents/rules` 不理解 Claude 的 `paths:` 条件加载，Claude 的 `.md` 与 Codex 的 `.toml` 子代理格式也不同。

三个 harness 都原生读取根目录的 `AGENTS.md`，因此不生成 `CLAUDE.md`/`GEMINI.md` 指针文件，也不生成 `.gemini/settings.json` 垫片（#54、#60）。支持目标为最新版 Claude Code、Codex 与 Antigravity；Gemini CLI 不再是支持目标。

**保障分为两级（#21）** — 不是"支持/不支持"的二分法。

| 级别 | 成立的内容 | 适用 harness |
|---|---|---|
| **baseline** | `AGENTS.md` 正文中的 P0/P1（含所选技术栈的 P0）+ **真正的 `.git/hooks/pre-commit` 门禁** + CI | **全部 harness，与 `--harness` 取值无关。** 无论 harness 读取什么，也无论是否由人在终端直接提交，门禁都会生效 |
| **full** | baseline + 该 harness 的原生层（子代理、skills、斜杠命令、按路径的条件加载、lifecycle 钩子） | 仅限适配器经过实测验证的 harness |

git 钩子**与 harness 无关，始终接入**（#21）。Claude Code 的 `PreToolUse` 钩子只在该会话通过 Bash 工具提交时触发，因此它属于早期反馈层而非强制线 — 决定性的强制线放在 harness 之外（`.git/hooks` + CI）。已存在的 `.git/hooks/pre-commit` 不会被覆盖，只会给出警告。

所选技术栈的 P0 会**直接插入 `AGENTS.md` 正文**，不依赖 `.claude/rules/` 引用链接，因此在不加载 `.claude/` 的 harness 上同样可达。未选择的技术栈不会被插入（Codex 指令合计默认上限为 32KiB — 以避免 context flooding）。

### 实测验证（2026-10-04）

| Harness | 实测版本 | baseline | full 层已确认 / 未确认的内容 |
|---|---|---|---|
| Claude Code | 2.1.289 | 成立 | `.claude/rules/*.md` 的 `paths:` 条件加载、子代理、skills、`settings.json` 钩子 — 均已对照[官方文档](https://code.claude.com/docs/en/memory.md)确认 |
| Codex | codex-cli 0.160.0 / GPT-6.1 Sol | 成立 | 已实测 `AGENTS.md`、内联技术栈 P0、`.agents/skills`、`.env` 门禁、`.codex/agents` 子代理（仅受信任项目）、`.codex/hooks.json` 钩子（需项目信任与钩子定义信任）以及按 cwd 加载的子目录 `AGENTS.md`。没有按文件路径的条件指令 |
| Antigravity | agy 1.2.16 | 成立 | 以 headless（`-p`）实测 `AGENTS.md`、内联技术栈 P0、`.agents/skills`、`.env` 门禁、`.agents/agents` 子代理、`.agents/hooks.json` 钩子（无信任确认即执行）以及 `.agents/rules` 中 `trigger: glob` 条件规则。子目录 `AGENTS.md` 仅按 cwd 加载 |

Codex（codex-cli 0.160.0，`gpt-6.1-sol`）与 agy（1.2.16）会在不调用任何工具的情况下自动加载各自模式产物中的 AGENTS.md 与内联技术栈 P0，并且只发现 `.agents/skills` 下的仓库 skills；两者都不会发现 `.claude/skills`。agy 1.2.7 的 headless 模式既不加载 `AGENTS.md` 也不加载 `GEMINI.md`，该问题已在 1.2.16 中解决。即使模型遗漏规则，git 钩子仍会以 exit 2 拦截已暂存的 `.env`。

支持状态的单一真实来源是 [`docs/harness-matrix.json`](harness-matrix.json)。本表会与该 manifest 对照，并由 CI 中的 `scripts/check-harness-matrix.py` 检查 — 若某个 `full` 等级超过 90 天未重新实测，或某项判定缺少证据，**构建将失败**。重新实测请运行 `scripts/spike-codex-contract.sh --dynamic` 与 `scripts/spike-agy-contract.sh --dynamic`。

**agy 规则适配器（#63）。** 使用 `--harness agy|all` 时，会把 `.claude/rules/*.md` 生成为 `.agents/rules/*.md`。有 `paths:` 时变为 `trigger: glob` + `globs:`，没有时变为 `trigger: always_on`。模式按 agy 1.2.16 的实测转换：含斜杠的相对模式（`src/**`）改为 `**/src/**`，不含斜杠的模式（`Dockerfile`、`*.py`）按文件名匹配，保持不变。多个模式用逗号连接且不加空格（逗号后的空格会成为下一个模式的一部分，导致无法匹配）。`.claude/rules` 仍是源；`--update` 会重新生成，并删除源已不存在的生成文件。没有生成标记的同名文件（用户自有）不会被改动。

已实测 Codex 与 agy 本身支持子代理、钩子和按路径的指令（含上表条件），但脚手架尚未生成子代理与钩子层（适配器只有 agy 规则），因此整体等级为 baseline。与 Claude Code 相同，钩子是早期反馈而非强制线。agy 会在没有信任确认的情况下执行仓库中的 `.agents/hooks.json`，在外部仓库运行 agy 前请先检查该文件（`security-audit` 代理会扫描它）。

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

将最新的基础文件（`.claude/`、`AGENTS.md`）应用到已完成引导的项目。
旧版本生成的 `.gemini/settings.json` 不会被改动（保留也无害）。
仅当 `.agents/skills` 不存在或内容相同时，才会把真实目录 `.claude/skills` 移入源 `.agents/skills` 并改为链接（#61）。两者都存在且内容不同时不做迁移，并提示手动合并。迁移后，基础 skills 会在 `.agents/skills` 一侧更新。

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
