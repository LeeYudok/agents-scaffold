#!/usr/bin/env python3
"""개인 레이어 사용자 확인 게이트 — Claude Code · Codex · agy 공용 (#94).

루트에 AGENTS.<NAME>.md 가 있으면 세션마다 "이 세션 사용자가 누구인가" 를 먼저 확인하게 강제한다.
ews ai-sdlc 의 사번 게이트(harness_gate.py)를 이 스캐폴드의 개인 레이어에 맞게 옮겼다.
직접 부르지 않고 personal-gate.sh <runtime> <event> 로 부른다(개인 파일이 없으면 셸에서 바로 통과).

  event          Claude Code·Codex   agy             동작
  session-start  SessionStart        SessionStart    미확인이면 확인 지시 주입, 오래된 마커 정리
  prompt         UserPromptSubmit    PreInvocation   미확인이면 지시 재주입
  pre-tool       PreToolUse          PreToolUse      미확인 세션은 질문 도구·선택 명령 외 차단,
                                                     확인 뒤에는 다른 사람의 AGENTS.<NAME>.md 수정 차단
  post-tool      PostToolUse         PostToolUse     선택 명령이 끝나면 세션 마커 기록

선택 명령: .claude/scripts/personal-layer.sh use <NAME|none> (단독 명령). 이 명령이
.claude/state/personal-gate/current 에 값을 남기고, 게이트는 그 값이 요청과 같을 때 세션을 연다.
agy 는 headless 에서 PostToolUse 가 오지 않을 수 있어 pre-tool 이 대기 마커를 남기고 다음 이벤트에서 확정한다.

마커: .claude/state/personal-gate/<session_id> (내용 = NAME 또는 none, .claude/.gitignore 의 state/)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

RUNTIMES = ("claude", "codex", "agy")
QUESTION_TOOLS = {"AskUserQuestion", "ToolSearch", "request_user_input", "ask_question"}
SHELL_TOOLS = {"Bash", "shell", "exec_command", "local_shell", "run_command"}
MARKER_TTL_SECONDS = 7 * 24 * 3600
PERSONAL_MAX_CHARS = 16000  # 확정 컨텍스트에 싣는 개인 파일 본문 한도
NONE = "none"
PERSONAL_FILE = re.compile(r"AGENTS\.([A-Za-z0-9_-]+)\.md")
NOT_PERSONAL = {"OVERRIDE"}  # Codex 생성물(AGENTS.override.md)
# 파일을 고치는 도구의 경로 인자(Claude·Codex·agy)
PATH_KEYS = {"file_path", "notebook_path", "path", "TargetFile", "AbsolutePath", "Path"}
PATCH_FILE = re.compile(r"^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+?)\s*$", re.M)
# 단독 선택 명령만 허용한다(앞의 `cd <dir> &&` 는 허용, 뒤에 명령을 잇는 건 불허).
USE_CMD = re.compile(
    r"^\s*(?:cd\s+\S+\s*&&\s*)?(?:(?:ba)?sh\s+)?(?:\S*/)?\.claude/scripts/personal-layer\.sh"
    r"\s+(?:use\s+(?P<arg>[A-Za-z0-9_-]+)|status)\s*$"
)


# ---------------------------------------------------------------- 경로·상태


def project_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def state_dir() -> Path:
    return project_dir() / ".claude" / "state" / "personal-gate"


def users() -> list[str]:
    names = []
    for path in sorted(project_dir().glob("AGENTS.*.md")):
        match = PERSONAL_FILE.fullmatch(path.name)
        if match and match.group(1).upper() not in NOT_PERSONAL:
            names.append(match.group(1).upper())
    return names


def normalize(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    return NONE if value.lower() == NONE else value.upper()


def valid(value: str | None) -> bool:
    return value == NONE or value in users()


def safe_id(session_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) or "unknown"


def marker_path(session_id: str) -> Path:
    return state_dir() / safe_id(session_id)


def pending_path(session_id: str) -> Path:
    return state_dir() / f"{safe_id(session_id)}.pending"


def announce_path(session_id: str) -> Path:
    # 확정 뒤 아직 "이 세션 사용자: X" 를 알리지 않았다는 표시. Claude 는 PostToolUse 로 바로 알리고,
    # Codex·agy 는 다음 프롬프트 이벤트에서 한 번 알린다.
    return state_dir() / f"{safe_id(session_id)}.announce"


def current_choice() -> str | None:
    try:
        return normalize((state_dir() / "current").read_text(encoding="utf-8"))
    except OSError:
        return None


def write_marker(session_id: str, user: str) -> None:
    path = marker_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(user + "\n", encoding="utf-8")
    pending_path(session_id).unlink(missing_ok=True)
    announce_path(session_id).write_text(user + "\n", encoding="utf-8")


def selected_user(session_id: str) -> str | None:
    path = marker_path(session_id)
    if path.is_file():
        value = normalize(path.read_text(encoding="utf-8"))
        if valid(value):
            return value
    pending = pending_path(session_id)
    if pending.is_file():
        value = normalize(pending.read_text(encoding="utf-8"))
        if valid(value) and current_choice() == value:
            write_marker(session_id, value)
            return value
    return None


def prune_markers() -> None:
    directory = state_dir()
    if not directory.is_dir():
        return
    cutoff = time.time() - MARKER_TTL_SECONDS
    for entry in directory.iterdir():
        if entry.is_file() and entry.name != "current" and entry.stat().st_mtime < cutoff:
            entry.unlink(missing_ok=True)


# ---------------------------------------------------------------- 입력 정규화


class Event:
    """하네스별 훅 입력을 같은 모양으로 맞춘다."""

    def __init__(self, runtime: str, data: dict, hook_event: str = "") -> None:
        self.runtime = runtime
        self.is_tool_event = hook_event == "pre-tool"
        if runtime == "agy":
            call = data.get("toolCall") or {}
            self.session_id = data.get("conversationId", "")
            self.tool = call.get("name", "")
            self.args = call.get("args") or {}
        else:
            self.session_id = data.get("session_id", "")
            self.tool = data.get("tool_name", "")
            self.args = data.get("tool_input") or {}

    def command(self) -> str:
        value = self.args.get("command", self.args.get("CommandLine", self.args.get("cmd", "")))
        if isinstance(value, list):
            value = value[-1] if value else ""  # Codex 는 ["bash", "-lc", "<명령>"] 일 수 있다
        return value if isinstance(value, str) else ""

    def use_request(self) -> tuple[bool, str | None]:
        """(선택 명령인가, 요청한 사용자)"""
        if self.tool not in SHELL_TOOLS:
            return False, None
        match = USE_CMD.match(self.command())
        return (True, normalize(match.group("arg"))) if match else (False, None)

    def edited_paths(self) -> list[str]:
        """이 도구 호출이 고치는 파일 경로. 내용 안의 파일 이름은 보지 않는다(본문에 개인 파일 이름을
        적는 것만으로 막히던 오탐, #94). Codex apply_patch 는 패치 머리줄에서 경로를 읽는다."""
        paths = [v for k, v in self.args.items() if k in PATH_KEYS and isinstance(v, str)]
        if self.tool == "apply_patch":
            paths += PATCH_FILE.findall(self.command())
        return paths

    def edited_owners(self) -> set[str]:
        if self.tool in SHELL_TOOLS or self.tool in QUESTION_TOOLS:
            return set()
        owners = set()
        for path in self.edited_paths():
            match = PERSONAL_FILE.fullmatch(os.path.basename(path.strip()))
            if match:
                owners.add(match.group(1).upper())
        return owners - NOT_PERSONAL


# ---------------------------------------------------------------- 출력


def emit(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False)
    log_path = os.environ.get("PERSONAL_GATE_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {' '.join(sys.argv[1:])} {text[:160]}\n")
    sys.stdout.write(text)


def inject(event: Event, hook_event: str, text: str) -> None:
    if event.runtime == "agy":
        step = {"systemMessage": {"systemMessage": text}} if hook_event == "SessionStart" else {"ephemeralMessage": text}
        emit({"injectSteps": [step]})
    else:
        emit({"hookSpecificOutput": {"hookEventName": hook_event, "additionalContext": text}})


def deny(event: Event, reason: str) -> None:
    if event.runtime == "agy":
        emit({"decision": "deny", "reason": reason})
    else:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": reason}})


def passthrough(event: Event) -> None:
    # Claude Code·Codex 는 빈 출력이면 통과다. agy 1.5.0 은 PreToolUse 의 {} 를 거부로 읽어서
    # (빈 출력·{"decision":"allow"} 는 허용, 2026-11-04 실측) 툴 이벤트에만 명시적으로 허용을 낸다.
    if event.runtime == "agy" and event.is_tool_event:
        emit({"decision": "allow"})


def instruction() -> str:
    options = ", ".join(users() + ["해당 없음(none)"])
    return (
        "[personal-gate] 이 세션은 아직 사용자를 확인하지 않았다. AGENTS.md 의 개인 레이어 규칙에 따라 "
        f"다른 작업보다 먼저 사용자에게 누구인지 묻는다(선택지: {options}). "
        "답을 받으면 `.claude/scripts/personal-layer.sh use <NAME>`(해당 없음이면 `use none`)을 단독 명령으로 실행한다. "
        "그 전에는 질문 도구와 이 명령 외 모든 도구 호출이 훅에서 차단되고, 어떤 개인 지침도 따르지 않는다."
    )


def selected_context(user: str) -> str:
    if user == NONE:
        return ("[personal-gate] 이 세션 사용자는 개인 레이어 해당 없음이다. AGENTS.<NAME>.md 의 개인 지침은 "
                "컨텍스트에 실려 있어도 모두 무시하고 AGENTS.md 만 따른다. 개인 파일은 수정하지 않는다(훅이 막는다).")
    # "읽어라" 는 지시만으로는 agy 가 파일을 열지 않아(1.5.0 실측) 본문을 함께 싣는다
    try:
        body = (project_dir() / f"AGENTS.{user}.md").read_text(encoding="utf-8")
    except OSError:
        body = ""
    if len(body) > PERSONAL_MAX_CHARS:
        body = body[:PERSONAL_MAX_CHARS] + f"\n…(잘림 — 나머지는 AGENTS.{user}.md 를 직접 읽는다)"
    return (f"[personal-gate] 이 세션 사용자: {user}. 지금부터 AGENTS.md(공통) + 아래 AGENTS.{user}.md(개인)를 함께 따른다. "
            f"컨텍스트에 다른 사람의 개인 지침이 있으면 무시한다. 이 사용자의 규칙·메모는 AGENTS.{user}.md 에만 덧붙이고 "
            f"다른 사람의 개인 파일은 수정하지 않는다(훅이 막는다).\n\n--- AGENTS.{user}.md ---\n{body}")


# ---------------------------------------------------------------- 핸들러


def on_session_start(event: Event) -> None:
    prune_markers()
    user = selected_user(event.session_id)
    inject(event, "SessionStart", selected_context(user) if user else instruction())


def on_prompt(event: Event) -> None:
    hook_event = "PreInvocation" if event.runtime == "agy" else "UserPromptSubmit"
    user = selected_user(event.session_id)
    if not user:
        inject(event, hook_event, instruction())
        return
    announce = announce_path(event.session_id)
    if announce.is_file():
        announce.unlink(missing_ok=True)
        inject(event, hook_event, selected_context(user))
        return
    passthrough(event)


def on_pre_tool(event: Event) -> None:
    user = selected_user(event.session_id)
    if user:
        others = sorted(owner for owner in event.edited_owners() if owner != user)
        if others:
            deny(event, f"[personal-gate] 이 세션 사용자는 {user} 다. AGENTS.{others[0]}.md 는 다른 사람의 개인 "
                        "지침이라 수정할 수 없다." + ("" if user == NONE else f" 이 사용자의 내용은 AGENTS.{user}.md 에 쓴다."))
        else:
            passthrough(event)
        return
    if event.tool in QUESTION_TOOLS:
        passthrough(event)
        return
    is_use, requested = event.use_request()
    if is_use:
        if valid(requested):
            path = pending_path(event.session_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(requested + "\n", encoding="utf-8")
        passthrough(event)
        return
    deny(event, instruction())


def on_post_tool(event: Event) -> None:
    is_use, requested = event.use_request()
    if is_use and valid(requested) and current_choice() == requested:
        write_marker(event.session_id, requested)
        # Codex 는 PostToolUse additionalContext 를 도구 출력 앞의 developer 메시지로 끼워 넣어
        # Chat Completions 계열 게이트웨이에서 오류가 날 수 있다(ai-sdlc 실측) — Claude 만 주입한다.
        if event.runtime == "claude":
            announce_path(event.session_id).unlink(missing_ok=True)
            inject(event, "PostToolUse", selected_context(requested))
            return
    passthrough(event)


HANDLERS = {"session-start": on_session_start, "prompt": on_prompt, "pre-tool": on_pre_tool, "post-tool": on_post_tool}


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in RUNTIMES or sys.argv[2] not in HANDLERS:
        sys.stderr.write(f"usage: personal-gate.sh {{{'|'.join(RUNTIMES)}}} {{{'|'.join(HANDLERS)}}}\n")
        return 1
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}
    event = Event(sys.argv[1], data, sys.argv[2])
    if not users():
        passthrough(event)
        return 0
    HANDLERS[sys.argv[2]](event)
    return 0


if __name__ == "__main__":
    sys.exit(main())
