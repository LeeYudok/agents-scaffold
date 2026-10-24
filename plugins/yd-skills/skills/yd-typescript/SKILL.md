---
name: yd-typescript
description: TypeScript 코드를 작성·리뷰할 때 타입 경계, 비동기 상태, DOM 접근, strict 설정을 점검한다. Bun 브라우저 코드에도 적용한다. 빌드·의존성은 yd-frontend-build, React 컴포넌트는 yd-react-expert가 맡는다.
---

# yd-typescript

TypeScript의 정적 보장이 실제 실행 데이터에도 성립하는지 확인한다. 기존 프로젝트의 런타임·프레임워크·배포 방식을 유지하고, 이번 변경과 관계없는 전면 리팩터링은 하지 않는다. 패키지·번들 설정은 `yd-frontend-build`, React 상태와 컴포넌트는 `yd-react-expert`가 맡는다.

## 데이터 경계

- `fetch().json()`, JSONP 콜백, `JSON.parse`, `localStorage`, DOM의 `dataset`은 타입이 붙어 보여도 외부 값이다. 입력을 `unknown`으로 받고 실제 사용하는 필드의 존재·타입·허용 범위를 확인한 뒤 도메인 타입으로 좁힌다. 실패 시 화면 상태나 저장 데이터가 어떻게 되는지도 정한다.
- `as ApiResponse`, `as HTMLElement`, 후위 `!`는 검증이 아니다. DOM 요소가 반드시 있어야 하면 한 번 조회해 `instanceof` 또는 null 검사를 거친 뒤 쓰고, 선택 요소는 없을 때의 동작을 명시한다. 제네릭 헬퍼도 런타임 검사를 생략하지 않는다.
- 선택적 필드에서 **부재**와 `undefined` 값이 다른 계약이면 `exactOptionalPropertyTypes`를 검토한다. 배열·인덱스 조회 실패가 의미 있으면 `noUncheckedIndexedAccess`를 켜거나 사용 지점에서 검사한다. 기존 설정을 한꺼번에 강화해 무관한 오류를 대량 생산하지 않는다.
- 이름·ID·URL처럼 외부 문자열을 HTML에 표시할 때는 `textContent`와 DOM 노드로 조립한다. `innerHTML`이 필요하다면 신뢰 경계와 허용 마크업을 먼저 명시한다.

## 비동기 UI

- 연속 선택·검색·폴링에서 이전 응답이 나중 응답을 덮을 수 있다. 요청 취소(`AbortController`)나 세대 번호로 최신 결과만 반영한다. 타이머·이벤트 리스너를 교체하거나 화면을 닫을 때 정리한다.
- POST 응답이 성공 코드여도 본문이 비었거나 형식이 틀릴 수 있다. 성공 여부와 응답 스키마를 각각 검사하고, 저장 완료 안내는 유효한 응답을 화면에 반영한 뒤 표시한다.
- 시간 제한 후 실패했을 때 서버 쓰기가 이미 끝났을 수 있다. 곧바로 재시도해 중복 기록을 만들기보다 현재 상태를 다시 조회하거나 사용자에게 확인 가능성을 알린다.

## Bun·TypeScript 확인

- Bun의 TS 실행·`bun build`는 타입 검사를 하지 않는다. 변경한 프로젝트의 `tsconfig.json`으로 `tsc --noEmit`을 별도로 실행하고, 브라우저 산출물은 `--target browser`로 만든다. 코드 작성과 빌드/패키징 책임은 구분한다. `bun build`의 기본 target 도 `browser`라 같은 결과지만, 산출물 용도를 드러내려고 명시한다. TypeScript 7 은 `tsconfig.json` 이 있는 폴더에서 파일을 직접 지정하면(`tsc --noEmit a.ts`) TS5112 로 거부하므로 `tsc --noEmit -p <tsconfig>`로 돌린다.
- `strict`를 기준으로 보되 기존 브라우저 대상 `lib`, `moduleResolution`, TS 버전을 확인하고 필요한 설정만 추가한다. Bun 런타임 API를 브라우저 번들에 섞지 않는다.
- 타입 검사와 빌드 후 실제 화면에서 변경한 경로를 확인한다. 외부 데이터 경계를 바꿨다면 정상·누락·오형식 입력 중 실제 위험을 드러내는 사례를 검증한다. 구현을 그대로 복제하는 테스트는 만들지 않는다.

## 완료 조건

- 외부 데이터와 DOM에 적용한 타입 단언의 근거가 코드에 있다.
- 비동기 갱신이 오래된 응답으로 최신 화면을 덮지 않는다.
- 프로젝트의 타입 검사·빌드가 통과하고 변경한 화면 동작을 확인했다.

## 근거

- [TypeScript `strict`](https://www.typescriptlang.org/tsconfig/strict), [`exactOptionalPropertyTypes`](https://www.typescriptlang.org/tsconfig/exactOptionalPropertyTypes.html), [`noUncheckedIndexedAccess`](https://www.typescriptlang.org/tsconfig/noUncheckedIndexedAccess.html)
- [Bun TypeScript](https://bun.sh/docs/typescript), [Bun bundler](https://bun.sh/docs/bundler) — Bun의 변환·번들은 타입 검사를 대신하지 않는다.
- 위 단언은 `scripts/verify_typescript_claims.py` 가 typescript 7.0.2 · bun 1.4.2 에서 재현한다(2026-10-05). 재현이 문서와 다르면 문서를 고친다.
