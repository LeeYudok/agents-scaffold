// Rules audit workflow — template example. Rename with a `{{PROJECT_NAME}}-` prefix
// when you adapt it to a specific rule set (see workflows/README.md).
// Audits target files against a .claude/rules/*.md rule file in parallel → adversarial
// verification (false-positive removal) → issue draft; with the repair option it also
// self-fixes confirmed violations, verifies the build, and submits a PR/MR (never merges).
// Invoke: Workflow {name: "rules-audit", args: ["src/pages", ...]}            — audit only
//         Workflow {name: "rules-audit", args: {repair: true}}                — full audit + self-repair
//         Workflow {name: "rules-audit", args: {targets: [...], rule: ".claude/rules/security.md", repair: true}}
// With args/targets omitted, the first agent discovers the audit targets itself.
export const meta = {
  name: 'rules-audit',
  description: 'Audit target files against a .claude/rules/ rule file, adversarially verify findings, and (with repair) self-fix confirmed violations up to a PR/MR — merging stays a human gate',
  whenToUse: 'When a full sweep for rule violations is needed (right after introducing a new rule, pre-release audit). To delegate the fixing too, pass args {repair: true}',
  phases: [
    { title: 'Discover', detail: 'collect audit targets and the rule file' },
    { title: 'Scan', detail: 'parallel audit per target' },
    { title: 'Verify', detail: 'adversarial check of each suspected violation' },
    { title: 'Synthesize', detail: 'merge confirmed findings into an issue draft' },
    { title: 'Repair', detail: '(repair option) prepare issue + worktree, fix violations' },
    { title: 'Verify-Build', detail: '(repair option) run the project build/test gates' },
    { title: 'Submit', detail: '(repair option) commit, push, open PR/MR — no merge' },
  ],
}

const FINDINGS = {
  type: 'object',
  required: ['violations'],
  properties: {
    violations: {
      type: 'array',
      items: {
        type: 'object',
        required: ['file', 'rule', 'detail'],
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          rule: { type: 'string' },
          detail: { type: 'string' },
        },
      },
    },
  },
}

const VERDICT = {
  type: 'object',
  required: ['real', 'reason'],
  properties: { real: { type: 'boolean' }, reason: { type: 'string' } },
}

// args contract: array (targets) | {targets?, rule?, repair?} | omitted
const opts = Array.isArray(args) ? { targets: args } : (args || {})
const repair = !!opts.repair
const ruleFile = opts.rule || null

phase('Discover')
let targets = Array.isArray(opts.targets) && opts.targets.length ? opts.targets : null
const discovered = await agent(
  'In this repo, prepare a rules audit. ' +
    (ruleFile
      ? `The rule file is ${ruleFile} — read its frontmatter "paths:" globs. `
      : 'Pick the most relevant .claude/rules/*.md rule file (one with a "paths:" frontmatter) and read its globs. ') +
    (targets
      ? `The audit targets are already chosen: ${JSON.stringify(targets)} — just confirm the rule file. `
      : 'Then list the directories/files matching those globs as audit target units (one route/module per entry, exclude test files). ') +
    'Return the rule file path and the target list.',
  {
    label: 'discover:targets',
    phase: 'Discover',
    effort: 'low',
    schema: {
      type: 'object',
      required: ['rule', 'targets'],
      properties: {
        rule: { type: 'string' },
        targets: { type: 'array', items: { type: 'string' } },
      },
    },
  },
)
const rule = ruleFile || discovered.rule
targets = targets || discovered.targets
log(`Auditing ${targets.length} targets against ${rule}${repair ? ' (self-repair mode)' : ''}`)

const results = await pipeline(
  targets,
  target =>
    agent(
      `Audit ${target} against the rule file ${rule}. ` +
        'Read the rule file first and check its P0/P1 items only. ' +
        'Report violations only, and do not include anything the rule file itself lists as an exception.',
      { label: `scan:${target}`, phase: 'Scan', schema: FINDINGS, effort: 'low' },
    ),
  (found, target) =>
    parallel(
      found.violations.map(v => () =>
        agent(
          `Refute this rule-violation claim: ${v.file}${v.line ? ':' + v.line : ''} — ${v.rule}: ${v.detail}. ` +
            `Read the file directly and check the original text and exception clauses of ${rule}; ` +
            'if it falls under an exception or the claim is factually wrong, real=false. When uncertain, real=false.',
          { label: `verify:${v.file}`, phase: 'Verify', schema: VERDICT },
        ).then(verdict => ({ ...v, target, verdict })),
      ),
    ),
)

const confirmed = results
  .flat()
  .filter(Boolean)
  .filter(f => f.verdict && f.verdict.real)
log(`${confirmed.length} violations confirmed`)

if (!confirmed.length) return { confirmed: [], draft: null }

phase('Synthesize')
const draft = await agent(
  'Turn this list of confirmed rule violations into an issue draft (standard professional tone). ' +
    'Group same-file/same-rule findings, write a title, a body with a violations table, and the expected fix direction. ' +
    'Do NOT actually register the issue: ' +
    JSON.stringify(confirmed),
  { phase: 'Synthesize' },
)

if (!repair) return { confirmed, draft }

// ---------- Self-repair — fix, verify, PR/MR. NEVER merge (human gate). ----------

phase('Repair')
// 1) Register the issue + dedicated worktree — later stages share this workspace sequentially.
const setup = await agent(
  'Prepare the self-repair in this repo. ' +
    '① Create an issue from this draft using the forge CLI per .claude/rules/forge.md ' +
    '(gh issue create / glab issue create; pass large bodies via a file). Draft: ' +
    JSON.stringify(typeof draft === 'string' ? draft.slice(0, 4000) : draft) +
    ' ② With the assigned issue number N, run: git worktree add ../{{PROJECT_NAME}}-rules-repair-N -b fix/issue-N-rules-audit ' +
    '(never checkout inside the primary clone). Return the issue number, worktree absolute path, and branch name.',
  {
    label: 'repair:setup',
    phase: 'Repair',
    schema: {
      type: 'object',
      required: ['issue', 'worktree', 'branch'],
      properties: {
        issue: { type: 'number' },
        worktree: { type: 'string' },
        branch: { type: 'string' },
      },
    },
  },
)
log(`Repair issue #${setup.issue}, worktree ${setup.worktree}`)

// 2) Fix violations — a single sdlc-developer fixes sequentially (avoids parallel-edit races in one worktree).
const fixed = await agent(
  `Inside the worktree ${setup.worktree} (never modify anything outside it), fix these rule violations. ` +
    `The reference is ${rule} — minimal diffs, no refactoring unrelated to the violations. ` +
    'Return the list of modified files and the outcome per violation (fixed/skip + reason). Violations: ' +
    JSON.stringify(confirmed),
  {
    label: 'repair:fix',
    phase: 'Repair',
    agentType: 'sdlc-developer',
    schema: {
      type: 'object',
      required: ['files', 'outcomes'],
      properties: {
        files: { type: 'array', items: { type: 'string' } },
        outcomes: { type: 'array', items: { type: 'string' } },
      },
    },
  },
)
log(`${fixed.files.length} files modified`)

phase('Verify-Build')
const build = await agent(
  `In the worktree ${setup.worktree}, run the project's typecheck/test gates ` +
    '(the stack gates in .claude/hooks/pre-commit.sh are the reference; install dependencies first if missing) ' +
    'and report pass/fail with an error summary on failure. Do not modify any code.',
  {
    label: 'repair:verify',
    phase: 'Verify-Build',
    agentType: 'sdlc-verifier',
    schema: {
      type: 'object',
      required: ['passed', 'summary'],
      properties: { passed: { type: 'boolean' }, summary: { type: 'string' } },
    },
  },
)

if (!build.passed) {
  log('Build/tests failed — skipping PR/MR, keeping the worktree')
  return {
    confirmed,
    issue: setup.issue,
    repaired: false,
    worktree: setup.worktree,
    buildFailure: build.summary,
  }
}

phase('Submit')
const mr = await agent(
  `In the worktree ${setup.worktree}, do the following: ` +
    `① git add ONLY these files, listed explicitly (no git add -A / no directories): ${JSON.stringify(fixed.files)} ` +
    `② commit with message "style(#${setup.issue}): self-repair rule violations (rules-audit)" ` +
    '+ a body summarizing the outcomes, ending with "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" ' +
    `③ git push -u origin ${setup.branch} ` +
    `④ open a PR/MR with the forge CLI per .claude/rules/forge.md, title "style(#${setup.issue}): self-repair rule violations", ` +
    `body "Closes #${setup.issue}" plus a note that this is an automated fix requiring human review before merge ` +
    '⑤ **NEVER merge.** Return the PR/MR URL.',
  {
    label: 'repair:mr',
    phase: 'Submit',
    schema: {
      type: 'object',
      required: ['mrUrl'],
      properties: { mrUrl: { type: 'string' } },
    },
  },
)
log(`PR/MR submitted (awaiting merge): ${mr.mrUrl}`)

return {
  confirmed,
  issue: setup.issue,
  repaired: true,
  files: fixed.files,
  outcomes: fixed.outcomes,
  mrUrl: mr.mrUrl,
  note: 'No merge performed — a human merges after PR/MR review (CI + code review + eyes on the diff)',
}
