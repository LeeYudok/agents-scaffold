# Memory Index

이 프로젝트 auto-memory SSOT는 `.claude/memory/` (시스템 기본 경로 미사용).
타입접두: `project_`/`feedback_`/`reference_`/`user_`. `user_*`만 개인(gitignore), 그 외 팀 공유.

<!-- 메모리 추가 시 아래에 한 줄씩:
## 프로젝트
- [제목](project_xxx.md) — 한 줄 훅
-->

- [하네스 설정 계약 실측](reference_harness-config-contracts.md) — Claude/Codex/agy 의 설정·디스커버리 경로와 함정(32KiB, trust boundary, PreToolUse 는 강제선 아님, 세 하네스 모두 AGENTS.md 네이티브 로드하나 Claude 는 CLAUDE.md 있으면 무시, 스킬은 Codex·agy=.agents/skills·Claude=.claude/skills, Codex·agy 서브에이전트·훅·경로별 지침 경로와 신뢰 조건, PreCompact 는 prompt 훅 미지원, 2026-11-04 claude 2.1.318·codex 0.166.0·agy 1.5.0 재측정 — agy 1.5.0 glob 룰 회귀로 baseline·Codex 0.166.0 훅 입력 cwd=명령 workdir, 2026-10-24 3사 문서 대조·플러그인 실측(Claude·Codex 공용 .claude-plugin, Codex 는 심링크를 버림, Codex 는 .codex/skills 도 탐색)) + skills CLI(`npx skills`) 탐색·`metadata.internal` 숨김 + 실측 요령(클라우드 프록시는 레포 설정 쓰기 차단)
- [이슈 #20 3자 교차리뷰 결론](project_agents-scaffold-multiagent-review.md) — compile-time emitter 확정, 해시검증 폐기→P0 reachability, 남은 후속 a~c
- [README 다국어 동시 수정](feedback_readme-multilang-sync.md) — README.md 고치면 en/zh/ja 3종도 같은 커밋에서. 언어 간 일치를 검사하는 자동 게이트가 없다
- [이슈 클레임·바운티 정책](project_issue-claim-and-bounty-policy.md) — 외부 `/attempt` 코멘트와 유료 작업 제안에 대한 확정 대응
- [프리셋 게이트 검증법](project_preset-gate-verification.md) — 가짜 툴 바이너리로 exit 분기 실측, bats 엔 툴체인 비의존 케이스만
- [스킬 스니펫의 조용한 실패](feedback_skill-snippet-silent-failure.md) — `2>/dev/null || true`·`a | tail || b` 가 깨진 플래그·폴백을 숨긴다. 스킬 점검 시 억제 떼고 실행 (#57)
- [dotfiles 원본은 이 레포](project_dotfiles-ssot.md) — 2026-10-24 부터 `dotfiles/` 가 SSOT, 옛 LeeYudok/dotfiles 는 보관. CI 는 루트 test.yml dotfiles job (#76)
- [doksam-skills 원본은 이 레포](project_doksam-skills-ssot.md) — 2026-10-24 부터 SSOT. 기본 13(`yd-*`)·옵트인 9(`--with-personal-skills`)·중복 4쌍 병합, 옛 레포 경로 대신 `npx skills add LeeYudok/agents-scaffold`·플러그인 (#78 #102)
- [계약 레벨 품질 수정](feedback_quality-fix-at-contract-level.md) — 산출물 품질 문제는 템플릿 CSS → 검증기 → SKILL.md 순으로 계약에 넣고 콜드 재생성으로 실증
- [UI 한쪽 색 띠 금지](feedback_ui-no-accent-stripe.md) — 카드 가장자리 accent stripe 는 "AI 냄새". 상태는 테두리 색·배지 글자로
- [로컬 HTML 렌더 QA](reference_local-html-render-qa.md) — 생성 HTML 은 headless Chrome 스크린샷으로 검수. 검증기 통과 ≠ 렌더 정상
- [레포 영역 구분](project_layout-zones.md) — 설치 원본(`.claude`·`presets`)·레포 전용(`bin`·`scripts`·메모리)·플러그인 생성물(`plugins/`)·동봉 제품(`dotfiles/`). `.claude/` 에 레포 전용 파일을 두면 `is_repo_private()` 등록 (#80~#82)
- [검색·설치 실측 함정](reference_repo-search-and-install-traps.md) — rg 는 .claude/ 를 건너뛴다(--hidden), 설치기·플러그인 생성기는 git ls-files 만 복사해 미스테이징 파일이 빠진다, zsh `$files` 무분할로 git add 실패, bats --jobs 는 GNU parallel 필요, 토큰은 출력 방식이 좌우
- [cmux 안 claude 래퍼 함정](reference_cmux-claude-shim-traps.md) — cmux 는 PATH 첫 non-shim claude 를 실제로 보고 exec → 래퍼가 cmux shim 으로 되넘기면 무한 루프, 본문의 `exec claude` 류는 재진입 shim 판정, 플래그 수용 실측은 `--version` 말고 `-p ""` (#109)
- [동봉 네이티브 도구는 Go](feedback_native-helper-go-not-rust.md) — 스킬에 넣어 사용자 머신에서 빌드하는 도구는 Rust 말고 Go 표준 라이브러리로. Rust release 빌드 CPU 부하로 사용자가 되돌림 (#117)
- [네이버 블로그 게시 함정](reference_naver-blog-playwright.md) — 절차 원본은 옵트인 스킬 yd-naver-blog(#122). 카테고리 추가는 선택 카테고리 하위로, 새 카테고리는 저장 전 정렬 불가, 네이버 증권 API 저녁 시세는 시간외 값, doksamlabs 당일 행은 장전 값
- [증시요약 게시 일정](user_naver-blog-market-schedule.md) — 평일 07:00·미장 개장 1시간 전(서머타임 21:30/그 외 22:30 KST), 블로그 diablodok "증시요약" 카테고리, 자동화 방식 미정 (개인)
- [hwpx plan v2 함정](reference_hwpx-plan-v2-traps.md) — v2 표는 header+배열 rows, 키-값 rows 는 검증 통과 후 키 이름이 찍힌다, caption 무시, bullets style 은 government_report 전용, 샌드박스는 cwd 하나
- [시크릿 마스킹을 sed 에 맡기지 않기](feedback_secret-redaction-bsd-sed.md) — BSD sed 는 \s 미지원이라 `KEY = "값"` 이 그대로 찍혔다(2026-11-14 네이버 API 시크릿 노출). 시크릿 파일은 키 이름만 뽑는다
- [Go·Rust 만 쓴다](user_lang-go-rust-only.md) — 새 스크립트·도구는 Go 나 Rust 로. Python 으로 새로 짜거나 레포에 넣자고 제안하지 않는다 (개인)
