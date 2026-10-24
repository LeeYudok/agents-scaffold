# workflows/ — stored orchestration workflows

Deterministic multi-agent orchestration scripts for Claude Code's **Workflow tool**.
One workflow = one `.js` file. Unlike a skill (a procedure the model follows), a workflow
is plain JavaScript whose control flow (loops, fan-out, gates) runs deterministically while
subagents do the actual work.

> Requires a harness that provides the Workflow tool. On setups without it these files are
> inert — they are never auto-loaded, so shipping them costs nothing.

## File shape

Every script starts with a pure-literal `meta` block, then the body:

```js
export const meta = {
  name: 'my-audit',
  description: 'one-liner shown in the permission dialog',
  whenToUse: 'when to pick this workflow',
  phases: [{ title: 'Scan', detail: '...' }, { title: 'Verify', detail: '...' }],
}
// body — async context, plain JS (no TypeScript syntax)
```

Primitives injected into the body:

- `agent(prompt, opts)` — spawn a subagent. With `opts.schema` (JSON Schema) the return
  value is a validated object instead of text. Other opts: `label`, `phase`, `model`,
  `effort`, `agentType` (e.g. `sdlc-developer`), `isolation: 'worktree'`.
- `parallel([thunks])` — run concurrently, barrier until all complete. Failed thunks
  resolve to `null` — `.filter(Boolean)` before use.
- `pipeline(items, stage1, stage2, ...)` — each item flows through all stages
  independently, no barrier between stages. Default choice for multi-stage work.
- `phase(title)` / `log(msg)` — progress grouping and narration.
- `args` — the value passed to the Workflow tool call, verbatim.

## Patterns worth copying (see `rules-audit.js` — a combination of the orchestrator-workers + evaluator-optimizer patterns from anthropics/claude-cookbooks)

- **Structured returns**: define JSON Schemas (`FINDINGS`, `VERDICT`) once, pass as
  `opts.schema` — no output parsing.
- **Adversarial verification**: every finding from a Scan agent goes to a separate
  verifier agent prompted to *refute* it (`real=false` when uncertain). This removes
  false positives before anything expensive happens.
  (In cookbooks vocabulary: evaluator-optimizer — separating the generator from the evaluator.)
- **Flexible args contract**: accept `array | {options} | omitted`, and let the first
  agent discover the work list when the caller doesn't provide one.
- **Human merge gate**: a workflow may fix, build-verify, push, and open a PR/MR —
  it must **never merge**. Say so explicitly in the submit prompt.
- **Worktree isolation**: repair-style workflows create a dedicated
  `git worktree` + issue branch and forbid edits outside it.

## Invocation

```
Workflow {name: "rules-audit", args: ["src/pages"]}          # audit only
Workflow {name: "rules-audit", args: {repair: true}}          # audit + self-repair
Workflow {scriptPath: ".claude/workflows/rules-audit.js"}     # by path
```

## Conventions

- New workflows use the `{{PROJECT_NAME}}-` prefix (project namespace); `rules-audit.js`
  is the shipped generic example — rename a copy when specializing it.
- Scripts must be self-contained plain JS; `Date.now()`/`Math.random()` are unavailable
  (they would break resume) — pass timestamps via `args`.
- Workflows can spawn dozens of agents; they run only on explicit user opt-in.
