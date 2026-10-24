
**bun**

- 시크릿(키/토큰/비밀번호) 코드 내 하드코딩 절대 금지
- 커밋 전 `bunx tsc --noEmit` 통과 필수
- `.env` 파일 git 스테이징 금지 (pre-commit 훅이 차단)
