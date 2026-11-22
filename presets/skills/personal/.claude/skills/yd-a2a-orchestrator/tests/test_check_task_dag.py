"""check_task_dag.py 가 SKILL.md 의 작업 DAG 단언을 판정하는지 본다 (stdlib only)."""

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_task_dag",
                                              SKILL / "scripts" / "check_task_dag.py")
m = importlib.util.module_from_spec(spec)
sys.modules["check_task_dag"] = m
spec.loader.exec_module(m)

SHA = "a" * 64


def task(tid, owner="codex-glm", reviewer="claude", state="done", deps=None,
         artifact="out/x", sha=SHA, checks=None):
    return {
        "id": tid,
        "owner": owner,
        "reviewer": reviewer,
        "repo": "dok3search",
        "branch": f"batch/{owner}-20261122-ab12cd34",
        "worktree": "/tmp/wt",
        "depends_on": deps or [],
        "state": state,
        "artifact": artifact,
        "sha256": sha,
        "checks": checks if checks is not None else [{"command": "cargo test", "exit_code": 0}],
    }


def good():
    return {
        "coordinator": {"agent": "codex", "term": 7},
        "pool": ["codex-glm", "codex-deepseek"],
        "tasks": [
            task("t1"),
            task("t2", owner="codex-deepseek", reviewer="codex", deps=["t1"]),
        ],
    }


def run(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main(argv)
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class TaskDag(unittest.TestCase):
    def test_complete_dag_passes(self):
        self.assertEqual(m.check(good()), [])

    def test_duplicate_task_id_is_failure(self):
        d = good()
        d["tasks"][1]["id"] = "t1"
        self.assertTrue(any("유일하지 않다" in e for e in m.check(d)))

    def test_missing_dependency_is_failure(self):
        d = good()
        d["tasks"][1]["depends_on"] = ["nope"]
        self.assertTrue(any("의존 대상 nope" in e for e in m.check(d)))

    def test_dependency_cycle_is_failure(self):
        d = good()
        d["tasks"][0]["depends_on"] = ["t2"]
        self.assertTrue(any("순환" in e for e in m.check(d)))

    def test_owner_and_reviewer_must_differ(self):
        d = good()
        d["tasks"][0]["reviewer"] = d["tasks"][0]["owner"]
        self.assertTrue(any("담당과 리뷰어가 같다" in e for e in m.check(d)))

    def test_unknown_state_is_failure(self):
        d = good()
        d["tasks"][0]["state"] = "finished"
        self.assertTrue(any("state" in e for e in m.check(d)))

    def test_done_with_nonzero_exit_is_failure(self):
        d = good()
        d["tasks"][0]["checks"] = [{"command": "cargo test", "exit_code": 1}]
        self.assertTrue(any("exit_code 가 0 이 아닌" in e for e in m.check(d)))

    def test_done_without_checks_is_failure(self):
        d = good()
        d["tasks"][0]["checks"] = []
        self.assertTrue(any("검증 명령(checks)이 없다" in e for e in m.check(d)))

    def test_done_without_artifact_is_failure(self):
        d = good()
        d["tasks"][0]["artifact"] = ""
        self.assertTrue(any("산출물 artifact 경로가 없다" in e for e in m.check(d)))

    def test_done_with_bad_hash_is_failure(self):
        d = good()
        d["tasks"][0]["sha256"] = "xyz"
        self.assertTrue(any("sha256" in e for e in m.check(d)))

    def test_missing_coordinator_is_failure(self):
        d = good()
        del d["coordinator"]
        self.assertTrue(any("coordinator" in e for e in m.check(d)))

    def test_missing_pool_is_failure(self):
        d = good()
        del d["pool"]
        self.assertTrue(any("pool(에이전트 풀) 목록이 없다" in e for e in m.check(d)))

    def test_finished_agent_is_returned_to_pool(self):
        d = good()
        d["pool"] = ["codex-glm"]  # codex-deepseek 는 t2 를 끝냈는데 풀에 없다
        self.assertTrue(any("풀에 반환되지 않았다" in e for e in m.check(d)))

    def test_busy_agent_in_pool_is_failure(self):
        d = good()
        d["tasks"][1]["state"] = "working"
        d["tasks"][1]["artifact"] = ""
        d["tasks"][1]["sha256"] = ""
        d["tasks"][1]["checks"] = []
        self.assertTrue(any("풀에 있으면 안 된다" in e for e in m.check(d)))

    def test_duplicate_pool_entry_is_failure(self):
        d = good()
        d["pool"] = ["codex-glm", "codex-glm", "codex-deepseek"]
        self.assertTrue(any("중복" in e for e in m.check(d)))

    def test_retry_cap_is_failure(self):
        d = good()
        d["tasks"][0]["attempts"] = m.MAX_ATTEMPTS + 1
        self.assertTrue(any("최대 3회" in e for e in m.check(d)))

    def test_todo_marker_is_failure(self):
        d = good()
        d["tasks"][0]["checks"] = [{"command": "cargo test (추가 예정)", "exit_code": 0}]
        self.assertTrue(any("추가 예정" in e for e in m.check(d)))

    def test_unreadable_input_is_tool_error(self):
        code, _, err = run(["-"], stdin="{not json")
        self.assertEqual(code, 2)
        self.assertIn("읽지 못했다", err)
        self.assertEqual(run([str(SKILL / "no-such.json")])[0], 2)

    def test_cli_exit_codes(self):
        self.assertEqual(run(["-"], stdin=json.dumps(good()))[0], 0)
        bad = good()
        bad["tasks"][1]["state"] = "failed"
        code, out, _ = run(["-"], stdin=json.dumps(bad))
        self.assertEqual(code, 0)  # failed 작업 자체는 위반이 아니다
        bad["tasks"][1]["reviewer"] = bad["tasks"][1]["owner"]
        code, out, _ = run(["-"], stdin=json.dumps(bad))
        self.assertEqual(code, 1)
        self.assertIn("위반", out)

    def test_verify_files_detects_changed_artifact(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            d = good()
            for e in d["tasks"]:
                p = root / e["artifact"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("v1")
                e["sha256"] = m.hash_path(p)
            self.assertEqual(m.verify_files(d, root), [])
            (root / "out/x").write_text("v2")
            errs = m.verify_files(d, root)
            self.assertEqual(len(errs), 2)
            self.assertIn("sha256 과 다르다", errs[0])
            (root / "out/x").unlink()
            self.assertTrue(any("가 없다" in e for e in m.verify_files(d, root)))

    def test_directory_hash_covers_contents_and_names(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "a.txt").write_text("x")
            h1 = m.hash_path(d)
            (d / "a.txt").write_text("y")
            h2 = m.hash_path(d)
            (d / "a.txt").rename(d / "b.txt")
            self.assertEqual(len({h1, h2, m.hash_path(d)}), 3)

    def test_worktree_isolation_allows_parallel_tasks(self):
        """서로 의존하지 않는 두 작업은 각자 워크트리·브랜치로 동시에 돌 수 있다."""
        d = good()
        d["tasks"][1]["depends_on"] = []
        d["tasks"][1]["worktree"] = "/tmp/wt-2"
        d["tasks"][1]["branch"] = "batch/codex-deepseek-20261122-99887766"
        self.assertEqual(m.check(d), [])

    def test_hash_subcommand_matches_sha256(self):
        with tempfile.NamedTemporaryFile() as f:
            f.write(b"abc")
            f.flush()
            code, out, _ = run(["hash", f.name])
        self.assertEqual((code, out.strip()), (0, hashlib.sha256(b"abc").hexdigest()))
        self.assertEqual(run(["hash", "/no/such/path"])[0], 2)


if __name__ == "__main__":
    unittest.main()
