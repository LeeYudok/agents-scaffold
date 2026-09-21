# Memory Index

이 프로젝트 auto-memory SSOT는 `.claude/memory/` (시스템 기본 경로 미사용).
타입접두: `project_`/`feedback_`/`reference_`/`user_`. `user_*`만 개인(gitignore), 그 외 팀 공유.

<!-- 메모리 추가 시 아래에 한 줄씩:
## 프로젝트
- [제목](project_xxx.md) — 한 줄 훅
-->

- [하네스 설정 계약 실측](reference_harness-config-contracts.md) — Claude/Codex/agy 의 설정·디스커버리 경로와 함정(32KiB, trust boundary, PreToolUse 는 강제선 아님, Claude 2.1.278 은 AGENTS.md 네이티브 로드하나 CLAUDE.md 있으면 무시)
- [이슈 #20 3자 교차리뷰 결론](project_agents-scaffold-multiagent-review.md) — compile-time emitter 확정, 해시검증 폐기→P0 reachability, 남은 후속 a~c
- [README 다국어 동시 수정](feedback_readme-multilang-sync.md) — README.md 고치면 en/zh/ja 3종도 같은 커밋에서. 언어 간 일치를 검사하는 자동 게이트가 없다
- [이슈 클레임·바운티 정책](project_issue-claim-and-bounty-policy.md) — 외부 `/attempt` 코멘트와 유료 작업 제안에 대한 확정 대응
- [프리셋 게이트 검증법](project_preset-gate-verification.md) — 가짜 툴 바이너리로 exit 분기 실측, bats 엔 툴체인 비의존 케이스만
