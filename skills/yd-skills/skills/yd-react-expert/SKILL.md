---
name: yd-react-expert
description: React 컴포넌트를 설계·구현·리팩터링하거나 상태 관리, useEffect 남용, 리렌더 성능, 접근성 문제를 다룰 때 사용한다. React 19 기준.
---

# yd-react-expert

컴포넌트 코드가 대상이다. 번들러·패키지 매니저·의존성은 `yd-frontend-build`,
디자인 토큰·컴포넌트 선택은 `yd-doksam-ui` 가 맡는다.

이 문서는 **일반론을 적지 않는다.** 판단이 갈리는 지점, 자주 틀리는 곳, React 19 에서
바뀐 것만 담는다.

## 1. 상태는 필요한 만큼만, 있어야 할 곳에

판단 순서:

1. **props 나 기존 상태에서 계산할 수 있는가** → 렌더 중에 계산한다. `useState` + `useEffect`
   조합으로 파생값을 동기화하지 않는다. 이 패턴이 버그의 큰 축이다.
2. **여러 컴포넌트가 공유하는가** → 가장 가까운 공통 부모로 올린다. 전역 스토어는
   "여러 화면이 같은 서버 상태를 본다"가 성립할 때만.
3. **URL 에 있어야 하는가** — 새로고침·공유·뒤로가기가 의미 있으면 라우터 상태다.
   상세 화면·필터·탭이 여기 해당한다.

```tsx
// 나쁨 — 파생값을 상태로 두고 동기화
const [filtered, setFiltered] = useState<Room[]>([])
useEffect(() => { setFiltered(rooms.filter(r => r.name.includes(q))) }, [rooms, q])

// 좋음 — 렌더 중 계산
const filtered = useMemo(() => rooms.filter(r => r.name.includes(q)), [rooms, q])
```

`useMemo` 는 **측정 가능한 비용이 있을 때만**. 배열 몇 개 도는 것에 붙이면 코드만 늘어난다.

## 2. useEffect 는 "외부 시스템과 동기화"에만

effect 를 쓰기 전에 답한다: **이 코드가 맞물리려는 외부 시스템이 무엇인가?**
(네트워크, DOM 이벤트, 타이머, 구독) 답이 없으면 effect 가 아니다.

- **사용자 행동의 결과는 이벤트 핸들러에서 처리한다.** 상태를 바꾸고 그 변화를 effect 로
  감지해 후속 작업을 하는 구조는 흐름을 끊고 중복 실행을 부른다.
- **StrictMode 에서 effect 는 두 번 실행된다.** 이건 버그가 아니라 정리(cleanup) 누락을
  드러내는 장치다. 두 번 돌아 깨지면 effect 쪽을 고친다. 개발 빌드에서만 일어나고 프로덕션 빌드는 한 번 실행한다.

### 비동기 요청 취소는 필수

```tsx
useEffect(() => {
  let alive = true
  api.messages(dbRef, roomId).then(m => { if (alive) setMessages(m) })
  return () => { alive = false }
}, [dbRef, roomId])
```

빠뜨리면 대상을 연달아 바꿀 때 **먼저 보낸 응답이 나중에 도착해 화면을 덮는다**(경합).
`AbortController` 를 쓸 수 있으면 그쪽이 더 낫다 — 요청 자체를 끊는다.

### 의존성 배열을 거짓말로 채우지 않는다

`eslint-plugin-react-hooks` 의 `exhaustive-deps` 는 빠진 값을 경고하고, `rules-of-hooks` 는 조건문 안의 훅을 오류로 막는다.
린트가 요구하는 값을 빼서 "한 번만 실행"을 흉내내지 않는다. 대신 원인을 없앤다 —
함수는 `useCallback` 으로 안정화하거나 effect 안으로 옮기고, 정말 마운트 1회면
그 사실이 드러나게 쓴다.

## 3. 리스트와 key

- `key` 는 **데이터의 안정적 식별자**. 배열 인덱스는 순서가 바뀌거나 중간 삽입이 있으면
  상태가 엉뚱한 행에 붙는다.
- **컴포넌트를 초기화하고 싶을 때 `key` 를 바꾸는 것은 정식 기법이다.**
  상세 뷰에서 대상이 바뀔 때 내부 상태를 리셋하는 가장 단순한 방법이다.

```tsx
<MessageView key={`${room.id}:${jumpTo ?? 0}`} ... />
```

- **렌더 안에서 컴포넌트를 정의하지 않는다.** 함수 컴포넌트 본문에서 `const Row = () => ...` 로
  만든 컴포넌트는 렌더마다 새 타입이다. React 는 매번 지우고 다시 만들어서 내부 state 가
  초기화되고 입력창은 포커스를 잃는다. 파일 최상위로 옮기고 필요한 값은 props 로 넘긴다.

## 4. React 19 에서 달라진 것

- **`forwardRef` 가 필요 없다** — 함수 컴포넌트가 `ref` 를 일반 prop 으로 받는다.
  기존 코드를 일괄 변환할 필요는 없지만 새 코드에서 쓰지 않는다.
- **`use()`** 로 promise·context 를 조건부로 읽을 수 있다. Suspense 경계와 함께 쓴다.
- `useFormStatus`·`useActionState` 는 폼 제출 상태를 다룬다. 서버 액션이 없는
  SPA 에서도 쓸 수 있다.
- ref 콜백이 정리 함수를 반환할 수 있다.

**서드파티 컴포넌트에 ref 를 넘겨 특정 자식으로 스크롤하는 식의 조작은 취약하다.**
내부가 어떤 엘리먼트를 렌더하는지에 의존하기 때문이다. 이럴 땐 `data-*` 속성을 붙이고
컨테이너에서 `querySelector` 로 찾는 편이 타입·구조 양쪽에서 안전하다.

## 5. 접근성 — 구조로 강제한다

리뷰에서 지적하는 대신 **틀리기 어렵게** 만든다.

- **아이콘 전용 버튼은 `aria-label` 이 없으면 만들지 않는다.** 레이블을 필수 prop 으로 받는
  래퍼 컴포넌트를 두면 구조적으로 막힌다.
- 클릭 가능한 것은 `<button>`/`<a>`. `<div onClick>` 은 키보드·스크린리더에서 사라진다.
- 폼 입력은 `<label htmlFor>` 로 연결한다. placeholder 는 레이블이 아니다.
- 에러 메시지는 `role="alert"`.
- 포커스 링을 지우지 않는다. 디자인상 바꿔야 하면 `focus-visible` 로 대체 스타일을 준다.
- 상태를 색으로만 알리지 않는다 — 텍스트·아이콘·모양을 함께 쓴다.
- 브라우저 `confirm()`/`alert()` 를 쓰지 않는다. 데스크톱 셸(웹뷰)에서 이벤트 루프를 막아
  앱이 굳는다. 2단계 인라인 확인이나 다이얼로그 컴포넌트로 대체한다.

## 6. 위험한 렌더

- **`dangerouslySetInnerHTML` 는 기본 금지.** 꼭 필요하면 서버에서 새니타이즈하고, 그 사실을
  주석에 남긴다. 사용자 입력·외부 데이터를 그대로 넣지 않는다.
- 외부에서 온 URL 을 `href`/`src` 에 넣을 때 스킴을 검사한다(`javascript:` 차단). React 19 는 `javascript:` URL 을 `throw` 하는 스크립트로 바꿔 렌더하지만(19.3 실측) 최후 방어일 뿐이다. `data:` 같은 다른 스킴은 그대로 통과하므로 허용 스킴 목록으로 직접 거른다.
- 사용자 텍스트는 JSX 텍스트 노드로 넣으면 자동 이스케이프된다 — 굳이 직렬화하지 않는다.

## 7. 에러 표면

- 서버가 주는 실패 사유를 **삼키지 않는다.** 공통 인터셉터(401 → 로그인 유도 등)를 둘 때는
  그 처리가 **적용되면 안 되는 요청**을 먼저 정한다. 로그인 요청의 401 은 "세션 만료"가
  아니라 "자격 불일치"이므로 서버 메시지가 그대로 보여야 한다.
- 사용자에게 보여줄 메시지와 로그용 상세를 구분한다.

## 8. 성능은 측정 후에 손댄다

기본은 "단순하게 쓰고, 느려지면 고친다". React 컴파일러가 도입된 프로젝트라면
수동 메모이제이션을 먼저 걷어낸다.

실제로 문제가 되는 것들:

- **리스트가 길다** → 가상 스크롤. 수백 건부터 체감된다.
- **큰 트리가 매 입력마다 리렌더** → 상태를 아래로 내리거나 입력을 지역화한다.
- **검색·필터가 매 타이핑마다 요청** → 디바운스(200~300ms). 이전 요청 취소도 함께.
- **부모가 매 렌더마다 새 객체·함수를 props 로 준다** → 자식이 memo 여도 소용없다.
- **서로 상관없는 요청이 차례로 기다린다(waterfall)** → `Promise.all` 로 동시에 보낸다.
  `await a(); await b();` 가 흔한 원인이다. 리렌더를 줄이는 것보다 효과가 훨씬 크다.
- **첫 화면에 안 쓰는 무거운 컴포넌트**(차트·에디터·지도) → `React.lazy` + `Suspense` 로
  나눈다. 번들 분석과 barrel import 정리는 `yd-frontend-build` 가 맡는다.
- **입력할 때마다 무거운 목록이 다시 그려져 타이핑이 끊긴다** → `useDeferredValue` 로
  목록 갱신을 뒤로 미룬다. 디바운스와 달리 요청 수는 줄지 않으니, 요청이 문제면 디바운스를 쓴다.

## 9. 화면 및 폼 인터랙션 검증 (Playwright / 접근성 트리)

- **스크린샷 대신 접근성 스냅샷 우선**: AI 에이전트나 자동화 도구로 UI를 검증할 때, 고비용 이미지 비교보다 `aria-controls`, `aria-expanded`, `role="alert"` 등 접근성 트리(Accessibility Tree)를 기반으로 DOM 상태와 노출 여부를 판정한다.
- **접힘(Accordion/Collapsible) 영역 내 폼 상태**: `hidden` 속성으로 숨겨진 폼 필드는 DOM에 남아 있어 자동완성을 보존하지만 렌더 트리에서는 비가시 상태다. 테스트 시 버튼 트리거로 가시 상태(`isVisible`) 전환 후 제출과 에러 안내 렌더링을 확인한다.

## 10. 완료 조건

- 타입체크 통과, `any` 0건
- 파생값을 상태로 두고 effect 로 동기화하는 코드가 없음
- 모든 비동기 effect 에 취소·정리가 있다
- 아이콘 전용 버튼에 접근 가능한 이름이 있다
- 리스트 `key` 가 안정적 식별자임
- `dangerouslySetInnerHTML` 을 썼다면 근거가 주석에 있다
- 실제로 띄워서 확인함 — 렌더 결과와 콘솔 에러 없음까지

## 11. 이 문서의 단언 재현

```bash
YD_REACT_VERIFY=1 python3 -m unittest discover -s .claude/skills/yd-react-expert/tests -t .claude/skills/yd-react-expert/tests -v
python3 .claude/skills/yd-react-expert/scripts/verify_react_claims.py   # 같은 단언을 한 번에 출력
```

위 단언 가운데 런타임 동작에 관한 것을 jsdom 으로 재현한다. 파생 상태, StrictMode, 비동기 경합, `key`,
렌더 중 컴포넌트 정의, `ref` prop, `use()`, `useActionState`, 이스케이프, `useDeferredValue`, `memo`,
훅 린트가 대상이다. 임시 디렉터리에 고정 버전 `react@19.3.0` 등을 `npm install` 해서 쓴다. 네트워크가 필요해서 `YD_REACT_VERIFY=1` 일 때만 돌고,
없으면 사유와 함께 건너뛴다. CI 는 `.github/workflows/react-claims.yml` 이 건너뜀을 실패로 친다.
React 를 올린 뒤 `scripts/verify_react_claims.py` 의 `PINNED` 를 바꿔 돌려 보고, 다르면 문서를 고친다.
단언과 테스트의 대응은 `tests/claims.json` 이 갖는다.

## Learned warnings

- (2026-10-04) 외부 스킬 `vercel-labs/agent-skills@vercel-react-best-practices` 와 비교했다. 설치하지 않고 §3 컴포넌트 정의 위치, §8 waterfall·lazy·`useDeferredValue` 만 흡수했다. 외부는 약 30% 가 Next.js·Vercel 전제이고, 측정 전에 미시 최적화를 적용하라는 톤이라 §8 원칙과 맞지 않는다. 접근성·보안·에러 처리는 다루지 않는다 (#188).

- (2026-08-23) Playwright E2E/MCP 검증 시 이미지보다 접근성 트리(`role=alert`, `aria-expanded` 등)를 확인하는 것이 토큰 효율과 판정 정확도가 높다. 접힌(hidden) 폼 영역은 가시성 토글 이벤트 후 인터랙션을 검증한다.
