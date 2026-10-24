---
name: sonar
description: Run SonarQube static analysis and check the results. Use to check code quality, security hotspots, or coverage.
argument-hint: "[rescan|hotspots|coverage|qg] [path-filter]"
---

Run SonarQube static analysis and summarize the results.

## Argument parsing

The first word of `$ARGUMENTS` is the subcommand. If absent, summarize the current cached metrics.

| Subcommand | Behavior |
|---|---|
| (none) | Summarize the currently cached metrics |
| `rescan` | Run the scanner + poll the CE task + summarize results |
| `hotspots` | Query TO_REVIEW security hotspots |
| `coverage` | Analyze coverage |
| `qg` | Quality Gate condition breakdown |
| `<path>` | Filter to CRITICAL issues under that path only |

## API access

- Read `sonar.projectKey` and `sonar.host.url` from `sonar-project.properties`
- **Token: environment variable first** — `SONAR_TOKEN` (or the project's `.env`). Never store the token in `sonar-project.properties`: that file is committed, so the token leaks into git history. If you find a `sonar.token` line there, recommend rotating it and moving the value to env.
- **Verify the host is alive before use**: `curl -s -o /dev/null -w "%{http_code}" $host/api/system/status` → if not 200, the properties URL may be stale (e.g. a dead `localhost:9000`); ask for / discover the real server and override with `-Dsonar.host.url`.
- Auth: `curl -u "$SONAR_TOKEN:" ...` or `curl -H "Authorization: Bearer $SONAR_TOKEN" ...`

**Two token types**:
- `sqp_` Project Analysis Token → for running `sonar-scanner`, general queries
- `squ_` User Token → for management APIs like changing hotspot status (switch to this if you get a 403)

## Subcommand details

### Default — current metrics summary

```bash
token="${SONAR_TOKEN:?set SONAR_TOKEN (do not read it from sonar-project.properties)}"
key=$(grep 'sonar.projectKey' sonar-project.properties | cut -d= -f2-)
curl -s -u "$token:" \
  "http://localhost:9000/api/measures/component?component=$key&metricKeys=bugs,vulnerabilities,code_smells,coverage,security_hotspots,duplicated_lines_density,ncloc"
```

Output as a table: bugs / vulnerabilities / security_hotspots / code_smells / coverage / ncloc

### `rescan` — rescan + delta

1. Liveness check the server (see API access) — abort early instead of a 30s scanner hang
2. Save current numbers to `/tmp/sonar-before.json`
3. Run the scanner with explicit overrides so stale properties can't hijack the run:
   ```bash
   sonar-scanner -Dsonar.host.url="$host" -Dsonar.token="$SONAR_TOKEN"
   ```
4. Poll the CE task (up to 90s, every 2s):
   ```bash
   for i in $(seq 1 45); do
     status=$(curl -s -u "$token:" "http://localhost:9000/api/ce/task?id=$ceTaskId" | python3 -c "import sys,json; print(json.load(sys.stdin)['task']['status'])")
     [ "$status" = "SUCCESS" ] && break
     [ "$status" = "FAILED" ] && { echo "task FAILED" >&2; break; }
     sleep 2
   done
   ```
5. **Check analysis warnings** — the CE task response carries `warnings` (also shown as a dashboard banner). Encoding problems, unset `sonar.python.version`, etc. appear ONLY here, never in the issue list. On an encoding warning, locate corrupted files:
   ```bash
   grep -rlI $'\xef\xbf\xbd' <source-dirs>   # files containing U+FFFD replacement chars
   ```
6. Show before/after delta

**Gotcha**: scanner exit ≠ metrics updated. Confirming CE task status=SUCCESS is required.

### `hotspots` — security hotspots

```bash
curl -s -u "$squ_token:" \
  "http://localhost:9000/api/hotspots/search?projectKey=$key&status=TO_REVIEW&ps=500" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); [print(h['ruleKey'], h['component'], h.get('line','')) for h in d['hotspots']]"
```

### `coverage` — coverage

Generate the test + coverage report, then print files sorted by lowest coverage.

### `qg` — Quality Gate

```bash
curl -s -u "$squ_token:" \
  "http://localhost:9000/api/qualitygates/project_status?projectKey=$key" \
  | python3 -c "import sys,json; [print(c['metricKey'], c['status'], c.get('actualValue','')) for c in json.load(sys.stdin)['projectStatus']['conditions']]"
```

**If `conditions` is an empty array, the gate is unconfigured** — "Success" is then meaningless (everything passes unconditionally). Say so explicitly instead of reporting a green gate.

## Gotcha FAQ

- **403 Insufficient privileges**: calling a management API with an `sqp_` token → switch to `squ_`
- **Rescan shows stale numbers**: missing CE task poll. Confirm status=SUCCESS then re-query
- **No bulk hotspot marking**: mark one at a time with a rationale → SAFE
- **Token found committed in `sonar-project.properties`**: recommend rotating it immediately and moving the value to env; don't keep using the leaked value
- **"analyzed as compatible with all Python 3 versions" warning**: stray `.py` files in `sonar.sources` — set `sonar.python.version` or add them to `sonar.exclusions`
