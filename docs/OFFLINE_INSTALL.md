# agents-scaffold — 폐쇄망·Windows 설치

인터넷이 막힌 환경(폐쇄망)에서 설치하는 절차. 개요는 [README](../README.ko.md) 참조.
원격 설치(`curl | bash`)는 GitHub 에서 템플릿을 받아오므로 폐쇄망에서는 동작하지 않는다 —
대신 인터넷 PC 에서 **번들**을 만들어 반입한다. 번들을 풀어 그 안의 스크립트를 실행하면
다운로드는 일어나지 않는다.

## 전제 — Windows 는 Git Bash 필수

부트스트랩 스크립트와 `.claude/hooks/*.sh` 는 전부 bash 다. Windows 에서는
**Git for Windows(Git Bash)** 가 있어야 한다. WSL 의 `bash.exe` 는 파일시스템 경로 체계가
달라 쓰지 않는다. Claude Code 도 Windows 에서 Git Bash 로 훅·셸을 실행한다.

| 필요한 것 | 용도 | 반입할 설치 파일 |
|---|---|---|
| Git for Windows | bash·git·sed·awk·tar·sha256sum 일체 | [git-scm.com/downloads/win](https://git-scm.com/downloads/win) — 64-bit Standalone Installer |
| Python 3 | `observe-lite.sh`·`stop-memory-remind.sh` 훅, `.claude/scripts/knowledge_graph.py` | [python.org/downloads/windows](https://www.python.org/downloads/windows/) — Windows installer (64-bit) |
| agents-scaffold 번들 | 템플릿 본체 | 아래 1단계에서 생성 |

스택별 도구(`bun`, `go`, `cargo`, `ruff` 등)는 pre-commit 게이트가 **있을 때만** 쓴다 — 없으면
해당 검사를 건너뛴다. 사내 미러에서 따로 반입한다.

## 1. 번들 만들기 (인터넷 PC)

```bash
git clone https://github.com/leeyudok/agents-scaffold.git
cd agents-scaffold
scripts/make-offline-bundle.sh            # 특정 태그면 --ref v1.2.0
```

`dist/` 에 세 파일이 생긴다: `agents-scaffold-offline-<버전>.zip`, 같은 이름의 `.tar.gz`,
`SHA256SUMS`. 번들은 **커밋된 내용만** 담는다(`git archive`). Windows 에서 만들어도
`.gitattributes` 가 적용돼 `*.sh` 는 LF 로 담긴다.

## 2. 반입 후 무결성 확인

```bash
# Git Bash
cd <반입 폴더> && sha256sum -c SHA256SUMS
```

```bat
rem cmd — 출력 해시를 SHA256SUMS 의 값과 비교
certutil -hashfile agents-scaffold-offline-<버전>.zip SHA256
```

## 3. 압축 해제

탐색기 "압축 풀기" 또는 `tar -xf agents-scaffold-offline-<버전>.zip`(Windows 10 이상 내장
`tar` 가 zip 도 푼다). `agents-scaffold/` 폴더 하나가 생긴다.

## 4. 설치

**Git Bash**:

```bash
bash agents-scaffold/bin/agents-scaffold.sh /c/work/myproj --stack springboot --yes
```

**cmd / PowerShell** — 런처가 Git Bash 를 찾아 대신 실행한다:

```bat
agents-scaffold\bin\agents-scaffold.cmd C:/work/myproj --stack springboot --yes
```

- 런처는 `AGENTS_SCAFFOLD_BASH` → `CLAUDE_CODE_GIT_BASH_PATH` → `%ProgramFiles%\Git` →
  `%LOCALAPPDATA%\Programs\Git` → `where git` 순으로 `Git\bin\bash.exe` 를 찾는다. 설치 위치가
  다르면 `set AGENTS_SCAFFOLD_BASH=D:\tools\Git\bin\bash.exe`.
- 대상 경로는 슬래시(`C:/work/myproj`)로 적는 편이 안전하다.
- 옵션은 온라인 설치와 같다 → [OPTIONS.md](OPTIONS.md).
- `bin/agents-scaffold.sh` 만 따로 복사해 실행하면 안 된다 — 옆에 `.claude/`·`presets/` 가
  없으면 원격 설치로 폴백해 다운로드를 시도하고 실패한다. 반드시 풀어 둔 트리 안에서 실행.

설치하면 대상 레포의 `.gitattributes` 에 훅 LF 고정 규칙(`.claude/hooks/*.sh text eol=lf`)이
추가된다. 팀원이 `core.autocrlf=true` 로 체크아웃해도 훅이 CRLF 로 깨지지 않게 하기 위함이다.

## 5. Windows 의 `python3`

훅은 `python3` 를 부른다. python.org 설치본은 `python`·`py` 만 만들고 `python3` 는 만들지
않는다. PATH 에 걸리는 `...\WindowsApps\python3.exe` 는 Microsoft Store 로 보내는 스텁이라
폐쇄망에서는 실패한다.

1. 설정 → 앱 → 고급 앱 설정 → **앱 실행 별칭**에서 `python.exe`·`python3.exe` 끄기
2. Python 설치 폴더(예: `C:\Program Files\Python312\`)에서 `python.exe` 를 복사해 `python3.exe` 로 저장
3. Git Bash 에서 확인: `python3 -c "import sys; print(sys.version)"`

`.cmd` 런처는 이 확인을 대신 해 주고, 실패하면 경고만 띄우고 설치는 계속한다.

## 6. 업데이트

새 번들을 같은 방식으로 반입·해제한 뒤 `--update` 로 실행한다.

```bash
bash agents-scaffold/bin/agents-scaffold.sh --update /c/work/myproj
```

## 문제 해결

| 증상 | 원인 → 조치 |
|---|---|
| `$'\r': command not found` | 훅이 CRLF 로 체크아웃됨 → `.gitattributes` 규칙 확인 후 `git add --renormalize .claude/hooks && rm .claude/hooks/*.sh && git checkout -- .claude/hooks` |
| `Error: template download failed` | 스크립트를 번들 트리 밖에서 실행 → 4단계 주의사항 참조 |
| `Git Bash not found` | Git for Windows 미설치 또는 비표준 경로 → `AGENTS_SCAFFOLD_BASH` 지정 |
| 훅이 조용히 아무것도 안 함 | `python3` 가 Store 스텁 → 5단계 |
| Claude Code 가 Git Bash 를 못 찾음 | 비표준 경로면 환경변수 `CLAUDE_CODE_GIT_BASH_PATH` 에 `bash.exe` 전체 경로 지정 |

Claude Code 자체의 폐쇄망 설치는 이 문서 범위 밖이다.
