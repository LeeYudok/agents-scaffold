# agents-scaffold — Air-gapped & Windows install

How to install without internet access. For the overview see the [README](../README.md).
The remote install (`curl | bash`) downloads the template from GitHub, so it cannot work in a
closed network — instead, build a **bundle** on a connected machine and carry it in. Running the
script from inside the extracted bundle performs no download.

## Prerequisite — Git Bash on Windows

The bootstrap script and `.claude/hooks/*.sh` are all bash. On Windows you need
**Git for Windows (Git Bash)**. WSL's `bash.exe` is not used — its path model differs.
Claude Code on Windows also runs hooks and shell commands through Git Bash.

| Requirement | Used for | Installer to carry in |
|---|---|---|
| Git for Windows | bash, git, sed, awk, tar, sha256sum | [git-scm.com/downloads/win](https://git-scm.com/downloads/win) — 64-bit Standalone Installer |
| Python 3 | `observe-lite.sh` / `stop-memory-remind.sh` hooks, `.claude/scripts/knowledge_graph.py` | [python.org/downloads/windows](https://www.python.org/downloads/windows/) — Windows installer (64-bit) |
| agents-scaffold bundle | the template itself | built in step 1 below |

Stack tools (`bun`, `go`, `cargo`, `ruff`, ...) are used by the pre-commit gate **only when
present** — missing tools skip their checks. Bring them in separately from your internal mirror.

## 1. Build the bundle (connected machine)

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
cd agents-scaffold
scripts/make-offline-bundle.sh            # for a specific tag: --ref v1.2.0
```

`dist/` gets three files: `agents-scaffold-offline-<version>.zip`, the matching `.tar.gz`, and
`SHA256SUMS`. The bundle holds **committed content only** (`git archive`). Even when built on
Windows, `.gitattributes` keeps `*.sh` LF inside the archive.

## 2. Verify integrity after transfer

```bash
# Git Bash
cd <transfer folder> && sha256sum -c SHA256SUMS
```

```bat
rem cmd — compare the printed hash with the value in SHA256SUMS
certutil -hashfile agents-scaffold-offline-<version>.zip SHA256
```

## 3. Extract

Explorer "Extract All", or `tar -xf agents-scaffold-offline-<version>.zip` (the built-in `tar`
on Windows 10+ also handles zip). You get a single `agents-scaffold/` folder.

## 4. Install

**Git Bash**:

```bash
bash agents-scaffold/bin/agents-scaffold.sh /c/work/myproj --stack springboot --yes
```

**cmd / PowerShell** — the launcher finds Git Bash and runs the script for you:

```bat
agents-scaffold\bin\agents-scaffold.cmd C:/work/myproj --stack springboot --yes
```

- The launcher looks for `Git\bin\bash.exe` in this order: `AGENTS_SCAFFOLD_BASH` →
  `CLAUDE_CODE_GIT_BASH_PATH` → `%ProgramFiles%\Git` → `%LOCALAPPDATA%\Programs\Git` →
  `where git`. For a non-standard location: `set AGENTS_SCAFFOLD_BASH=D:\tools\Git\bin\bash.exe`.
- Write the target path with forward slashes (`C:/work/myproj`) to be safe.
- Options are the same as the online install → [OPTIONS.en.md](OPTIONS.en.md).
- Do not copy `bin/agents-scaffold.sh` out on its own — without `.claude/` and `presets/` next to
  it, it falls back to the remote install, tries to download and fails. Always run it inside the
  extracted tree.

The install appends a hook LF rule (`.claude/hooks/*.sh text eol=lf`) to the target repo's
`.gitattributes`, so teammates checking out with `core.autocrlf=true` do not get CRLF hooks.

## 5. `python3` on Windows

The hooks call `python3`. The python.org installer creates `python` and `py`, not `python3`.
The `...\WindowsApps\python3.exe` on PATH is a stub that redirects to the Microsoft Store and
fails in a closed network.

1. Settings → Apps → Advanced app settings → **App execution aliases**: turn off `python.exe` and `python3.exe`
2. In the Python install folder (e.g. `C:\Program Files\Python312\`), copy `python.exe` to `python3.exe`
3. Check from Git Bash: `python3 -c "import sys; print(sys.version)"`

The `.cmd` launcher runs this check for you; on failure it warns and continues the install.

## 6. Updating

Carry in and extract a new bundle the same way, then run with `--update`.

```bash
bash agents-scaffold/bin/agents-scaffold.sh --update /c/work/myproj
```

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `$'\r': command not found` | Hooks checked out with CRLF → check the `.gitattributes` rule, then `git add --renormalize .claude/hooks && rm .claude/hooks/*.sh && git checkout -- .claude/hooks` |
| `Error: template download failed` | Script run outside the bundle tree → see the note in step 4 |
| `Git Bash not found` | Git for Windows missing or in a non-standard path → set `AGENTS_SCAFFOLD_BASH` |
| Hooks silently do nothing | `python3` is the Store stub → step 5 |
| Claude Code cannot find Git Bash | Non-standard path → set `CLAUDE_CODE_GIT_BASH_PATH` to the full `bash.exe` path |

Installing Claude Code itself in a closed network is out of scope for this document.
