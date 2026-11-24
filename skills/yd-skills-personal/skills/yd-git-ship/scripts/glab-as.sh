#!/bin/sh
# Run glab as an agent's GitLab account without printing its token.
#
# Usage: glab-as.sh <claude|codex|agy> <glab args...>
#   glab-as.sh claude api user                      # -> "username": "claude-ai"
#   glab-as.sh claude mr create -R <gitlab-host>/<ns>/<repo> ...
# The token comes from ~/workspace/.env.toml [gitlab_<agent>_ai].token and only
# lives in this process's environment. YD_ENV_TOML overrides the file path (tests).
# GITLAB_HOST is passed through when set; otherwise glab picks the host from the
# -R argument, the current repo's git remote, or its configured default host.
#
# python3 may be older than 3.11 (no tomllib) depending on the calling shell's PATH —
# e.g. macOS /usr/bin/python3 3.9 under `bash -l`. read_token.py then falls back to a
# stdlib reader (#203). YD_TOML_FALLBACK=1 forces that path (tests).
set -eu

agent="${1:-}"
case "$agent" in
  claude|codex|agy) shift ;;
  *) echo "usage: $0 <claude|codex|agy> <glab args...>" >&2; exit 2 ;;
esac

here=$(cd "$(dirname "$0")" && pwd)
GITLAB_TOKEN=$(python3 "$here/read_token.py" "$agent" "${YD_ENV_TOML:-$HOME/workspace/.env.toml}")
export GITLAB_TOKEN
exec glab "$@"
