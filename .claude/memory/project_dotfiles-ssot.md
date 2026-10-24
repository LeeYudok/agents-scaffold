---
name: dotfiles 원본은 agents-scaffold/dotfiles
description: 2026-10-24 부터 머신 셸 환경 dotfiles 의 SSOT 는 이 레포 dotfiles/ — 옛 LeeYudok/dotfiles 는 보관용, CI 는 루트 test.yml 의 dotfiles job
metadata:
  type: project
---

# dotfiles 원본(SSOT) = agents-scaffold/dotfiles (#76)

- 2026-10-24 `LeeYudok/dotfiles@73225ea` 를 `dotfiles/` 에 복사했고, 같은 날 이 레포를 원본으로 확정했다. 옛 `LeeYudok/dotfiles`
  는 보관용 — 고치지 않는다(보관 처리는 사람 몫, 이 세션엔 쓰기 권한이 없었다).
- dotfiles 변경도 이 레포 규약을 탄다: 이슈 → 브랜치 → PR(`Closes #N`). `dotfiles/AGENTS.md`·`AGENTS.yaml` 은 함께 갱신하고
  `dotfiles/scripts/check-agents-yaml.sh` 로 검증한다.
- CI: 하위 `dotfiles/.github/workflows/check.yml` 은 GitHub 가 실행하지 않는다. 루트 `.github/workflows/test.yml` 의 `dotfiles` job 이
  식별자·문법 검사와 밀폐형 시험 5종을 돌린다. `test-windows-paths.sh` 는 실제 apt·curl 설치를 해서 제외(프록시 환경에선 실패하고,
  실행하면 컨테이너에 zsh 가 실제로 설치된다).
- in-place self-clean(템플릿을 그 자리에서 프로젝트로 쓸 때)은 `dotfiles/` 를 지운다. 일반 설치는 `dotfiles/` 를 복사하지 않는다.
