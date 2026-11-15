---
name: reference_repo-search-and-install-traps
description: 이 레포에서 검색·설치 실측을 할 때 결과를 틀리게 만드는 함정 — rg 는 .claude/ 를 기본으로 건너뛰고, 설치기는 git ls-files 만 복사한다 (2026-11-05)
metadata:
  type: reference
---

- **rg 는 숨김 폴더를 기본으로 건너뛴다.** 이 레포는 핵심이 `.claude/` 에 있다. 2026-11-05 기준 "게이트" 가 `rg -l` 로는 35개 파일에서 나왔지만, 실제로는 85개 파일(`git ls-files` 기준)에 있었다. 이 레포를 검색할 때는 `rg --hidden` 을 쓰거나 `git grep` 을 쓴다.
- **설치기(`bin/agents-scaffold.sh`)는 `git ls-files -- .claude` 목록만 복사한다**(`list_claude_files`). 그래서 새로 만든 훅·스크립트를 스테이징하기 전에 설치 산출물로 실측하면 그 파일이 빠진다. 2026-11-04 #94 에서는 `personal-gate.sh` 가 빠졌고, agy 가 훅 실행 실패(exit 127)로 모든 툴을 막았다. 실측 전에 `git add` 부터 한다.
- **플러그인 생성기(`scripts/dev/build-plugins.py`)도 git 이 추적하는 파일만 복사한다.** 2026-11-13 #117 에서 새 `go/` 폴더를 스테이징하기 전에 돌리자 플러그인 사본에서 빠졌다. 새 파일은 `git add` 한 뒤 생성기를 돌린다. 파일 권한(실행 비트)을 바꾼 뒤에도 다시 돌려야 `--check` 가 통과한다.
- **zsh 는 `$files` 를 단어로 나누지 않는다.** `git add -- $files` 는 목록 전체를 경로 하나로 넘겨 실패한다. 같은 줄을 `;` 로 `git commit` 에 이으면 이미 스테이징된 일부만 커밋된다(2026-11-13 두 번 겪음). 목록은 `git add --pathspec-from-file=<파일>` 로 넘기고, `git status --porcelain` 에서 이미 스테이징된 삭제(`D `)는 빼야 한다(경로가 없어 pathspec 오류). 커밋은 스테이징 확인 뒤 따로 실행한다.
- **`bats --jobs N` 은 GNU parallel 이 필요하다.** 이 맥에는 없어서 "Executed 0 instead of expected 110 tests" 를 내고 exit 1 로 끝난다. 병렬 옵션 없이 돌린다.
- 토큰을 줄이는 데는 검색 엔진보다 출력 방식이 더 크게 작용한다. 같은 질의에서 `rg -n` 은 19 KB, `rg -l` 은 1.8 KB, FTS5 상위 5개는 0.3 KB 였다. 6 MB 규모에서 rg 는 약 13 ms, 파이썬 FTS5 CLI 는 약 15 ms(그중 10 ms 가 인터프리터 시작)로 속도 차이는 없다.

관련: [[reference_harness-config-contracts]]
