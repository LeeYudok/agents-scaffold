# AGENTS.md

이 저장소에서 작업하는 AI 에이전트와 기여자를 위한 안내. 사용자용 설치·사용법은 [README.md](README.md) 에 있고, 여기서는 **무엇을 하는 프로젝트인지, 무엇을 깨면 안 되는지, 어떻게 검증하는지**를 다룬다.

> **기계 판독용 정보는 [`AGENTS.yaml`](AGENTS.yaml)** — 구성요소 그래프(`nodes`/`edges`), `commands`, `secret_files`(경로·키 이름만), `policies`, `known_issues` 등. 작업 전 이 파일을 먼저 읽고, 구성요소·경로·명령·환경변수가 바뀌면 이 문서와 **함께** 갱신한다. 두 파일이 어긋나면 실제 코드·파일시스템을 확인해 둘 다 고친다. 고친 뒤엔 `scripts/check-agents-yaml.sh` 로 검증한다. 날짜·버전 값은 항상 따옴표로 감싼다.

## 프로젝트 개요

새 머신에 셸 환경을 한 번에 맞추는 개인 dotfiles 부트스트랩이다. 관리 대상은 다섯 가지뿐이다.

1. **zsh 설정** — macOS 용(`zsh/zshrc.macos`)과 Linux 서버용(`zsh/zshrc.linux`). 같은 섹션 순서를 따르고, 외부 도구는 설치돼 있을 때만 활성화한다.
2. **starship 프롬프트** — `starship/starship.toml`. Catppuccin Mocha 팔레트, 2줄 프롬프트, Nerd Font 글리프. OS 공통.
3. **Claude Code statusline** — `claude/statusline-command.sh` 와, `~/.claude/settings.json` 의 `statusLine` 키 하나.
4. **Codex CLI status line** — `~/.codex/config.toml` 의 `[tui]` `status_line` 키 하나. Codex 는 외부 명령 status line 이 없어 `codex/status-line.py` 가 그 키만 merge/복원한다. 내장 비용 항목은 Enterprise 전용이라, API 환산 비용은 Stop 훅 `codex/cost-hook.py`(→ `~/.codex/cost-hook.py`)가 턴마다 표시하고 `codex/hooks.py` 가 `~/.codex/hooks.json` 에 그 항목 하나만 merge/제거한다.

5. **Antigravity CLI statusline** — `agy/statusline-command.sh`(→ `~/.gemini/antigravity-cli/statusline-command.sh`)와, `~/.gemini/antigravity-cli/settings.json` 의 `statusLine` 키 하나. Claude 와 같은 외부 명령 방식이며 `agy/settings.py` 가 그 키만 merge/복원한다.

이 다섯을 `install.sh` 가 홈 디렉터리에 배치하고 `uninstall.sh` 가 설치 전 상태로 되돌린다. 프레임워크(oh-my-zsh 등)나 dotfile 매니저(stow, chezmoi)는 쓰지 않는다 — 셸 스크립트 두 개와 복사할 파일들이 전부다. 빌드·패키지·테스트 러너는 없다. GitHub Actions는 식별자·문법 검사만 실행한다.

대상 환경: macOS(Apple Silicon/Intel, Homebrew 필수), Linux(RHEL/Rocky 계열 `dnf`, Debian 계열 `apt-get`), Windows 는 WSL2 안에서만(Linux 경로를 그대로 쓴다). Git Bash/MSYS/Cygwin 에서 `install.sh` 는 지원하지 않고 0 단계에서 중단한다. 셸 스크립트는 bash, 배치되는 설정은 zsh.

별도 경로: **폐쇄망 Windows(인터넷·WSL2 불가)** 는 `windows/install-git.ps1`(cmd 는 `install-git.cmd`)이 반입한 Git for Windows 설치 파일로 Git 을 오프라인 설치하고, Git Bash 용 `gitbash/bashrc`·`bash_profile` 을 배치한다. zsh·starship·statusline 은 이 경로에 없다. 역연산은 `windows/uninstall-git.ps1`.

## 디렉터리와 파일별 역할

| 경로 | 배치 위치 | 역할 |
|---|---|---|
| `install.sh` | — | 부트스트랩. 의존성 검사 → 패키지(sudo 불가 시 플러그인은 태그 tarball 폴백) → starship.toml → Nerd Fonts → zshrc → statusline + `statusLine` 키 merge → Codex `status_line` 키 merge + 비용 훅 → Antigravity statusline + `statusLine` 키 merge → chsh 안내 |
| `uninstall.sh` | — | `install.sh` 의 역연산. `--purge`(새로 설치한 패키지까지), `--keep-backup` |
| `starship/starship.toml` | `~/.config/starship.toml` | 프롬프트 정의 |
| `eza/theme.yml` | `~/.config/eza/theme.yml` | eza 아이콘 덮어쓰기. 기본 아이콘 중 Nerd Font v3 전용 코드를 v2·v3 공통 글리프로 바꾼다 |
| `zsh/zshrc.macos` | `~/.zshrc` (Darwin) | brew 기반. `HOMEBREW_PREFIX` 자동 감지 |
| `zsh/zshrc.linux` | `~/.zshrc` (그 외) | 미니멀판. 도구가 없으면 기본 프롬프트·`ls --color`·일반 `cd` 로 폴백. 플러그인은 `/usr/share` 우선, 없으면 `~/.local/share/zsh/plugins` |
| `zsh/zshrc.local.example` | 배치 안 함 | `~/.zshrc.local` 템플릿. 사용자가 직접 복사한다. **placeholder 만** 담는다 |
| `claude/statusline-command.sh` | `~/.claude/statusline-command.sh` | statusLine JSON(stdin) → 두 줄 출력. `jq` 필요 |
| `codex/status-line.py` | 배치 안 함 | `check`/`apply`/`restore`. `~/.codex/config.toml` 의 `[tui]` `status_line` 키만 줄 단위로 편집. `install.sh`·`uninstall.sh` 가 호출 |
| `codex/cost-hook.py` | `~/.codex/cost-hook.py` | Codex Stop 훅. rollout jsonl 의 `token_count` 를 API 단가로 환산해 `systemMessage` 로 출력. 단가표는 이 파일에 있다 |
| `codex/hooks.py` | 배치 안 함 | `check`/`apply`/`restore`. `~/.codex/hooks.json` 의 `Stop` 에 비용 훅 항목 하나만 추가/제거 |
| `agy/statusline-command.sh` | `~/.gemini/antigravity-cli/statusline-command.sh` | Antigravity CLI 상태 JSON(stdin) → 두 줄 출력. `jq` 필요. 한도는 남은 비율을 사용률로 바꿔 표시 |
| `agy/settings.py` | 배치 안 함 | `check`/`apply`/`restore`. `settings.json` 의 `statusLine` 키만 편집(`type`/`command`/`enabled` 만 맞추고 사용자 선택 키 보존). `install.sh`·`uninstall.sh` 가 호출 |
| `scripts/test-agy-statusline.sh` | — | `agy/settings.py` 임시 `HOME` 왕복(멱등·키 보존·바이트 복원·거부)과 고정 payload 렌더 시험 |
| `gitbash/bashrc` | `~/.bashrc` (Windows, Git Bash) | Git Bash 용. UTF-8·`core.quotepath`(환경변수로만)·히스토리·alias, 외부 도구는 있을 때만 |
| `gitbash/bash_profile` | `~/.bash_profile` (Windows, Git Bash) | 로그인 셸이 `~/.bashrc` 를 읽게 한다. 없으면 Git Bash 가 스스로 만들어 역연산에서 빠지므로 함께 배치 |
| `windows/install-git.ps1` | — | 폐쇄망 Windows 부트스트랩. 사전 검사(서명) → Git 오프라인 설치 → PATH → Windows Terminal fragment·바로가기 → bashrc → 확인 |
| `windows/uninstall-git.ps1` | — | `install-git.ps1` 의 역연산. `-Purge`(설치 기록이 있는 Git 까지), `-KeepBackup` |
| `windows/*.cmd` | — | cmd 에서 같은 이름의 `.ps1` 을 `-ExecutionPolicy Bypass` 로 실행하는 래퍼 |
| `scripts/test-windows-git.sh` | — | `windows/`·`gitbash/` 정적 시험. 인코딩(BOM·ASCII)·줄바꿈·bash 문법·pwsh 구문 분석(있을 때) |
| `.gitattributes` | — | 기본 LF, `.ps1`/`.cmd` 는 CRLF 그대로(`-text`) |
| `scripts/test-install-safety.sh` | — | 임시 HOME·모의 apt/dnf/sudo로 반복 제거, 미설치 파일 보존, Claude 사전 검사, 패키지별 기록·purge, sudo 불가·패키지 실패 시 플러그인 tarball 폴백 검증 |
| `scripts/test-codex-status-line.sh` | — | `status-line.py` 의 임시 `HOME` 왕복 시험. `status_line` 순서까지 검증 |
| `scripts/test-codex-cost-hook.sh` | — | `cost-hook.py` 금액 계산(고정 rollout)과 `hooks.py` 임시 `HOME` 왕복 시험 |
| `scripts/test-windows-paths.sh` | — | Git Bash 거부(어느 OS 에서나)와 WSL 폰트 건너뛰기(Linux 에서만) 시험 |
| `.gitignore` | — | 머신별·시크릿 파일명 차단 |
| `AGENTS.yaml` | — | 기계 판독용 사실(구성요소 그래프·명령·정책 요약·함정). 이 문서와 함께 갱신한다 |
| `scripts/check-identifiers.sh` | — | Git 인덱스의 식별자 패턴 검사. 검출 시 파일명만 출력하고 실패 |
| `scripts/check-syntax.sh` | — | bash·zsh 파일별 문법 검사와 Python 컴파일 검사 |
| `.github/workflows/check.yml` | — | PR·main push에서 식별자·문법 검사 실행 |
| `scripts/check-agents-yaml.sh` | — | `AGENTS.yaml` 검증기(구조·따옴표 없는 날짜·그래프·경로). agents-yaml 스킬 원본을 수정 없이 복사. python3 + PyYAML 필요 |

홈에 생기는 부산물: `~/.config/dotfiles/backup/`(원본 기록과 설치 manifest), 배치 대상 옆의 `*.bak`(1세대), Linux 에서 sudo 없이 받은 `~/.local/share/zsh/plugins/<name>`, 폰트 디렉터리의 `.nerd-font-<name>-installed` 마커와 `.nerd-font-<name>-files.txt` manifest.

## 추적 범위 — 가장 중요한 규칙

이 저장소는 공개 저장소다. **어느 머신에나 그대로 적용 가능한 것만 커밋한다.**

커밋하지 않는 것:

- 실제 호스트명, IP(공인·사설 모두), SSH 포트, 내부 도메인·URL, 클러스터·네임스페이스·시크릿 이름
- API 키·토큰·비밀번호, 그리고 그것을 조회하는 구체적인 절차
- 개인 에이전트 지침(`~/.claude/CLAUDE.md` 등), `~/.claude/settings.json` 전체(permissions/hooks/model 포함)
- 특정 머신 목록이나 "어느 서버에 적용했는지" 같은 운영 현황
- 절대 경로에 박힌 사용자명(`/Users/<name>/...`) — `$HOME` 을 쓴다

대신 두는 곳:

- 머신별 alias/함수 → `~/.zshrc.local` (두 zshrc 가 플러그인 직전에 `source`)
- 시크릿 → `~/.secrets.zsh` (mode 600, zshrc 는 `source` 만 한다)

`zshrc.local.example`, README, 주석에 예시가 필요하면 `<host>`, `<container>` 같은 placeholder 를 쓴다. 홈 파일을 저장소로 가져와 동기화할 때가 제일 새기 쉬운 지점이다 — 커밋 전에 `git diff --cached` 를 직접 읽고 아래 검증 절의 식별자 검사를 돌린다.

## 불변 규칙 (스크립트를 고칠 때)

- **멱등**: `install.sh`·`uninstall.sh` 는 몇 번을 재실행해도 결과가 같아야 한다. 패키지는 없을 때만 설치하고, 파일은 내용이 다를 때만 덮어쓴다.
- **실패는 변경 전에**: 의존성 검사(0 단계)에서 실패하면 `~/.config/dotfiles/backup` 을 포함해 홈에 아무것도 만들지 않는다. 새 전제 조건은 0 단계에 추가한다. Claude 설정은 최상위 객체까지 확인하고, Linux는 패키지 조회 도구(rpm/dpkg-query)도 검사한다.
- **덮어쓰기 전 백업**: 홈 파일 배치는 반드시 `deploy_file` 을 거친다(최초 원본을 `.orig`/`.absent` 로 기록 → 내용이 다르면 `.bak` → 복사). `cp` 직접 호출 금지. 최초 기록은 재실행 때 갱신하지 않는다.
- **`settings.json` 은 키 단위 merge**: `statusLine` 외의 키를 읽거나 바꾸지 않는다. 쓰기는 같은 디렉터리의 임시 파일 + `os.replace` 로 원자적으로, 기존 mode 를 보존한다. 깨진 JSON 이면 손대지 않고 중단한다.
- **`config.toml` 도 키 단위 merge**: `[tui]` 의 `status_line` 외에는 읽거나 바꾸지 않는다. TOML writer 가 없으므로 그 키의 줄만 교체하고 나머지는 바이트 그대로 둔다. `tomllib` 이 있으면 쓰기 전에 "`status_line` 외에는 같다"를 검증하고, 깨진 TOML·미지원 표기면 손대지 않고 중단한다. `install.sh` 와 `uninstall.sh` 가 같은 파서를 쓰도록 로직은 `codex/status-line.py` 한 곳에만 둔다. Codex 를 쓰지 않는 머신에서는 `~/.codex` 를 만들지 않는다.
- **Antigravity `settings.json` 도 키 단위 merge**: `statusLine` 외의 키를 바꾸지 않고, `statusLine` 안에서도 `type`/`command`/`enabled` 만 맞춘다. 설치 전 기록은 `agy-settings.json.orig`/`.absent`. 로직은 `agy/settings.py` 한 곳에 둔다. Antigravity CLI 를 쓰지 않는 머신(`agy` 명령도 `~/.gemini/antigravity-cli` 도 없음)에서는 `~/.gemini` 를 만들지 않는다.
- **`hooks.json` 은 공유 파일**: 다른 도구(터미널 앱 등)가 수시로 자기 훅을 넣고 빼므로 설치 전 원본으로 통째 되돌리지 않는다. `codex/hooks.py` 는 command 가 `~/.codex/cost-hook.py` 를 가리키는 항목만 넣고 빼며, 설치 전 기록은 파일 유무(`codex-hooks.json.absent`/`.present`)만 남긴다. 깨진 JSON·예상 밖 구조면 손대지 않고 중단한다.
- **비용 훅은 Codex 를 막지 않는다**: `cost-hook.py` 는 어떤 오류든 조용히 exit 0 하고, 단가를 모르면 출력하지 않는다. 단가표를 고칠 때는 출처 URL 과 확인 날짜 주석도 같이 갱신한다.
- **WSL 에서는 `$HOME` 밖을 건드리지 않는다**: WSL 은 `/proc/version` 의 `microsoft` 로 감지하고(`is_wsl`), Nerd Font 단계를 건너뛰고 안내만 한다. Windows 사용자 프로필에 폰트를 설치하는 식의 자동화는 넣지 않는다 — 역연산과 임시 `HOME` 왕복 시험이 성립하지 않는다. `DOTFILES_PROC_VERSION` 은 감지에 쓸 파일을 바꾸는 시험용 변수다.
- **설치한 것만 지운다**: `--purge` 는 manifest(`brew-installed.txt`·`pkg-installed.txt`·`bin-installed.txt`·`plugin-installed.txt`)에 기록된 것만, 폰트는 파일 manifest 에 적힌 것만 제거한다. 원래 있던 것을 지우지 않는다. Linux 플러그인은 패키지 DB로 각각 조회해 새로 설치에 성공한 것만 기록한다(EPEL 포함). 패키지 설치는 `sudo -n` 이 될 때만 시도하고(비밀번호 프롬프트로 무인 설치가 멈추지 않게), 안 되면 버전 고정 태그 tarball 을 `~/.local/share/zsh/plugins` 에 풀어 `plugin-installed.txt` 에 기록한다. purge 는 그 디렉터리 아래 기록된 경로만 지운다. `.orig`/`.absent` 없는 파일·`.bak`과 설치 기록 없는 Claude 설정·Codex 훅은 보존한다.
- **사용자 파일은 건드리지 않는다**: `~/.zshrc.local`, `~/.secrets.zsh`, `~/.claude/CLAUDE.md` 는 만들지도 지우지도 않는다.
- **install 과 uninstall 은 한 쌍**: `install.sh` 가 홈에 뭔가를 새로 만들면 같은 변경에서 `uninstall.sh` 에 역연산을 넣는다.
- **번호 동기화**: `install.sh` 의 섹션 번호, 헤더 주석의 동작 목록, README 의 단계 표는 항상 같은 번호를 쓴다. 단계를 바꾸면 세 곳을 같이 고친다.
- **zshrc 구조**: 두 zshrc 는 같은 섹션 순서(환경·PATH → 히스토리·옵션 → 자동완성 → 툴 초기화 → alias → 시크릿 → 머신별 → 플러그인)를 지킨다. 도구·디렉터리는 존재할 때만 활성화하고 없으면 조용히 건너뛴다. `zsh-syntax-highlighting` 은 맨 마지막에 source 한다. PATH 는 `typeset -U path` 로 중복을 막는다.
- **Windows 스크립트 인코딩**: `.ps1` 은 UTF-8 **BOM**·CRLF(Windows PowerShell 5.1 은 BOM 이 없으면 한글을 cp949 로 읽어 구문까지 깨진다), `.cmd` 는 **ASCII**·CRLF, `gitbash/` 는 LF. PowerShell 5.1 에서 돌아야 하므로 7 전용 문법(`??`, `&&` 파이프라인 연산자 등)을 쓰지 않는다. `scripts/test-windows-git.sh` 가 검사한다.
- **폐쇄망 Windows 경로도 같은 규칙**: 인터넷에서 아무것도 받지 않는다(설치 파일은 반입). 사전 검사 실패 시 아무것도 바꾸지 않고, 홈 파일은 `gitbash-<name>.orig`/`.absent` 기록 후 내용이 다를 때만 `.bak` 백업하고 배치한다. Git 은 이 스크립트가 새로 설치했을 때만 `gitbash-git-installed.txt` 에 기록하고 `-Purge` 는 그것만 지운다. 사용자 PATH 는 추가한 항목만 기록·제거하고 값의 종류(REG_EXPAND_SZ)를 보존한다. Windows Terminal 은 `settings.json` 대신 fragment 로만 건드린다. `~/.gitconfig`, `~/.bashrc.local` 은 만들지도 바꾸지도 않는다.
- **`trap ... RETURN` 금지**: bash 에서 함수 밖으로 새어 이후 모든 함수 리턴에 발화한다. 임시 디렉터리 정리는 단일 지점에서 한다.
- **프롬프트 심볼은 Nerd Font 글리프**: 이모지를 쓰지 않는다. `starship.toml`·`eza/theme.yml` 의 글리프는 v2·v3 공통 BMP 영역(U+E000~F8FF)만 쓴다 — v3 전용 5자리(U+F0000~)는 v2 폰트를 내장한 터미널(Termius 등)에서 깨진다. 글리프를 편집 도구로 옮기다 빈 문자열로 사라진 적이 있으니, 고친 뒤 `od`·Python 으로 코드포인트가 실제로 들어 있는지 확인한다. `starship.toml` 은 starship 1.22(Linux 배포판 버전)에서도 동작해야 한다.

## 검증

PR·main push에서는 식별자·문법 검사를 자동 실행한다. push 전에는 `git add` 후 `git diff --cached`를 직접 검토하고 아래 두 검사 스크립트를 실행한다. 식별자 검사는 Git 인덱스를 대상으로 하며 모든 시크릿을 탐지하지는 않는다. 동작에 관한 검증은 변경 범위에 맞춰 아래에서 선택한다.

```bash
# 문법 — bash·zsh는 파일마다 검사, Python은 컴파일 검사
scripts/check-syntax.sh

# 글리프 — v3 전용 5자리 코드가 없어야 한다 (결과 [])
python3 -c "import sys;print([hex(ord(c)) for f in sys.argv[1:] for c in open(f,encoding='utf-8').read() if ord(c)>=0xF0000])" starship/starship.toml eza/theme.yml

# 실제 홈에 영향 없이 설치/제거 왕복 (패키지는 이미 설치된 머신 기준)
T="$(mktemp -d)"
HOME="$T" ./install.sh && HOME="$T" ./install.sh      # 두 번째 실행에서 변경이 없어야 한다
HOME="$T" ./uninstall.sh && find "$T" -type f -not -path '*/Library/Caches/*'   # 남는 파일이 없어야 한다 (macOS 는 brew 캐시가 임시 홈에 생긴다)

# statusline
echo '{"workspace":{"current_dir":"/tmp"},"model":{"display_name":"test"}}' | bash claude/statusline-command.sh

# 설치·제거 안전성 — 실제 패키지·네트워크 사용 없이 임시 HOME·모의 apt/dnf로 회귀 검사
scripts/test-install-safety.sh

# Codex status line — 임시 HOME 에서 apply 2회 → restore 후 원본과 바이트 비교, 깨진 TOML·미지원 표기 거부
scripts/test-codex-status-line.sh

# Codex 비용 훅 — 고정 rollout 으로 금액 계산(Standard·Fast·단가 없음), hooks.json merge 멱등·다른 훅 보존·거부
scripts/test-codex-cost-hook.sh

# Antigravity statusline — settings.json statusLine 키 왕복(멱등·다른 키 보존·바이트 복원·깨진 JSON 거부), 고정 payload 렌더
scripts/test-agy-statusline.sh

# 폐쇄망 Windows 스크립트 — 인코딩·줄바꿈·bash 문법, pwsh 가 PATH 에 있으면 .ps1 구문 분석까지. 실제 설치는 Windows 에서만 확인할 수 있다
scripts/test-windows-git.sh

# Windows 경로 — Git Bash 거부는 어느 OS 에서나, WSL 흉내 왕복은 Linux 에서만 돈다 (macOS 에서는 컨테이너로)
scripts/test-windows-paths.sh
podman run --rm -v "$PWD":/src:ro docker.io/library/ubuntu:24.04 bash -c \
  'apt-get update -qq && apt-get install -y -qq sudo curl unzip python3 ca-certificates >/dev/null && cp -r /src /work && cd /work && scripts/test-windows-paths.sh'

# AGENTS.yaml — 구조·타입·그래프·경로 검증 (PyYAML 필요)
scripts/check-agents-yaml.sh

# 공개 전 식별자 검사 — git add 후 실행, 검출·실행 오류는 실패
scripts/check-identifiers.sh
```

`HOME` 을 바꾼 왕복 시험은 Nerd Font 를 실제로 내려받는다(수십 MB). 폰트와 무관한 변경이면 임시 홈의 폰트 디렉터리에 `.nerd-font-JetBrainsMono-installed`, `.nerd-font-D2Coding-installed` 마커를 미리 만들어 건너뛸 수 있다.

## 작업 흐름

- 이슈를 먼저 등록하고 번호를 브랜치·커밋에 넣는다: `feat/issue-<n>-<slug>`, 커밋 제목 `feat(#<n>): ...` (`feat`/`fix`/`docs`/`chore`).
- 기본 브랜치는 `main`. 직접 커밋하지 않고 브랜치 → PR 로 올린다.
- 동작을 바꾸면 README 의 해당 절과 스크립트 헤더 주석을 같은 커밋에서 갱신한다.
- 커밋 메시지·문서·주석은 한국어, 표준 문어체.
