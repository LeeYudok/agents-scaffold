---
name: docs-sync
description: Bring documentation back in line with the code after changes to behavior, paths, versions, or generated output. Use on "update the docs", "refresh the README", "docs are stale", and right before opening a PR that changed any of those. Checks each documented claim against the actual code, command output, or official docs, and updates the parallel-language files together.
user-invocable: true
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Documentation sync (docs-sync)

Stale docs pass every automated gate. The link checker only sees broken links; the test suite
never reads prose. So this is enforced as a procedure.

## Principles

- **Verify claim by claim.** Do not skim for readability. Extract the **checkable claims** a
  sentence makes — paths, versions, numbers, behavior, defaults — and check each against reality.
- **Never edit without evidence.** A `file:line`, a command's output, or an official-docs URL.
  What you could not confirm gets marked **"unverified"** rather than deleted — deleting it
  destroys the information.
- **No optimistic wording.** If something only partly works, do not write that it "works". State
  what holds and what does not.

## Procedure

### 1. Extract the change surface

```bash
git log --oneline <last-doc-commit>..HEAD
git diff --stat <last-doc-commit>..HEAD
```

Keep only what documentation can be wrong about: CLI flags and defaults, paths, generated
artifacts, versions, thresholds, gate behavior, support scope.

### 2. Collect the checkable claims

Targets: `README*`, `AGENTS.md`, `CLAUDE.md`, per-directory `README.md`, skill/agent docs.

```bash
grep -rn '`[^`]*/`\|version\|default\|v[0-9]\+\.[0-9]' README*.md docs/ 2>/dev/null
```

What goes stale fastest: **directory-tree blocks** (new artifacts missing), **version strings**,
**"it automatically ..." behavior claims**, **support matrices**.

### 3. Check each claim

| Claim type | How to verify |
|---|---|
| Path / file exists | `ls` / `find` — against the generated output, not the source tree |
| CLI flag or default | Run `<cmd> --help`. The output is the evidence, never another doc |
| Tool version | `<cmd> --version`, and **record the measurement date** |
| Behavior ("auto-loads") | The tool's **official-docs URL**. If none exists, say "no documented basis" |
| Numbers / thresholds | grep the code, or measure the real artifact (`wc -c`, ...) |
| Gate behavior | Actually run it and check the exit code |

### 4. Update parallel-language and overlay files together (required)

Updating one side leaves the others stale, and **no gate catches it.**

```bash
ls README*.md                       # every language README
ls presets/lang-en/ 2>/dev/null     # is there a language overlay?
```

- Touching one README means touching every language edition in the **same commit** — in this
  repository that is `README.md` (English), `README.ko.md`, `README.zh.md`, `README.ja.md`.
- Touching a `.claude/**` base file means touching its `presets/lang-en/` counterpart too.
- These are not translations but **per-language editions of the same facts** — numbers, versions,
  paths, and table structure stay identical.
- Blanket replacement breaks across languages. `grep -n` the target text in each file first.

### 5. Run the gates

```bash
python3 .claude/scripts/knowledge_graph.py --check   # expect 0 broken links
```

Run the test suite even for docs-only changes — a command or path quoted in the docs that no
longer matches the tests will surface here.

### 6. Report

List each correction as **`before → after + evidence`**. Do not collapse it into "updated the
README". Report what you left marked "unverified" as well.

## Done when

- Every checkable claim has evidence or an explicit "unverified" marker
- Parallel-language and overlay counterparts are in the same commit
- Link checker reports 0 broken, test suite passes

## Learned warnings

- Deleting a stale statement breaks the trail of why it disappeared — prefer marking it
  "unverified" with the measurement date.
- Directory-tree blocks go stale most often. A commit that adds an artifact but not the tree entry
  slips past the link checker, because tree entries are code-block text rather than links.
