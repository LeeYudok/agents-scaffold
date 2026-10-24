
**bun**

- Never hardcode secrets (keys/tokens/passwords) in code
- `bunx tsc --noEmit` must pass before commit
- Never stage `.env` (the pre-commit hook blocks it)
