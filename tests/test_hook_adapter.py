#!/usr/bin/env python3
"""hook-adapter.py 유닛테스트 (#65) — stdlib unittest 전용.

입력 예시는 2026-10-04 실측 페이로드(codex-cli 0.160.0, agy 1.2.16)에서 가져왔다.

실행: python3 -m unittest discover -s tests -p 'test_*.py'
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ADAPTER = os.path.join(REPO_ROOT, ".claude", "hooks", "hook-adapter.py")

spec = importlib.util.spec_from_file_location("hook_adapter_under_test", ADAPTER)
ha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ha)

SETTINGS = {
    "hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "gate.sh"}]}],
        "PostToolUse": [
            {"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "fmt.sh", "timeout": 15}]},
            {"matcher": "Bash", "hooks": [{"type": "command", "command": "notify.sh"}]},
        ],
        "PreCompact": [{"hooks": [{"type": "prompt", "prompt": "save state"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "stop.sh"}]}],
    }
}


def emit(harness):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(SETTINGS, f)
        path = f.name
    try:
        out = subprocess.run([sys.executable, ADAPTER, "emit", harness, path],
                             capture_output=True, text=True, check=True)
        return json.loads(out.stdout)
    finally:
        os.unlink(path)


class Emit(unittest.TestCase):
    def test_codex_maps_tools_and_skips_gate_and_prompt_hooks(self):
        hooks = emit("codex")["hooks"]
        self.assertEqual(sorted(hooks), ["PostToolUse", "Stop"])
        matchers = [g["matcher"] for g in hooks["PostToolUse"]]
        self.assertEqual(matchers, ["apply_patch", "Bash"])
        self.assertNotIn("matcher", hooks["Stop"][0])
        cmd = hooks["PostToolUse"][0]["hooks"][0]["command"]
        self.assertIn("hook-adapter.py\" run codex PostToolUse 'Edit|Write' 'fmt.sh'", cmd)
        self.assertEqual(hooks["PostToolUse"][0]["hooks"][0]["timeout"], 20)

    def test_agy_uses_named_definition_and_handler_arrays(self):
        doc = emit("agy")
        self.assertEqual(list(doc), ["agents-scaffold"])
        hooks = doc["agents-scaffold"]
        self.assertEqual(sorted(hooks), ["PostToolUse", "Stop"])
        self.assertIn("write_to_file", hooks["PostToolUse"][0]["matcher"])
        self.assertEqual(hooks["PostToolUse"][1]["matcher"], "run_command")
        # Stop 은 matcher 없는 핸들러 배열
        self.assertEqual(hooks["Stop"][0]["type"], "command")
        self.assertIn("|| echo ..)", hooks["Stop"][0]["command"])


class Normalize(unittest.TestCase):
    def test_codex_apply_patch_splits_files(self):
        payload = {"session_id": "s1", "cwd": "/w", "tool_name": "apply_patch",
                   "tool_input": {"command": "*** Begin Patch\n*** Add File: /w/a.py\n+x\n"
                                             "*** Update File: b/c.ts\n*** Move to: b/d.ts\n*** End Patch"}}
        calls = ha.normalize("codex", "PostToolUse", payload, "/w")
        self.assertEqual([c["tool_input"]["file_path"] for c in calls], ["/w/a.py", "/w/b/c.ts", "/w/b/d.ts"])
        self.assertTrue(all(c["tool_name"] == "Edit" and c["session_id"] == "s1" for c in calls))

    def test_codex_bash_passes_through(self):
        payload = {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "pytest"}, "tool_response": "1 passed"}
        self.assertEqual(ha.normalize("codex", "PostToolUse", payload, "/w"), [payload])

    def test_agy_tools_become_claude_tools(self):
        def call(name, **args):
            return {"conversationId": "c1", "workspacePaths": ["/w"], "toolCall": {"name": name, "args": args}}
        write = ha.normalize("agy", "PostToolUse", call("write_to_file", TargetFile="/w/x.py"), "/w")[0]
        self.assertEqual((write["tool_name"], write["tool_input"]["file_path"], write["session_id"]), ("Write", "/w/x.py", "c1"))
        edit = ha.normalize("agy", "PostToolUse", call("replace_file_content", TargetFile="y.py"), "/w")[0]
        self.assertEqual((edit["tool_name"], edit["tool_input"]["file_path"]), ("Edit", "/w/y.py"))
        bash = ha.normalize("agy", "PostToolUse", call("run_command", CommandLine="go test ./..."), "/w")[0]
        self.assertEqual((bash["tool_name"], bash["tool_input"]["command"]), ("Bash", "go test ./..."))
        stop = ha.normalize("agy", "Stop", {"conversationId": "c1"}, "/w")[0]
        self.assertEqual((stop["session_id"], stop["stop_hook_active"]), ("c1", False))


class StopReply(unittest.TestCase):
    def test_block_is_translated_per_harness(self):
        out = json.dumps({"decision": "block", "reason": "save memory"})
        self.assertEqual(ha.stop_reply("codex", out, "", 0), {"decision": "block", "reason": "save memory"})
        self.assertEqual(ha.stop_reply("agy", out, "", 0), {"decision": "continue", "reason": "save memory"})

    def test_exit_2_with_stderr_and_no_request(self):
        self.assertEqual(ha.stop_reply("agy", "", "why\n", 2), {"decision": "continue", "reason": "why"})
        self.assertIsNone(ha.stop_reply("codex", "", "", 0))


class Run(unittest.TestCase):
    def test_runs_claude_command_with_claude_payload_in_project_root(self):
        with tempfile.TemporaryDirectory() as root:
            dump = os.path.join(root, "dump.json")
            cmd = f'cat > "{dump}"; echo "$CLAUDE_PROJECT_DIR|$(pwd)" > "{dump}.env"'
            payload = {"conversationId": "c9", "workspacePaths": [root],
                       "toolCall": {"name": "write_to_file", "args": {"TargetFile": os.path.join(root, "f.py")}}}
            subprocess.run([sys.executable, ADAPTER, "run", "agy", "PostToolUse", "Edit|Write", cmd],
                           input=json.dumps(payload), text=True, check=True, cwd=os.path.join("/"))
            with open(dump) as f:
                seen = json.load(f)
            self.assertEqual((seen["tool_name"], seen["session_id"]), ("Write", "c9"))
            with open(dump + ".env") as f:
                project_dir, cwd = f.read().strip().split("|")
            self.assertEqual(project_dir, root)
            self.assertEqual(os.path.realpath(cwd), os.path.realpath(root))

    def test_matcher_filters_on_claude_tool_name(self):
        with tempfile.TemporaryDirectory() as root:
            dump = os.path.join(root, "dump.json")
            payload = {"conversationId": "c9", "workspacePaths": [root],
                       "toolCall": {"name": "run_command", "args": {"CommandLine": "ls"}}}
            subprocess.run([sys.executable, ADAPTER, "run", "agy", "PostToolUse", "Edit|Write", f'cat > "{dump}"'],
                           input=json.dumps(payload), text=True, check=True)
            self.assertFalse(os.path.exists(dump))

    def test_stop_block_becomes_agy_continue(self):
        with tempfile.TemporaryDirectory() as root:
            cmd = """echo '{"decision":"block","reason":"remember"}'"""
            out = subprocess.run([sys.executable, ADAPTER, "run", "agy", "Stop", "", cmd],
                                 input=json.dumps({"conversationId": "c1", "workspacePaths": [root]}),
                                 capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(out.stdout), {"decision": "continue", "reason": "remember"})


if __name__ == "__main__":
    unittest.main()
