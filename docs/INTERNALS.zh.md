# agents-scaffold — 内部结构

生成的 `.claude/` 目录树与设计模式。概览请见 [README](../README.zh.md)。

## 内含什么

```
.claude/
  agents/
    security-audit.md   12 项 P0/P1 安全 grep 扫描
    db-migration.md      DDL 安全检查 + 回滚 SQL 生成
    sdlc-developer.md    最小范围实现 agent（SDLC 角色分离）
    sdlc-tester.md        AC/TC 测试编写 agent
    sdlc-verifier.md      流水线执行 + 报告 agent
    agent-evolve.md       自我改进元 agent —— 根据运行反馈打磨 agents/*.md
  commands/              （在 Claude Code 上属遗留 — 斜杠命令已并入 skills）
    sonar.md             SonarQube 分析（CE 任务轮询、sqp_/squ_ 令牌处理）
    sdlc-cycle.md         5 阶段 SDLC 自动化
    knowledge-graph.md    重新生成 .claude 知识图谱 + 断链检查
  hooks/
    pre-commit.sh         pre-commit 门禁骨架（技术栈片段的接入点）
    post-edit-format.sh   PostToolUse(Edit|Write) → 自动格式化
    post-test-notify.sh   PostToolUse(Bash, *test*) → 终端通知
    stop-memory-remind.sh Stop 钩子 → 每会话一次的记忆提醒
    cc-check.py            PostToolUse(Bash, git commit) → CC > 15 时告警
  memory/
    MEMORY.md              auto-memory 索引（SSOT）
    README.md               记忆类型/使用规则
  rules/
    common.md               P0/P1/P2 优先级分级 + 通用工作流（始终加载）
    security.md              密钥/认证 P0 + 锁定/管理员初始化规则（按路径作用域）
    testing.md               每功能一测试、mock 优先的单元测试、用户视角断言
    data.md                  数据脚本规则 —— 禁止批量暂存、显式指定编码
    README.md                按路径作用域加载 + 规则编写原则
  skills/
    skill-evolve/            自我改进元 skill（"Learned warnings" 模式）
    status/                   多技术栈状态检查
    review/                   code-reviewer + security-audit 封装
    memory-factcheck/         记忆事实核查 —— 对照代码/DB/issue 验证并修正过期内容
    security-precheck/        审计前安全排查 → 拆分 issue → 并行修复
    docs-sync/                文档现行化 — 逐条主张核对 + 多语言配对文件同步
    handoff/                  会话交接 — 通过 HANDOFF.md / Issue 传递可恢复的状态
  workflows/             （不会自动加载 — 需显式调用）
    rules-audit.js           存储式 Workflow 示例 —— 扫描/验证/修复，合并由人工把关
  scripts/               （不会自动加载 — 需显式调用）
    knowledge_graph.py       .claude 生态图谱 + --check 断链门禁
  settings.json               钩子接线 + 默认 deny 规则
AGENTS.md                 项目大脑 —— 规则 SSOT（P0/P1/P2 + 工作流）
.gemini/settings.json     通过 context.fileName 让 Gemini CLI 读取 AGENTS.md
presets/                  预设片段（复制覆盖模型）
  forge-github/           GitHub forge —— gh、PR、`Closes #N` 自动关闭
  forge-gitlab/           GitLab forge —— glab、MR、`Closes #N` 自动关闭（合并后需确认）
  nextjs/ bun/ ...        各技术栈片段（规则 + pre-commit.partial.sh）
  lang-en/                英文覆盖层（base/forge-*/stacks/*）—— 见下文 `--lang`
bin/                      agents-scaffold.sh 引导脚本
tests/                    引导脚本的 bats 回归测试套件
```

## 关键模式

- **P0/P1/P2 优先级分级**：定义于 `common.md` + `AGENTS.md`。P0 = 安全/密钥/数据破坏，无一例外。
- **SDLC 角色分离**：developer/tester/verifier 三个 agent + `/sdlc-cycle` 自动化命令。
- **skill-evolve / agent-evolve**：从错误中提炼 "Learned warnings" 并追加的自我改进模式。`skill-evolve` 作用于 `.claude/skills/*.md`，`agent-evolve` 作用于 `.claude/agents/*.md`。
- **Memory SSOT**：`.claude/memory/`（不使用系统默认路径）。类型前缀：`project_`/`feedback_`/`reference_`/`user_`。
- **按路径作用域加载的规则**：frontmatter `paths:` 使规则仅在处理匹配文件时自动加载。
- **多 agent 隔离**：并行 subagent 可能同时触碰同一文件时，使用 `isolation: "worktree"`。
