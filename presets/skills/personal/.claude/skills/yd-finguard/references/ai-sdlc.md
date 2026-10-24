# AI-SDLC 연계 계약

한 줄의 서비스 제작 요청을 여러 스킬이 이어받을 때 각 단계의 산출물과 중단
조건을 고정한다. 이 문서는 오케스트레이터가 아니라 FinGuard 보안 게이트를
파이프라인에 끼우는 계약이다.

| 단계 | 담당 계약 | 입력 | 통과 근거 | 중단 조건 |
|---|---|---|---|---|
| 1. 기획 | `yd-mobile-web-planner` | 사용자 요구 | Storyboard + Business Rules 검증 통과 | 화면 ID 또는 규칙 문서 누락 |
| 2. UI 표준 | `yd-doksam-ui` (doksam 프로젝트일 때) | 목업·브랜드 프로필 | 표준 검사 통과 | SSOT 접근 실패, 미해결 표준 위반 |
| 3. 구현 | `yd-nextjs-implementer` | 기획 산출물 한 쌍 | 화면/규칙 추적표, lint·build·test | 문서 불일치, 미구현 화면·차단 테스트 실패 |
| 4. 보안 | `yd-finguard` | 빌드 가능한 소스 | 합의한 심각도의 finding 0건 | 게이트 실패 또는 검사 도구 불완전 |
| 5. 실행 검증 | 구현 스킬 + 사용 가능한 브라우저 도구 | 검증된 빌드 | 헬스체크와 핵심 User Flow 결과 | 서버 기동 실패, 핵심 인터랙션 실패 |
| 6. 배포 | 프로젝트의 배포 계약 | 위 단계 증거 | 배포 URL·버전·헬스체크 | 사용자 승인/자격증명/운영 절차 부재 |

기획서가 없는 요청은 1단계부터 시작한다. 이미 검증된 기획서나 프로젝트가
있으면 해당 단계까지의 근거를 확인하고 이어간다. 단계를 건너뛴 경우에는
건너뛴 사실과 잔여 위험을 최종 보고에 남긴다.

## 구현 스택 분기

`yd-nextjs-implementer`의 이름은 호환성을 위해 유지되지만, 기획서 구현 시 프론트
모드는 Next.js App Router와 Vite + React SPA 중 하나다. 사용자가 지정하지
않으면 서버 렌더링·SEO·Server Actions가 필요한지 판단해 선택 근거를 먼저
기록한다. 빌드 설정은 `yd-frontend-build`, 컴포넌트 판단은 `yd-react-expert`, doksam
UI 표준은 `yd-doksam-ui`가 소유한다.

## 로컬 실행과 E2E

보안 게이트가 통과한 뒤 프로젝트가 정한 `dev` 명령으로 서버를 기동한다.
Next.js의 관례 URL은 `http://localhost:3000`, Vite의 관례 URL은
`http://localhost:5173`이지만 점유 시 실제 URL을 기록한다. 포트 선택과 첫
응답 확인은 구현 스킬의 스크립트가 판정한다 — 프로세스 생존을 기동으로
읽지 않기 위해서다.

```sh
python3 <yd-nextjs-implementer-스킬경로>/scripts/serve_and_check.py \
  --cmd "pnpm dev -- --port {port}" --dir <프로젝트> --port 3000 --route /
```

그 위에서 다음 핵심 흐름을 확인한다.

- 주요 내비게이션이 화면 ID 매핑대로 이동한다.
- 문의·주문 등 쓰기 폼은 유효/무효 입력과 성공/오류 상태를 모두 확인한다.
- 테스트가 실제 외부 주문·결제·메시지를 만들 수 있으면 샌드박스 또는 mock을
  사용하고, 없으면 실행 전 승인을 받는다.

서버는 검증 후 종료한다. 사용자가 계속 실행해 달라고 요청한 경우에만 프로세스
ID, URL, 종료 방법을 전달한다.

## pre-commit 예

저장소가 일반 Git hook을 사용한다면 프로젝트의 추적 가능한 훅 스크립트에서
다음 형태로 호출한다.

```sh
python3 <설치된-yd-finguard-스킬>/scripts/run_gate.py \
  --dir . --block-on ERROR \
  --rules <yd-finguard-repo>/rules \
  --mapping <yd-finguard-repo>/mapping/rules.yaml
```

로컬 훅은 빠른 피드백일 뿐 CI/MR 게이트를 대체하지 않는다. MR 서버 모드는
FinGuard 원본의 `serve` 계약과 `.finguard.yml` 정책을 따른다.
