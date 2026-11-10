# Security Policy

agents-scaffold installs a git pre-commit gate and agent permission rules into other repositories, so a flaw
here can weaken every project that uses it. Reports are welcome.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's private reporting instead:
[Report a vulnerability](https://github.com/LeeYudok/agents-scaffold/security/advisories/new).

Include the version (`bin/agents-scaffold.sh --version`), the command you ran, and what happened. You should
get a first reply within 7 days. Fixes are released as a new tag and noted in [CHANGELOG.md](CHANGELOG.md).

## What counts

- The pre-commit gate letting through something it claims to block (a staged `.env`, a failing stack check).
- The installer writing outside the target directory, or deleting or overwriting user files without a backup.
- A generated hook, rule or setting that runs code the user did not ask for.
- A deny rule in the generated `.claude/settings.json` that can be bypassed in an obvious way.

## Installing safely

`curl … | bash` from `main` runs whatever is on `main` at that moment. To pin what you run:

```bash
# pin to a release tag, and verify the template tarball
export AGENTS_SCAFFOLD_REF=v1.0.0
export AGENTS_SCAFFOLD_SHA256=<sha256 of the tag's source tarball, from the release page>
curl -fsSL https://raw.githubusercontent.com/leeyudok/agents-scaffold/v1.0.0/bin/agents-scaffold.sh | bash -s -- --yes
```

Or download the release bundle, check it against `SHA256SUMS`, and run `bin/agents-scaffold.sh` from the
extracted tree — no further download happens (see [docs/OFFLINE_INSTALL.en.md](docs/OFFLINE_INSTALL.en.md)).
`--dry-run` shows what an install would write before it writes anything.

## Scope of the guarantees

The gate is a real `.git/hooks/pre-commit`, so it holds for any tool and for humans — but anyone can skip a
local hook with `git commit --no-verify`. Treat it as a guard against mistakes, and keep CI as the backstop.
