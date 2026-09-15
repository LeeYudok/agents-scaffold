---
name: preset-gate-verification
description: 스택 프리셋 pre-commit 게이트를 로컬에 툴체인 없이 검증하는 법과, bats 에 "정상 통과" 케이스를 넣으면 안 되는 스택 조건
metadata:
  type: project
---

새 스택 프리셋(`presets/<stack>/.claude/hooks/pre-commit.partial.sh`)의 실동작은
**PATH 앞에 가짜 툴 바이너리를 깔아** 검증한다. 스크래치 레포를
`bin/agents-scaffold.sh <dir> --stack <stack>,bun --yes` 로 부트스트랩하고,
`$SCRATCH/bin/<tool>` 에 서브커맨드별 exit code 를 흉내내는 셸 스크립트를 둔 뒤
`PATH="$SCRATCH/bin:$PATH" bash .claude/hooks/pre-commit.sh` 로 정상/빌드실패/포맷불일치
각각의 exit code(0/2/2)를 실측한다. 2026-08-30 #7 dotnet 프리셋에서 로컬에 .NET SDK 가
없는 채로 이 방식으로 게이트 3분기를 전부 확인했다.

bats 케이스는 반대로 **툴체인이 GitHub Actions 러너에 기본 설치된 스택**(dotnet, go,
java 등)에서 "게이트가 통과한다" 케이스를 넣으면 안 된다 — 가짜 fixture 프로젝트에
실제 빌드가 돌아 CI 에서만 exit 2 가 난다. 넣을 수 있는 결정적 케이스는
① 시크릿 파일 스테이징 차단(툴 존재 확인보다 앞에서 실행), ② 프로젝트 파일이 없을 때
no-op, ③ 다른 스택과 조합 시 양쪽 파셜 스플라이스([[readme-multilang-sync]] 와 함께
`docs/OPTIONS.*` 4종·README 4종 갱신도 같은 커밋).

**Why**: 게이트 파셜은 exit 경로가 핵심인데(#6 회귀 클래스), 로컬에 SDK 가 없으면
"skipping" 분기만 밟혀 아무것도 검증되지 않는다.
**How to apply**: 프리셋 PR 전 가짜 바이너리로 실패 분기 exit 2 를 확인하고, bats 에는
툴체인 비의존 케이스만 남긴다.
