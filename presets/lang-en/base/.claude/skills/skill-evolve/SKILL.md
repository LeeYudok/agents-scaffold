---
name: skill-evolve
description: A meta-skill that takes feedback after a skill runs and automatically improves the corresponding SKILL.md. Use when a skill was wrong or incomplete, or to record a newly discovered gotcha.
argument-hint: "[name of skill to improve] [feedback/improvement]"
allowed-tools: Edit, Read, Write, Bash
---

# Skill Self-Improvement

> Origin: the skill of the same name in [leeyudok/doksam-skills](https://github.com/leeyudok/doksam-skills).
> **Deliberately forked** for template bundling — not auto-synced; good improvements are cherry-picked manually.

Reflects problems found during execution and user feedback into the target skill's SKILL.md.

## Trigger

`/skill-evolve <skill-name> <feedback>`

## Process

1. **Read the target**: Read the full `.claude/skills/<skill-name>/SKILL.md`.
2. **Analyze**: Analyze the feedback + recent execution context → decide what to change.
   - New gotcha → add to the `## Learned warnings` section with a date
   - Step correction → update the process section
   - Wrong command → fix it
3. **Propose**: Quote the existing content + present the change as a diff (added/removed lines).
4. **Ask for confirmation**: "Apply this change? (Y/n)"
5. **Apply**: After confirmation, edit SKILL.md directly.
6. **Commit**: After re-confirming the branch:
   ```bash
   git add .claude/skills/<skill-name>/SKILL.md
   git commit -m "evolve skill/<skill-name>: <summary> (#<issue>)"   # issue number required (P1)
   ```
7. **Verify (mini eval)**: Run the modified skill on the same kind of input that triggered the improvement, and confirm via a before/after comparison that the previously failing part is actually fixed.

## Rules

- Never delete existing Learned warnings — only accumulate
- Date tag required: `(YYYY-MM-DD)`
- Merge duplicate warnings
- Re-confirm the branch right before committing (avoid committing on main)

## Output format

```
Proposed improvement
Existing: [quote]
Proposed: [revision]

diff:
+ added line
- removed line

Apply this change? (Y/n)
```

## Learned warnings

(Notes discovered during execution accumulate here)
