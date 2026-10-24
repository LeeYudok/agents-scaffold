# Forge 워크플로 — GitLab

<!-- paths 없음 → 항상 로드. forge-gitlab 프리셋이 주입. -->

이 프로젝트는 **GitLab** 을 이슈/MR forge 로 쓴다.

- **CLI**: `glab` (issue/mr)
- **이슈 등록**: `glab issue create -t "<제목>" -d "<본문>" -y`
- **이슈 확인**: `glab issue view <N>`
- **MR 생성**: `glab mr create -t "<제목>" -d "Closes #<N>" --fill -y`
- **머지 후 이슈 클로즈 확인**: GitLab 19 에서 MR 본문 `Closes #N` 자동 클로즈는 정상 동작한다(실측). 단 단정하지 말고 머지 직후 `glab issue view <N>` 의 `state` 를 확인 — `opened` 로 남아 있으면 그때 `glab issue note <N>` + `glab issue close <N>` 수동 클로즈.
- **머지 자체도 확인**: `glab mr merge` 는 main 이동 직후 405 로 일시 실패하면서 필터된 출력에선 성공처럼 보일 수 있다 — 브랜치/워크트리 정리 전 `glab mr view <N>` 이 `state: merged` 인지 확인하고, 아니면 수 초 뒤 재시도.
- **리뷰·머지**: `glab mr merge --squash`
- **긴 본문**: fenced code·표·백슬래시 포함 본문은 파일로 먼저 쓰고 `glab issue create -d "$(cat body.md)"` / API `-F description=@body.md`(인라인 escape 실패·ARG_MAX 회피).
