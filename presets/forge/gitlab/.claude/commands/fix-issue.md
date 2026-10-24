---
name: fix-issue
argument-hint: [issue-number]
---

GitLab 이슈 #$ARGUMENTS 를 처리한다(이슈 우선 워크플로):

1. `glab issue view $ARGUMENTS` — 이슈 내용 확인
2. 관련 소스 파일 탐색
3. 브랜치 생성: `git checkout -b fix/issue-$ARGUMENTS-<요약>`
4. 최소 수정 구현 + 회귀 테스트 작성
5. 빌드/테스트 그린 확인(`./gradlew test` 또는 `npm test`)
6. 커밋(`#$ARGUMENTS` 참조) → push → MR 생성 → squash 머지
7. **머지 후 클로즈 확인**: `glab issue view $ARGUMENTS` 로 상태 확인 — `Closes #N` 자동 클로즈가 정상 동작하므로, `opened` 로 남은 경우에만 `glab issue note $ARGUMENTS` + `glab issue close $ARGUMENTS`
