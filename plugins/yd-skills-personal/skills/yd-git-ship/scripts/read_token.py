#!/usr/bin/env python3
"""Print [gitlab_<agent>_ai].token from a TOML file — for glab-as.sh only (#203).

Usage: read_token.py <claude|codex|agy> <path-to-env.toml>
Uses tomllib (Python 3.11+). Older Pythons (macOS /usr/bin/python3 3.9, which
`bash -l` picks up) fall back to a stdlib reader for this one key.
YD_TOML_FALLBACK=1 forces the fallback (tests). Kept out of glab-as.sh because
macOS /bin/sh (bash 3.2) misparses quotes in a heredoc inside $(...).
"""
import os
import re
import sys


def read_fallback(text, section):
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            # 헤더 뒤 주석([x] # ...)도 헤더다. 알아볼 수 없는 헤더([[x]] 등)는 섹션을 비워
            # 앞 섹션이 이어지는 것으로 착각해 다른 계정 토큰을 집지 않게 한다.
            header = re.match(r"^\[\s*([^\[\]]+?)\s*\]\s*(?:#.*)?$", line)
            current = header.group(1).strip().strip("\"'") if header else None
            continue
        if current == section:
            value = re.match(r"""^token\s*=\s*(?:"([^"]*)"|'([^']*)')""", line)
            if value:
                return value.group(1) if value.group(1) is not None else value.group(2)
    return None


def main(argv):
    if len(argv) != 2 or argv[0] not in ("claude", "codex", "agy"):
        sys.exit("usage: read_token.py <claude|codex|agy> <env.toml>")
    agent, path = argv
    section = "gitlab_%s_ai" % agent
    try:
        if os.environ.get("YD_TOML_FALLBACK"):
            raise ImportError("fallback forced")
        import tomllib
        with open(path, "rb") as f:
            token = tomllib.load(f).get(section, {}).get("token")
    except ImportError:
        try:
            with open(path, encoding="utf-8") as f:
                token = read_fallback(f.read(), section)
        except FileNotFoundError:
            sys.exit("glab-as: %s not found" % path)
    except FileNotFoundError:
        sys.exit("glab-as: %s not found" % path)
    if not token:
        sys.exit("glab-as: [%s].token not found in %s" % (section, path))
    print(token)


if __name__ == "__main__":
    main(sys.argv[1:])
