---
name: fix-issue
argument-hint: [issue-number]
---

GitHub 이슈 #$ARGUMENTS 를 처리한다(이슈 우선 워크플로):

1. `gh issue view $ARGUMENTS` — 이슈 내용 확인
2. 관련 소스 파일 탐색
3. 브랜치 생성: `git checkout -b fix/issue-$ARGUMENTS-<요약>`
4. 최소 수정 구현 + 회귀 테스트 작성
5. 빌드/테스트 그린 확인(`./gradlew test` 또는 `npm test`)
6. 커밋(`#$ARGUMENTS` 참조) → push → PR 생성(`gh pr create --fill --body "Closes #$ARGUMENTS"`) → `gh pr merge --squash`
7. **자동 클로즈**: PR 본문의 `Closes #$ARGUMENTS` 로 머지 시 이슈가 자동으로 닫힌다. 수동 클로즈 불필요.
