---
paths:
  - "Dockerfile"
  - "Containerfile"
  - "*.dockerfile"
  - "docker-compose*.yml"
  - "docker-compose*.yaml"
  - "**/*.container"
  - "**/*.service"
  - "**/*.network"
  - "quadlet/**"
  - "playbooks/**/*.yml"
  - "playbooks/**/*.yaml"
  - "ansible/**/*.yml"
---

# Docker/Podman/Ops Rules

## Container standard
- **Runtime**: rootless **podman** + **Quadlet** (`systemctl --user`, linger=yes).
- No running `docker run` directly → manage with `.container` Quadlet units.
- Host → container: nginx reverse proxy (`127.0.0.1:<port>`) + certbot TLS.

## Networking (pasta)
- Container → host service: use `host.docker.internal` (pasta networking, not `127.0.0.1`).
- New container volumes: SELinux `:z` (shared) or `:Z` (private) label required.
- No `--network=host` (limited under rootless podman).

## Containerfile linting
- `hadolint Containerfile` — must pass in CI.
- When ignoring a `DL` rule, state the reason in a comment: `# hadolint ignore=DL3008`.
- Multi-stage builds recommended — do not include build-time dependencies in the runtime image.
- Base images: pin the tag (no `latest`). Digest pinning recommended for security-sensitive environments.

## Security scanning
- `trivy image --severity CRITICAL --exit-code 1` — zero CRITICAL findings required.
- HIGH vulnerabilities: warn only, not blocking. CRITICAL blocks deployment.
- Either `grype` or `trivy` is required in CI.

## YAML / Ansible
- `yamllint` — per `.yamllint.yml`.
- `ansible-lint` — required when playbooks change.
- `ansible-playbook --syntax-check` — before committing.
- Dry run: `--check --diff` — always confirm before an actual deployment.

## Quadlet units
- When a unit file changes, run `systemd-analyze verify <file>` first.
- Restart policy: `Restart=on-failure` by default. State a reason for `always`.
- Environment variables: use the `EnvironmentFile=%h/deploy/<svc>/.env` pattern. No hardcoding inside the unit file.

## P0
- No hardcoding secrets/tokens in Containerfiles, playbooks, or unit files
- `hadolint` must have no CRITICAL errors before committing
- No `.env` staged into git

## P1
- No deploying images with any CRITICAL `trivy` findings
- New subdomains: add the nginx conf + confirm certbot certificate issuance before deploying
- When changing a Quadlet unit, follow `systemctl --user daemon-reload` then `systemctl --user restart <unit>` in order

## P2 (recommended)
- Analyze image layers with `dive` to check for unnecessary included files
- Maintain `.dockerignore` / `.containerignore` — minimize the build context
