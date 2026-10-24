#!/bin/sh
# yd-script-editor 런타임 설치 + 레포별 에디터 서비스 등록. 다시 돌리면 그게 업데이트다(스킬 변경 반영).
#
#   sh setup.sh <레포> [--public]   # 설치·빌드 → 서비스(launchd/systemd) 등록·재시작 → 응답 확인
#   sh setup.sh <레포> status       # 서비스·응답 상태
#   sh setup.sh <레포> remove       # 그 레포의 서비스 내리고 정의 파일 삭제(런타임·콘텐츠는 남긴다)
#
# <레포>/script-editor.json 이 설정이다(name·content·prefix·base·port·public …, SKILL.md 참고).
# 런타임: $SCRIPT_EDITOR_HOME(기본 ~/.local/share/yd-script-editor) — app(+node_modules)·engine·venv·dist/<name>.
# 스킬 폴더에는 아무것도 쓰지 않는다.
set -eu

SKILL=$(cd "$(dirname "$0")/.." && pwd)
RT=${SCRIPT_EDITOR_HOME:-$HOME/.local/share/yd-script-editor}

[ $# -ge 1 ] || { sed -n '2,10p' "$0"; exit 2; }
REPO=$(cd "$1" && pwd)
CONF=$REPO/script-editor.json
[ -f "$CONF" ] || { echo "설정이 없음: $CONF" >&2; exit 1; }
MODE=${2:-install}

conf() {   # conf <파이썬 식(c = 설정 dict)>
    python3 -c "import json,sys; c=json.load(open(sys.argv[1])); v=$1; print('' if v is None else v)" "$CONF"
}
NAME=$(conf "c['name']")
PORT=$(conf "c.get('port', 18750)")
BASE=/$(conf "c.get('base', '/editor').strip('/')")
[ "$BASE" = / ] && BASE=""
echo "$NAME" | grep -Eq '^[a-z0-9][a-z0-9-]*$' || { echo "name 은 영소문자·숫자·- 만: $NAME" >&2; exit 1; }
# 공개 대상: public 은 {ssh, url} 하나 또는 그 배열. 줄마다 "<ssh 호스트> <공개 URL>"
TARGETS=$(python3 - "$CONF" <<'PY'
import json, re, sys
p = json.load(open(sys.argv[1])).get('public') or []
for t in p if isinstance(p, list) else [p]:
    if not t.get('ssh'):
        continue
    if not re.fullmatch(r'[A-Za-z0-9._@-]+', t['ssh']):
        sys.exit(f"public.ssh 는 SSH 호스트 이름만: {t['ssh']}")
    print(t['ssh'], t.get('url') or '')
PY
)
HOSTS=$(printf '%s\n' "$TARGETS" | awk 'NF {print $1}')

OS=$(uname -s)
SERVER=com.$(id -un).script-editor.$NAME
AGENTS=$HOME/Library/LaunchAgents
UNITS=$HOME/.config/systemd/user
LOGS=$HOME/Library/Logs
UID_=$(id -u)

svc_down() {   # svc_down <라벨>
    if [ "$OS" = Darwin ]; then
        launchctl bootout "gui/$UID_/$1" 2>/dev/null || true
        rm -f "$AGENTS/$1.plist"
    else
        systemctl --user disable --now "$1.service" 2>/dev/null || true
        rm -f "$UNITS/$1.service"
    fi
}

check_local() {
    curl -fs -m 2 -o /dev/null "http://127.0.0.1:$PORT$BASE/"
}

check_tunnel() {   # check_tunnel <ssh 호스트>
    ssh -n -o BatchMode=yes "$1" "curl -fs -m 3 -o /dev/null http://127.0.0.1:$PORT$BASE/ -H 'Host: 127.0.0.1:$PORT'" 2>/dev/null
}

tunnel_label() {   # 대상마다 터널 서비스 하나: <SERVER>.tunnel.<ssh 호스트>
    echo "$SERVER.tunnel.$(printf %s "$1" | tr -c 'A-Za-z0-9.-' '-')"
}

tunnels_down() {   # 이 레포의 터널 전부(이전 라벨 <SERVER>.tunnel 포함)
    if [ "$OS" = Darwin ]; then
        labels=$({ ls "$AGENTS" 2>/dev/null | sed -n 's/\.plist$//p'; launchctl list 2>/dev/null | awk '{print $3}'; } |
            grep -F "$SERVER.tunnel" | sort -u || true)
    else
        labels=$(ls "$UNITS" 2>/dev/null | sed -n 's/\.service$//p' | grep -F "$SERVER.tunnel" || true)
    fi
    for l in $labels; do svc_down "$l"; done
}

case $MODE in
remove)
    tunnels_down; svc_down "$SERVER"
    [ "$OS" = Darwin ] || systemctl --user daemon-reload
    echo "내렸어요: $SERVER (+터널)"
    exit 0 ;;
status)
    for l in $SERVER $(for h in $HOSTS; do tunnel_label "$h"; done); do
        if [ "$OS" = Darwin ]; then
            st=$(launchctl print "gui/$UID_/$l" 2>/dev/null | awk '/^\tstate =/ {print $3; exit}')
        else
            st=$(systemctl --user is-active "$l.service" 2>/dev/null || true)
        fi
        echo "$l: ${st:-없음}"
    done
    check_local && echo "로컬: http://127.0.0.1:$PORT$BASE/ 응답" || echo "로컬: 응답 없음"
    for h in $HOSTS; do check_tunnel "$h" && echo "터널: $h 쪽 응답" || echo "터널: $h 쪽 응답 없음"; done
    exit 0 ;;
install|--public) ;;
*) echo "모르는 명령: $MODE" >&2; exit 2 ;;
esac
PUBLIC=no
[ "$MODE" = --public ] && PUBLIC=yes
[ "$PUBLIC" = yes ] && [ -z "$HOSTS" ] && { echo "--public 에는 script-editor.json public.ssh 가 필요" >&2; exit 1; }

NODE=${NODE:-$(command -v node)}
[ -x "$NODE" ] || { echo "node 가 없음(>=22.18)" >&2; exit 1; }
command -v ffmpeg >/dev/null || echo "주의: ffmpeg 가 PATH 에 없음 — 음성·렌더·믹스가 실패한다" >&2

# 1) 런타임 동기화(스킬 → 런타임). node_modules·빌드·venv 는 런타임에만 둔다
mkdir -p "$RT/app" "$RT/engine" "$RT/dist"
rsync -a --delete --exclude node_modules --exclude dist "$SKILL/assets/app/" "$RT/app/"
rsync -a --delete --exclude __pycache__ "$SKILL/assets/engine/" "$RT/engine/"

# 2) 의존성 + 레포별 화면 빌드(base 를 넣어)
cd "$RT/app"
if command -v pnpm >/dev/null; then pnpm install --frozen-lockfile --silent; else npm install --no-audit --no-fund --silent; fi
DIST=$RT/dist/$NAME
./node_modules/.bin/vite build --logLevel warn --base "$BASE/" --outDir "$DIST" --emptyOutDir

# 3) 렌더 엔진 venv(Pillow·numpy). 음성 합성(OmniVoice)은 설정 synth.python 의 별도 venv 를 쓴다
if [ ! -x "$RT/venv/bin/python" ]; then python3 -m venv "$RT/venv"; fi
"$RT/venv/bin/python" -m pip install -q --disable-pip-version-check -r "$RT/engine/requirements.txt"

# 4) 서비스. 포트를 남이 잡고 있으면 멈춘다
pid=$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1 || true)
if [ -n "$pid" ] && ! ps -o command= -p "$pid" | grep -q "$RT/app\|src/server/index.ts"; then
    echo "$PORT 을 다른 프로세스($pid: $(ps -o comm= -p "$pid"))가 쓰고 있음" >&2; exit 1
fi
PATHV=$(dirname "$NODE"):$(dirname "$(command -v ffmpeg 2>/dev/null || echo /usr/bin/x)"):/usr/bin:/bin
AUTOSSH=$(command -v autossh || true)
if [ "$PUBLIC" = yes ] && [ -z "$AUTOSSH" ]; then echo "autossh 가 없음 — 설치 후 다시(brew/apt install autossh)" >&2; exit 1; fi

if [ "$OS" = Darwin ]; then
    mkdir -p "$AGENTS" "$LOGS"
    cat > "$AGENTS/$SERVER.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$SERVER</string>
  <key>ProgramArguments</key>
  <array><string>$NODE</string><string>src/server/index.ts</string></array>
  <key>WorkingDirectory</key><string>$RT/app</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>$PATHV</string>
    <key>SCRIPT_EDITOR_CONFIG</key><string>$CONF</string>
    <key>SCRIPT_EDITOR_DIST</key><string>$DIST</string>
    <key>SCRIPT_EDITOR_ENGINE</key><string>$RT/engine</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOGS/$SERVER.log</string>
  <key>StandardErrorPath</key><string>$LOGS/$SERVER.log</string>
</dict>
</plist>
EOF
    launchctl bootout "gui/$UID_/$SERVER" 2>/dev/null || true
    [ -n "$pid" ] && kill "$pid" 2>/dev/null && sleep 1
    launchctl bootstrap "gui/$UID_" "$AGENTS/$SERVER.plist"
    [ "$PUBLIC" = yes ] && tunnels_down
    for h in $([ "$PUBLIC" = yes ] && echo "$HOSTS"); do
        TUNNEL=$(tunnel_label "$h")
        cat > "$AGENTS/$TUNNEL.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$TUNNEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$AUTOSSH</string><string>-M</string><string>0</string><string>-N</string>
    <string>-o</string><string>ServerAliveInterval=30</string>
    <string>-o</string><string>ServerAliveCountMax=3</string>
    <string>-o</string><string>ExitOnForwardFailure=yes</string>
    <string>-o</string><string>ControlMaster=no</string>
    <string>-o</string><string>ControlPath=none</string>
    <string>-R</string><string>127.0.0.1:$PORT:127.0.0.1:$PORT</string>
    <string>$h</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict><key>HOME</key><string>$HOME</string><key>AUTOSSH_GATETIME</key><string>0</string></dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>$LOGS/$TUNNEL.log</string>
  <key>StandardErrorPath</key><string>$LOGS/$TUNNEL.log</string>
</dict>
</plist>
EOF
        launchctl bootstrap "gui/$UID_" "$AGENTS/$TUNNEL.plist"
    done
    LOGF=$LOGS/$SERVER.log
else
    mkdir -p "$UNITS"
    cat > "$UNITS/$SERVER.service" <<EOF
[Unit]
Description=yd-script-editor $NAME

[Service]
WorkingDirectory=$RT/app
Environment=PATH=$PATHV
Environment=SCRIPT_EDITOR_CONFIG=$CONF
Environment=SCRIPT_EDITOR_DIST=$DIST
Environment=SCRIPT_EDITOR_ENGINE=$RT/engine
ExecStart=$NODE src/server/index.ts
Restart=on-failure

[Install]
WantedBy=default.target
EOF
    [ "$PUBLIC" = yes ] && tunnels_down
    for h in $([ "$PUBLIC" = yes ] && echo "$HOSTS"); do
        cat > "$UNITS/$(tunnel_label "$h").service" <<EOF
[Unit]
Description=yd-script-editor $NAME tunnel to $h
After=$SERVER.service

[Service]
Environment=AUTOSSH_GATETIME=0
ExecStart=$AUTOSSH -M 0 -N -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -R 127.0.0.1:$PORT:127.0.0.1:$PORT $h
Restart=always
RestartSec=30

[Install]
WantedBy=default.target
EOF
    done
    systemctl --user daemon-reload
    [ -n "$pid" ] && kill "$pid" 2>/dev/null && sleep 1
    systemctl --user enable --now "$SERVER.service" >/dev/null
    systemctl --user restart "$SERVER.service"
    for h in $([ "$PUBLIC" = yes ] && echo "$HOSTS"); do
        systemctl --user enable --now "$(tunnel_label "$h").service" >/dev/null
    done
    LOGF="journalctl --user -u $SERVER"
fi

# 5) 확인
i=0
until check_local; do
    i=$((i + 1)); [ $i -ge 20 ] && { echo "에디터가 $PORT 에서 응답하지 않음 — $LOGF" >&2; exit 1; }
    sleep 1
done
echo "에디터: http://127.0.0.1:$PORT$BASE/"
[ "$PUBLIC" = yes ] || exit 0
printf '%s\n' "$TARGETS" | while read -r h url; do
    [ -n "$h" ] || continue
    i=0
    until check_tunnel "$h"; do
        i=$((i + 1)); [ $i -ge 10 ] && { echo "$h 쪽 터널이 안 열림" >&2; exit 1; }
        sleep 3
    done
    echo "터널: $h 127.0.0.1:$PORT → 127.0.0.1:$PORT"
    [ -n "$url" ] && echo "공개: $url (원격 리버스 프록시가 $BASE/ 를 이 포트로 넘겨야 함)"
done
