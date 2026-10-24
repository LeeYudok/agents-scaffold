---
name: 레포 영역 구분(설치 원본·레포 전용·플러그인·동봉 제품)
description: 이 레포의 디렉터리는 사용자 프로젝트로 설치되는 원본, 이 레포에서만 쓰는 파일, 생성된 플러그인 사본, 동봉한 별도 제품으로 나뉜다 — 새 파일을 어디에 두고 설치 필터에 등록할지의 기준 (#80~#82)
metadata:
  type: project
---

# 레포 영역 구분 (2026-10-24, #80~#82)

- **설치 원본** — `AGENTS.md`, `.claude/`, `presets/{stacks,forge,lang,skills}/`. `bin/agents-scaffold.sh` 가 사용자 프로젝트로 복사한다.
  - 예외: `.claude/` 안의 이 레포 전용 파일. 지금은 `.claude/memory/*.md` 가 해당한다(`README.md`·`MEMORY.template.md` 만 배포).
  - `.claude/` 에 레포 전용 파일을 새로 두면 `is_repo_private()` 에 등록한다. 등록하지 않으면 모든 사용자 프로젝트로 퍼진다.
  - 이것을 빠뜨린 탓에 메모리 11개가 #24 부터 배포됐다(#80).
- **레포 전용** — `bin/`, `scripts/`(사용자 도구 `install-skills.sh`·`make-offline-bundle.sh`), `scripts/dev/`(메인테이너·CI 전용), `tests/`, `docs/`, `.github/`. 설치되지 않고, in-place 설치는 self-clean 으로 지운다.
- **플러그인(생성물)** — `.claude-plugin/marketplace.json`, `plugins/<이름>/`. `skills/` 는 `scripts/dev/build-plugins.py` 가 원본에서 만든 실파일 사본이다.
  - 직접 고치지 않는다. 원본을 고친 뒤 다시 생성해 같은 커밋에 넣는다(CI `plugins` job·`tests/test_build_plugins.py`).
  - 심링크를 쓰지 않는 이유: codex 0.164.0 이 심링크를 버린다.
- **동봉 제품** — `dotfiles/`(#76). 스캐폴드와 별개 제품이고 설치되지 않는다.
- 왜: 세 하네스 모두 프로젝트 메모리·레포 전용 영역 규약이 없다. 그래서 무엇이 배포되는지는 이 레포가 스스로 정해야 한다(2026-10-24 3사 문서 대조).
