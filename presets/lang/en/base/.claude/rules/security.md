---
# Tune these globs to your tree (rules/README principle 2): too broad ≈ always loaded
# (context cost), too narrow silently skips files.
paths:
  - "src/**"
  - "app/**"
  - "server/src/main/**"
  - "web/app/**"
  - "web/components/**"
  - "web/lib/**"
  - "api/**"
  - "lib/**"
  - "**/*.yml"
  - "**/*.yaml"
  - "**/*.properties"
---

# Security · Auth Rules

## P0
- **No hardcoded secrets**: never put API keys, DB passwords, or tokens in source, config
  (`application.yml`, `.env`), logs, or commit messages. `[auto-enforced: pre-commit (.env block
  always; gitleaks scan when installed)]` Add false positives to `.gitleaks.toml` allowlist with
  rationale.
- **No unauthenticated endpoints**: every business API beyond login/static pages requires an
  auth/session check. Admin APIs use an explicit require-admin pattern.
- **No destructive DB APIs**: never expose an API that performs `DELETE/DROP/TRUNCATE`.
  If needed, require explicit user consent.

## Frontend
- **No secrets in public/bundled env vars** (`NEXT_PUBLIC_*`, `VITE_*`, ...) — they ship in the
  bundle in plain text. Calls needing a secret go through the backend.
- Never expose tokens/session values in `console.log`, error messages, or query strings.

## Backend
- **External API credentials come from a secret store or DB lookup**, never from code.
- **Login brute-force lockout**: respect configurable max-attempts / lockout-window settings
  (sane defaults, e.g. 5 attempts / 5 minutes).
- **Initial admin seeding**: create once at startup only when admin credentials are provided via
  environment variables (with a duplicate check). Never auto-generate an admin when the env vars
  are absent (local runs etc.).
