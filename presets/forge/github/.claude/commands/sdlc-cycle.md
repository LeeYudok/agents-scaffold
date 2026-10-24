---
name: sdlc-cycle
description: 이슈/기획서 기준 SDLC 한 사이클(이슈→개발→테스트→검증→PR)을 사람 개입 없이 자동 실행.
argument-hint: "<이슈번호 또는 기획서경로.md> [--no-mr] [--no-issue]"
---

# SDLC 한 사이클 (GitHub)

`$ARGUMENTS` 로 이슈번호 또는 기획서 경로를 받아, **이슈 → 개발 → 테스트 → 검증 → PR** 한 사이클을 돈다.
각 단계는 게이트: 실패하면 멈추거나 앞 단계로 되돌린다.
옵션: `--no-mr`(PR 생략), `--no-issue`(이슈 생성 생략).

> 시작 전 체크: 인자가 파일경로면 Read로 읽는다. 없으면 중단 + 경로 요청.
> 글로벌 규칙 준수: 이슈-우선, 커밋 직전 브랜치 재확인. GitHub 는 `Closes #N` 으로 머지 시 자동 클로즈.

## Phase 0 — 인입 & 이슈

1. 이슈번호면 `gh issue view $N` 으로 내용 파악. 기획서면 Read.
2. (`--no-issue` 아니면) 이슈 생성:
   ```bash
   gh issue create -t "<기능명>" -b "<범위 요약>"
   ```
   → 이슈번호 N 확보.
3. 브랜치 생성 (현재 main이면):
   ```bash
   git checkout -b feature/issue-N-<slug>
   ```

## Phase 1 — 개발 → 서브에이전트 `sdlc-developer`

이슈/기획서 내용을 주고 **최소 스코프 구현** 위임.
산출물(변경 파일 목록·충족 요구사항·미구현 항목) 수령.

## Phase 2 — 테스트 → 서브에이전트 `sdlc-tester`

AC/TC 기준 테스트 코드 작성 위임. 실행 X — 작성까지.

## Phase 3 — 검증 → 서브에이전트 `sdlc-verifier`

빌드+테스트 파이프라인 실행 + 결과 보고.
- **PASS**: Phase 4 로
- **FAIL**: 실패 단계·원인 가설 수령 → Phase 1(또는 2)로 되돌려 수정 + 재검증. **최대 2회** 재시도. 2회 후 실패 → 정지 + Phase 4 실패 보고.

## Phase 4 — PR (`--no-mr` 면 생략)

```bash
# 커밋 직전 브랜치 재확인
git branch --show-current

git add -p  # 또는 git add <files>
git commit -m "feat(#N): <기능명>"
git push -u origin feature/issue-N-<slug>
gh pr create -t "feat(#N): <기능명>" --body "Closes #N" --fill
```

> PR 본문의 `Closes #N` 으로 머지 시 이슈 자동 클로즈 — 수동 클로즈 불필요.

## Phase 5 — 보고

| 항목 | 값 |
|------|-----|
| 이슈 | #N |
| 브랜치 | feature/N-slug |
| 변경 파일 | n개 |
| 검증 | lint/build/test PASS·FAIL, 통과 수, 재시도 횟수 |
| PR | URL 또는 생략 사유 |

다음 액션(머지·추가 수정·배포)을 제안.

---

### 단계별 단독 실행

- 개발만: `Agent sdlc-developer` 에 이슈 내용 전달
- 테스트만: `Agent sdlc-tester`
- 검증만: `Agent sdlc-verifier`
