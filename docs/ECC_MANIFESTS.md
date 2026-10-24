# ECC manifests 구조 분석 — 프리셋 확장 시 참고

> 출처: ECC([affaan-m/ECC](https://github.com/affaan-m/ECC), MIT) `manifests/` (2026-07-09 스냅샷).
> agents-scaffold 프리셋(현 10종 스택 + forge 2종)이 더 늘어나 "스택 = 프리셋 1개" 평면 구조가
> 버거워질 때 참고할 선택 설치 설계. **지금 당장 도입하는 것 아님** — 임계점은 아래 "도입 판단" 참조.

## 3계층 모델

ECC 인스톨러(`install.sh --profile/--modules/--with`)는 JSON 매니페스트 3개로 구동된다:

```
profiles (7종)  ──펼침──▶  modules (33종)  ◀──참조──  components (78종)
"사용자가 고르는 것"        "실제 설치 단위"            "사용자 친화 별칭"
```

| 파일 | 역할 | 핵심 필드 |
|---|---|---|
| `install-profiles.json` | 용도별 묶음(minimal/core/developer/security/research/full…) | `modules[]` |
| `install-modules.json` | 설치 단위. **파일 경로·대상 하네스·의존성** 보유 | `kind`(rules/agents/skills/…), `paths[]`, `targets[]`(claude/cursor/codex…), `dependencies[]`, `defaultInstall`, `cost`(light/medium/heavy), `stability`(stable/beta) |
| `install-components.json` | `lang:python`, `framework:nextjs` 같은 별칭 → 모듈 매핑 | `family`(baseline/language/framework/capability), `modules[]` |

설계 포인트:

- **의존성 해소**: 모듈이 `dependencies` 를 선언 → 인스톨러가 위상 정렬로 자동 포함
  (예: `machine-learning` 선택 시 `framework-language`+`workflow-quality`+`database`+`devops-infra`+`security` 딸려옴).
- **비용/안정성 태깅**: `cost: heavy`, `stability: beta` 로 컨텍스트 무게와 성숙도를 메타데이터화 —
  minimal 프로파일이 훅 런타임을 빼는 근거가 데이터로 남는다.
- **하네스 타깃팅**: 모듈마다 `targets[]` 로 어떤 하네스(claude/cursor/codex/zed…)에 설치 가능한지 선언.
- **components 는 UX 레이어**: 여러 별칭(`lang:typescript`, `framework:react`)이 같은 모듈
  (`framework-language`)로 수렴 — 사용자 언어와 설치 단위를 분리.

## agents-scaffold 현행과 대응

| ECC | agents-scaffold 현행 | 비고 |
|---|---|---|
| profile | 없음 (전 스택 공통 base + `--stack` 나열) | base `.claude/` 가 사실상 단일 core 프로파일 |
| module | `presets/stacks/<stack>/` 디렉터리 | 의존성·비용 메타데이터 없음, 경로 규약(`rules/<stack>.md` + `pre-commit.partial.sh`)이 암묵 스키마 |
| component | `--stack nextjs,ops` 인자 | 별칭 = 디렉터리명 1:1 |

## 도입 판단 (임계점)

현행 평면 구조가 깨지는 신호 — 아래 중 2개 이상이면 매니페스트화 검토:

1. **프리셋 간 의존/조합** 등장 — 예: `nextjs` 가 `bun` 룰을 전제, `forge-*` 와 스택 프리셋의 조합 규칙.
2. **부분 설치 수요** — "룰만, 훅 없이" 같은 요청 (ECC 의 minimal/opencode 프로파일에 해당).
3. **프리셋 15개 이상** — 대화형 프롬프트/README 나열이 못 버티는 규모.
4. **비Claude 하네스 타깃 분기** — Gemini/기타 하네스에 못 가는 프리셋이 생길 때 (`targets` 필요).

도입 시 최소안: `presets/manifest.json` 1개 파일로 시작
(`{id, description, dependencies[], cost}` 만 — profiles/components 분리는 그 다음 단계),
`bin/agents-scaffold.sh` 의 스택 머지 루프 앞에 의존성 펼침만 추가.

## 반면교사

- ECC 는 매니페스트 3개 + 인스톨러 JS(수백 줄)를 스스로 유지보수 — agents-scaffold 규모(프리셋 10종)에
  이 복잡도를 미리 들여오면 배보다 배꼽. **필요 신호 전 도입 금지.**
- `defaultInstall: true` 모듈이 늘면 "minimal" 이 무거워지는 drift — 프로파일별 스냅샷 테스트가 없으면 조용히 비대해진다.
