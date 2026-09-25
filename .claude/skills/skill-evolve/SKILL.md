---
name: skill-evolve
description: 스킬 실행 후 피드백을 받아 해당 SKILL.md를 자동 개선하는 메타 스킬. 스킬이 틀렸거나 누락이 있을 때, 또는 새로 배운 함정을 기록할 때 사용.
argument-hint: "[개선할 스킬 이름] [피드백/개선 내용]"
allowed-tools: Edit, Read, Write, Bash
---

# 스킬 자기개선

> 원형: [leeyudok/doksam-skills](https://github.com/leeyudok/doksam-skills) 의 동명 스킬.
> 템플릿 동봉용으로 **의도적 분기** — 자동 동기하지 않으며, 좋은 개선은 수동 체리픽.

실행 중 발견한 문제, 사용자 피드백을 해당 스킬의 SKILL.md에 반영한다.

## 트리거

`/skill-evolve <스킬명> <피드백>`

## 프로세스

1. **대상 읽기**: `.claude/skills/<스킬명>/SKILL.md` 전체 읽기.
2. **분석**: 피드백 + 최근 실행 맥락 분석 → 변경 부분 결정.
   - 새로운 gotcha → `## Learned warnings` 섹션에 날짜와 함께 추가
   - 단계 수정 → 프로세스 섹션 업데이트
   - 잘못된 명령 → 수정
3. **제안**: 기존 내용 인용 + 변경 diff(추가/삭제 라인별) 제시.
4. **확인 요청**: "적용하시겠습니까? (Y/n)"
5. **적용**: 확인 후 SKILL.md 직접 수정.
6. **커밋**: 브랜치 재확인 후:
   ```bash
   git add .claude/skills/<스킬명>/SKILL.md
   git commit -m "evolve skill/<스킬명>: <요약> (#<이슈>)"   # 이슈 번호 필수(P1)
   ```
7. **검증(미니 eval)**: 개선 계기가 된 것과 같은 유형의 입력으로 수정된 스킬을 실행해, 개선 전 실패했던 지점이 실제로 고쳐졌는지 전후 비교로 확인.

## 규칙

- 기존 Learned warnings는 삭제하지 않고 누적
- 날짜 태그 필수: `(YYYY-MM-DD)`
- 중복 경고는 병합
- 커밋 직전 브랜치 재확인 (main 위 커밋 방지)

## 출력 형식

```
개선 제안
기존: [인용]
제안: [수정안]

diff:
+ 추가 라인
- 삭제 라인

적용하시겠습니까? (Y/n)
```

## Learned warnings

(실행 중 발견한 주의사항이 여기에 누적됩니다)
