# brief.json 형식

`scripts/build_brief.py` 가 읽는 자료다. 예제는 `assets/example/brief.json` 이고 내용은 지어낸 것이다.

## 맨 위

| 키 | 뜻 |
|---|---|
| `palette` | 팔레트 이름. 기본 `ink-cobalt` |
| `doc_title` | 브라우저 탭 제목 |
| `eyebrow` | 결론 위 작은 글. 문서 종류와 독자 |
| `title` | 결론. `*글자*` 는 강조색, 줄바꿈은 `\n` |
| `lead` | 결론 아래 두세 문장 |
| `kpis` | 핵심 숫자. `value`, `label`, 선택으로 `warn` |
| `sections` | 장 목록 |
| `full_text` | 글 전문. 맨 아래 접어 둔다 |

## 장

| 키 | 뜻 |
|---|---|
| `label` | 장 번호 옆 짧은 이름 |
| `title` | 주장 문장 |
| `lead` | 한두 문장 |
| `blocks` | 블록 목록 |

## 블록

| `type` | 내용 |
|---|---|
| `figure` | SVG 그림. `kind`, `spec`, 선택으로 `keys`(번호별 풀이) |
| `cards` | 짧은 글 세 칸. `items[].title`, `text` |
| `docs` | 문서별 비교. `title`, `sub`, `rows`, `cut`(뺀 것), `ask`(협의할 것), `main` |
| `pairs` | 숫자가 아닌 두 값. `label`, `a: [값, 출처]`, `b: [값, 출처]` |
| `waffle` | 칸 채우기. `groups[].label`, `style`(`have`·`grow`·`need`), `items` |
| `org` | 조직. `top`, `items` 모두 `[역할, 이름]` |
| `decisions` | 결정 카드. `title`, `options`, `note` |
| `note` | 그림 아래 주석 |

- `kpis` 는 3~4개다. 정해지지 않은 값에는 `warn` 을 준다.
- `decisions` 의 `options` 는 고를 수 있는 안을 적는다. 안이 하나뿐이면 지금 상태를 적는다.
