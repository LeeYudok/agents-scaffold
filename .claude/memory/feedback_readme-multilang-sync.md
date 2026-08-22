---
name: feedback_readme-multilang-sync
description: README.md 를 고치면 README.en/zh/ja 3종도 같은 커밋에서 함께 고친다
metadata:
  type: feedback
---

README 를 수정할 때는 **4종(`README.md` 영문 · `README.ko.md` · `README.zh.md` · `README.ja.md`)을 같은 커밋에서 함께 수정한다.** 한국어만 고치고 나머지를 미루지 않는다 (2026-08-22 지시).

**Why**: 이 저장소의 README 는 4개 언어가 같은 내용을 담는 병렬 문서다. 한쪽만 갱신하면 나머지 3개가 조용히 stale 이 되는데, 링크 체커(`knowledge_graph.py --check`)도 bats 스위트도 **언어 간 내용 일치는 검사하지 않으므로** 어떤 자동 게이트에도 걸리지 않는다. 실제로 #26 에서 하네스 실측 서술·트리 설명이 4종 모두에서 동시에 낡아 있었다.

**How to apply**:
- README 변경 diff 를 만들 때 대상 파일 목록을 항상 `README.md README.ko.md README.zh.md README.ja.md` 로 잡는다.
- `README.md` 는 **영문**이다(#45 — GitHub 첫 화면이 영어여야 비한국어 방문자가 이탈하지 않는다). 한국어 원본은 `README.ko.md`. 작성은 여전히 한국어로 먼저 해도 되지만, 커밋에는 두 파일이 함께 들어간다.
- 번역이 아니라 **같은 사실의 각 언어판**이다 — 수치·버전·경로·표 구조를 동일하게 유지하고, 문장만 해당 언어답게 쓴다.
- 언어별로 대응 문자열이 달라 치환이 깨지기 쉬우므로, 4개 파일 각각에서 교체 대상 원문을 먼저 `grep -n` 으로 확인한 뒤 수정한다.
- 같은 원칙이 `presets/lang-en/` 오버레이에도 적용된다 — ko 베이스 파일을 고쳤으면 대응하는 `presets/lang-en/` 파일도 같은 커밋에서 고친다 (#21 의 `AGENTS.partial.md` 10 + 10 이 그 예).

관련: [[project_agents-scaffold-multiagent-review]]
