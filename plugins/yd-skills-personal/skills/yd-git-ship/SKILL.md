---
name: yd-git-ship
description: 'GitLab 레포에 에이전트(Claude Code·Codex·Antigravity)가 작업을 올리는 절차 — 이슈 등록, batch/<agent>-<날짜>-<8자리 hex> 브랜치, "[<model>] <type>: <desc> (#N)" 커밋, Closes MR, merge commit(squash 금지), CI 추적, commit-msg hook 설치. "커밋", "푸시", "MR", "머지", "올려", "이슈 등록", "ship" 등 git/GitLab 에 뭔가 남길 때마다 사용.'
---

# yd-git-ship — 에이전트 작업을 GitLab 에 올리기

규칙 원본은 `~/.claude/ref-git-agents.md` (세 에이전트 공통, agents-mem 의 공통본을 각 호스트에 동기화). 이 스킬은 그 규칙을 따르는 **절차와 도구**다. 규칙과 이 문서가 다르면 원본이 우선한다. 원본 파일이 없는 환경(새 머신, 외부 설치)에서는 이 문서의 절차가 곧 규칙이다.

스크립트 위치: 이 스킬 폴더의 `scripts/` (Claude `~/.claude/skills/yd-git-ship`, Codex `~/.agents/skills/yd-git-ship`, Antigravity `~/.gemini/config/skills/yd-git-ship` — 모두 doksam-skills `install.sh` 가 건 같은 원본의 심링크).

## 0. 내 값 정하기

| | Claude Code | Codex | Antigravity |
|---|---|---|---|
| `AGENT` | `claude` | `codex` | `agy` |
| 커밋 `-c` | `user.name=claude-ai user.email=claude-ai@<도메인>` | `codex-ai` / `codex-ai@<도메인>` | `agy-ai` / `agy-ai@<도메인>` |
| 모델 태그 | 지금 도는 모델 이름, 예 `[Claude Opus 5.5]` | 예 `[GPT-6 Sol]` | 예 `[Gemini 3.8 Flash]` |

모델 태그는 추측하지 말고 자기 시스템 정보에 적힌 실제 모델명을 쓴다.

```bash
SK=~/.claude/skills/yd-git-ship/scripts      # 에이전트별 경로로
GL="$SK/glab-as.sh claude"                  # 토큰을 출력하지 않고 자기 계정으로 glab 실행
REPO=<gitlab-host>/<ns>/<repo>          # -R 에는 호스트까지 붙인다. 명령은 그 레포 폴더 안에서
$GL api user | grep '"username"'            # claude-ai 인지 확인
```

`glab-as.sh` 는 Python 3.11 미만(tomllib 없음)에서도 요청한 계정 섹션의 토큰만 읽는다. 호출한 셸의 PATH 에 따라 시스템 Python 3.9 가 잡혀도 동작한다.

## 1. 시작 전 점검

```bash
git status -sb; git branch --show-current
$GL api "projects/<ns>%2F<repo>/merge_requests?state=opened&author_username=claude-ai"   # 내 열린 MR 있으면 그것부터 머지
$GL api "projects/<ns>%2F<repo>" | python3 -c 'import json,sys;p=json.load(sys.stdin);print(p["squash_option"],p["merge_method"])'
$SK/install-hook.sh --check || $SK/install-hook.sh   # 없으면 설치 → scripts/commit-msg.sh 를 첫 커밋에 포함
```

- `squash_option` 이 `always` 면 squash 금지 규칙과 충돌하니 사용자에게 알린다. `merge_method` 가 `ff` 면 merge commit 이 안 생기니 역시 알린다.
- 레포 AGENTS.md 에 "squash 머지" 같은 옛 문구가 있으면 원본 규칙이 우선이고, 이번 배치에서 같이 고친다.
- hook 은 본문의 `Co-Authored-By: Claude` 와 `Generated with Claude Code` 줄을 사람 커밋이어도 거부한다. `Merge` 로 시작하는 제목은 형식 검사에서 뺀다.
- jj 레포(`.jj/`)는 `jj commit` 이 git hook 을 안 돌린다. 커밋 제목을 직접 맞추고 push 전 `git log` 로 확인한다.

## 2. 이슈

작업 단위마다 이슈. 본문은 파일로 쓰고 "누가 판정하나"를 넣는다.

```bash
$GL issue create -R $REPO --title "..." --description "$(cat body.md)" --yes
```

## 3. 배치 브랜치 · 커밋 · push

```bash
git switch main && git pull -q
git switch -c "batch/claude-$(date +%Y%m%d)-$(openssl rand -hex 4)"   # 배치마다 새 8자리 hex
BR=$(git branch --show-current)                    # 셸 상태가 안 이어지면 쓸 때마다 이렇게 다시 읽는다
git add <명시 파일만>                               # -A 금지, .env 금지
if git diff --cached | grep -iE 'glpat-|ghp_|password[[:space:]]*[:=]|secret[[:space:]]*[:=]|token[[:space:]]*[:=]'; then
  echo "시크릿 의심 — 커밋하지 않고 멈춘다(값을 확인하고 스테이징에서 뺀다)"
else
  git -c user.name=claude-ai -c user.email=claude-ai@<도메인> commit -m "[Claude Opus 5.5] docs: ... (#N)" \
    && git push -u origin HEAD                     # 수시로 push, MR 은 아직
fi
```

- 브랜치는 `batch/<agent>-<YYYYMMDD>-<8자리 hex>` 다. hex 는 배치를 시작할 때 `openssl rand -hex 4` 로 한 번 만들고 MR·정리까지 같은 이름을 쓴다.
  날짜 뒤 `-2`·`-3` 순번은 쓰지 않는다. 같은 에이전트의 세션 둘이 같은 순번을 골라 겹친다(아래 Learned warnings).
- 머지하며 지운 브랜치 이름을 다시 push 하지 않는다. 다음 배치는 새 hex 로 시작한다.
- 이슈별로 커밋을 나눈다(merge commit 으로 합쳐도 이슈 단위 `git revert` 가 되게).
- hook 이 막으면 메시지를 고친다. `--no-verify` 로 우회하지 않는다(오타 수준만 `YD_TRIVIAL=1`).

## 4. MR · 머지

```bash
$GL mr create -R $REPO --source-branch "$(git branch --show-current)" --target-branch main \
  --title "[Claude Opus 5.5] <요약>" --description "$(cat mr.md)" --remove-source-branch --yes
# mr.md 에 반드시: Closes #a #b ...   (Refs 만 쓰지 않는다)
$GL mr merge <iid> -R $REPO --remove-source-branch --yes        # --squash 붙이지 않는다
```

- push 직후 `mr merge` 가 `405 Method Not Allowed` 면 GitLab 이 아직 mergeability 를 계산 중이다(`detailed_merge_status: checking`). `mergeable` 이 될 때까지 몇 초 기다렸다가 다시 머지한다.
- 이슈를 닫으면 안 되는 부분 작업이면, 그 부분만 다루는 이슈를 새로 만들어 `Closes` 한다.
- 다른 에이전트가 먼저 머지해 충돌나면 `git merge origin/main` 으로 풀고 push (rebase·force push 금지).
- glab 은 **그 레포 폴더 안에서** 실행하고 출력을 `| tail` 로 자르지 않는다. `mr create` 는 현재 폴더의 remote 를 source 로 잡아서, 다른 폴더에서 돌리면 `422 Source project is not a fork` 가 나는데 `tail` 이 그걸 가린다. 실패하면 `--recover` 로 재시도.

## 5. 머지 후

```bash
$GL api "projects/<ns>%2F<repo>/merge_requests/<iid>" | python3 -c 'import json,sys;m=json.load(sys.stdin);print(m["state"],m["merge_commit_sha"],m["squash"])'
python3 $SK/ci_wait.py --agent claude <ns>/<repo> <merge_commit_sha>   # run_in_background 로. 배포 잡까지 끝나야 완료
$GL api "projects/<ns>%2F<repo>/issues/<N>" | grep '"state"'   # opened 면 note + close
BR=$(git branch --show-current); git switch main && git pull -q && git branch -d "$BR"
git log -1 --format='%an %s'                                   # 작성자·태그 확인
```

`ci_wait.py` 종료 코드는 0 성공(또는 파이프라인 없음), 1 실패·취소, 2 시간 초과, 3 도구 오류(glab 실패·토큰 없음)다. 3 을 CI 실패로 읽지 말고 토큰·네트워크부터 확인한다.

`m["squash"]` 가 true 면 규칙 위반이다. 사용자에게 보고한다(되돌리려면 force push 가 필요하므로 임의로 고치지 않는다).

## 메모리 미러처럼 코드 없는 운영 갱신

main 직접 커밋이 허용되는 예외지만 제목 규칙은 지킨다: `[Claude Opus 5.5] chore: sync memory mirror (#N)`.

## Learned warnings

- (2026-10-05) 같은 에이전트(claude)의 세션 두 개가 같은 날 각자 `batch/claude-20261005-8` 을 골랐다. 한쪽이 llmgw#57 을 머지하며 브랜치를 지웠다. 직후 다른 쪽이 같은 이름으로 같은 기능을 push 했다. 작업이 중복되고 MR(!46)이 충돌로 남았다. 날짜 뒤 순번 대신 배치마다 `openssl rand -hex 4` 8자리를 붙인다 (#205).
