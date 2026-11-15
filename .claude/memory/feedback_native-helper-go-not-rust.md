---
name: feedback_native-helper-go-not-rust
description: 스킬에 동봉하는 네이티브 도구(검사기 등)는 Rust 가 아니라 Go 표준 라이브러리로 쓴다 — 사용자 머신에서 첫 실행 때 빌드되므로 빌드 CPU 부하가 곧 사용자 경험이다 (2026-11-13, #117)
metadata:
  type: feedback
---

스킬 안에 소스로 넣고 사용자 머신에서 처음 실행할 때 빌드하는 도구는 Go(표준 라이브러리만)로 쓴다. Rust 는 쓰지 않는다.

**Why:** 2026-11-13 사용자 지시 "검사기 러스트 하지말고 go로 다시 바꾸자 러스트 cpu 부하 많이 걸려서 안되겠다". #115 의 Rust 판 `yd-writer-kr` 검사기는 소스가 바뀔 때마다 fancy-regex·serde 를 포함한 `cargo build --release` 를 돌렸다. 이 맥에 Rust 빌드 캐시가 146M 쌓였다. Go 판(#117)은 빈 Go 캐시에서도 약 2초에 빌드되고 바이너리는 3.4M 다.

**How to apply:**
- 외부 모듈을 넣지 않는다. 그래야 폐쇄망에서도 Go 툴체인만으로 빌드되고 go.sum·벤더링이 필요 없다.
- 런처는 `GOTOOLCHAIN=local`·`CGO_ENABLED=0` 으로 빌드한다. 결과는 사용자 캐시에 소스 지문별로 둔다.
- Go regexp(RE2)는 전후방 탐색이 없고 `\d`·`\s`·`\b` 가 ASCII 기준이다. 한글 처리 규칙을 옮길 때 이 차이부터 확인한다.

관련: [[project_layout-zones]] [[reference_repo-search-and-install-traps]]
