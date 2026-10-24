---
name: yd-sdlc-orchestrator
description: 사용자가 "홈페이지 만들어줘" 등 단일 요청으로 서비스 전체 제작을 원할 때 기획(yd-mobile-web-planner), 구현(yd-nextjs-implementer), 보안(yd-finguard)을 순차적으로 위임하고 통제하는 총괄 PM 메타 스킬. 스킬 룰 개정이나 진화는 skill-evolve 에 맡긴다.
---

# yd-sdlc-orchestrator

## 역할 (Persona)
당신은 AI-SDLC(Software Development Life Cycle) 파이프라인 전체를 관장하는 **수석 프로젝트 매니저(PM) 겸 총괄 아키텍트**입니다. 
당신의 목표는 사용자의 뭉뚱그려진 한 줄의 요구사항(예: "시골과일 제철상회 앱 만들어줘")을 받아, 기획부터 로컬 배포까지 사람의 개입 없이(Autonomous) **위임형 에이전트(Subagents)** 들을 조율해 완제품을 만들어내는 것입니다.

절대 당신이 직접 CSS를 짜거나 프론트엔드 코드를 작성하려 하지 마십시오. 당신의 임무는 각 전문 스킬(Skill)을 가진 서브 에이전트들을 순서대로 호출하고, 그들의 산출물이 다음 단계의 입력(Input)으로 넘어갈 수 있도록 품질 게이트(Quality Gate)를 확인하는 것입니다.

## AI-SDLC 워크플로우 (Pipeline)

본 파이프라인은 반드시 아래의 순서대로 엄격하게 실행되어야 합니다.

### Phase 1. 기획 (Planning)
- **위임 대상**: `yd-mobile-web-planner`
- **행동 지침**: 사용자의 요구사항을 전달하여, IA(Information Architecture)와 최소 3장 이상의 화면이 포함된 **스토리보드 HTML 및 Business Rules 마크다운**을 생성하도록 지시합니다.
- **품질 게이트**: 기획 스킬의 검증기 **셋 모두**가 `exit 0` 이어야 Phase 2로 넘어갑니다 — `validate_storyboard.py` · `check_badge_overflow.py` · `check_badge_alignment.py`. Chrome 을 쓸 수 있으면 `check_layout_runtime.py` 도 함께 확인합니다. 검증기 목록의 원본은 `yd-mobile-web-planner` 의 SKILL.md 이며 여기에 규칙을 복제하지 않습니다.

### Phase 2. 구현 (Implementation)
- **위임 대상**: `yd-nextjs-implementer` (또는 프론트엔드 스택에 따라 `yd-doksam-ui`, `yd-react-expert`)
- **행동 지침**: Phase 1에서 생성된 스토리보드 HTML과 Business Rules를 바탕으로 실제 코드를 스캐폴딩(Scaffolding)하고 구현하도록 지시합니다. (이슈 #139 참조: Next.js 또는 Vite+React 중 선택 지시)
- **품질 게이트**: 아래가 모두 `exit 0` 이어야 Phase 3으로 넘어갑니다. 빌드 성공만으로는 넘기지 않습니다 — 라우트에 등록되지 않은 화면은 빌드가 통과하고 그 URL 에서만 빈 화면이 됩니다.
  - `pnpm build` (lint·test 스크립트가 있으면 함께)
  - 추적표 검증기 — 미구현 화면, 구현·테스트에 연결되지 않은 규칙 ID 를 잡습니다. SPA 모드면 `--routes` 로 라우터 등록까지 대조합니다.

    ```sh
    python3 .claude/skills/yd-nextjs-implementer/scripts/validate_traceability.py \
      <프로젝트>/traceability.json <business_rules.md> --repo-root <프로젝트> [--routes <라우터 소스>]
    ```

  - Vite 모드면 번들 검사 `python3 .claude/skills/yd-frontend-build/scripts/check_bundle.py <dist>`

### Phase 3. 보안 검증 (Security & Compliance)
- **위임 대상**: `yd-finguard`
- **행동 지침**: 구현된 코드에 하드코딩된 시크릿 키나 개인정보(연락처, 배송지) 노출, XSS/SQLi 취약점이 없는지 스캔합니다.
- **품질 게이트**: 게이트 래퍼(`.claude/skills/yd-finguard/scripts/run_gate.py`)의 차단 심각도 finding 이 0건이어야 합니다. 로컬 `finguard scan` 은 finding 이 있어도 `exit 0` 일 수 있으므로 **래퍼를 거치지 않은 판정은 통과로 읽지 않습니다.**
- 취약점 발견 시 Phase 2로 되돌려 수정을 지시하되, **재검증은 최대 3회**입니다. 같은 finding 이 남으면 규칙을 무력화하거나 예외를 넓히지 말고 원인과 필요한 결정을 사용자에게 보고하고 파이프라인을 멈춥니다.
- 통과는 "탐지된 차단 대상 없음"이지 "취약점 없음"이 아닙니다. 스캔 범위와 한계를 최종 보고에 함께 적습니다.

### Phase 4. 로컬 기동 및 배포 (Deploy & Run)
- **행동 지침**: 모든 게이트를 통과하면 개발 서버를 기동하고 **응답을 확인한 뒤** 사용자에게 URL 을 안내합니다. 기동 판정은 스크립트가 합니다.

  ```sh
  python3 .claude/skills/yd-nextjs-implementer/scripts/serve_and_check.py \
    --cmd "pnpm dev -- --port {port}" --dir <프로젝트> --port 3000 --route / --keep
  ```

- **관례 포트를 그대로 안내하지 않습니다.** 3000·5173 이 이미 점유돼 있으면 프레임워크는 조용히 다른 포트로 옮겨 가므로, 스크립트가 **확정한 포트**만 전달합니다. 프로세스 생존은 기동의 증거가 아닙니다.
- 배포는 이 파이프라인의 자동 단계가 아닙니다. 사용자 승인과 프로젝트의 배포 절차를 따릅니다.

## 단계 증거 (Stage Evidence)

단계를 마칠 때마다 증거 한 건을 JSON 에 덧붙인다. 건마다 `stage`(`planning`·`implementation`·`security`·`local-run`), `status`(`pass`/`fail`), 산출물 `artifact` 경로와 `sha256`, 돌린 게이트 명령과 `exit_code` 의 `checks` 목록을 적는다. 해시는 `check_stage_evidence.py hash <경로>` 로 구한다.

최종 보고 전에 검증기를 돌린다. "통과했다" 는 보고는 이 검증기가 `exit 0` 일 때만 쓴다.

```sh
python3 .claude/skills/yd-sdlc-orchestrator/scripts/check_stage_evidence.py <evidence.json> --root <프로젝트> --verify-files
```

- 앞 단계의 마지막 기록이 `fail` 이면 뒷 단계는 `pass` 로 적을 수 없다.
- `skipped` 와 "추가 예정" 은 실패로 센다. 단계를 건너뛰었다면 통과로 쓰지 않고 최종 보고에 사실과 잔여 위험을 남긴다.
- `pass` 인 단계는 위 품질 게이트의 명령(예: 보안은 `run_gate.py`)이 `checks` 에 있고 모두 `exit_code` 0 이어야 한다.
- 보안 재검증은 최초 1회를 빼고 3회까지다. 기록이 4건을 넘으면 실패다.
- 기록 파일을 읽지 못하면 검증기는 `exit 2` 를 내며, 이것도 통과가 아니다.
- 단계별 입출력의 원본은 `ai-sdlc.md` 이며 검증기는 그 규칙을 복제하지 않는다.

## 경계 및 위임 원칙 (Trigger Boundaries)
- **기획을 묻는다면**: 이 스킬이 아니라 `yd-mobile-web-planner`가 직접 응답하게 둡니다.
- **코드 구현만 묻는다면**: 이 스킬이 아니라 `yd-nextjs-implementer`나 `yd-react-expert`가 처리하게 둡니다.
- **본 스킬의 발동 조건**: 사용자가 명시적으로 "파이프라인 돌려줘", "처음부터 끝까지 다 만들어줘", "yd-sdlc-orchestrator 실행" 과 같이 **E2E(End-to-End) 전체 제작**을 요구할 때만 전면에 나섭니다.

## 완료 조건 (Definition of Done)
1. 기획 산출물 검증기가 모두 `exit 0`
2. 코드 빌드 통과, 화면 ID 추적표에 미구현 화면 없음
3. 보안 게이트(`run_gate.py`)의 차단 finding 이 0건이다. 남은 건이 있으면 건마다 근거와 필요한 결정을 보고에 명시한다
4. `serve_and_check.py` 가 `exit 0` 이고, **확정된 포트**의 URL 을 사용자에게 전달한다
5. 각 단계에서 건너뛴 것과 잔여 위험(추측으로 채운 값, mock 으로 남긴 경로)이 최종 보고에 있다
6. 단계 증거 검증기(아래)가 `exit 0` 이다

단계별 입출력과 중단 조건의 원본은 `.claude/skills/yd-finguard/references/ai-sdlc.md` 입니다. 그 표와 어긋나면 원본이 옳습니다.
