#!/usr/bin/env python3
"""Codex·agy 훅 어댑터 (#65) — stdlib 전용.

훅의 원본은 Claude Code 형식(.claude/settings.json 의 hooks + .claude/hooks/*)이다. Codex 와
agy(Antigravity)는 훅 설정 위치·이벤트·입력 JSON·응답 형식이 달라서, 이 스크립트가 두 가지를 맡는다.

  emit <codex|agy> <settings.json>
      settings.json 의 훅에서 .codex/hooks.json 또는 .agents/hooks.json 내용을 stdout 으로 낸다.
  run <codex|agy> <Event> <claude-matcher> <claude-command>
      하네스가 넘긴 입력을 Claude 형식으로 바꿔 원래 훅 명령을 실행하고, 응답을 하네스 형식으로 돌려준다.

실측(codex-cli 0.160.0, agy 1.2.16, 2026-10-04):
- Codex 입력은 Claude 와 거의 같다(session_id·cwd·tool_name·tool_input·tool_response). 셸은 tool_name
  "Bash", 파일 편집은 "apply_patch" 이고 tool_input.command 에 패치 텍스트가 온다. Stop 응답
  {"decision":"block","reason":...} 를 Claude 와 같이 받아 한 턴 더 돈다. 훅은 세션 cwd 에서 실행된다.
- agy 입력은 camelCase 다(conversationId·workspacePaths·toolCall{name,args}). 셸은 run_command
  (args.CommandLine), 파일 편집은 write_to_file·replace_file_content·multi_replace_file_content·sed_file
  (args.TargetFile). PostToolUse 에 명령 출력은 없다. Stop 은 {"decision":"continue","reason":...} 로
  한 턴 더 돈다. 훅은 hooks.json 이 있는 .agents/ 에서 실행된다.
- 둘 다 프로젝트 경로 환경변수가 없어서 CLAUDE_PROJECT_DIR 를 여기서 채운다.

옮기지 않는 것: PreToolUse(커밋 게이트는 .git/hooks 가 맡는다, 차단 의미도 하네스마다 다르다),
prompt 타입 훅(PreCompact 등 — 두 하네스에 대응물이 없다).
"""
import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

MARK = "hook-adapter.py"
TOOL_EVENTS = {"PostToolUse"}
SUPPORTED = {
    "codex": {"PostToolUse", "Stop", "SessionStart", "UserPromptSubmit"},
    "agy": {"PostToolUse", "Stop"},
}
# Claude 툴 이름 → 하네스 툴 이름(matcher). 목록에 없는 이름은 그 하네스에서 옮기지 않는다.
TOOL_MAP = {
    "codex": {"Bash": ["Bash"], "Edit": ["apply_patch"], "Write": ["apply_patch"], "MultiEdit": ["apply_patch"]},
    "agy": {
        "Bash": ["run_command"],
        "Edit": ["replace_file_content", "multi_replace_file_content", "sed_file"],
        "Write": ["write_to_file"],
        "MultiEdit": ["multi_replace_file_content"],
    },
}
AGY_WRITE_TOOLS = {"write_to_file"}
AGY_EDIT_TOOLS = {"replace_file_content", "multi_replace_file_content", "sed_file"}
PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Move to): (.+?)\s*$", re.M)
# hooks.json 안에서 어댑터를 찾는 방법 — codex 는 세션 cwd, agy 는 .agents/ 에서 실행된다
ADAPTER_PATH = {
    "codex": '"$(git rev-parse --show-toplevel 2>/dev/null || pwd)/.claude/hooks/hook-adapter.py"',
    "agy": '"$(git rev-parse --show-toplevel 2>/dev/null || echo ..)/.claude/hooks/hook-adapter.py"',
}


def harness_matcher(harness, claude_matcher):
    names = []
    for part in claude_matcher.split("|"):
        for name in TOOL_MAP[harness].get(part.strip(), []):
            if name not in names:
                names.append(name)
    return "|".join(names)


def emit(harness, settings_path):
    with open(settings_path, encoding="utf-8") as f:
        hooks = (json.load(f) or {}).get("hooks") or {}
    events = {}
    for event, groups in hooks.items():
        if event not in SUPPORTED[harness]:
            continue
        for group in groups or []:
            claude_matcher = group.get("matcher", "") or ""
            matcher = harness_matcher(harness, claude_matcher) if event in TOOL_EVENTS else ""
            if event in TOOL_EVENTS and claude_matcher and not matcher:
                continue
            for hook in group.get("hooks") or []:
                if hook.get("type") != "command" or not hook.get("command"):
                    continue
                command = hook["command"]
                if "'" in command or "'" in claude_matcher:
                    print(f"hook-adapter: skipped a {event} hook with a single quote: {command}", file=sys.stderr)
                    continue
                entry = {
                    "type": "command",
                    "command": f"python3 {ADAPTER_PATH[harness]} run {harness} {event} '{claude_matcher}' '{command}'",
                    "timeout": int(hook.get("timeout", 30)) + 5,
                }
                events.setdefault(event, []).append((matcher, entry))
    out = {}
    for event, items in events.items():
        groups = []
        for matcher, entry in items:
            if event in TOOL_EVENTS:
                groups.append({"matcher": matcher or ".*", "hooks": [entry]})
            elif harness == "codex":
                groups.append({"hooks": [entry]})
            else:
                groups.append(entry)  # agy 의 Invocation·Stop 이벤트는 핸들러 배열이다
        out[event] = groups
    if harness == "codex":
        doc = {"hooks": out}
    else:
        doc = {"agents-scaffold": out}
    json.dump(doc, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def project_root(harness, payload):
    if harness == "agy":
        paths = payload.get("workspacePaths") or []
        if paths:
            return paths[0]
    elif payload.get("cwd"):
        cwd = payload["cwd"]
        try:
            top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True, timeout=5)
            if top.returncode == 0 and top.stdout.strip():
                return top.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return cwd
    return os.getcwd()


def absolute(path, base):
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))


def normalize(harness, event, payload, root):
    """하네스 입력 → Claude 형식 입력 목록(편집 한 번이 여러 파일이면 파일마다 하나)."""
    if harness == "codex":
        if event in TOOL_EVENTS and payload.get("tool_name") == "apply_patch":
            patch = (payload.get("tool_input") or {}).get("command") or ""
            base = payload.get("cwd") or root
            return [dict(payload, tool_name="Edit", tool_input={"file_path": absolute(p, base)})
                    for p in PATCH_FILE.findall(patch)]
        return [payload]

    session = payload.get("conversationId") or ""
    common = {"session_id": session, "hook_event_name": event, "cwd": root}
    if event == "Stop":
        return [dict(common, stop_hook_active=False)]
    call = payload.get("toolCall") or {}
    name, args = call.get("name") or "", call.get("args") or {}
    error = payload.get("error") or ""
    target = args.get("TargetFile") or args.get("AbsolutePath") or args.get("File") or ""
    if name == "run_command":
        tool_name, tool_input = "Bash", {"command": args.get("CommandLine", "")}
    elif name in AGY_WRITE_TOOLS and target:
        tool_name, tool_input = "Write", {"file_path": absolute(target, root)}
    elif name in AGY_EDIT_TOOLS and target:
        tool_name, tool_input = "Edit", {"file_path": absolute(target, root)}
    else:
        tool_name, tool_input = name, args
    response = {"is_error": True, "error": error} if error else ""
    return [dict(common, tool_name=tool_name, tool_input=tool_input, tool_response=response)]


def stop_reply(harness, stdout, stderr, code):
    """Claude Stop 훅의 '한 턴 더' 요청을 하네스 형식으로 바꾼다. 요청이 없으면 None."""
    reason = None
    try:
        data = json.loads(stdout) if stdout.strip() else {}
        if isinstance(data, dict) and data.get("decision") == "block":
            reason = data.get("reason") or ""
    except ValueError:
        pass
    if reason is None and code == 2:
        reason = stderr.strip()
    if reason is None:
        return None
    if harness == "codex":
        return {"decision": "block", "reason": reason}
    return {"decision": "continue", "reason": reason}


def run(harness, event, claude_matcher, command):
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    root = project_root(harness, payload)
    pattern = re.compile(rf"^(?:{claude_matcher})$") if (event in TOOL_EVENTS and claude_matcher) else None
    env = dict(os.environ, CLAUDE_PROJECT_DIR=root)
    for claude_payload in normalize(harness, event, payload, root):
        if pattern and not pattern.match(str(claude_payload.get("tool_name", ""))):
            continue
        try:
            done = subprocess.run(command, shell=True, input=json.dumps(claude_payload, ensure_ascii=False),
                                  capture_output=True, text=True, cwd=root, env=env)
        except OSError as e:
            print(f"hook-adapter: {e}", file=sys.stderr)
            continue
        if done.stderr:
            sys.stderr.write(done.stderr)
        if event == "Stop":
            reply = stop_reply(harness, done.stdout, done.stderr, done.returncode)
            if reply:
                print(json.dumps(reply, ensure_ascii=False))
                return 0
    return 0


def main(argv):
    if len(argv) >= 3 and argv[0] == "emit" and argv[1] in SUPPORTED:
        return emit(argv[1], argv[2])
    if len(argv) >= 5 and argv[0] == "run" and argv[1] in SUPPORTED:
        return run(argv[1], argv[2], argv[3], argv[4])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
