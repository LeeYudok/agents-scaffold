---
name: yd-agents-mem
description: 에이전트 메모리·전역 지침·설정을 GitLab agents-mem 레포에 백업하고 되돌린다. 전역 CLAUDE.md·infra-*.md·ref-*.md·프로젝트 메모리·스킬·에이전트·settings 를 고친 뒤 미러를 갱신할 때, 다른 호스트가 바꾼 전역 지침을 받을 때, 새 머신을 복원할 때 사용한다. "메모리 백업", "미러 갱신", "agents-mem 싱크", "sync_memory", "전역 지침 동기화" 요청에 쓴다. 메모리 내용이 맞는지 감사하는 일은 memory-factcheck 를 쓴다.
---

# yd-agents-mem — 에이전트 자산 백업

에이전트 4종(claude·codex·gemini·antigravity)의 메모리와 설정을 `agents-mem` 레포에
호스트별로 미러한다. 이 스킬은 **언제 무엇을 돌리는지**만 정한다. 동작 원리와 디렉터리
신뢰 등급의 원본은 레포의 `CLAUDE.md` 다. 둘이 어긋나면 레포가 옳다.

| 항목 | 값 |
|---|---|
| 레포 | 전역 지침(`~/.claude/CLAUDE.md`)의 agents-mem 항목이 가리키는 GitLab 레포 |
| 로컬 경로 | 그 레포의 클론 (아래 명령의 `$AGENTS_MEM_DIR`) |
| 미러 위치 | `hosts/<이 호스트>/` — 호스트명은 `AGENTS_MEM_HOST` → `LocalHostName` → `hostname -s` |
| 전역 지침 공통본 | `shared/claude/global/` (CLAUDE.md·infra-*.md·ref-*.md, 3-way 동기화) |
| 상시 이슈 | agents-mem 레포의 "메모리 미러 동기화(상시)" 이슈 |

## 언제 돌리나

| 상황 | 할 일 |
|---|---|
| 전역 지침(`~/.claude/CLAUDE.md`·`infra-*.md`·`ref-*.md`)을 고쳤다 | 동기화 + 커밋 |
| 프로젝트 메모리(`~/.claude/projects/*/memory/`)를 추가·수정했다 | 동기화 + 커밋 |
| 전역 스킬·에이전트·`settings.json`·훅을 바꿨다 | 동기화 + 커밋 |
| 다른 호스트에서 전역 지침을 바꿨다고 들었다 | `git pull` 후 동기화 |
| 새 머신이다 | 복원 (아래) |

세션 끝에 몰아서 하지 않는다. 고친 직후 돌려야 다른 호스트·다른 에이전트가 바로 받는다.

## 동기화

레포 루트에서 실행한다.

```bash
cd "$AGENTS_MEM_DIR"
git pull -q
scripts/sync_memory.sh --dry-run     # 무엇이 바뀌는지 먼저 본다
scripts/sync_memory.sh
git status --short | head -30
```

- `sync_memory.sh` 는 먼저 `sync_global.sh` 로 전역 지침을 공통본과 3-way 로 맞추고, 이어서 자기 호스트 디렉터리만 미러한다. **충돌 경고가 나오면 멈추고** 해당 파일을 사용자에게 보여준다. 양쪽 다 그대로 남아 있으므로 손으로 합친다.
- 원천 어디에도 없는 파일은 경고만 하고 지우지 않는다. 미러가 유일본일 수 있다. 진짜 지울 것인지는 사용자가 정한다.
- 심링크 자산(스킬 원본(`agents-scaffold`)을 가리키는 스킬·에이전트)은 내용을 복사하지 않고 `links.tsv` 에 대상 경로만 남긴다. 스킬 내용의 원본은 `doksam-skills` 레포다.

## 커밋

1. **시크릿 스캔을 먼저 한다.** 걸리면 커밋하지 않고 멈춘다. **걸린 줄을 출력하지 않는다** —
   진짜 토큰이면 값이 터미널과 로그에 남는다. 건수와 파일 이름만 본다.

   ```bash
   git add -- hosts/<호스트> shared
   python3 <스킬경로>/scripts/scan_secrets.py --staged
   ```

   스캐너는 스테이징된 **추가 줄**만 보고 `파일:줄 [패턴]` 과 건수만 낸다. 자격증명 파일
   (`oauth_creds`·`auth.json`)과 다른 호스트 디렉터리(`hosts/<다른 호스트>/`·`hosts/_legacy-shared/`)
   변경도 이름만으로 막는다. `exit 0` 이어야 커밋한다. `exit 2` 는 스캔을 못 했다는 뜻이라
   통과가 아니다. 값이 `<`·`$`·`(` 로 시작하면 자리표시자나 변수 참조로 보고 넘긴다.
   이미 커밋된 미러 전체를 점검할 때는 `--tree hosts/<호스트>` 를 쓴다. 이때도 줄 번호만 낸다.

   걸린 파일은 값을 출력하지 않는 방법으로 확인한다(키 이름만: `grep -oE '^[A-Za-z_]+\s*[:=]'`).
   실제 시크릿이면 스테이징을 풀고 사용자에게 알린다. 이미 푸시했다면 회전(rotate)을 권한다.

2. main 직접 커밋이 허용되는 예외다. 제목 규칙은 지킨다. 무엇이 바뀌었는지 한 구절을 붙인다.

   ```bash
   git -c user.name=claude-ai -c user.email=claude-ai@<도메인> commit -m "[<모델명>] chore: sync memory mirror — <바뀐 것 한 구절> (#<상시 이슈>)"
   git push -q
   ```

3. 상시 이슈는 닫지 않는다.

## 새 머신 복원

```bash
scripts/restore_memory.sh --dry-run                 # 매핑 확인
scripts/restore_memory.sh                           # 현재 호스트 미러에서
scripts/restore_memory.sh --host=<name> --dry-run   # 다른 호스트 미러로 시드
scripts/sync_global.sh --adopt-shared               # 이 호스트 첫 도입 (로컬은 *.pre-shared.bak 백업)
```

- 실제 홈을 건드리지 않고 시험하려면 `HOME=<빈 디렉터리> scripts/restore_memory.sh` 로 돌린다.
- redact 된 값(MCP 토큰 등)은 복원되지 않는다. 출력에 나온 목록을 사용자에게 넘긴다.
- 복원 뒤 `agents-scaffold` 의 `scripts/install-skills.sh --with-agent` 와 `--verify` 로 스킬 링크를 다시 맞춘다. 미러는 링크 대상만 기록하기 때문이다.
- `npx skills` 로 설치한 외부 스킬은 미러에 내용이 없다. 실체가 `~/.agents/skills/` 에 있고 미러는 그 링크만 남긴다. 아래 명령으로 다시 설치한다. 이미 검토·승인한 스킬이므로 `-y` 를 쓴다.

  ```bash
  # find-skills (vercel-labs/skills, MIT) — 2026-10-04 검토·승인
  npx skills add vercel-labs/skills -s find-skills -g -a claude-code codex antigravity antigravity-cli -y
  ln -sfn ~/.agents/skills/find-skills ~/.gemini/config/skills/find-skills
  ```

  새 외부 스킬도 이 목록에 더할 수 있다. 그 전에 전역 지침대로 SKILL.md·scripts 를 검토하고 사용자 승인을 받는다.

## 하지 않는 것

- 다른 호스트 디렉터리(`hosts/<다른 호스트>/`)와 `hosts/_legacy-shared/` 를 손으로 고치지 않는다.
- 자격증명(oauth_creds·auth.json·PAT)을 어떤 경로로도 커밋하지 않는다.
- 메모리 내용이 사실과 맞는지 판정하지 않는다. 그건 `memory-factcheck` 몫이다.
- 백업 대상 자산을 늘릴 때는 `scripts/lib.sh` 의 목록만 고친다. 그 작업은 agents-mem 레포의 일반 이슈·MR 절차를 따른다.

## Learned warnings

- (2026-10-05) macOS `LocalHostName` 에 대문자가 있으면(예: `MyMac-Pro`) sync 는 소문자 폴더 `hosts/mymac-pro/` 에 쓴다. `scan_secrets.py` 는 호스트명을 소문자로 바꾸지 않아 그 폴더를 "다른 호스트"로 막았다(위반 21건, exit 1). `resolve_host()` 가 소문자로 맞추도록 고쳤다. 옛 스캐너에서 같은 증상이 나오면 `AGENTS_MEM_HOST=<소문자 호스트명>` 으로 호스트를 지정해 우회한다 (#208).
