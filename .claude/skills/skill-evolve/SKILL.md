---
name: skill-evolve
description: 사용자 피드백이나 에이전트의 실패 사례를 이 저장소 스킬의 SKILL.md 규칙으로 반영하는 메타 스킬. "스킬 고쳐줘", "이 실수 스킬에 박아줘", "다음부터 안 그러게 스킬에 반영해", "/skill-evolve <스킬명> <피드백>" 같은 요청이나, 같은 실수가 두 번 나와 스킬 문서를 고쳐야 할 때 사용한다. 이슈 등록 → batch 브랜치 → 테스트 → 사용자 승인 → 커밋 순서로 진행한다.
---

# Role

당신은 에이전트의 실패 경험과 사용자의 피드백을 구조적인 지침으로 변환해 스킬을 진화시키는 **메타 에이전트**다. 한 번 저지른 실수를 두 번 다시 반복하지 않도록 스킬 문서(`SKILL.md`)에 교훈을 영구히 각인한다. 
단순한 텍스트 수정을 넘어, **격리된 브랜치 생성, 규약 강제 검증, 확인 후 적용**이라는 전문가 수준의 안전한 워크플로우를 관장한다.

# 트리거

`/skill-evolve <스킬명> <피드백>`

# Workflow

아래 절차를 엄격하게 순서대로 수행한다. 건너뛰는 단계는 없다.

## Phase 1. 진단 및 격리

1. **상태 점검**: 현재 워킹 트리가 깨끗한지(`git status -s`가 비어 있는지) 확인한다. `python3 <스킬경로>/scripts/evolve_guard.py clean` 이 같은 일을 하며, 비어 있지 않으면 exit 1 로 변경 목록을 보여 준다.
2. **이슈 먼저**: 저장소 트래커에 이슈를 만든다. 본문에 피드백 원문, 고칠 스킬, 누가 판정하는지를 적는다. 이 번호를 브랜치·커밋·PR 에 쓴다.
3. **브랜치**: `main` 에 직접 커밋하지 않는다. 진행 중인 배치 브랜치(`batch/<에이전트>-<YYYYMMDD>-<8자리 hex>`)가 있으면 거기에 얹고, 없으면 `main` 에서 새로 만든다. hex 는 `openssl rand -hex 4` 로 배치마다 새로 만든다(yd-git-ship 과 같은 규칙 — 순번 `-2` 는 세션끼리 겹친다).
4. **대상 읽기**: `.claude/skills/<스킬명>/SKILL.md`(옵트인 스킬은 `presets/skills/personal/.claude/skills/<스킬명>/SKILL.md`) 전체를 읽어 현재 내용을 파악한다. 설치된 프로젝트에서는 `.agents/skills/<스킬명>/SKILL.md` 가 원본이고 `.claude/skills` 는 그 링크다.

## Phase 2. 분석 및 규칙 제정

피드백과 최근 실행 로그를 분석해 **무엇이 문제였는지, 앞으로 어떻게 행동해야 하는지** 명확한 규칙(Rule)으로 도출한다.
- 새로운 gotcha(자주 하는 실수)는 `### Learned warnings` 섹션에 추가한다.
- 기존 절차의 결함이라면 프로세스 섹션을 업데이트한다.
- 잘못된 명령어 템플릿이 있다면 수정한다.

## Phase 3. 문서 수정 (엄격한 편집 규칙)

저장소의 스킬 규약(`.claude/skills/README.md`)을 어기지 않도록 다음 원칙을 준수하여 `SKILL.md`를 편집(도구 활용)한다.
- **Frontmatter 유지**: 원래 없던 키를 임의로 추가하지 않는다. 새 스킬은 `name`·`description` 만 쓴다(기존 스킬에 이미 있는 `user-invocable` 등은 유지).
- **이모지 금지**: 산출물 및 스킬 문서 내에 이모지 사용을 엄격히 금지한다.
- **기존 경고 보존**: `Learned warnings`의 기존 경고는 명시적으로 무효화된 것이 아니면 삭제하지 않고 누적한다. 날짜 태그(`(YYYY-MM-DD)`)를 반드시 포함한다.
- 편집은 `replace_file_content` 등의 정확한 파일 편집 도구를 사용해 반영한다.

편집을 마치면 `python3 <스킬경로>/scripts/evolve_guard.py check <스킬명>` 으로 위 규칙을 기계적으로 확인한다.

- `Learned warnings` 줄은 `- (YYYY-MM-DD) ...` 형식이어야 하고, 달력에 없는 날짜는 위반이다.
- 기준(`--base`, 기본 `HEAD`)에 있던 경고가 사라졌으면 위반이다. 사용자가 명시적으로 무효화한 경고라면 `--allow-removal` 을 붙인다.
- 새 경고를 넣는 작업이면 `--require-section` 으로 섹션이 있는지도 본다.
- 위반이 있으면 exit 1 이다.
- 스킬 이름이 없거나 경로를 벗어나면 exit 2 이다.

## Phase 4. 자동 검증 (핵심 로직)

문서 수정을 디스크에 반영한 직후, **반드시 저장소 테스트를 실행**하여 구조적 규약(Frontmatter, 문서 단언과 claims, 레이아웃 등)을 깨뜨리지 않았는지 기계적으로 확인한다. 이 저장소는 `scripts/dev/run-skill-tests.sh`(스킬별 테스트)와 `python3 -m unittest discover -s tests -p 'test_*.py'`(공통 규약)이고, 다른 저장소는 그 저장소의 실행기(`scripts/run_tests.sh` 등)다.
- 테스트가 실패하면(exit code > 0), **이 스킬이 고친 파일만** 되돌린다(`git restore -- <그 스킬의 SKILL.md 경로>`). 경로 없는 `git restore .` 는 다른 변경까지 지운다. `python3 <스킬경로>/scripts/evolve_guard.py verify <스킬명>` 이 테스트 실행과 되돌리기를 한 번에 하고, 실패하면 exit 1 이다. 통과하면 편집을 그대로 둔다. 테스트 실행기를 찾지 못하면 exit 2 이고 편집도 그대로 둔다. 그다음 원인을 분석하고 다시 수정한다. 위반 상태로 다음 단계로 넘어가지 않는다.
- 구조 검증과 별개로 **미니 eval**: 개선 계기가 된 것과 같은 유형의 입력으로 수정된 스킬을 실행해, 개선 전 실패했던 지점이 실제로 고쳐졌는지 전후 비교로 확인한다. (claude-scaffold 동명 스킬에서 체리픽, 2026-08-16)

## Phase 5. 리뷰 및 커밋

1. 테스트 통과 후 사용자에게 **변경 사항(Diff 요약)**을 명확히 보고하고 커밋 승인을 얻는다.
2. 사용자가 승인(`Y`)하면 고친 파일만 명시해 `git add` 한다(`git add .`·`-A` 금지). 커밋 제목은 `[<모델명>] docs(<스킬명>): <개선 요약> (#N)` 이고, 작성자는 사람이 아니면 에이전트 계정(`-c user.name=claude-ai` 등)이다.
3. 푸시하고 PR(또는 MR)을 연다. 본문에 `Closes #N` 을 넣고, 머지는 merge commit 으로 한다(squash 금지). 저장소 규칙이 별도로 있으면 그것을 따른다.

# 출력 형식

테스트 통과 후 사용자에게 승인을 요청할 때는 아래 형식을 따른다.

```text
개선 제안
기존: [인용]
제안: [수정안]

diff 요약:
+ 추가/수정된 내용 요약
- 삭제된 내용 요약

저장소 테스트 통과 여부: [통과됨]

수정된 내용을 커밋하시겠습니까? (Y/n)
```

## Learned warnings

- (2026-06-20) 외부 `skill-evolve` 스킬 흡수: 기존내용 인용, diff 출력 형식 추가.
- (2026-08-01) doksam-skills 구조에 맞게 대상 파일 경로(`skills/<스킬명>/SKILL.md`) 및 frontmatter 형식(오직 `name`, `description`만 허용) 수정.
- (2026-08-01) **Flawless 업그레이드**: 직접 커밋 방지, 브랜치 격리, 테스트(`run_tests.sh`) 강제 의무화 등 메타 에이전트 워크플로우 적용.
- (2026-10-04) `yd-skill-evolve` 로 이름 변경. `evolve/` 브랜치와 `git add .` 를 버리고 이슈 먼저 → batch 브랜치 → 명시 파일 커밋 → `Closes #N` PR 로 전역 git 규칙에 맞췄다 (#169).
- (2026-10-05) 배치 브랜치 순번(`-2`) 대신 8자리 hex 를 쓴다. 같은 날 세션 둘이 같은 순번을 골라 충돌했다. yd-git-ship 과 같게 맞췄다 (#205).
- (2026-10-24) doksam-skills 가 agents-scaffold 로 합쳐지며 이 스킬이 원본이 됐다. 이름은 `skill-evolve`, 대상 경로는 `.claude/skills/<스킬명>/`·`presets/skills/personal/.claude/skills/<스킬명>/`, 기본 테스트 실행기는 `scripts/dev/run-skill-tests.sh`. 기존 스킬의 frontmatter 키는 유지하고 새 키만 막는다 (agents-scaffold #78).
