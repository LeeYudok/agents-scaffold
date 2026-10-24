#!/usr/bin/env python3
"""Wait for the pipeline of a commit on GitLab and report its result.

Usage: ci_wait.py [--agent claude|codex|agy] <ns/repo> <sha> [--timeout 3600] [--interval 30]
Run it in the background (run_in_background=true). Exit 0 = success or no
pipeline, 1 = failed/canceled, 2 = timed out, 3 = tool error (glab failed or
returned non-JSON, e.g. missing token); a tool error is never reported as 1.
With --agent, glab runs through glab-as.sh so the agent token from
~/workspace/.env.toml is used (needed where glab has no stored login);
without it, glab's own login is used. The token never leaves glab.
The host is GITLAB_HOST when set; otherwise glab resolves it from the
current repo's git remote or its configured default host.
"""
import os
import argparse
import json
import subprocess
import sys
import time
import urllib.parse

DONE_OK = {"success", "skipped"}
DONE_BAD = {"failed", "canceled"}


GLAB_AS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glab-as.sh")


def api(path, agent=None):
    host = os.environ.get("GITLAB_HOST")
    cmd = ["glab", "api"] + (["--hostname", host] if host else []) + [path]
    if agent:
        cmd = ["sh", GLAB_AS, agent] + cmd[1:]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("sha")
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument("--agent", choices=["claude", "codex", "agy"])
    a = ap.parse_args()
    proj = urllib.parse.quote(a.repo, safe="")
    deadline = time.time() + a.timeout
    seen_none = 0
    while time.time() < deadline:
        try:
            pipes = api(f"projects/{proj}/pipelines?sha={a.sha}&per_page=1", a.agent)
        except (subprocess.CalledProcessError, ValueError, OSError) as e:
            detail = getattr(e, "stderr", None) or e
            print(f"tool error: glab api failed: {str(detail).strip()}", file=sys.stderr)
            return 3
        if not pipes:
            seen_none += 1
            if seen_none >= 4:
                print(f"no pipeline for {a.sha[:8]} (repo has no CI for this ref)")
                return 0
        else:
            p = pipes[0]
            if p["status"] in DONE_OK | DONE_BAD:
                print(f'pipeline {p["id"]} {p["status"]} {p["web_url"]}')
                return 0 if p["status"] in DONE_OK else 1
        time.sleep(a.interval)
    print(f"timeout waiting for {a.sha[:8]}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
