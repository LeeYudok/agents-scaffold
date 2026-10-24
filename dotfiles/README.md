# dotfiles

zsh + starship 셸 환경과 Claude Code·Antigravity CLI statusline, Codex CLI status line 을 새 머신에 한 번에 맞추는 부트스트랩 저장소. macOS(Homebrew)와 Linux(dnf/apt), Windows(WSL2) 를 같은 `install.sh` 로 설치하고, `uninstall.sh` 로 설치 전 상태까지 되돌린다. Android 는 Termux 에 Debian 을 올려 같은 `install.sh` 를 쓴다 — [Android (Termux + proot-distro)](#android-termux--proot-distro). WSL2 를 쓸 수 없는 폐쇄망 Windows 는 `windows/install-git.cmd` 로 Git 을 오프라인 설치하고 Git Bash 환경을 맞춘다 — [Windows 폐쇄망 (Git Bash)](#windows-폐쇄망-git-bash).

어느 머신에나 그대로 적용할 수 있는 설정만 추적한다. 호스트 alias·내부 URL·API 키·개인 에이전트 지침처럼 머신이나 사람에 묶인 것은 저장소 밖(`~/.zshrc.local`, `~/.secrets.zsh`)에 둔다 — 자세한 경계는 [추적 범위](#추적-범위) 참고. 에이전트·기여자용 상세 규칙은 [AGENTS.md](AGENTS.md).

## 구성

```
dotfiles/
├── install.sh                 # 부트스트랩 스크립트 (멱등)
├── uninstall.sh               # install.sh 적용 전 상태로 복원 (--purge 로 패키지까지)
├── AGENTS.md                  # 프로젝트 개요·불변 규칙·검증 방법 (AI 에이전트/기여자용)
├── AGENTS.yaml                # AGENTS.md 의 기계 판독용 짝 — 구성요소 그래프·명령·정책·함정
├── .gitignore                 # 머신별·시크릿 파일명, 반입용 설치 파일(windows/offline/) 차단
├── .gitattributes             # 줄바꿈 고정 — 기본 LF, .ps1/.cmd 는 CRLF 그대로
├── .github/
│   └── workflows/check.yml    # PR·main push 에서 식별자·문법 검사 (CI)
├── starship/
│   └── starship.toml          # Catppuccin Mocha 팔레트 2줄 프롬프트, Nerd Font 글리프 (OS 공통)
├── eza/
│   └── theme.yml              # eza 아이콘 덮어쓰기 — Nerd Font v2 폰트에서도 깨지지 않게
├── zsh/
│   ├── zshrc.macos            # macOS 용 — brew 기반(Apple Silicon/Intel 자동), eza/bat/zoxide/fzf/pyenv/pnpm/플러그인
│   ├── zshrc.linux            # Linux 서버용 — 같은 구조의 미니멀판, 도구는 있을 때만 활성
│   └── zshrc.local.example    # 머신별 alias/함수 템플릿(placeholder) → ~/.zshrc.local (미추적) 로 복사해 사용
├── claude/
│   └── statusline-command.sh  # Claude Code 하단 statusline 2줄 (경로·git·모델·컨텍스트 / 비용·캐시·한도·버전)
├── gitbash/
│   ├── bashrc                 # Git Bash 용 ~/.bashrc — UTF-8·한글 경로·히스토리·alias, starship/zoxide 는 있을 때만
│   └── bash_profile           # Git Bash 로그인 셸이 ~/.bashrc 를 읽게 하는 ~/.bash_profile
├── windows/
│   ├── install-git.ps1        # 폐쇄망 Windows — Git for Windows 오프라인 설치 + Git Bash 환경 (멱등)
│   ├── install-git.cmd        # cmd 에서 위 스크립트 실행 (ExecutionPolicy Bypass)
│   ├── uninstall-git.ps1      # install-git.ps1 의 역연산 (-Purge 로 설치한 Git 까지)
│   └── uninstall-git.cmd      # cmd 에서 위 스크립트 실행
├── agy/
│   ├── statusline-command.sh  # Antigravity CLI(agy) 하단 statusline 2줄 (경로·git·모델·컨텍스트 / Gemini·3P 한도·작업·버전)
│   └── settings.py            # ~/.gemini/antigravity-cli/settings.json 의 statusLine 키만 merge/복원
├── codex/
│   ├── status-line.py         # Codex CLI status line — config.toml 의 [tui] status_line 키만 merge/복원
│   ├── cost-hook.py           # Codex Stop 훅 — 턴마다 API 환산 비용 한 줄 표시 → ~/.codex/cost-hook.py
│   └── hooks.py               # hooks.json 의 Stop 에 위 훅 항목 하나만 merge/제거
└── scripts/
    ├── check-identifiers.sh       # 공개 전 식별자 검사 — Git 인덱스 대상, 검출 시 파일명만 출력하고 실패
    ├── check-syntax.sh            # bash·zsh 파일별 문법 검사 + Python 컴파일 검사
    ├── check-agents-yaml.sh       # AGENTS.yaml 검증 — 구조·따옴표 없는 날짜·그래프·경로 (PyYAML 필요)
    ├── test-install-safety.sh     # 설치·제거 안전성 — 모의 apt/dnf/sudo 로 반복 제거·기록·purge·플러그인 폴백 (임시 HOME)
    ├── test-codex-status-line.sh  # codex/status-line.py 왕복 시험 (임시 HOME)
    ├── test-codex-cost-hook.sh    # cost-hook.py 금액 계산 + hooks.py 왕복 시험 (임시 HOME)
    ├── test-agy-statusline.sh     # agy/settings.py 왕복 + statusline 렌더 시험 (임시 HOME)
    ├── test-windows-paths.sh      # Git Bash 거부·WSL 폰트 건너뛰기 시험 (임시 HOME)
    └── test-windows-git.sh        # windows/·gitbash/ 정적 시험 (인코딩·줄바꿈·문법)
```

## 설치

```bash
git clone https://github.com/LeeYudok/dotfiles.git
cd dotfiles && ./install.sh
```

`install.sh` 동작 (스크립트 내 섹션 번호와 동일):

| # | 단계 | 내용 |
|---|---|---|
| 0 | 의존성 검사 | Git Bash/MSYS/Cygwin 이면 "WSL2 에서 실행" 안내와 함께 중단. `curl`·`unzip`·`python3`, macOS 는 `brew`, Linux 는 `dnf`+`rpm` 또는 `apt-get`+`dpkg-query` 가 없으면 **홈 파일을 하나도 만들지 않고** 종료. `~/.claude/settings.json`·`~/.gemini/antigravity-cli/settings.json` 이 깨진 JSON 또는 객체가 아닌 JSON이거나 `~/.codex/config.toml`·`~/.codex/hooks.json` 을 편집할 수 없는 상태(깨진 TOML·JSON, 예상 밖 구조 등)여도 여기서 중단. |
| 1 | 패키지 설치 | macOS: brew 로 `starship eza bat zoxide fzf fd jq zsh-autosuggestions zsh-syntax-highlighting` (없을 때만). Linux: `zsh`(dnf/apt), `starship`(공식 스크립트, sudo 없으면 `~/.local/bin`), 자동완성 플러그인 2종(패키지별 설치 여부 확인, dnf 는 필요 시 EPEL 활성화 후. sudo 를 비밀번호 없이 쓸 수 없거나 패키지 설치에 실패하면 GitHub 태그 tarball → `~/.local/share/zsh/plugins`), `jq`(sudo 가능할 때만, 아니면 경고), `zoxide`·`fzf`·`eza`(GitHub 최신 릴리스 바이너리 → `~/.local/bin`, sudo 불필요, x86_64/aarch64). |
| 2 | starship.toml · eza 테마 | `starship/starship.toml` → `~/.config/starship.toml`, `eza/theme.yml` → `~/.config/eza/theme.yml`(v3 전용 eza 아이콘을 v2·v3 공통 글리프로 덮어씀) |
| 2.5 | Nerd Fonts | GitHub 최신 릴리스에서 `JetBrainsMono`, `D2Coding` zip 을 받아 `.ttf`/`.otf` 를 폰트 디렉터리(macOS `~/Library/Fonts`, Linux `~/.local/share/fonts` + `fc-cache`)에 설치. 폰트별 `.nerd-font-<name>-installed` 마커 파일로 재설치 방지. **WSL 에서는 건너뛰고 안내만** 한다 — [Windows (WSL2)](#windows-wsl2) 참고. |
| 3 | zshrc | OS 에 맞는 `zsh/zshrc.*` → `~/.zshrc`. 머신별 alias/함수는 `~/.zshrc.local`(미추적) 에 두며 스크립트가 만들지 않는다 — 없으면 안내만. |
| 4 | Claude statusline | `claude/statusline-command.sh` → `~/.claude/statusline-command.sh` (+x). 스크립트 런타임에 `jq` 필요 — 없으면 경고만. 이어서 **python3** 로 `~/.claude/settings.json` 의 `statusLine` 키만 merge (다른 키 불변, 파일 없으면 생성). 같은 디렉터리의 임시 파일에 쓰고 `os.replace` 로 교체하므로 중단돼도 원본이 깨지지 않고, 기존 파일 mode 를 보존한다. |
| 5 | Codex status line | Codex 를 쓰는 머신(`codex` 명령 또는 `~/.codex` 존재)에서만. `codex/status-line.py apply` 로 `~/.codex/config.toml` 의 `[tui]` `status_line` 키만 merge (다른 테이블·키·주석 불변, 파일 없으면 생성). 비용 훅 `codex/cost-hook.py` 를 `~/.codex/cost-hook.py` 로 배치하고 `codex/hooks.py apply` 로 `~/.codex/hooks.json` 의 `Stop` 에 그 항목 하나만 추가한다(다른 훅 불변). 원자적 쓰기와 mode 보존은 4 단계와 같다. `hooks.json` 이 깨진 JSON 이면 0 단계에서 중단. |
| 6 | Antigravity statusline | Antigravity CLI 를 쓰는 머신(`agy` 명령 또는 `~/.gemini/antigravity-cli` 존재)에서만. `agy/statusline-command.sh` → `~/.gemini/antigravity-cli/statusline-command.sh` (+x) 배치 후 `agy/settings.py apply` 로 `settings.json` 의 `statusLine` 키만 merge (다른 키 불변, 사용자가 둔 `padding`·`stack_with_default` 도 유지). 원자적 쓰기와 mode 보존은 4 단계와 같다. |
| 7 | 기본 셸 | `$SHELL` 이 zsh 가 아니면 `chsh -s <zsh 경로>` 안내만 (자동 변경 안 함). |

런타임 의존성: `curl`, `unzip`, `python3`(0 단계에서 검사). macOS 는 Homebrew, Linux 는 패키지 조회용 `rpm` 또는 `dpkg-query`도 필요하다. Windows 는 WSL2 안에서 실행한다. `jq` 는 statusline 스크립트(Claude·Antigravity) 런타임 전용이라 1 단계에서 자동 설치한다(Linux 는 sudo 가능할 때만).

Linux 에서 sudo 권한이 없으면 **zsh 만 미리 설치돼 있으면 된다.** 나머지는 사용자 영역(`~/.local/bin`, `~/.local/share/zsh/plugins`)에 설치하거나 경고만 하고 넘어간다(jq 가 없으면 statusline 만 동작하지 않는다).

멱등(idempotent): 재실행해도 안전하다. 배치 대상 파일(`starship.toml`·`eza/theme.yml`·`.zshrc`·`statusline-command.sh`(Claude·Antigravity)·`~/.codex/cost-hook.py`)은 기존 파일과 내용이 다를 때만 `.bak` 백업 후 덮어쓴다 — `.bak` 은 1세대만 유지되므로 두 번 연속 다른 내용을 배치하면 첫 백업은 사라진다.

최초 실행 시 덮어쓸 파일의 원본과 설치 기록을 `~/.config/dotfiles/backup/` 에 남긴다(`<name>.orig` / `<name>.absent`, `brew-installed.txt`·`pkg-installed.txt`·`bin-installed.txt`, `settings.json.orig`, `codex-config.toml.orig`, `codex-hooks.json.absent`/`.present`, `agy-settings.json.orig`/`.absent`). 재실행해도 이 기록은 갱신하지 않으므로 몇 번을 돌려도 "설치 전 원본"이 보존된다. Nerd Font 는 설치한 파일명을 `.nerd-font-<name>-files.txt` manifest 로 남긴다.

`~/.claude/settings.json` 전체는 이 저장소에 두지 않는다 — permissions/hooks/model 등 머신별·보안 민감 설정 포함. statusline 스크립트와 해당 키 merge 만 관리.

## Windows (WSL2)

Windows 에서는 **WSL2 안에서** 설치한다. Git Bash(Git for Windows)·MSYS2·Cygwin 은 지원하지 않는다 — zsh 와 패키지 매니저가 없어 zshrc·플러그인·`--purge` 역연산이 성립하지 않는다. 그 환경에서 `install.sh` 를 돌리면 0 단계에서 안내와 함께 중단하고 홈은 건드리지 않는다.

```powershell
wsl --install            # PowerShell(관리자). 기본 배포판 Ubuntu 설치 후 재부팅
```

```bash
# WSL 셸 안에서
sudo apt-get update && sudo apt-get install -y git curl unzip python3
git clone https://github.com/LeeYudok/dotfiles.git
cd dotfiles && ./install.sh
chsh -s "$(command -v zsh)"
```

`install.sh` 는 커널 버전 문자열(`/proc/version`)의 `microsoft` 로 WSL 을 감지해 **2.5 단계(Nerd Fonts)를 건너뛴다.** 글리프를 그리는 것은 Windows 쪽 터미널이라 WSL 안에 폰트를 설치해도 효과가 없기 때문이다. 폰트는 Windows 에 직접 설치한다.

1. [Nerd Fonts 릴리스](https://github.com/ryanoasis/nerd-fonts/releases/latest)에서 `JetBrainsMono.zip`(한글 글리프가 필요하면 `D2Coding.zip`)을 받아 압축을 풀고, `.ttf` 를 선택해 우클릭 → 설치.
2. Windows Terminal → 설정 → 해당 WSL 프로필 → 모양 → 글꼴에서 `JetBrainsMono Nerd Font` 를 지정. VS Code 통합 터미널은 `terminal.integrated.fontFamily` 에 같은 이름을 넣는다.

Windows 사용자 프로필은 WSL 의 `$HOME` 밖이라 스크립트가 자동으로 설치하지 않는다(되돌리기와 임시 `HOME` 시험이 성립하지 않는다). 나머지 단계(zshrc·starship·Claude statusline·Codex status line)는 일반 Linux 와 같고, Claude Code·Codex 도 WSL 안에 설치해 쓴다. `uninstall.sh` 는 WSL 에서도 그대로 동작한다 — 폰트는 마커·manifest 가 없으므로 건드릴 것이 없다.

## Android (Termux + proot-distro)

Android 에서는 **Termux 에 proot-distro 로 Debian 을 설치하고 그 안에서** `install.sh` 를 실행한다. Termux 기본 셸은 `sudo`(root)가 없고 패키지가 표준 경로(`/usr`) 대신 Termux 전용 prefix 에 깔려 `install.sh` 의 전제와 맞지 않으므로 직접 실행하지 않는다.

```bash
# Termux 기본 세션에서
pkg install proot-distro
proot-distro install debian
proot-distro login debian

# Debian 안에서 — install.sh 가 sudo 로 패키지를 설치하므로 sudo 도 넣는다
apt-get update && apt-get install -y sudo git curl unzip python3
git clone https://github.com/LeeYudok/dotfiles.git
cd dotfiles && ./install.sh
```

이후 과정은 일반 Linux(apt) 와 같다. 다만 2.5 단계가 설치하는 `~/.local/share/fonts` 는 proot 안쪽 폰트 디렉터리라 **화면에는 반영되지 않는다.** 글리프를 그리는 것은 Termux 앱이고, Termux 는 자기 홈의 `~/.termux/font.ttf` 한 파일만 읽는다. 이 파일이 없으면 Android 기본 폰트로 그려 프롬프트·statusline 아이콘이 네모로 깨진다.

proot 안에서 다음을 실행해 Nerd Font 하나를 Termux 폰트로 지정한다. 한글 폭을 맞추려면 D2Coding 의 Mono 변형을 권한다.

```bash
# proot 안에서 — Termux 홈은 proot-distro 가 기본으로 bind 한다
T=/data/data/com.termux/files/home/.termux
mkdir -p "$T"
cp ~/.local/share/fonts/D2KodingLigatureNerdFontMono-Regular.ttf "$T/font.ttf"
```

적용은 **proot 밖**에서 한다. Termux 기본 세션에서 `termux-reload-settings` 를 실행하거나 앱을 완전히 종료했다 다시 연다(proot 안에서는 `am` 이 없어 실패한다). `printf '\ue0a0 \uf07c \ue725\n'` 이 아이콘으로 보이면 된다.

- Termux 가 아닌 SSH 앱(JuiceSSH, Termius 등)으로 접속한다면 그 앱의 글꼴 설정에서 Nerd Font 를 지정한다.
- `~/.termux` 는 proot 의 `$HOME` 밖이라 스크립트가 자동으로 만들지 않고, `uninstall.sh` 도 건드리지 않는다. 되돌리려면 `font.ttf` 를 직접 지운다.

## Windows 폐쇄망 (Git Bash)

인터넷과 WSL2 를 쓸 수 없는 Windows(사내 폐쇄망 등)에서는 zsh 환경 대신 **Git for Windows 와 Git Bash** 만 맞춘다. `install.sh` 는 쓰지 않고 `windows/` 의 PowerShell 스크립트를 PowerShell 또는 cmd 에서 실행한다. 관리자 권한이 없어도 된다.

### 반입할 것

인터넷이 되는 PC 에서 둘을 받아 USB 등으로 옮긴다.

1. 이 저장소 — GitHub 의 Code → Download ZIP (폐쇄망 PC 에는 아직 git 이 없다). 압축을 푼다.
2. Git for Windows 64비트 설치 파일 하나 — [git-scm.com/downloads/win](https://git-scm.com/downloads/win) 또는 [릴리스 페이지](https://github.com/git-for-windows/git/releases/latest).
   - `Git-<버전>-64-bit.exe` (설치형, 권장) — 시작 메뉴·탐색기 "Git Bash Here"·앱 제거 목록까지 갖춰진다.
   - `PortableGit-<버전>-64-bit.7z.exe` (포터블) — 압축만 풀므로 소프트웨어 설치가 막힌 PC 에서 쓴다.
   - 릴리스 페이지의 SHA-256 값도 적어 둔다(스크립트가 출력하는 값과 대조).

받은 설치 파일은 압축을 푼 저장소의 `windows\offline\` 에 둔다(없으면 만든다. `.gitignore` 대상). 다른 곳에 두면 `-Installer` 로 지정한다.

### 실행

```bat
:: cmd
cd <압축을 푼 경로>\dotfiles
windows\install-git.cmd
```

```powershell
# PowerShell
cd <압축을 푼 경로>\dotfiles
powershell -ExecutionPolicy Bypass -File windows\install-git.ps1
# 옵션: -Installer <경로>  -Scope Machine(관리자, 모든 사용자)  -PortableDir <경로>  -SkipBashrc
```

`install-git.ps1` 동작 (스크립트 내 섹션 번호와 동일):

| # | 단계 | 내용 |
|---|---|---|
| 0 | 사전 검사 | 설치 파일을 `-Installer` → `windows\offline\` → `windows\` → `~\Downloads` 순으로 찾는다(설치형 우선, 높은 버전 우선). Authenticode 서명이 없거나 내용이 서명과 다르면 중단, 그 밖의 상태(폐쇄망이라 폐기 목록 확인 불가 등)는 경고하고 SHA-256 을 출력한다. `-Scope Machine` 인데 관리자가 아니거나 포터블 경로가 비어 있지 않아도 중단. 여기서 멈추면 **아무것도 바꾸지 않는다.** |
| 1 | Git 설치 | Git 이 이미 있으면(레지스트리·포터블 경로·PATH) 건너뛴다. 설치형은 `/VERYSILENT /CURRENTUSER`(관리자 불필요, `%LOCALAPPDATA%\Programs\Git`) 무인 설치 — `PathOption=Cmd`(git 만 PATH 에), `CURLOption=WinSSL`(Windows 인증서 저장소 사용 → 사내 CA 로 서명된 내부 Git 서버 접속). 포터블은 `%LOCALAPPDATA%\Programs\PortableGit` 에 압축을 풀고 `post-install.bat` 을 돌린다. |
| 2 | PATH | `<Git>\cmd` 가 사용자·시스템 PATH 어디에도 없을 때만(포터블 등) 사용자 PATH 에 추가. 새로 여는 cmd/PowerShell 창부터 `git` 이 잡힌다. |
| 3 | Git Bash 실행 경로 | Windows Terminal 이 있으면 fragment(`%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\dotfiles-gitbash\`)로 'Git Bash' 프로필을 추가(`settings.json` 은 건드리지 않는다). 포터블은 시작 메뉴 바로가기 `Git Bash (Portable)` 를 만든다. |
| 4 | bashrc | `gitbash/bashrc` → `~/.bashrc`, `gitbash/bash_profile` → `~/.bash_profile` (내용이 다를 때만 `.bak` 백업 후, 최초 원본은 `~/.config/dotfiles/backup/gitbash-*.orig`/`.absent`). |
| 5 | 확인 | `git --version` 과 Git Bash 로 `~/.bashrc` 문법 검사. |

설치 후 Git Bash 는 시작 메뉴 **Git Bash**, Windows Terminal 의 **Git Bash** 프로필, 탐색기 우클릭 **Open Git Bash here**(설치형) 중 하나로 연다. cmd/PowerShell 에서는 새 창부터 `git` 을 쓸 수 있다.

`~/.bashrc` 는 한글이 깨지지 않게 UTF-8 로케일을 쓰고, `git status` 등이 한글 경로를 `\355\225\234` 처럼 이스케이프하지 않게 `core.quotepath=false` 를 **환경변수로 이 셸에서만** 적용한다(`~/.gitconfig` 는 건드리지 않는다). 히스토리·alias(`ll`, `gs`, `gl`, `open` 등)를 두고, `starship`·`zoxide` 는 설치돼 있을 때만 켠다 — 없으면 Git Bash 기본 프롬프트(브랜치 표시)를 쓴다. 머신별 alias·시크릿은 `~/.bashrc.local`(미추적, 스크립트가 만들지 않음)에 둔다.

주의:

- 그룹 정책이 PowerShell 실행 정책을 `MachinePolicy` 로 고정하면 `-ExecutionPolicy Bypass` 도 무시된다. 그때는 설치 파일을 직접 실행해 Git 을 깔고, `-Installer` 없이 스크립트를 다시 돌리면 1 단계를 건너뛰고 Git Bash 환경만 맞춘다(스크립트 실행 자체가 막히면 `gitbash/bashrc`·`bash_profile` 을 홈에 직접 복사).
- 설치형이 사용자 단위 설치 중에도 UAC(관리자) 창을 띄우거나 실패하면(PC 정책에 따라 다르다) `PortableGit-<버전>-64-bit.7z.exe` 를 대신 반입해 같은 명령을 돌린다 — 압축 해제뿐이라 권한이 필요 없다.
- Git 을 새 버전으로 올리려면 새 `Git-<버전>-64-bit.exe` 를 직접 실행한다(설치형은 제자리 업그레이드). 스크립트는 Git 이 이미 있으면 설치를 건너뛴다.
- 저장소 `.gitattributes` 가 `.ps1`/`.cmd` 는 CRLF 그대로, 나머지는 LF 로 고정한다. `gitbash/bashrc` 가 CRLF 로 바뀌면 bash 가 읽지 못하므로 편집기에서 줄바꿈을 바꾸지 않는다.
- zsh·starship·Claude/Codex statusline 은 이 경로에 포함되지 않는다. 폐쇄망에서도 WSL2 를 쓸 수 있으면 [Windows (WSL2)](#windows-wsl2) 를 따른다.

되돌리기:

```bat
windows\uninstall-git.cmd            :: ~/.bashrc·~/.bash_profile 복원, 프로필·바로가기·추가한 PATH 제거
windows\uninstall-git.cmd -Purge     :: 위에 더해 install-git 이 새로 설치한 Git 까지 제거 (원래 있던 Git 은 유지)
windows\uninstall-git.cmd -KeepBackup
```

## 되돌리기 (uninstall.sh)

```bash
./uninstall.sh            # 배치 파일 복원/제거 + settings.json statusLine(Claude·Antigravity)·Codex status_line 키 복원·비용 훅 제거 + Nerd Font 제거
./uninstall.sh --purge    # 위에 더해 install.sh 가 새로 설치한 brew/dnf/apt 패키지·starship 등 바이너리·tarball 플러그인 제거
./uninstall.sh --keep-backup   # ~/.config/dotfiles/backup 을 남김 (기본은 복원 후 삭제)
```

- 복원 우선순위: `~/.config/dotfiles/backup/<name>.orig` 가 있으면 그 내용으로, `.absent` 면 삭제, 둘 다 없으면 대상 파일과 `.bak` 을 그대로 둔다. 따라서 제거를 다시 실행해도 복원된 원본은 유지된다. 설치 기록이 없는 구버전 배치는 `.bak` 내용을 직접 확인해 수동 복원한다.
- 설치 기록이 없는 Claude 설정과 Codex 훅은 그대로 둔다.
- `settings.json` 은 `statusLine` 키만 설치 전 값으로 되돌리고 다른 키(permissions/hooks/model 등)는 그대로 둔다. 설치 전에 파일이 없었고 남는 키도 없으면 파일 자체를 지운다. 쓰기는 install 과 같은 원자적 교체이며, 깨진 JSON 이면 손대지 않고 중단한다.
- `~/.codex/config.toml` 도 `[tui]` 의 `status_line` 키만 설치 전 값으로 되돌린다. 설치 전에 키가 없었으면 키를 지우고, 그 결과 설치가 만든 `[tui]` 테이블이나 파일이 비면 같이 지운다. 설치가 Codex 단계를 건너뛴 머신에서는 아무것도 하지 않는다.
- `~/.codex/hooks.json` 은 다른 도구도 자기 훅을 넣고 빼는 공유 파일이라 원본으로 통째 되돌리지 않고, 비용 훅 항목(`~/.codex/cost-hook.py` 를 가리키는 것)만 뺀다. 설치 전에 파일이 없었고 남는 훅도 없으면 파일을 지운다. `~/.codex/cost-hook.py` 는 다른 배치 파일과 같은 규칙으로 복원/삭제한다.
- `~/.gemini/antigravity-cli/settings.json` 도 `statusLine` 키만 설치 전 값으로 되돌린다(설치 전에 없던 파일이고 남는 키가 없으면 파일 삭제). 스크립트는 다른 배치 파일과 같은 규칙으로 복원/삭제하고, 비게 된 `~/.gemini/antigravity-cli`·`~/.gemini` 는 지운다. 설치가 agy 단계를 건너뛴 머신에서는 아무것도 하지 않는다.
- `~/.zshrc.local`, `~/.secrets.zsh`, `~/.claude/CLAUDE.md` 는 사용자 파일이므로 건드리지 않는다.
- 폰트는 manifest 에 적힌 파일만 지운다. manifest 없이 설치된 옛 머신은 마커만 지우고 경고를 낸다.
- `--purge` 는 `install.sh` 가 **새로 설치했다고 기록한 것만** 제거한다. 이미 깔려 있던 starship/eza 등은 건드리지 않는다. Linux 플러그인과 EPEL도 새로 설치에 성공한 패키지만 기록한다. sudo 없이 tarball 로 받은 플러그인은 `~/.local/share/zsh/plugins` 아래 기록된 디렉터리만 지운다.
- 끝나면 `~/.zshrc` 가 원본(또는 없음)으로 돌아가 zsh 기본 프롬프트로 동작한다. 기본 셸 자체는 `chsh` 로 직접 되돌린다.
- 설치·제거 안전성 회귀 검사는 `scripts/test-install-safety.sh`로 실행한다. 임시 HOME과 모의 apt/dnf/sudo를 사용하므로 실제 패키지 설치나 다운로드가 없다.
- 실제 홈에 영향 없이 시험하려면 `HOME=$(mktemp -d) ./install.sh && HOME=<같은 경로> ./uninstall.sh`.

## 프롬프트 (starship.toml)

starship 1.26 기준. `[palettes.catppuccin_mocha]` 로 색을 이름으로 참조하고, 심볼은 전부 Nerd Font 글리프(이모지 없음).

- 2줄: `╭─ OS아이콘 user @host dir git브랜치 [git상태] +추가 -삭제 via 언어버전 took 실행시간 백그라운드작업수` / `╰─ 종료코드 ❯`
- 오른쪽 프롬프트(`right_format`)에 현재 시각 `HH:MM:SS`
- hostname 은 SSH 접속일 때만 (`ssh_only`), username 은 root 등 비기본 사용자일 때만
- git: branch(원격 추적 브랜치 포함)·status·state(rebase/merge 진행률)·`git_metrics`(라인 증감)
- 언어/런타임은 해당 프로젝트 파일이 있을 때만: rust/python(pyenv·venv)/node/bun/java/go, docker context 는 compose 파일 있을 때만. kubernetes 모듈은 기본 비활성.
- `directory.substitutions` 로 `~/workspace` → `ws` 축약
- 터미널 폰트를 JetBrainsMono Nerd Font(또는 D2Coding Nerd Font)로 지정해야 글리프가 깨지지 않는다 (2.5 단계에서 설치). WSL·Termux 처럼 터미널이 다른 곳에 있으면 그쪽에 지정한다 — [Windows (WSL2)](#windows-wsl2), [Android (Termux + proot-distro)](#android-termux--proot-distro). Linux 서버의 starship 1.22 에서도 동작(palettes 는 1.9+, os 모듈 1.16+).
- 글리프는 Nerd Font v2·v3 공통 BMP 영역(U+E000~F8FF)만 쓴다. v3 에서 추가된 5자리 코드(U+F0000~)는 Termius 처럼 v2 계열 폰트를 내장한 터미널에서 □로 깨지기 때문이다. eza 도 기본 아이콘 일부가 v3 전용이라 `eza/theme.yml` 로 덮어쓴다(색상 출력일 때 적용 — `ls`/`ll`/`la` alias 는 기본으로 색상을 쓴다). 새 아이콘을 넣을 때 확인: `python3 -c "import sys;print([hex(ord(c)) for c in open(sys.argv[1]).read() if ord(c)>=0xF0000])" starship/starship.toml` 결과가 `[]` 여야 한다.

## zsh (zshrc.macos / zshrc.linux)

두 파일은 같은 섹션 순서를 따른다: 환경·PATH → 히스토리·옵션 → 자동완성 → 툴 초기화 → alias/함수 → 시크릿(`~/.secrets.zsh`) → 머신별(`~/.zshrc.local`) → 플러그인(맨 끝, `zsh-syntax-highlighting` 이 마지막).

- PATH 는 `typeset -U path` 로 중복 자동 제거. macOS 판은 `HOMEBREW_PREFIX` 를 자동 감지(Apple Silicon `/opt/homebrew`, Intel `/usr/local`, `brew shellenv` 가 이미 설정했으면 그 값)하고, rustup·JAVA_HOME(openjdk@21)·pnpm·Antigravity 등은 **디렉터리가 있을 때만** PATH 에 넣는다. starship/zoxide/fzf/eza/bat/플러그인도 없으면 조용히 건너뛴다.
- 머신별 항목(SSH 호스트 alias, 컨테이너 접속 alias, 프로젝트 전용 함수·경로 등)은 `~/.zshrc.local`(미추적) 에 두고 두 zshrc 가 플러그인 직전에 `source` 한다. 새 머신은 `cp zsh/zshrc.local.example ~/.zshrc.local` 후 필요한 예시만 주석을 풀어 그 머신 값으로 채운다.
- `claude --yolo`, `agy --yolo` → `--dangerously-skip-permissions`(권한 확인 없이 Claude Code·Antigravity CLI 실행). 각 명령을 감싸는 셸 함수가 `--yolo` 인자만 바꿔 넘기며, 해당 명령이 PATH 에 있을 때만 정의한다.
- 개인 설정을 빼고 Claude Code 를 실행해 문제를 가려낼 때(바닐라 실행)는 아래 둘 중 하나를 쓴다. 래퍼 함수까지 건너뛰려면 `command claude` 로 부른다. Claude Code 2.1.293 기준이며, 자세한 로딩 규칙은 [공식 문서](https://code.claude.com/docs/en/memory)에 있다.

  ```bash
  # hooks·플러그인·CLAUDE.md·auto memory·MCP 를 모두 끈다. 인증은 ANTHROPIC_API_KEY 만 받는다(구독 로그인 불가).
  command claude --bare --strict-mcp-config

  # 구독 로그인을 유지한 채 유저 설정·MCP·스킬·~/.claude/CLAUDE.md·auto memory 를 뺀다. 프로젝트 설정과 프로젝트 CLAUDE.md 는 남는다.
  command claude --setting-sources project --strict-mcp-config --disable-slash-commands \
    --settings '{"claudeMdExcludes":["'"$HOME"'/.claude/CLAUDE.md"],"autoMemoryEnabled":false}'
  ```
- 히스토리: 세션 간 공유, 중복 제거, 앞에 공백 붙인 명령은 기록 안 함(시크릿 입력용). ↑/↓ 는 입력한 접두어로 필터.
- compinit 은 하루 한 번만 전체 스캔(`.zcompdump` 캐시)해 기동 시간을 줄인다.
- fzf: `Ctrl-R` 히스토리, `Ctrl-T` 파일, `Alt-C` 디렉터리. `fd` 있으면 파일 탐색 소스로 사용.
- zoxide 가 `cd` 를 대체(`cd <키워드>` 로 점프).
- 시크릿(API 키 등)은 `~/.secrets.zsh`(mode 600, 미추적)에만 두고 zshrc 는 `source` 만 한다. zshrc 에 값을 직접 쓰지 않는다.
- Linux 판은 starship/eza/zoxide/fzf 가 없으면 각각 기본 프롬프트·`ls --color`·일반 `cd` 로 폴백.
- Linux 판은 로케일이 UTF-8 이 아니면(`LANG` 이 비어 `POSIX` 인 컨테이너·Termux proot 등) 설치된 로케일 중 `ko_KR.UTF-8` → `C.UTF-8` → `en_US.UTF-8` 순으로 골라 `LANG` 을 맞춘다. 그대로 두면 zsh 가 한글을 바이트 단위로 세어 입력·삭제 때 커서가 밀린다. 이미 UTF-8 이면 건드리지 않는다.

## Claude Code statusline

`claude/statusline-command.sh` 는 stdin 으로 받은 Claude Code statusLine JSON 을 파싱해 **두 줄**로 출력한다. 런타임에 `jq` 가 필요하다.

| 줄 | 내용 |
|---|---|
| 1행 | 경로 · git 브랜치/dirty · 모델명(추론 강도 · thinking · fast) · 컨텍스트 사용률 바와 입력/창 크기 · 출력 토큰 |
| 2행 | 세션 비용 · 소요 시간(전체·API) · 변경 라인 수 · 프롬프트 캐시 적중률 · 5시간/주간 사용 한도와 리셋 시각 · 출력 스타일 · CLI 버전 |

```
dotfiles │ git: main │ Opus 5 (1M context) medium think │ █░░░░░░░░░ 10% (98k/1000k) ↑3
$1.51 5m(api 1m) │ cache 95% │ 5h 16%~12:00  7d 48%~05:00 │ Proactive │ v2.1.278
```

렌더 빈도가 높으므로 `jq` 는 한 번만 호출해 모든 필드를 US(0x1f) 구분자로 받는다(탭은 IFS 공백류라 빈 필드가 합쳐져 값이 밀린다). payload 에 없는 필드는 그 구간을 통째로 생략하므로, 해당 키를 주지 않는 CLI 버전에서도 나머지는 그대로 나온다. 컨텍스트는 60%/80% 에서 색이 바뀌고 `exceeds_200k_tokens` 가 참이면 경고색과 `>200k` 표시가 붙는다.

`install.sh` 는 스크립트를 배치하고 `~/.claude/settings.json` 의 `statusLine` 키 하나만 merge 한다. `settings.json` 전체와 `~/.claude/CLAUDE.md` 같은 개인 지침은 이 저장소가 관리하지 않는다.

## Antigravity CLI statusline

Antigravity CLI(`agy`)는 Claude Code 와 같은 방식이다 — 에이전트 상태가 바뀔 때마다 `settings.json` 의 `statusLine.command` 를 실행해 상태 JSON 을 stdin 으로 넘기고, stdout 을 프롬프트 아래에 그린다. `agy/statusline-command.sh` 는 Claude statusline 과 같은 모양·색으로 **두 줄**을 출력한다. 런타임에 `jq` 가 필요하다.

| 줄 | 내용 |
|---|---|
| 1행 | 경로 · git 브랜치/dirty(payload 의 `vcs`, 없으면 git 으로 확인) · 모델명 · 에이전트 상태(`idle` 은 생략) · 컨텍스트 사용률 바와 입력/창 크기 · 출력 토큰 |
| 2행 | Gemini 모델 5시간/주간 사용률과 리셋까지 남은 시간(`G`) · 타사 모델 한도(`3P`) · 작업·산출물·서브에이전트 수 · sandbox(+net) · vim 모드 · CLI 버전 |

```
proj │ git: main * │ Gemini 3.5 Flash working │ █░░░░░░░░░ 14% (88k/1048k) ↑61k
G 5h 15%~1h00m  7d 90%~1d1h │ tasks 2 agents 2 │ sandbox │ v1.2.3
```

- 한도는 payload 에 남은 비율(`quota["gemini-5h"].remaining_fraction` 등)로 오지만 Claude statusline 과 맞춰 **사용률**(100 − 남은 %)로 보여주고, 60%/80% 에서 색이 바뀐다. 값이 없는 한도·0 인 개수는 칸째 생략한다.
- 설정 파일은 `~/.gemini/antigravity-cli/settings.json`, 키는 camelCase `statusLine` 이다(`statusline` 은 무시된다). `install.sh` 는 `{"type": "command", "command": "bash ~/.gemini/antigravity-cli/statusline-command.sh", "enabled": true}` 로 맞추고, 사용자가 넣은 `padding`·`stack_with_default`(기본 줄 아래에 붙이기)는 그대로 둔다. Antigravity 안에서 `/statusline` 으로 바꾼 값은 `install.sh` 재실행 때 덮어쓴다.
- `settings.json` 의 나머지(모델·권한 등)는 이 저장소가 관리하지 않는다.

## Codex CLI status line

Codex CLI 는 Claude Code 와 달리 **외부 명령을 실행하는 status line 이 없다.** `~/.codex/config.toml` 의 `[tui]` 테이블에 내장 항목 ID 배열을 적는 방식만 지원하므로, 스크립트를 배치하는 대신 그 키 하나를 맞춘다.

```toml
[tui]
status_line = ["current-dir", "estimated-thread-cost", "thread-credits", "weekly-limit", "five-hour-limit", "model-with-reasoning", "context-used", "git-branch", "total-input-tokens", "total-output-tokens", "fast-mode", "codex-version"]
```

Codex TUI 는 터미널 폭이 부족하면 **오른쪽 항목부터 `…` 로 생략하므로** 중요한 것을 앞에 둔다: 위치(경로) → 비용(예상 비용 · 크레딧) → 주간/5시간 사용 한도 → 모델(추론 강도) → 컨텍스트 사용률 → git 브랜치 → 부가 정보(입출력 토큰 · fast 모드 · CLI 버전). 80열 터미널에서도 비용·한도가 잘리지 않도록 한 순서이고, `scripts/test-codex-status-line.sh` 가 이 배열을 그대로 검증한다.

`estimated-thread-cost`·`thread-credits` 는 **Enterprise 워크스페이스에서만 값이 오고**, 그 밖의 로그인(개인·팀 ChatGPT 구독, API 키)에서는 칸 자체가 생략된다 — 설정 오류가 아니다. 한도 항목도 서버가 값을 줄 때만 보이며, 현재 값은 Codex 안에서 `/status` 로 확인한다.

codex-cli 0.156.0 이 인식하는 항목 ID 는 이 밖에도 `app-name`, `project-name`, `run-state`, `thread-title`, `thread-name`, `thread-id`, `context-remaining`, `used-tokens`, `task-progress` 가 있다. 구성을 바꾸려면 `codex/status-line.py` 의 `WANT` 를 고친다(Codex 안에서 `/statusline` 으로 바꾼 값은 `install.sh` 재실행 때 덮어쓴다).

python3 표준 라이브러리에는 TOML writer 가 없어 `status_line` 키의 줄만 교체한다. python 3.11+ 이면 `tomllib` 으로 쓰기 전에 결과를 다시 파싱해 `status_line` 외에는 바뀌지 않았는지 확인하고, 다르면 쓰지 않고 중단한다. `[tui]` 테이블 표기가 아닌 설정(`tui.status_line = ...`, 인라인 테이블)은 지원하지 않는다. `config.toml` 의 나머지(모델·프로필·프로젝트 신뢰 설정 등)는 이 저장소가 관리하지 않는다.

### API 환산 비용 (Stop 훅)

내장 비용 항목이 비는 환경을 위해, Codex 의 **Stop 훅**(턴이 끝날 때 실행)이 턴마다 아래 한 줄을 대화 영역에 표시한다.

```
API 환산 $1.23 · 이번 턴 +$0.04 · 입력 1.4M(캐시 90%) · 출력 11.3k
```

- 세션 기록(`~/.codex/sessions/…/rollout-*.jsonl`)의 `token_count` 누적값을 구간마다 그때의 모델 단가로 곱한다. 스레드 도중 모델을 바꿔도 구간별로 계산되고, 단가표에 없는 모델(로컬 모델 등)만 쓴 스레드는 아무것도 표시하지 않는다.
- 단가는 [OpenAI API 가격표](https://developers.openai.com/api/docs/pricing)의 Standard · Short context 값을 `codex/cost-hook.py` 에 적어 둔 것이다. 가격이 바뀌거나 새 모델이 나오면 그 표를 고친다. 긴 컨텍스트 할증은 반영하지 않는다.
- Fast mode 여부는 세션 기록에 남지 않아 `config.toml` 최상위 `service_tier` 가 `"fast"`/`"priority"` 일 때만 Fast mode 단가를 쓴다. Codex 안에서 `/fast` 로만 켠 경우는 Standard 단가로 계산된다.
- ChatGPT 구독 로그인이면 실제 청구액이 아니라 **같은 사용량을 API 로 썼을 때의 추정치**다.
- Codex 는 새로 추가된 훅을 한 번 검토·승인해야 실행한다. 설치 후 Codex 를 처음 열 때 나오는 훅 검토 안내에서 승인한다.

## 추적 범위

| 추적한다 | 추적하지 않는다 |
|---|---|
| OS 공통 프롬프트(`starship.toml`) | 실제 호스트명·IP·SSH 포트·내부 URL |
| OS 별 zshrc (도구가 있을 때만 켜지는 구조) | 머신별 alias/함수 → `~/.zshrc.local`, Git Bash 는 `~/.bashrc.local` |
| Git Bash 용 `bashrc`·`bash_profile`, 폐쇄망 Git 설치/제거 스크립트 | Git for Windows 설치 파일(`windows/offline/`) |
| placeholder 로만 채운 `zshrc.local.example` | API 키·토큰 → `~/.secrets.zsh` (mode 600) |
| statusline 스크립트(Claude·Antigravity), Codex `status_line` 항목 구성·비용 훅 | `~/.claude/settings.json`·`~/.gemini/antigravity-cli/settings.json`·`~/.codex/config.toml`·`~/.codex/hooks.json` 전체, 개인 `CLAUDE.md` |
| 설치/제거 스크립트와 문서 | 머신별 적용 현황, 백업 파일(`*.bak`) |

`.gitignore` 가 오른쪽 열의 파일명을 막아 두지만, 템플릿이나 문서에 실제 값을 적는 실수는 막지 못한다. 커밋 전에 `git diff --cached` 로 호스트명·IP·URL 이 들어가지 않았는지 확인한다.

## 홈 파일과의 드리프트

`install.sh` 는 홈 파일을 저장소 사본으로 덮어쓴다(`.bak` 1세대 백업). 홈에서 먼저 고친 설정이 있으면 저장소 사본이 더 오래된 상태일 수 있으므로, 재실행 전에 `diff zsh/zshrc.macos ~/.zshrc`, `diff starship/starship.toml ~/.config/starship.toml` 로 확인한다. 폐쇄망 Windows 는 Git Bash 에서 `diff gitbash/bashrc ~/.bashrc` 로 본다(`install-git.ps1` 도 내용이 다르면 `.bak` 백업 후 덮어쓴다). 홈에서 가져올 때는 시크릿 값이나 머신 고유 경로가 섞여 있지 않은지 본다.

## 갱신 규칙

PR·`main` push에서 식별자·문법 검사를 자동 실행한다. push 전에는 `git add` 후 `git diff --cached`를 검토하고 `scripts/check-identifiers.sh`와 `scripts/check-syntax.sh`를 실행한다(Git·bash·zsh·python3 필요). CI 는 `.github/workflows/check.yml` 이 같은 두 검사를 돌린다. `AGENTS.yaml` 을 고쳤으면 `scripts/check-agents-yaml.sh`(PyYAML 필요)로 검증한다. 식별자 검사는 스테이징된 파일의 정해진 패턴만 확인하므로 직접 검토도 필요하다.

- 로컬에서 `~/.zshrc` / `~/.config/starship.toml` / `~/.claude/statusline-command.sh` / `~/.gemini/antigravity-cli/statusline-command.sh` / `~/.codex/cost-hook.py` / (Git Bash) `~/.bashrc` 를 바꾸면 이 저장소에도 반영해 커밋한다.
- 머신별 일회성 설정(특정 호스트 alias 등)은 `~/.zshrc.local` 에 두고 저장소 zshrc 에는 넣지 않는다. 공통화 가능한 것만 양쪽 zshrc 에 반영.
- `install.sh` 에 단계를 추가하면 헤더 주석과 이 README 의 단계 표를 같이 고친다. 홈에 뭔가를 새로 만들면 `uninstall.sh` 에 그 역연산도 같이 넣는다. `windows/install-git.ps1` 과 `uninstall-git.ps1` 도 같은 관계다.
- `windows/*.ps1` 은 UTF-8 BOM·CRLF, `*.cmd` 는 ASCII·CRLF 로 저장한다(Windows PowerShell 5.1·cmd.exe 가 한글·LF 를 잘못 읽는다). `scripts/test-windows-git.sh` 로 확인한다.
- 작업은 이슈 먼저(`#N`) → `feat/issue-<N>-<slug>` 브랜치(`feat`/`fix`/`docs`/`chore`) → PR. 커밋 제목은 `feat(#N): ...`. 검증 명령은 [AGENTS.md](AGENTS.md#검증) 참고.
