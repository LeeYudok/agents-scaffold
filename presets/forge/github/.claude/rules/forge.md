# Forge 워크플로 — GitHub

<!-- paths 없음 → 항상 로드. forge-github 프리셋이 주입. -->

이 프로젝트는 **GitHub** 을 이슈/PR forge 로 쓴다.

- **CLI**: `gh` (issue/pr)
- **이슈 등록**: `gh issue create -t "<제목>" -b "<본문>"`
- **이슈 확인**: `gh issue view <N>`
- **PR 생성**: `gh pr create --fill --body "Closes #<N>"`
- **자동 클로즈**: PR 본문/커밋 메시지의 `Closes #N`(또는 `Fixes`/`Resolves`)로 **머지 시 이슈가 자동으로 닫힌다** — 수동 클로즈 불필요.
- **리뷰·머지**: `gh pr merge --squash`
- **긴 본문**: fenced code·표·백슬래시 포함 본문은 파일로 먼저 쓰고 `gh issue create -F body.md` / `gh pr create -F body.md`(인라인 escape 실패·ARG_MAX 회피).
