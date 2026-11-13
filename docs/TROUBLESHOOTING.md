# agents-scaffold — 문제 해결

게이트·설치 스크립트·하네스가 기대와 다르게 움직일 때 보는 문서다. 시작은 [README](../README.ko.md).
English: [TROUBLESHOOTING.en.md](TROUBLESHOOTING.en.md).

아래 명령은 프로젝트 옆에 agents-scaffold 를 clone 해 두었다고 보고, 프로젝트 루트에서 실행한다.

| 증상 | 절 |
|---|---|
| 통과해야 할 커밋이 막혔다 | [게이트가 커밋을 막았다](#게이트가-커밋을-막았다) |
| 막혀야 할 커밋이 통과한다 | [게이트가 돌지 않는다](#게이트가-돌지-않는다) |
| Claude Code 가 `AGENTS.md` 를 따르지 않는다 | [Claude Code 가 AGENTS.md 를 읽지 않는다](#claude-code-가-agentsmd-를-읽지-않는다) |
| `Warning: ... pre-commit already exists` | [기존 pre-commit 훅이나 husky 가 있다](#기존-pre-commit-훅이나-husky-가-있다) |
| `Warning: python3 not found` | [python3 가 없다](#python3-가-없다) |
| `--update` 뒤에 `*.new` 파일이 생겼다 | [--update 뒤의 .new 파일](#--update-뒤의-new-파일) |
| `AGENTS.md.bak-<시각>` 파일이 생겼다 | [AGENTS.md.bak 파일](#agentsmdbak-파일) |
| `Warning: symlink unavailable` | [심볼릭 링크를 못 만든다 (Windows)](#심볼릭-링크를-못-만든다-windows) |
| `Error: unknown stack` | [모르는 스택](#모르는-스택) |
| Codex·Antigravity 에서 룰·서브에이전트·훅이 빠진다 | [Codex 와 Antigravity 의 한계](#codex-와-antigravity-의-한계) |
| 걷어내고 싶다 | [제거](#제거) |

## 게이트가 커밋을 막았다

게이트는 `.claude/hooks/pre-commit.sh` 이고, git 이 `.git/hooks/pre-commit` 을 거쳐 실행한다. 막을 때는
`Blocked:` 로 시작하는 줄을 찍고 exit 2 로 끝나며, git 은 커밋을 중단한다(1.0.0 이전의 스택 게이트는 `차단:` 으로
찍는다). 그 줄부터 읽는다. 어떤 검사가 실패했는지 적혀 있다.

| 메시지 | 뜻 | 조치 |
|---|---|---|
| `Blocked: a .env-type file is staged.` | 스테이징된 경로가 `.env`, `.env.<무엇>`, 또는 하위 폴더의 그런 파일이다 | `git rm --cached <파일>` 로 빼고 `.gitignore` 에 넣는다. `.env.example` 같은 견본도 걸린다. 이름을 바꾸거나(`env.example`), 그 파일만 알고서 `--no-verify` 로 커밋한다 |
| `Blocked: the staged .claude/skills (copy) differs from its source .agents/skills` | 사본 모드(링크 없음)에서 스킬의 한쪽만 스테이징했다 | `.agents/skills` 쪽을 고치고 같은 경로의 `.claude/skills` 에 복사한 뒤 두 경로를 함께 `git add` 한다 |
| 스택 메시지(`tsc`, `ruff`, `gradlew` 등) | 선택한 스택의 빌드·타입·린트 검사가 실패했다 | 메시지에 나온 도구를 직접 돌려 고친 뒤 다시 커밋한다 |

커밋하지 않고 출력 전체를 보려면 게이트를 직접 실행한다.

```bash
.claude/hooks/pre-commit.sh; echo "exit=$?"
```

우회는 가능하고, 그 판단은 사용자 몫이다. `git commit --no-verify` 는 그 커밋 한 번에 한해 로컬 훅을 모두 건너뛴다.
스캐폴드는 이를 막지 못한다. CI 에서 같은 검사를 돌려야 하는 이유다. 검사가 프로젝트에 맞지 않으면
`.claude/hooks/pre-commit.sh` 를 고친다. 사용자 파일이고, `--update` 는 고친 내용을 덮어쓰지 않는다
([.new 파일](#--update-뒤의-new-파일) 참조).

## 게이트가 돌지 않는다

`.git/hooks/` 는 커밋에 들어가지 않는다. 그래서 훅은 설치 스크립트를 돌린 그 clone 에만 있고, 다른 clone 은
한 번씩 직접 연결해야 한다. 먼저 확인한다.

```bash
cat "$(git rev-parse --git-path hooks)/pre-commit"
```

`.claude/hooks/pre-commit.sh` 를 실행하는 줄이 있어야 한다. 파일이 없으면 `--update` 를 돌리거나(없는 훅을 연결한다)
직접 만든다.

```bash
../agents-scaffold/bin/agents-scaffold.sh --update .
# or, without the scaffold:
printf '%s\n' '#!/usr/bin/env bash' 'exec "$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh"' > .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
```

그 밖의 원인은 다음과 같다.

- `git init` 전에 설치했다. 설치 스크립트가 `Note: target is not the root of a git repo yet` 와 함께 위 명령을
  알려준다. `git init` 뒤에 실행한다.
- 레포의 하위 폴더에 설치했다. 설치 스크립트는 상위 레포의 훅을 건드리지 않는다(같은 `Note` 가 나온다). 상위 레포의
  pre-commit 훅에서 `<하위폴더>/.claude/hooks/pre-commit.sh` 를 직접 부른다.
- `--no-verify` 로 커밋했다.

worktree·submodule·`core.hooksPath` 는 처리한다. 훅은 git 이 실제로 찾는 위치에 쓰인다.

## Claude Code 가 AGENTS.md 를 읽지 않는다

Claude Code 는 `AGENTS.md` 를 네이티브로 읽는다(v2.1.277 이상). 단, **`CLAUDE.md` 가 없을 때만** 그렇다.
프로젝트에 `CLAUDE.md` 나 `CLAUDE.local.md` 가 있으면 Claude Code 는 그 파일만 읽고 `AGENTS.md` 를 건너뛴다.
둘을 합치지 않는다. 설치 스크립트는 이 파일들을 만들지도 고치지도 않는다.

해결: 남겨 둘 `CLAUDE.md`(또는 `CLAUDE.local.md`)의 첫 줄을 다음으로 한다.

```markdown
@AGENTS.md
```

또는 `CLAUDE.md` 내용을 `AGENTS.md` 로 옮기고 `CLAUDE.md` 를 지운다. Claude Code 가 2.1.277 보다 낮으면
업그레이드하거나 같은 한 줄짜리 `CLAUDE.md` 를 둔다.

## 기존 pre-commit 훅이나 husky 가 있다

설치 스크립트는 자기가 쓰지 않은 pre-commit 훅을 덮어쓰지 않는다. 대신 다음을 찍는다.

```console
Warning: .git/hooks/pre-commit already exists — not overwriting. Add this line to it to run the gate:
  "$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh" || exit $?
```

그 줄을 기존 훅에 넣는다. 훅 끝에 `exec` 나 `exit` 가 있으면 그 앞에 넣는다. husky 를 쓰면(`core.hooksPath` 가
`.husky`) 경고에 `.husky/pre-commit` 이 나오고, 같은 줄을 거기에 넣는다.

```bash
# .husky/pre-commit
"$(git rev-parse --show-toplevel)/.claude/hooks/pre-commit.sh" || exit $?
npx lint-staged
```

훅 안에 `.claude/hooks/pre-commit.sh` 가 들어가면 설치와 `--update` 는 더 경고하지 않는다. 다른 훅 관리 도구
(pre-commit, lefthook)도 같다. 그 스크립트를 실행하는 로컬 훅을 하나 추가한다.

## python3 가 없다

```console
Warning: python3 not found — codex hook adapter (.codex/hooks.json) not generated.
```

`python3` 가 필요한 것은 Codex·Antigravity 의 **훅 어댑터**(`.codex/hooks.json`, `.agents/hooks.json`)뿐이다.
생성할 때도, 실행할 때도 쓴다. 없어도 나머지 설치는 온전하다. `AGENTS.md`, 룰, 스킬, 생성된 서브에이전트,
Antigravity 룰, git pre-commit 게이트(bash 스크립트)는 그대로 들어간다.

해결: `python3` 가 `PATH` 에 잡히도록 Python 3 를 설치하고 `--update` 를 돌린다. 기록된 하네스에 맞춰 빠진
어댑터를 생성한다. Windows 는 [OFFLINE_INSTALL.md 5단계](OFFLINE_INSTALL.md#5-windows-의-python3)를 본다.
Python 으로 쓴 Claude Code 보조 훅(`cc-check.py`)도 `python3` 가 있어야 돈다.

## --update 뒤의 .new 파일

`--update` 는 기록된 선택으로 지금 설치하면 나올 결과를 다시 만들고, 파일 단위로 비교한다. 같으면 건너뛰고,
없으면 추가하고, **다르면 기존 파일을 그대로 둔다.** 새 버전은 옆에 `<file>.new` 로 쓴다. 사용자가 고친 것인지
원본이 바뀐 것인지는 구분하지 못하므로 두 경우 모두 `.new` 가 생긴다.

```bash
../agents-scaffold/bin/agents-scaffold.sh --update . --dry-run   # list what would be added or staged as .new
find . -name '*.new' -not -path './.git/*'                       # after a real run
diff -u .claude/rules/common.md .claude/rules/common.md.new
```

파일마다 다음 중 하나를 고른다.

- 고친 적 없는 파일이다 → 새 버전을 받는다. `mv <file>.new <file>`
- 직접 고친 파일이다 → diff 에서 필요한 부분만 내 파일에 합치고 `.new` 를 지운다.
- 내 것을 그대로 쓴다 → `.new` 를 지운다. 두 파일이 다른 동안에는 다음 `--update` 가 다시 만든다.

`AGENTS.md` 는 빈 섹션을 채우는 순간부터 항상 다르므로 업데이트 때마다 `AGENTS.md.new` 가 생긴다. diff 로 새 규칙만
확인하고 지운다. `.claude/hooks/pre-commit.sh` 도 비교한다. 기준은 기록된 스택으로 다시 조립한 게이트다.
`.claude/memory/MEMORY.md` 는 사용자 파일이라 `.new` 를 만들지 않는다.

선택은 `.claude/.scaffold.json` 에서 읽는다. 이 파일이 없으면(1.0.0 이전 설치이거나 지운 경우) forge·스택·언어·
하네스를 프로젝트에서 추론하고 첫 줄에 `(inferred)` 를 찍는다. 그 줄을 확인하고, 추론이 틀렸으면 옵션을 명시한다.
명시한 값은 그때 기록된다.

## AGENTS.md.bak 파일

**설치 스크립트**(`--update` 가 아니다)를 기존 프로젝트에 다시 돌리면 `AGENTS.md` 를 새로 만든다. 기존
`AGENTS.md` 가 새로 만든 것과 다르면 먼저 백업한다.

```console
== your previous AGENTS.md differed from the generated one — saved as AGENTS.md.bak-20261110-154053 (merge what you need back) ==
```

`.bak` 파일에서 직접 쓴 섹션(프로젝트 개요·스택·명령, 그 밖에 추가한 내용)을 `AGENTS.md` 로 옮기고 `.bak` 을
지운다. `AGENTS.md` 를 새로 만들지 않고 기존 설치만 갱신하려면 `--update` 를 쓴다. 일반 설치에 `--dry-run` 을
붙이면 이미 있고 내용이 다른 파일을 쓰기 전에 보여준다.

## 심볼릭 링크를 못 만든다 (Windows)

```console
Warning: symlink unavailable — .claude/skills is a copy of .agents/skills.
  Edit .agents/skills only; the pre-commit gate blocks a commit whose staged copy drifts.
```

스킬 원본은 `.agents/skills` 이고, Claude Code 는 심볼릭 링크 `.claude/skills` 로 같은 파일을 읽는다. 링크를
만들 수 없는 환경(Windows Git Bash 기본값)에서는 사본을 만든다. 동작은 같고 규칙이 하나 생긴다. 스킬은
`.agents/skills` 에서 고치고, 같은 경로의 `.claude/skills` 에 복사해 둘을 함께 스테이징한다. 두 쪽이 다른 커밋은
게이트가 막는다.

링크로 되돌리려면 링크를 만들 수 있게 한 뒤(Windows: 개발자 모드, `git config core.symlinks true`, Git Bash 에서
`export MSYS=winsymlinks:nativestrict`) `--update` 를 돌린다. 링크를 만들 수 있으면 사본을 링크로 바꾼다.
어느 환경에서든 사본 모드를 쓰려면 `AGENTS_SCAFFOLD_NO_SYMLINK=1` 로 설치한다.

비슷한 경우가 하나 더 있다. `core.symlinks=false` 로 clone 하면 링크가 작은 일반 파일로 체크아웃된다. Claude Code 는
스킬을 찾지 못하고 게이트가 `Warning: .claude/skills is a plain file` 을 찍는다. `core.symlinks` 를 켜고 그 경로를
다시 체크아웃한다. 자세한 내용은 [OFFLINE_INSTALL.md](OFFLINE_INSTALL.md)에 있다.

## 모르는 스택

```console
Error: unknown stack 'nextj'. Available: android, bun, dotnet, flutter, go, javaweb, nextjs, ops, php-laravel, python, ruby-rails, rust, springboot
```

`--stack` 이름을 틀리면 exit 1 로 멈추고 아무것도 쓰지 않는다(예전에는 경고만 하고 그 스택의 게이트 없이 설치를
끝냈다). 올바른 이름은 `--list-stacks` 가 한 줄에 하나씩 찍는다. 여러 스택은 공백 없이 쉼표로 잇는다:
`--stack nextjs,python`.

## Codex 와 Antigravity 의 한계

설치 실패가 아니라 하네스의 실측 한계이고, [harness-matrix.json](harness-matrix.json) 에 기록돼 있다. 두 하네스
모두 `AGENTS.md` 와 git 게이트는 성립한다.

- **Codex 는 신뢰한 프로젝트에서만 `.codex/` 를 읽고**, 훅은 훅 정의를 검토(`/hooks`)한 뒤에만 실행한다. 그 전에는
  생성된 서브에이전트와 훅이 동작하지 않는다.
- **Codex 에는 파일 경로 조건부 지침이 없다.** `.claude/rules` 의 `paths:` 룰이 닿지 않는다. 선택한 스택의 P0 를
  `AGENTS.md` 본문에 직접 넣는 이유다.
- **Antigravity 1.5.0 은 `.agents/rules` 의 `trigger: glob` 룰을 로드하지 않는다.** 일치하는 파일을 읽은 뒤에도
  그렇다(`always_on` 룰은 로드된다). Antigravity 가 baseline 등급인 이유다.
- **Antigravity 는 레포의 `.agents/hooks.json` 을 신뢰 확인 없이 실행한다.** 직접 만들지 않은 레포에서 agy 를
  돌리기 전에 그 파일을 읽어 본다.

## 제거

```bash
../agents-scaffold/bin/agents-scaffold.sh --uninstall . --dry-run   # list what would be removed and kept
../agents-scaffold/bin/agents-scaffold.sh --uninstall . --yes
```

`--uninstall` 은 기록된 선택으로 설치했을 결과를 다시 만들고, 그것과 아직 같은 파일만 지운다. `--yes` 가 없으면
확인을 받고, 물어볼 터미널이 없으면 거부한다.

다음은 남겨 두므로 직접 판단한다.

- 사용자가 고친 파일. 남긴 목록으로 보여준다. 필요 없으면 직접 지운다.
- `.claude/memory/`. 프로젝트 메모리는 지우지 않는다.
- `AGENTS.md.bak-*`·`*.new` 파일과 `.gitattributes` 에 추가된 훅 관련 줄.
- 스캐폴드의 한 줄 말고 다른 내용이 있는 pre-commit 훅. 게이트를 기존 훅이나 husky 에 이어 붙였다면 그 줄을 직접
  지운다. 지우지 않으면 다음 커밋이 없는 스크립트 때문에 실패한다.

스캐폴드가 만든 `.git/hooks/pre-commit` 은 지워지므로 이 clone 에서는 게이트가 멈춘다. 다른 clone 의 훅 파일은
각자 지울 때까지 남는다.
