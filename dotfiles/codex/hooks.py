#!/usr/bin/env python3
"""Codex CLI 비용 훅 등록 — ~/.codex/hooks.json 의 Stop 훅 목록에 codex/cost-hook.py 항목 하나만 관리한다.

사용법 (install.sh / uninstall.sh 가 호출):
  hooks.py check     # 쓰지 않고 apply 가 가능한지만 검사 (깨진 JSON·예상 밖 구조면 exit 1)
  hooks.py apply     # Stop 에 비용 훅 항목이 없으면 추가. 최초 1회 설치 전 파일 유무를 ~/.config/dotfiles/backup 에 기록
  hooks.py restore   # 설치 기록이 있을 때 비용 훅 항목만 제거. 설치 전에 없던 파일이고 남은 훅이 없으면 파일도 지운다

hooks.json 은 다른 도구(터미널 앱 등)도 자기 훅을 넣고 빼는 공유 파일이라, 설치 전 원본으로 통째 되돌리지 않고
이 스크립트가 넣은 항목(command 가 ~/.codex/cost-hook.py 를 가리키는 것)만 넣고 뺀다. 다른 키·항목은 읽기만 한다.
쓰기는 같은 디렉터리의 임시 파일 + os.replace 로 원자적으로 하고 기존 mode 를 보존한다.

Codex 는 새로 추가되거나 바뀐 훅을 사용자가 한 번 검토(신뢰)해야 실행한다 — 설치 후 Codex 를 열면 안내가 뜬다.
"""
import json, os, sys, tempfile

HOME = os.path.expanduser("~")
HOOKS = os.path.join(HOME, ".codex", "hooks.json")
SCRIPT = os.path.join(HOME, ".codex", "cost-hook.py")
BACKUP = os.path.join(HOME, ".config", "dotfiles", "backup")
ABSENT = os.path.join(BACKUP, "codex-hooks.json.absent")
PRESENT = os.path.join(BACKUP, "codex-hooks.json.present")
EVENT = "Stop"
WANT = {"type": "command", "command": f"python3 {SCRIPT}", "timeout": 10}


class Abort(Exception):
    pass


def ours(handler):
    return isinstance(handler, dict) and str(handler.get("command", "")).rstrip().endswith("/.codex/cost-hook.py")


def load():
    """(dict, 존재 여부). 깨진 JSON 이나 예상 밖 구조면 Abort."""
    if not os.path.exists(HOOKS):
        return {}, False
    try:
        with open(HOOKS, encoding="utf-8") as f:
            d = json.load(f)
    except ValueError as e:
        raise Abort(f"{HOOKS} 이 올바른 JSON 이 아님 ({e}) — 원본을 건드리지 않고 중단")
    if not isinstance(d, dict) or not isinstance(d.get("hooks", {}), dict) \
            or not isinstance(d.get("hooks", {}).get(EVENT, []), list):
        raise Abort(f"{HOOKS} 의 구조가 예상과 다름 (hooks.{EVENT} 가 배열이 아님) — 원본을 건드리지 않고 중단")
    for group in d.get("hooks", {}).get(EVENT, []):
        if not isinstance(group, dict) or not isinstance(group.get("hooks", []), list):
            raise Abort(f"{HOOKS} 의 hooks.{EVENT} 항목 구조가 예상과 다름 — 원본을 건드리지 않고 중단")
    return d, True


def atomic_write(obj):
    d = os.path.dirname(HOOKS)
    os.makedirs(d, exist_ok=True)
    mode = os.stat(HOOKS).st_mode & 0o777 if os.path.exists(HOOKS) else 0o600
    fd, tmp = tempfile.mkstemp(prefix=".hooks.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, HOOKS)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def strip(d):
    """비용 훅 항목을 뺀 사본과 뺀 개수. 비게 된 그룹·이벤트 키도 정리한다."""
    d = json.loads(json.dumps(d))
    hooks = d.get("hooks", {})
    removed = 0
    groups = []
    for group in hooks.get(EVENT, []):
        kept = [h for h in group.get("hooks", []) if not ours(h)]
        removed += len(group.get("hooks", [])) - len(kept)
        if kept or not group.get("hooks"):
            group["hooks"] = kept
            groups.append(group)
    if groups:
        hooks[EVENT] = groups
    else:
        hooks.pop(EVENT, None)
    return d, removed


def check():
    load()


def apply():
    d, existed = load()
    handlers = [h for g in d.get("hooks", {}).get(EVENT, []) for h in g.get("hooks", [])]
    if [h for h in handlers if ours(h)] == [WANT]:
        print("[install] codex hooks.json 비용 훅 이미 최신")
        return
    os.makedirs(BACKUP, exist_ok=True)
    if not os.path.exists(ABSENT) and not os.path.exists(PRESENT):
        open(ABSENT if not existed else PRESENT, "w").close()
    d, _ = strip(d)
    d.setdefault("hooks", {}).setdefault(EVENT, []).append({"hooks": [dict(WANT)]})
    atomic_write(d)
    print("[install] codex hooks.json Stop 에 비용 훅 추가 (Codex 에서 한 번 신뢰 승인 필요)")


def restore():
    if not os.path.exists(ABSENT) and not os.path.exists(PRESENT):
        return                                  # 설치 기록 없는 공유 파일은 그대로 둔다
    if not os.path.exists(HOOKS):
        return
    d, _ = load()
    d, removed = strip(d)
    if os.path.exists(ABSENT) and d.get("hooks") == {} and set(d) <= {"hooks"}:
        os.remove(HOOKS)
        print("[uninstall] codex hooks.json 삭제 (설치 전에는 없던 파일이고 남은 훅 없음)")
    elif removed:
        atomic_write(d)
        print("[uninstall] codex hooks.json 비용 훅 제거 (다른 훅은 유지)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"check": check, "apply": apply, "restore": restore}.get(cmd)
    if fn is None:
        print(f"사용법: {sys.argv[0]} check|apply|restore", file=sys.stderr)
        return 2
    try:
        fn()
    except Abort as e:
        print(f"[codex-hooks] 오류: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
