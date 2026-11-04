#!/usr/bin/env python3
"""personal-gate 훅 시험 (#94) — stdlib unittest 전용.

임시 레포에 게이트 스크립트를 복사해 하네스별 입력 JSON 을 넣고, 주입·차단·통과 출력을 본다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(REPO, ".claude", "hooks")
USE = ".claude/scripts/personal-layer.sh use TEST"


class Gate(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, ".claude", "hooks"))
        for name in ("personal-gate.sh", "personal-gate.py"):
            shutil.copy(os.path.join(HOOKS, name), os.path.join(self.root, ".claude", "hooks", name))
        with open(os.path.join(self.root, "AGENTS.md"), "w") as f:
            f.write("# base\n")

    def tearDown(self):
        shutil.rmtree(self.root)

    def personal(self, name="TEST"):
        with open(os.path.join(self.root, f"AGENTS.{name}.md"), "w") as f:
            f.write(f"# mine\n\n{name}-RULE-7781\n")

    def run_gate(self, runtime, event, payload):
        out = subprocess.run(["sh", os.path.join(self.root, ".claude", "hooks", "personal-gate.sh"), runtime, event],
                             input=json.dumps(payload), capture_output=True, text=True, cwd="/")
        self.assertEqual(out.returncode, 0, out.stderr)
        return json.loads(out.stdout) if out.stdout.strip() else None

    def choose(self, value):
        state = os.path.join(self.root, ".claude", "state", "personal-gate")
        os.makedirs(state, exist_ok=True)
        with open(os.path.join(state, "current"), "w") as f:
            f.write(value + "\n")

    def claude_tool(self, tool, tool_input, sid="s1"):
        return {"session_id": sid, "tool_name": tool, "tool_input": tool_input}

    def assert_denied(self, out):
        self.assertEqual(out["hookSpecificOutput"]["permissionDecision"], "deny")

    def confirm(self, value="TEST", runtime="claude", sid="s1"):
        cmd = f".claude/scripts/personal-layer.sh use {value}"
        payload = {"session_id": sid, "tool_name": "Bash", "tool_input": {"command": cmd}}
        self.run_gate(runtime, "pre-tool", payload)
        self.choose(value)  # personal-layer.sh use 가 남기는 값
        return self.run_gate(runtime, "post-tool", payload)

    def test_without_personal_files_everything_passes(self):
        self.assertIsNone(self.run_gate("claude", "pre-tool", self.claude_tool("Read", {"file_path": "x"})))
        # agy 1.5.0 은 PreToolUse 의 {} 를 거부로 읽는다 — 허용은 명시한다
        self.assertEqual(self.run_gate("agy", "pre-tool", {"conversationId": "c", "toolCall": {"name": "read_file"}}),
                         {"decision": "allow"})
        self.assertIsNone(self.run_gate("agy", "prompt", {"conversationId": "c"}))
        # AGENTS.override.md 는 Codex 생성물이라 개인 파일로 치지 않는다
        with open(os.path.join(self.root, "AGENTS.override.md"), "w") as f:
            f.write("x\n")
        self.assertIsNone(self.run_gate("claude", "session-start", {"session_id": "s1"}))

    def test_unconfirmed_session_gets_instruction_and_tools_are_blocked(self):
        self.personal()
        ctx = self.run_gate("claude", "session-start", {"session_id": "s1"})["hookSpecificOutput"]["additionalContext"]
        self.assertIn("TEST", ctx)
        self.assertIn("use <NAME>", ctx)
        self.assertIn("additionalContext", self.run_gate("claude", "prompt", {"session_id": "s1"})["hookSpecificOutput"])
        self.assert_denied(self.run_gate("claude", "pre-tool", self.claude_tool("Read", {"file_path": "x"})))
        self.assert_denied(self.run_gate("claude", "pre-tool", self.claude_tool("Bash", {"command": USE + " && rm -rf x"})))
        self.assertIsNone(self.run_gate("claude", "pre-tool", self.claude_tool("AskUserQuestion", {})))
        self.assertIsNone(self.run_gate("claude", "pre-tool", self.claude_tool("Bash", {"command": "bash ./" + USE})))

    def test_selection_opens_the_gate_and_guards_other_peoples_files(self):
        self.personal()
        self.personal("OTHER")
        out = self.confirm()
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("이 세션 사용자: TEST", ctx)
        self.assertIn("TEST-RULE-7781", ctx)  # 개인 파일 본문을 함께 싣는다
        self.assertNotIn("OTHER-RULE-7781", ctx)
        self.assertIsNone(self.run_gate("claude", "pre-tool", self.claude_tool("Read", {"file_path": "x"})))
        self.assertIsNone(self.run_gate("claude", "prompt", {"session_id": "s1"}))  # Claude 는 이미 알렸다
        self.assert_denied(self.run_gate("claude", "pre-tool", self.claude_tool("Edit", {"file_path": "AGENTS.OTHER.md"})))
        self.assertIsNone(self.run_gate("claude", "pre-tool", self.claude_tool("Edit", {"file_path": "AGENTS.TEST.md"})))
        # 다른 세션은 여전히 미확인이다
        self.assert_denied(self.run_gate("claude", "pre-tool", self.claude_tool("Read", {"file_path": "x"}, sid="s2")))

    def test_file_names_inside_content_do_not_count_as_edits(self):
        # 본문에 다른 사람 파일 이름이 있어도 고치는 대상이 아니면 막지 않는다(오탐 회귀)
        self.personal()
        self.personal("OTHER")
        self.confirm()
        write = self.claude_tool("Write", {"file_path": "tests/x.py", "content": "see AGENTS.OTHER.md"})
        self.assertIsNone(self.run_gate("claude", "pre-tool", write))
        patch = {"session_id": "s1", "tool_name": "apply_patch",
                 "tool_input": {"command": "*** Begin Patch\n*** Update File: AGENTS.OTHER.md\n@@\n-a\n+b\n*** End Patch"}}
        self.assert_denied(self.run_gate("claude", "pre-tool", patch))

    def test_selection_without_matching_choice_does_not_open(self):
        self.personal()
        self.choose("none")
        self.run_gate("claude", "post-tool", self.claude_tool("Bash", {"command": USE}))
        self.assert_denied(self.run_gate("claude", "pre-tool", self.claude_tool("Read", {"file_path": "x"})))

    def test_none_ignores_and_protects_personal_files(self):
        self.personal()
        out = self.confirm("none")
        self.assertIn("해당 없음", out["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.run_gate("claude", "pre-tool", self.claude_tool("Read", {"file_path": "x"})))
        self.assert_denied(self.run_gate("claude", "pre-tool", self.claude_tool("Write", {"file_path": "AGENTS.TEST.md"})))

    def test_agy_uses_its_own_formats_and_confirms_from_pending_marker(self):
        self.personal()
        out = self.run_gate("agy", "session-start", {"conversationId": "c1"})
        self.assertIn("TEST", out["injectSteps"][0]["systemMessage"]["systemMessage"])
        self.assertIn("ephemeralMessage", self.run_gate("agy", "prompt", {"conversationId": "c1"})["injectSteps"][0])
        denied = self.run_gate("agy", "pre-tool", {"conversationId": "c1", "toolCall": {"name": "read_file", "args": {}}})
        self.assertEqual(denied["decision"], "deny")
        ok = self.run_gate("agy", "pre-tool", {"conversationId": "c1",
                                               "toolCall": {"name": "run_command", "args": {"CommandLine": USE}}})
        self.assertEqual(ok, {"decision": "allow"})
        self.choose("TEST")  # headless 에서는 PostToolUse 없이 다음 이벤트에서 확정된다
        announced = self.run_gate("agy", "prompt", {"conversationId": "c1"})
        self.assertIn("이 세션 사용자: TEST", announced["injectSteps"][0]["ephemeralMessage"])
        self.assertIsNone(self.run_gate("agy", "prompt", {"conversationId": "c1"}))  # 한 번만 알린다
        self.assertEqual(self.run_gate("agy", "pre-tool", {"conversationId": "c1", "toolCall": {"name": "read_file"}}),
                         {"decision": "allow"})

    def test_codex_denies_like_claude_and_skips_post_tool_context(self):
        self.personal()
        payload = {"session_id": "x1", "tool_name": "Bash", "tool_input": {"command": "ls"}}
        self.assert_denied(self.run_gate("codex", "pre-tool", payload))
        self.assertIsNone(self.confirm(runtime="codex", sid="x1"))  # Codex 에는 PostToolUse 주입을 하지 않는다
        self.assertIsNone(self.run_gate("codex", "pre-tool", payload))
        ctx = self.run_gate("codex", "prompt", {"session_id": "x1"})["hookSpecificOutput"]["additionalContext"]
        self.assertIn("이 세션 사용자: TEST", ctx)  # 다음 프롬프트에서 한 번 알린다


class AdapterEmitsGate(unittest.TestCase):
    def emit(self, harness, *extra):
        out = subprocess.run([sys.executable, os.path.join(HOOKS, "hook-adapter.py"), "emit", harness,
                              os.path.join(REPO, ".claude", "settings.json"), *extra],
                             capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_codex_gate_comes_first_and_is_not_wrapped(self):
        hooks = self.emit("codex")["hooks"]
        first = hooks["PreToolUse"][0]["hooks"][0]["command"]
        self.assertIn("personal-gate.sh", first)
        self.assertIn("codex pre-tool", first)
        self.assertNotIn("hook-adapter.py", first)
        self.assertTrue(any("hook-adapter.py" in g["hooks"][0]["command"] for g in hooks["PostToolUse"]))

    def test_gate_only_emits_just_the_gate(self):
        doc = self.emit("agy", "--gate-only")["agents-scaffold"]
        self.assertEqual(sorted(doc), ["PostToolUse", "PreInvocation", "PreToolUse", "SessionStart"])
        self.assertIn("agy prompt", doc["PreInvocation"][0]["command"])
        self.assertNotIn("hook-adapter.py", json.dumps(doc))


if __name__ == "__main__":
    unittest.main()
