#!/usr/bin/env python3
"""Antigravity CLI(agy) status line 등록 — ~/.gemini/antigravity-cli/settings.json 의 statusLine 키 하나만 관리한다.

사용법 (install.sh / uninstall.sh 가 호출):
  settings.py check     # 쓰지 않고 apply 가 가능한지만 검사 (깨진 JSON·최상위가 객체가 아니면 exit 1)
  settings.py apply     # statusLine 을 이 저장소 스크립트로 맞춘다. 최초 1회 설치 전 상태를 ~/.config/dotfiles/backup 에 기록
  settings.py restore   # statusLine 만 설치 전 값으로 되돌린다. 설치 전에 없던 파일이고 남은 키가 없으면 파일도 지운다

statusLine 외의 키(모델·권한 등)는 읽기만 한다. statusLine 안에서도 type/command/enabled 만 맞추고
사용자가 넣은 padding·stack_with_default 같은 선택 키는 그대로 둔다.
쓰기는 같은 디렉터리의 임시 파일 + os.replace 로 원자적으로 하고 기존 mode 를 보존한다.
키 이름은 camelCase(statusLine) 여야 한다 — statusline 으로 쓰면 Antigravity CLI 가 무시한다.
"""
import json, os, sys, tempfile

HOME = os.path.expanduser("~")
DIR = os.path.join(HOME, ".gemini", "antigravity-cli")
SETTINGS = os.path.join(DIR, "settings.json")
SCRIPT = os.path.join(DIR, "statusline-command.sh")
BACKUP = os.path.join(HOME, ".config", "dotfiles", "backup")
ORIG = os.path.join(BACKUP, "agy-settings.json.orig")
ABSENT = os.path.join(BACKUP, "agy-settings.json.absent")
WANT = {"type": "command", "command": f"bash {SCRIPT}", "enabled": True}


class Abort(Exception):
    pass


def load(path=SETTINGS):
    """(dict, 존재 여부). 깨진 JSON 이나 최상위가 객체가 아니면 Abort."""
    if not os.path.exists(path):
        return {}, False
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except ValueError as e:
        raise Abort(f"{path} 이 올바른 JSON 이 아님 ({e}) — 원본을 건드리지 않고 중단")
    if not isinstance(d, dict):
        raise Abort(f"{path} 최상위가 객체가 아님 — 원본을 건드리지 않고 중단")
    return d, True


def atomic_write(obj, path=SETTINGS):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else 0o600
    fd, tmp = tempfile.mkstemp(prefix=".settings.", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def check():
    load()


def apply():
    d, existed = load()
    cur = d.get("statusLine")
    new = dict(cur) if isinstance(cur, dict) else {}
    new.update(WANT)
    if cur == new:
        print("[install] agy settings.json statusLine 이미 최신")
        return
    # 최초 1회: settings.json 유무와 이전 내용을 기록 (restore 용)
    os.makedirs(BACKUP, exist_ok=True)
    if not os.path.exists(ORIG) and not os.path.exists(ABSENT):
        if existed:
            atomic_write(d, ORIG)
        else:
            open(ABSENT, "w").close()
    d["statusLine"] = new
    atomic_write(d)
    print("[install] agy settings.json statusLine 키 갱신")


def restore():
    if not os.path.exists(ORIG) and not os.path.exists(ABSENT):
        return                                  # install 이 agy 단계를 건너뛴 머신
    if not os.path.exists(SETTINGS):
        return
    d, _ = load()
    before = json.loads(json.dumps(d))
    prev = load(ORIG)[0].get("statusLine") if os.path.exists(ORIG) else None
    if prev is None:
        d.pop("statusLine", None)
    else:
        d["statusLine"] = prev
    if d == before and d:
        return                                  # 이미 설치 전 상태 — 다시 쓰지 않는다
    if os.path.exists(ABSENT) and not d:
        os.remove(SETTINGS)
        print("[uninstall] agy settings.json 삭제 (설치 전에는 없던 파일이고 남은 키 없음)")
    else:
        atomic_write(d)
        print("[uninstall] agy settings.json statusLine 키를 설치 전 상태로 복원 (다른 키는 유지)")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"check": check, "apply": apply, "restore": restore}.get(cmd)
    if fn is None:
        print(f"사용법: {sys.argv[0]} check|apply|restore", file=sys.stderr)
        return 2
    try:
        fn()
    except Abort as e:
        print(f"[agy-settings] 오류: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
