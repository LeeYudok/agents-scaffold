---
paths:
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/src/test/**"
  - "tests/**"
  - "**/*_test.go"
  - "**/*_test.py"
  - "**/test_*.py"
---

# Testing Rules

## P1
- **Every new feature ships with at least 1 test** (unit or integration). `[discipline]`
- **All tests green before commit/merge**. `[auto-enforced: pre-commit stack gates + CI —
  partial: gates only cover the stacks detected by the hook; run the rest manually]`

## Backend
- Prefer **mock-based unit tests** over full-context integration tests (e.g. Mockito over
  `@SpringBootTest`) — faster builds, no environment dependency.
- Write the happy path **and the failure scenarios** (bad input, missing target).
- Descriptive sentence-style test names that state the expected behavior.

## Frontend
- Mock the router/navigation layer (e.g. `vi.mock` for `next/navigation`).
- Provide required providers in a test wrapper (e.g. `QueryClientProvider` with `retry: false`).
- **User-perspective assertions**: verify visible text/roles (`getByRole`/`findByText`), and
  assert the formatted value the user actually sees, not the raw one.
- Responsive screens that render the same content for desktop and mobile need `getAllBy*` —
  `getByText` fails on the duplicate match.
