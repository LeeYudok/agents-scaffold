#!/usr/bin/env python3
"""SKILL.md 의 Go 단언을 설치된 Go 툴체인으로 재현한다 (이슈 #201).

    python3 .claude/skills/yd-go-expert/scripts/verify_go_claims.py

단언마다 임시 모듈을 만들어 `go run`·`go build`·`go vet` 으로 실제 동작을 관찰한다.
언어 의미(루프 변수 등)는 go.mod 의 `go` 줄이 정하므로 그 줄도 단언의 일부로 둔다.
하나라도 문서와 다르면 exit 1 이다. Go 가 없으면 건너뛴다(exit 0, 사유 출력).

각 check_* 함수는 관찰값 dict 만 돌려주고 판정은 EXPECT 한 곳에 있다. 테스트
(tests/test_go_claims.py)도 같은 함수를 불러 같은 관찰값을 검사한다.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GO = shutil.which("go")


def go_version() -> tuple[int, int]:
    out = subprocess.run([GO, "env", "GOVERSION"], capture_output=True, text=True).stdout
    m = re.match(r"go(\d+)\.(\d+)", out.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _env() -> dict:
    env = dict(os.environ)
    env.update({"GOTOOLCHAIN": "local", "GOWORK": "off", "GOFLAGS": "", "GO111MODULE": "on"})
    return env


def mod(d: Path, files: dict[str, str], go: str = "1.22") -> Path:
    """임시 모듈을 만든다. files 의 키는 d 기준 상대 경로."""
    (d / "go.mod").write_text(f"module m\n\ngo {go}\n")
    for name, body in files.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return d


def go(d: Path, *args: str) -> dict:
    r = subprocess.run([GO, *args], cwd=d, capture_output=True, text=True, env=_env(), timeout=240)
    return {"rc": r.returncode, "out": r.stdout.strip(), "err": r.stderr.strip()}


def run_main(d: Path, src: str, gomod: str = "1.22", extra: dict[str, str] | None = None) -> dict:
    mod(d, {"main.go": src, **(extra or {})}, gomod)
    return go(d, "run", ".")


def check_typed_nil(d: Path) -> dict:
    r = run_main(d, '''package main

import "fmt"

type MyErr struct{}

func (*MyErr) Error() string { return "x" }

func typed() error  { var e *MyErr; return e }
func literal() error { return nil }

func main() { fmt.Println(typed() != nil, literal() != nil) }
''')
    return {"typed_nil_is_non_nil": r["out"].split()[0] if r["out"] else r["err"],
            "literal_nil_is_non_nil": r["out"].split()[1] if r["out"] else r["err"]}


def check_wrap_chain(d: Path) -> dict:
    r = run_main(d, '''package main

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
)

var ErrNotFound = errors.New("not found")

func main() {
	_, base := os.Open("/nonexistent/x")
	w := fmt.Errorf("열기 실패: %w", ErrNotFound)
	v := fmt.Errorf("열기 실패: %v", ErrNotFound)
	var pe *fs.PathError
	wp := fmt.Errorf("열기 실패: %w", base)
	vp := fmt.Errorf("열기 실패: %v", base)
	fmt.Println(errors.Is(w, ErrNotFound), errors.Is(v, ErrNotFound),
		errors.As(wp, &pe), errors.As(vp, &pe))
}
''')
    f = r["out"].split()
    return {"raw": r["out"] or r["err"], "is_w": f[0] if f else "", "is_v": f[1] if f else "",
            "as_w": f[2] if f else "", "as_v": f[3] if f else ""}


LOOP_SRC = '''package main

import "fmt"

func main() {
	var fs []func() int
	for i := 0; i < 3; i++ {
		fs = append(fs, func() int { return i })
	}
	for _, f := range fs {
		fmt.Print(f(), " ")
	}
}
'''


def check_loopvar(d: Path) -> dict:
    (d / "new").mkdir()
    (d / "old").mkdir()
    new = run_main(d / "new", LOOP_SRC, "1.22")
    old = run_main(d / "old", LOOP_SRC, "1.21")
    return {"go_1_22": new["out"], "go_1_21": old["out"]}


def check_servemux(d: Path) -> dict:
    r = run_main(d, '''package main

import (
	"fmt"
	"net/http"
	"net/http/httptest"
)

func hit(mux *http.ServeMux, method, path string) string {
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(method, path, nil))
	return fmt.Sprintf("%d:%s", rec.Code, rec.Body.String())
}

func main() {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/rooms/{ref}", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, r.PathValue("ref"))
	})
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "fallback") })
	mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) { fmt.Fprint(w, "api") })
	fmt.Println(hit(mux, "GET", "/api/rooms/abc"))
	fmt.Println(hit(mux, "GET", "/api/other"))
	fmt.Println(hit(mux, "GET", "/zzz"))
	fmt.Println(hit(mux, "GET", "/api/rooms/a%20b"))
	fmt.Println(hit(mux, "GET", "/api/rooms/a%2Fb"))
	only := http.NewServeMux()
	only.HandleFunc("GET /api/rooms/{ref}", func(w http.ResponseWriter, r *http.Request) {})
	fmt.Println(hit(only, "POST", "/api/rooms/abc"))
}
''')
    lines = r["out"].splitlines()
    return {"raw": r["out"] or r["err"], "lines": lines}


def check_embed(d: Path) -> dict:
    src = '''package main

import (
	"embed"
	"fmt"
	"io/fs"
)

//go:embed %s
var f embed.FS

func main() {
	var names []string
	fs.WalkDir(f, ".", func(p string, e fs.DirEntry, err error) error {
		if !e.IsDir() { names = append(names, p) }
		return nil
	})
	fmt.Println(names)
}
'''
    out = {}
    for tag, pat in (("plain", "dist"), ("all", "all:dist")):
        sub = d / tag
        sub.mkdir()
        mod(sub, {"main.go": src % pat, "dist/index.html": "x", "dist/.hidden": "x", "dist/_skip.txt": "x"})
        out[tag] = go(sub, "run", ".")["out"]
    return out


def check_embed_missing(d: Path) -> dict:
    mod(d, {"main.go": '''package main

import "embed"

//go:embed dist
var f embed.FS

func main() { _ = f }
'''})
    r = go(d, "build", "./...")
    return {"rc": r["rc"], "err": r["err"]}


def check_embed_parent(d: Path) -> dict:
    (d / "x").mkdir()
    mod(d / "x", {})
    (d / "up").mkdir()
    (d / "up" / "a.txt").write_text("x")
    pkg = d / "x" / "pkg"
    pkg.mkdir()
    (pkg / "main.go").write_text('''package main

import "embed"

//go:embed ../../up/a.txt
var f embed.FS

func main() { _ = f }
''')
    r = go(d / "x", "build", "./...")
    return {"rc": r["rc"], "err": r["err"]}


def check_defer_in_loop(d: Path) -> dict:
    r = run_main(d, '''package main

import "fmt"

func main() {
	for i := 0; i < 3; i++ {
		defer fmt.Println("defer", i)
		fmt.Println("body", i)
	}
	fmt.Println("loop end")
}
''')
    return {"order": r["out"].splitlines()}


def check_append_alias(d: Path) -> dict:
    r = run_main(d, '''package main

import (
	"fmt"
	"slices"
)

func main() {
	a := make([]int, 3, 10)
	b := append(a, 1)
	b[0] = 99
	c := append(slices.Clone(a), 1)
	c[1] = 77
	fmt.Println(a[0], a[1])
}
''')
    return {"a": r["out"] or r["err"]}


def check_json_nil_slice(d: Path) -> dict:
    r = run_main(d, '''package main

import (
	"encoding/json"
	"fmt"
)

func main() {
	var n []int
	e := []int{}
	a, _ := json.Marshal(n)
	b, _ := json.Marshal(e)
	fmt.Println(string(a), string(b))
}
''')
    return {"out": r["out"] or r["err"]}


def check_os_root(d: Path) -> dict:
    mod(d, {"main.go": '''package main

import (
	"fmt"
	"os"
)

func main() {
	root, err := os.OpenRoot("jail")
	if err != nil { panic(err) }
	defer root.Close()
	for _, p := range []string{"in.txt", "../secret.txt", "link/secret.txt"} {
		f, err := root.Open(p)
		if f != nil { f.Close() }
		fmt.Println(p, err == nil)
	}
}
''', "jail/in.txt": "ok"}, "1.24")
    (d / "secret.txt").write_text("s")
    os.symlink(d, d / "jail" / "link")
    r = go(d, "run", ".")
    return {"lines": r["out"].splitlines(), "err": r["err"]}


def check_evalsymlinks(d: Path) -> dict:
    """어휘 검사만으로는 심볼릭 링크 우회를 못 막고, EvalSymlinks 후에는 막힌다."""
    (d / "jail").mkdir()
    (d / "secret").mkdir()
    os.symlink(d / "secret", d / "jail" / "link")
    (d / "prog").mkdir()
    run_main(d / "prog", '''package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func main() {
	jail, _ := filepath.EvalSymlinks(os.Args[1])
	p := filepath.Join(os.Args[1], "link", "x")
	lexical := strings.HasPrefix(filepath.Clean(p), os.Args[1])
	real, _ := filepath.EvalSymlinks(filepath.Dir(p))
	resolved := strings.HasPrefix(real, jail+string(filepath.Separator))
	fmt.Println(lexical, resolved)
}
''')
    # run_main 은 인자를 못 넘기므로 빌드 후 직접 실행한다
    b = subprocess.run([GO, "build", "-o", str(d / "prog" / "p"), "."], cwd=d / "prog",
                       capture_output=True, text=True, env=_env())
    o = subprocess.run([str(d / "prog" / "p"), str(d / "jail")], capture_output=True, text=True)
    return {"build_rc": b.returncode, "out": o.stdout.strip()}


def check_stdversion_vet(d: Path) -> dict:
    src = '''package main

import "errors"

func main() { _, _ = errors.AsType[*MyErr](errors.New("x")) }

type MyErr struct{}

func (*MyErr) Error() string { return "x" }
'''
    old = d / "old"
    old.mkdir()
    mod(old, {"main.go": src}, "1.24")
    new = d / "new"
    new.mkdir()
    mod(new, {"main.go": src}, "1.26")
    return {"vet_1_24": go(old, "vet", "./..."), "vet_1_26": go(new, "vet", "./...")}


def check_waitgroup_go(d: Path) -> dict:
    src = '''package main

import "sync"

func main() {
	var wg sync.WaitGroup
	wg.Go(func() {})
	wg.Wait()
}
'''
    old = d / "old"
    old.mkdir()
    mod(old, {"main.go": src}, "1.24")
    new = d / "new"
    new.mkdir()
    mod(new, {"main.go": src}, "1.25")
    return {"vet_1_24": go(old, "vet", "./..."), "run_1_25": go(new, "run", ".")}


EXPECT = {
    "TYPED-NIL": (check_typed_nil,
                  lambda o: o["typed_nil_is_non_nil"] == "true" and o["literal_nil_is_non_nil"] == "false"),
    "ERRORS-WRAP-W": (check_wrap_chain, lambda o: o["is_w"] == "true" and o["as_w"] == "true"),
    "ERRORS-WRAP-V": (check_wrap_chain, lambda o: o["is_v"] == "false" and o["as_v"] == "false"),
    "LOOPVAR-122": (check_loopvar, lambda o: o["go_1_22"].split() == ["0", "1", "2"]),
    "LOOPVAR-OLD": (check_loopvar, lambda o: o["go_1_21"].split() == ["3", "3", "3"]),
    "MUX-METHOD-WILDCARD": (check_servemux,
                            lambda o: o["lines"][0] == "200:abc" and o["lines"][5].startswith("405:")),
    "MUX-SPECIFIC-WINS": (check_servemux,
                          lambda o: o["lines"][1] == "200:api" and o["lines"][2] == "200:fallback"),
    "MUX-PATHVALUE-DECODED": (check_servemux,
                              lambda o: o["lines"][3] == "200:a b" and o["lines"][4] == "200:a/b"),
    "EMBED-NO-MATCH": (check_embed_missing,
                       lambda o: o["rc"] != 0 and "no matching files found" in o["err"]),
    "EMBED-PARENT": (check_embed_parent, lambda o: o["rc"] != 0 and "../" in o["err"]),
    "EMBED-HIDDEN": (check_embed,
                     lambda o: ".hidden" not in o["plain"] and "_skip.txt" not in o["plain"]
                     and ".hidden" in o["all"] and "_skip.txt" in o["all"]),
    "DEFER-IN-LOOP": (check_defer_in_loop,
                      lambda o: o["order"][:4] == ["body 0", "body 1", "body 2", "loop end"]
                      and o["order"][4:] == ["defer 2", "defer 1", "defer 0"]),
    "APPEND-ALIAS": (check_append_alias, lambda o: o["a"] == "99 0"),
    "JSON-NIL-SLICE": (check_json_nil_slice, lambda o: o["out"] == "null []"),
    "OS-ROOT": (check_os_root,
                lambda o: o["lines"] == ["in.txt true", "../secret.txt false", "link/secret.txt false"]),
    "SYMLINK-BYPASS": (check_evalsymlinks, lambda o: o["out"] == "true false"),
    "VET-STDVERSION-ASTYPE": (check_stdversion_vet,
                              lambda o: o["vet_1_24"]["rc"] != 0 and "go1.26" in o["vet_1_24"]["err"]
                              and o["vet_1_26"]["rc"] == 0),
    "WG-GO": (check_waitgroup_go,
              lambda o: o["run_1_25"]["rc"] == 0 and o["vet_1_24"]["rc"] != 0),
}

# 이 Go 버전 이상이어야 의미 있는 단언
MIN_GO = {"OS-ROOT": (1, 24), "VET-STDVERSION-ASTYPE": (1, 26), "WG-GO": (1, 25), "LOOPVAR-122": (1, 22),
          "LOOPVAR-OLD": (1, 22), "MUX-METHOD-WILDCARD": (1, 22), "MUX-SPECIFIC-WINS": (1, 22),
          "MUX-PATHVALUE-DECODED": (1, 22)}


def skip_reason(claim: str) -> str | None:
    if not GO:
        return "go 가 PATH 에 없다"
    need = MIN_GO.get(claim)
    if need and go_version() < need:
        return f"go{need[0]}.{need[1]}+ 필요, 설치본은 go{go_version()[0]}.{go_version()[1]}"
    return None


def run(claim: str) -> tuple[dict, bool]:
    fn, ok = EXPECT[claim]
    with tempfile.TemporaryDirectory() as tmp:
        obs = fn(Path(tmp))
    return obs, bool(ok(obs))


def main() -> int:
    if not GO:
        print("SKIP go 가 PATH 에 없어 Go 단언을 재현하지 못했다")
        return 0
    print(subprocess.run([GO, "version"], capture_output=True, text=True).stdout.strip())
    failed = skipped = 0
    for claim in EXPECT:
        why = skip_reason(claim)
        if why:
            skipped += 1
            print(f"skip {claim}: {why}")
            continue
        obs, ok = run(claim)
        failed += not ok
        print(f"{'ok  ' if ok else 'FAIL'} {claim}: {obs}")
    print(f"{len(EXPECT) - failed - skipped}/{len(EXPECT)} 단언 재현 (건너뜀 {skipped})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
