#!/usr/bin/env python3
"""SKILL.md 의 TypeScript·Bun 단언을 실제 도구로 재현한다.

    python3 .claude/skills/yd-typescript/scripts/verify_typescript_claims.py

임시 디렉터리에 고정 버전의 typescript 를 `npm install` 한 뒤, 단언마다 작은 .ts 파일을 만들어
`bun run`·`bun build`·`tsc` 로 돌려 관찰값을 얻는다. bun 은 PATH 의 것을 쓰고 버전을 출력한다.
네트워크가 필요하므로 단위 테스트는 YD_TS_VERIFY=1 일 때만 돈다(tests/test_typescript_claims.py).
하나라도 문서와 다르면 exit 1 이다. bun·node·npm 중 하나라도 없으면 사유를 찍고 건너뛴다(exit 0).

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

PINNED = {"typescript": "7.0.2"}
BUN, NODE, NPM = shutil.which("bun"), shutil.which("node"), shutil.which("npm")
_workdir: Path | None = None

BAD = 'const n: number = "x";\nconsole.log(typeof n);\n'
CAST = 'const r = JSON.parse(`{"a":"x"}`) as { a: number };\nconsole.log(typeof r.a);\n'
NONNULL = 'const m = new Map<string, string>();\nconsole.log(m.get("k")!.length);\n'
EXACT = 'type T = { a?: number };\nconst t: T = { a: undefined };\nconsole.log("a" in t);\n'
INDEX = "const xs: number[] = [];\nconsole.log(xs[0].toFixed());\n"
BUNAPI = "console.log(typeof Bun.file);\n"
EMPTY = """const res = new Response("", { status: 200 });
let parsed = "parsed";
try { await res.json(); } catch (e) { parsed = (e as Error).name; }
console.log(JSON.stringify({ ok: res.ok, parsed }));
"""
RACE = """const delays = [30, 5];
const request = (i: number) => new Promise<string>((r) => setTimeout(() => r(`r${i}`), delays[i]));
let naive = "";
await Promise.all([0, 1].map((i) => request(i).then((v) => { naive = v; })));
let gen = 0;
let guarded = "";
await Promise.all([0, 1].map((i) => { const mine = ++gen; return request(i).then((v) => { if (mine === gen) guarded = v; }); }));
console.log(JSON.stringify({ naive, guarded }));
"""
ABORT = """const server = Bun.serve({ port: 0, fetch: async () => { await Bun.sleep(300); return new Response("late"); } });
const ac = new AbortController();
const pending = fetch(`http://127.0.0.1:${server.port}/`, { signal: ac.signal });
setTimeout(() => ac.abort(), 20);
let name = "resolved";
try { await pending; } catch (e) { name = (e as Error).name; }
server.stop(true);
console.log(JSON.stringify({ name }));
"""
STRICT_ONLY = "function f(x) { return x; }\nconsole.log(f(1));\n"


def unavailable() -> str | None:
    missing = [n for n, p in (("bun", BUN), ("node", NODE), ("npm", NPM)) if not p]
    return f"{', '.join(missing)} 이 PATH 에 없다" if missing else None


def sh(cmd: list, cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def workdir() -> Path:
    """고정 버전을 한 번만 설치한 임시 디렉터리. YD_TS_WORKDIR 로 재사용할 수 있다."""
    global _workdir
    if _workdir:
        return _workdir
    preset = os.environ.get("YD_TS_WORKDIR")
    d = Path(preset) if preset else Path(tempfile.mkdtemp(prefix="yd-ts-claims-"))
    if not preset:
        atexit.register(shutil.rmtree, d, ignore_errors=True)
    if not (d / "node_modules" / ".bin" / "tsc").exists():
        d.mkdir(parents=True, exist_ok=True)
        (d / "package.json").write_text(json.dumps({"name": "claims", "private": True, "type": "module",
                                                    "dependencies": PINNED}))
        r = sh([NPM, "install", "--no-audit", "--no-fund", "--loglevel=error"], d, timeout=600)
        if r.returncode:
            raise RuntimeError(f"npm install 실패: {r.stderr[-500:]}")
    _workdir = d
    return d


def put(d: Path, name: str, text: str) -> Path:
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def tsc(d: Path, *args, cwd: Path | None = None) -> dict:
    r = sh([d / "node_modules" / ".bin" / "tsc", "--noEmit", *args], cwd or d)
    return {"exit": r.returncode, "out": (r.stdout + r.stderr).strip()}


def last_json(r: subprocess.CompletedProcess) -> dict:
    if r.returncode:
        raise RuntimeError(f"시나리오 실패: {(r.stderr or r.stdout)[-600:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def no_typecheck(d: Path) -> dict:
    f = put(d, "bad.ts", BAD)
    run = sh([BUN, "run", f], d)
    build = sh([BUN, "build", f, "--target", "browser"], d)
    return {"runExit": run.returncode, "runOut": run.stdout.strip(),
            "buildExit": build.returncode, "buildBytes": len(build.stdout)}


def tsc_catches(d: Path) -> dict:
    put(d, "bad.ts", BAD)
    return tsc(d, "--strict", "bad.ts")


def project_config(d: Path) -> dict:
    sub = d / "proj"
    put(sub, "strict.ts", STRICT_ONLY)
    put(sub, "tsconfig.json", json.dumps({"compilerOptions": {"strict": True, "noEmit": True},
                                          "include": ["strict.ts"]}))
    return {"files": tsc(d, "strict.ts", cwd=sub), "project": tsc(d, "-p", ".", cwd=sub)}


def build_target(d: Path) -> dict:
    f = put(d, "bad.ts", BAD)
    out = {k: sh([BUN, "build", f, *a], d).stdout for k, a in
           (("default", []), ("browser", ["--target", "browser"]), ("bun", ["--target", "bun"]))}
    return {"defaultIsBrowser": out["default"] == out["browser"],
            "bunHasPragma": out["bun"].startswith("// @bun"), "browserHasPragma": out["browser"].startswith("// @bun")}


def bun_api(d: Path) -> dict:
    f = put(d, "bunapi.ts", BUNAPI)
    build = sh([BUN, "build", f, "--target", "browser", "--outfile", d / "bundle.js"], d)
    ran = sh([NODE, d / "bundle.js"], d)
    return {"buildExit": build.returncode, "nodeExit": ran.returncode,
            "nodeErr": "ReferenceError: Bun is not defined" in ran.stderr}


def cast(d: Path) -> dict:
    f = put(d, "cast.ts", CAST)
    return {"tsc": tsc(d, "--strict", f.name), "runtime": sh([BUN, "run", f], d).stdout.strip()}


def nonnull(d: Path) -> dict:
    f = put(d, "nn.ts", NONNULL)
    r = sh([BUN, "run", f], d)
    return {"tsc": tsc(d, "--strict", f.name), "runExit": r.returncode, "typeError": "TypeError" in r.stderr}


def exact_optional(d: Path) -> dict:
    f = put(d, "eo.ts", EXACT)
    return {"without": tsc(d, "--strict", f.name),
            "with": tsc(d, "--strict", "--exactOptionalPropertyTypes", f.name),
            "keyPresent": sh([BUN, "run", f], d).stdout.strip()}


def unchecked_index(d: Path) -> dict:
    f = put(d, "ix.ts", INDEX)
    return {"without": tsc(d, "--strict", f.name), "with": tsc(d, "--strict", "--noUncheckedIndexedAccess", f.name)}


def race(d: Path) -> dict:
    return last_json(sh([BUN, "run", put(d, "race.ts", RACE)], d))


def abort(d: Path) -> dict:
    return last_json(sh([BUN, "run", put(d, "abort.ts", ABORT)], d))


def empty_body(d: Path) -> dict:
    return last_json(sh([BUN, "run", put(d, "empty.ts", EMPTY)], d))


EXPECT = {
    "BUN-NO-TYPECHECK": (no_typecheck,
                         lambda o: o["runExit"] == 0 and o["runOut"] == "string"
                         and o["buildExit"] == 0 and o["buildBytes"] > 0),
    "TSC-CATCHES": (tsc_catches, lambda o: o["exit"] != 0 and "TS2322" in o["out"]),
    "TSC-PROJECT-CONFIG": (project_config,
                           lambda o: o["files"]["exit"] != 0 and "TS5112" in o["files"]["out"]
                           and o["project"]["exit"] != 0 and "TS7006" in o["project"]["out"]),
    "BUN-BUILD-TARGET": (build_target,
                         lambda o: o["defaultIsBrowser"] and o["bunHasPragma"] and not o["browserHasPragma"]),
    "BUN-API-IN-BROWSER": (bun_api, lambda o: o["buildExit"] == 0 and o["nodeExit"] != 0 and o["nodeErr"]),
    "CAST-NOT-VALIDATION": (cast, lambda o: o["tsc"]["exit"] == 0 and o["runtime"] == "string"),
    "NONNULL-NOT-VALIDATION": (nonnull, lambda o: o["tsc"]["exit"] == 0 and o["runExit"] != 0 and o["typeError"]),
    "EXACT-OPTIONAL": (exact_optional,
                       lambda o: o["without"]["exit"] == 0 and o["with"]["exit"] != 0
                       and "TS2375" in o["with"]["out"] and o["keyPresent"] == "true"),
    "UNCHECKED-INDEX": (unchecked_index,
                        lambda o: o["without"]["exit"] == 0 and o["with"]["exit"] != 0
                        and ("TS2532" in o["with"]["out"] or "TS18048" in o["with"]["out"])),
    "ASYNC-RACE": (race, lambda o: o["naive"] == "r0"),
    "ASYNC-GUARD": (race, lambda o: o["guarded"] == "r1"),
    "ABORT-CONTROLLER": (abort, lambda o: o["name"] == "AbortError"),
    "EMPTY-BODY-200": (empty_body, lambda o: o["ok"] is True and o["parsed"] == "SyntaxError"),
}


def run(claim: str) -> tuple[dict, bool]:
    scenario, ok = EXPECT[claim]
    obs = scenario(workdir())
    return obs, bool(ok(obs))


def versions() -> str:
    bun = sh([BUN, "--version"], Path.cwd()).stdout.strip()
    return f"typescript {PINNED['typescript']} · bun {bun}"


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
    print(f"{len(EXPECT) - failed}/{len(EXPECT)} 단언 재현 ({versions()})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
