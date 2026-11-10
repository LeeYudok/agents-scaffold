# agents-scaffold — 스킬

설치하면 어떤 스킬이 들어가는지, 스캐폴드 없이 스킬만 설치하려면 어떻게 하는지 정리한다. 시작은
[README](../README.ko.md). English: [SKILLS.en.md](SKILLS.en.md).

## 설치하면 들어가는 것

| 설치 | 스킬 | 서브에이전트 | 내용 |
|---|---|---|---|
| `--lang ko` (기본) | 24 | 19 | 워크플로 스킬(한국어)과 `yd-*` 전문 스킬 14개, 그 에이전트 12개 |
| `--lang en` | 10 | 7 | 워크플로 스킬(영어) |
| 어느 쪽이든 `--with-personal-skills` | +9 | +4 | 메인테이너 환경 전용 `yd-*` 스킬 |

**워크플로 스킬 10개**: `review`, `status`, `search-first`, `security-precheck`, `docs-sync`, `handoff`,
`memory-factcheck`, `skill-evolve`, `grill-me`, 그리고 `example-skill`. `example-skill` 은 스킬을 새로 만들 때
복제하는 템플릿이다.

**`yd-*` 전문 스킬 14개**: `yd-pg-expert`, `yd-oracle-expert`, `yd-sqlite-expert`, `yd-db-expert`,
`yd-go-expert`, `yd-react-expert`, `yd-typescript`, `yd-frontend-build`, `yd-cve-check`, `yd-mobile-web-planner`,
`yd-nextjs-implementer`, `yd-blueprint`, `yd-agents-yaml`, `yd-writer-kr`. 한국어로 쓰여 있고 영어 오버레이가 없다.
그래서 `--lang en` 설치에는 넣지 않는다.

| 옵션 | 효과 |
|---|---|
| `--with-yd-skills` | 영어 설치에 `yd-*` 14개와 그 에이전트를 넣는다 |
| `--no-yd-skills` | 한국어 설치에서 뺀다 |
| `--with-personal-skills` | 옵트인 9개도 설치한다. 특정 GitLab·호스트·ui.doksam.com·FinGuard 를 전제하므로 다른 환경에서는 쓰기 어렵다 |

선택은 `.claude/.scaffold.json` 에 기록되고, `--update` 는 같은 묶음을 유지한다. 스킬별 표와 작성 규약은
[.claude/skills/README.md](../.claude/skills/README.md) 에 있다.

스킬 원본은 `.agents/skills/` 한 곳이다(Codex·Antigravity 가 읽는 경로). Claude Code 는 심볼릭 링크
`.claude/skills -> ../.agents/skills` 로 같은 파일을 읽는다. 링크를 만들 수 없는 환경의 사본 모드는
[OPTIONS.md](OPTIONS.md#하네스---harness) 를 본다.

## 플러그인으로 전역 설치

Claude Code 와 Codex 가 같은 `.claude-plugin/marketplace.json` 을 읽는다.

```bash
claude plugin marketplace add LeeYudok/agents-scaffold && claude plugin install yd-skills@agents-scaffold
codex plugin marketplace add LeeYudok/agents-scaffold && codex plugin add yd-skills@agents-scaffold
```

- `yd-skills` 에는 `yd-*` 14개와 `handoff`·`docs-sync`·`memory-factcheck`·`skill-evolve` 가, `yd-skills-personal`
  에는 옵트인 9개가 들어 있다. 둘 다 한국어다.
- Claude Code 에서는 플러그인 스킬 이름 앞에 플러그인 이름이 붙는다(`yd-skills:yd-pg-expert`).
- 플러그인은 스킬만 싣는다. Claude Code 플러그인은 rules 를, Codex 플러그인은 서브에이전트를 싣지 못하므로
  프로젝트 규칙·훅·서브에이전트는 설치 스크립트가 맡는다.
- 각 플러그인에는 Antigravity 용 매니페스트(`.antigravity-plugin/plugin.json`)도 있다. agy 문서를 보고 만들었다.
  agy 1.5.0 의 `agy plugin validate` 는 통과하고, 설치는 아직 실측하지 않았다.

## `skills` CLI 로 설치

[vercel-labs/skills](https://github.com/vercel-labs/skills) 가 이 레포의 스킬(`.claude/skills/` 와 플러그인
마켓플레이스)을 찾아, 고른 것만 지원하는 에이전트에 설치한다.

```bash
npx skills add LeeYudok/agents-scaffold                            # pick from the 21 general skills
npx skills add LeeYudok/agents-scaffold --skill yd-cve-check -a claude-code
INSTALL_INTERNAL_SKILLS=1 npx skills add LeeYudok/agents-scaffold  # also the scaffold-only and personal ones
```

21개는 단독으로 도는 워크플로 스킬 7개와 `yd-*` 14개다. `review`·`security-precheck` 는 스캐폴드 서브에이전트가
있어야 돌고 `example-skill` 은 템플릿이라, 이 셋은 CLI 에서 숨기고(`metadata.internal`) 설치 스크립트로만 받는다.
`.claude/skills/` 에 있는 것은 한국어 원본이다. 워크플로 스킬의 영어판은 `--lang en` 설치로 받는다.

## 폐쇄망·개발용: `install-skills.sh`

이 레포를 clone 해 `scripts/install-skills.sh` 를 실행한다. `~/.claude/skills`·`~/.agents/skills`·
`~/.gemini/config/skills` 에 심볼릭 링크를 만들고, `--personal`·`--copy`·`--project <dir>` 를 지원한다.

Antigravity 전역 설치 경로는 두 도구가 서로 다르다. `skills` 1.7.6 은 `~/.gemini/antigravity-cli/skills` 에 쓰고
`install-skills.sh` 는 `~/.gemini/config/skills` 를 쓴다
([vercel-labs/skills#1483](https://github.com/vercel-labs/skills/pull/1483) 이 들어가면 같아진다).
