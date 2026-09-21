# skills/ — situational intelligence (skills)

Procedural knowledge triggered in specific situations. Each skill = 1 directory + `SKILL.md`
(frontmatter `name`/`description` (+`user-invocable`) + procedural body). When the description
trigger matches, Claude loads it and follows it as-is. `user-invocable: true` also allows manual
invocation.

```
skills/
└── <name>/
    ├── SKILL.md      # keep the body short — trigger + core procedure only
    ├── scripts/      # (optional) scripts the skill executes
    └── resources/    # (optional) heavy reference material — linked from the body, loaded only when needed
```

The principle is progressive disclosure: SKILL.md is always loaded, so keep it short and
move long source texts, tables, and examples into `resources/` files read only when needed.

Included: `example-skill/`, `review/`, `status/`, `search-first/`, `skill-evolve/`,
`memory-factcheck/` (memory fact-check vs code/DB/issues), `security-precheck/` (pre-audit security sweep),
`docs-sync/` (doc currency — claim-by-claim verification and parallel-language sync),
`handoff/` (session handoff — pass resumable state through `HANDOFF.md` / an issue and pick it up),
`grill-me/` (adversarial requirements interrogation — the lightest option, staying inside the
conversation. Picked per task against the heavier superpowers `brainstorming` and Ouroboros; see
"Picking a requirements-hardening tool" in the README for the comparison).
New skills should use the `{{PROJECT_NAME}}-sk-*` prefix.
