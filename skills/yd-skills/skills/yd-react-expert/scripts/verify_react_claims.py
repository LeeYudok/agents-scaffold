#!/usr/bin/env python3
"""SKILL.md 의 React 단언을 react@19 로 재현한다 (이슈 #201).

    python3 .claude/skills/yd-react-expert/scripts/verify_react_claims.py

임시 디렉터리에 고정 버전의 react·react-dom·jsdom·eslint 를 `npm install` 한 뒤, 단언마다
`react_claims.mjs <시나리오>` 를 개발 빌드(NODE_ENV=development)로 실행해 관찰값을 얻는다.
네트워크가 필요하므로 단위 테스트는 YD_REACT_VERIFY=1 일 때만 돈다(tests/test_react_claims.py).
하나라도 문서와 다르면 exit 1 이다. node·npm 이 없으면 사유를 찍고 건너뛴다(exit 0).

판정은 EXPECT 한 곳에 있다. 시나리오는 관찰값만 돌려준다.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PINNED = {
    "react": "19.3.0",
    "react-dom": "19.3.0",
    "jsdom": "30.1.2",
    "eslint": "10.12.0",
    "eslint-plugin-react-hooks": "7.1.1",
}
NODE, NPM = shutil.which("node"), shutil.which("npm")
_workdir: Path | None = None


def unavailable() -> str | None:
    if not NODE or not NPM:
        return "node 또는 npm 이 PATH 에 없다"
    return None


def workdir() -> Path:
    """고정 버전을 한 번만 설치한 임시 디렉터리. YD_REACT_WORKDIR 로 재사용할 수 있다."""
    global _workdir
    if _workdir:
        return _workdir
    preset = os.environ.get("YD_REACT_WORKDIR")
    d = Path(preset) if preset else Path(tempfile.mkdtemp(prefix="yd-react-claims-"))
    if not preset:
        atexit.register(shutil.rmtree, d, ignore_errors=True)
    if not (d / "node_modules" / "react").exists():
        d.mkdir(parents=True, exist_ok=True)
        (d / "package.json").write_text(json.dumps({"name": "claims", "private": True, "type": "module",
                                                    "dependencies": PINNED}))
        r = subprocess.run([NPM, "install", "--no-audit", "--no-fund", "--loglevel=error"], cwd=d,
                           capture_output=True, text=True, timeout=600)
        if r.returncode:
            raise RuntimeError(f"npm install 실패: {r.stderr[-500:]}")
    shutil.copy(HERE / "react_claims.mjs", d / "react_claims.mjs")
    _workdir = d
    return d


def scenario(name: str, node_env: str = "development") -> dict:
    d = workdir()
    env = dict(os.environ, NODE_ENV=node_env)
    r = subprocess.run([NODE, "react_claims.mjs", name], cwd=d, capture_output=True, text=True,
                       env=env, timeout=120)
    if r.returncode:
        raise RuntimeError(f"시나리오 {name} 실패: {r.stderr[-800:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


EXPECT = {
    "DERIVED-IN-RENDER": ("derived",
                          lambda o: o["ssr"] == {"effect": "<p>0</p>", "calc": "<p>2</p>"}
                          and o["renders"] == {"effect": 2, "calc": 1}
                          and o["effectText"] == o["calcText"] == "2"),
    "STRICT-EFFECT-TWICE": ("strictmode",
                            lambda o: o["env"] == "development"
                            and o["strict"] == ["mount", "cleanup", "mount"] and o["plain"] == ["mount"]),
    "STRICT-DEV-ONLY": ("strictmode:production", lambda o: o["env"] == "production" and o["strict"] == ["mount"]),
    "ASYNC-RACE": ("race", lambda o: o["naive"] == "A-msgs" and o["guarded"] == "B2-msgs"),
    "INDEX-KEY": ("indexkey",
                  lambda o: o["index"] == {"id": "b", "value": "typed-into-a"}
                  and o["id"] == {"id": "b", "value": ""}),
    "KEY-RESET": ("keyreset",
                  lambda o: o["afterClick"] == "1" and o["sameKey"] == "1" and o["newKey"] == "0"),
    "INLINE-COMPONENT": ("inlinecomponent",
                         lambda o: o["inline"]["sameNode"] is False and o["inline"]["attached"] is False
                         and o["hoisted"]["sameNode"] is True),
    "REF-AS-PROP": ("refprop", lambda o: o["refIsInput"] is True),
    "REF-CLEANUP": ("refprop", lambda o: o["log"] == ["attach:DIV", "cleanup"]),
    "USE-CONDITIONAL": ("use",
                        lambda o: "provided" in o["ctxOn"] and "off" in o["ctxOff"] and "resolved" in o["promise"]),
    "USE-ACTION-STATE-SPA": ("actionstate",
                             lambda o: o["before"] == "init" and o["after"] == "saved:x"),
    "TEXT-ESCAPED": ("escape",
                     lambda o: "&lt;img" in o["text"] and "<img" not in o["text"]),
    "INNERHTML-RAW": ("escape", lambda o: "<img src=x onerror=alert(1)>" in o["raw"]),
    "JS-URL": ("jsurl", lambda o: "javascript:alert(1)" not in o["html"]),
    "LINT-MISSING-DEP": ("eslint",
                         lambda o: any(m["rule"] == "react-hooks/exhaustive-deps" and "missing dependency" in m["msg"]
                                       for m in o["missingDep"]) and o["clean"] == []),
    "LINT-HOOK-CONDITIONAL": ("eslint",
                              lambda o: any(m["rule"] == "react-hooks/rules-of-hooks" and m["severity"] == 2
                                            for m in o["conditionalHook"])),
    "WATERFALL": ("waterfall", lambda o: o["sequential"] >= 230 and o["parallel"] < 200),
    "DEFERRED-VALUE": ("deferred",
                       lambda o: o["log"] == ["b/a", "b/b"] and o["text"] == "b"),
    "MEMO-FRESH-OBJECT": ("memo", lambda o: o["freshObject"] == 1 and o["stableObject"] == 0),
}


def run(claim: str) -> tuple[dict, bool]:
    name, ok = EXPECT[claim]
    name, _, node_env = name.partition(":")
    obs = scenario(name, node_env or "development")
    return obs, bool(ok(obs))


def main() -> int:
    why = unavailable()
    if why:
        print(f"SKIP {why}")
        return 0
    failed = 0
    for claim in EXPECT:
        obs, ok = run(claim)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {claim}: {json.dumps(obs, ensure_ascii=False)[:300]}")
    print(f"{len(EXPECT) - failed}/{len(EXPECT)} 단언 재현 (react {PINNED['react']})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
