---
name: grill-me
description: Use when the user invokes /grill-me or asks to have an idea, feature request, or spec grilled, stress-tested, interrogated, or challenged before implementation. Opt-in alternative to superpowers:brainstorming — the user picks one or the other per task.
user-invocable: true
---

# Grill Me — adversarial requirements interrogation

> An original skill inspired by — and designed as an opt-in alternative to — the
> `brainstorming` skill from [obra/superpowers](https://github.com/obra/superpowers) (MIT);
> the downstream workflow (plan → TDD → review) follows the superpowers process.

Interrogate the user's idea until the spec stops changing, then hand a hardened spec
to the normal implementation flow. Explicitly invoking this skill substitutes for
`superpowers:brainstorming` for the current task; everything downstream
(plan → TDD → review) is unchanged.

**This is a multi-round interview, not a questionnaire.** The failure mode to avoid:
firing one batch of clarifying questions, accepting the answers at face value, and
jumping to design. Each round digs into the previous round's answers.

## Procedure

1. **Announce the mode.** One line: you will grill the idea before any code, and the
   output will be a hardened spec. No implementation, no design proposals until step 5.

2. **Round loop.** Ask **at most 3 questions per round**, all on one theme, then wait
   for answers. Pick the sharpest unresolved theme each round, in rough order:
   - Purpose — who needs this, what breaks if it doesn't exist, why now?
   - Hidden assumptions — what is being taken for granted (auth model, data shape, scale)?
   - Edge cases & failure modes — revocation, concurrency, partial failure, abuse.
   - Security/privacy — PII exposure, new attack surface, unauthenticated paths (P0).
   - YAGNI — which parts can be cut from v1 with no real loss?
   - Operations — rollback, migration, monitoring, who gets paged?

3. **Challenge the answers.** A vague answer ("나중에 생각하죠", "아마 괜찮을 듯")
   is not accepted silently — either push back once with a concrete consequence
   ("if we skip expiry, a fired employee keeps dashboard access — acceptable?") or
   record it verbatim in the spec under **Accepted risks**. Every deferral lands in
   **Non-goals** or **Accepted risks**; nothing evaporates.

4. **Exit condition.** Stop when a full round produces no spec changes, or the user
   says stop. Do not stop merely because one round of answers arrived.

5. **Deliver the hardened spec** in this exact shape:

   ```markdown
   ## Hardened spec — <feature>
   ### Decisions        <!-- each as "question → decision" -->
   ### Non-goals (v1)   <!-- YAGNI cuts, deferred scope -->
   ### Accepted risks   <!-- user chose to accept, verbatim -->
   ### Acceptance criteria
   ```

   Then hand off: proceed with the project workflow (issue → branch → plan/TDD).

## When NOT to use

- Trivial fixes, typos, mechanical changes — just do them.
- The user wants collaborative idea *generation* → `superpowers:brainstorming` (separate plugin).
- A large, vaguely specified job that must be turned into a spec and then run and evaluated in a
  loop → Ouroboros (separate MCP server). State survives a dropped session, but it is the heaviest
  of the three.
- Mid-implementation questions — this skill is for before work starts.

This skill **only interrogates**, and it stays inside the conversation — no files, no server state.
Escalate to the heavier options only when that is not enough. See "Picking a requirements-hardening
tool" in the README for the comparison.
