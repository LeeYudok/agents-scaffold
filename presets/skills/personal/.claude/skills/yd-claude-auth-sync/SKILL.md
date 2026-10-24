---
name: yd-claude-auth-sync
description: 한 PC 에서 claude login 으로 다시 인증한 Claude Code 로그인을, 사용자가 등록해 둔 다른 PC·서버에도 똑같이 맞춘다. 키체인·~/.claude/.credentials.json 의 claudeAiOauth 만 ssh 표준입력으로 넘기고 토큰은 출력하지 않는다. "클로드 인증 서버들에 공유", "claude 로그인 다른 PC 에도 맞춰", "인증값 똑같이" 요청에 쓴다. 저장소 동기화는 yd-git-sync 가 맡는다.
---

# yd-claude-auth-sync

## 역할

Claude Code 를 여러 호스트에서 쓸 때, 한 곳에서 로그인하면 나머지가 같은 로그인을 쓰게 만든다. 원본은 지금 PC 이고 대상은 사용자가 등록한 호스트다.

토큰을 다루는 스킬이다. 아래 위생 규칙이 기능보다 먼저다.

## 위생 규칙

- **토큰 값을 화면·로그·argv 에 내지 않는다.** 스크립트는 토큰을 ssh 표준입력으로만 넘긴다. 확인할 때도 값 대신 구독 종류·만료 시각·파일 크기만 본다.
- **`security ... -w`·`cat .credentials.json` 을 단독으로 실행하지 않는다.** 출력이 그대로 대화에 남는다. 필요하면 파이프 안에서 JSON 키 이름만 뽑는다.
- **옮기는 값은 `claudeAiOauth` 하나다.** 키체인에는 MCP 서버 로그인(`mcpOAuth`)도 함께 있는데, 이 PC 전용이라 옮기지 않는다. 대상 파일에 있던 다른 키는 그대로 둔다.
- **호스트 목록은 저장소 밖에 둔다.** 이 저장소는 공개다. 호스트 이름·주소·사용자 경로를 스킬 문서나 커밋에 적지 않는다.
- 사용자가 토큰을 채팅에 붙여 넣으면 쓰지 말고, 다시 발급하라고 권한다.

## 준비 (처음 한 번)

호스트 목록 파일을 만든다. 한 줄에 ssh 별칭 하나다. `#` 뒤는 주석이다.

```bash
mkdir -p ~/.config/yd-claude-auth-sync
$EDITOR ~/.config/yd-claude-auth-sync/hosts   # 별칭을 한 줄씩
chmod 600 ~/.config/yd-claude-auth-sync/hosts
```

경로는 `YD_CLAUDE_AUTH_HOSTS` 로 바꿀 수 있다. 각 별칭은 `ssh <별칭>` 이 비밀번호 없이 되어야 한다(스크립트는 `BatchMode=yes` 로 접속한다).

## 워크플로

### 1. 원본 확인

```bash
python3 <skill>/scripts/sync_auth.py --dry-run
```

원본 요약(구독 종류, access token 만료 시각)과 대상 호스트를 보여 준다. 원본은 macOS 면 키체인 `Claude Code-credentials`, 리눅스면 `~/.claude/.credentials.json` 이다. 원본이 없으면 이 PC 에서 `claude` 로 먼저 로그인한다. 로그인은 브라우저 승인이 필요하므로 사용자가 직접 한다.

### 2. 맞추기와 확인

```bash
python3 <skill>/scripts/sync_auth.py --verify
python3 <skill>/scripts/sync_auth.py --host <별칭> --verify   # 한 호스트만
python3 <skill>/scripts/sync_auth.py --verify-only            # 쓰지 않고 확인만
```

호스트마다 결과가 한 줄씩 나온다.

- `same` — 이미 같은 로그인이다. 아무것도 쓰지 않는다.
- `updated (backup .credentials.json.bak-<시각>)` — 기존 파일을 시각 접미사로 백업하고 새로 썼다. 새 파일은 권한 600 이고, 임시 파일에 쓴 뒤 바꿔 끼워 중간에 끊겨도 깨진 파일이 남지 않는다.
- `verify ok` — 그 호스트에서 `claude -p` 가 응답했다. `claude 없음` 이면 그 호스트에 설치부터 한다.

하나라도 실패하면 종료 코드는 1 이다. 실패한 호스트는 별칭과 ssh 접속부터 확인한다.

## 한계

- **같은 refresh token 을 여러 호스트가 나눠 쓴다.** access token 이 만료되면 먼저 갱신한 호스트가 새 refresh token 을 받는다. 나머지는 로그인이 풀릴 수 있다. 그러면 갱신한 호스트를 원본으로 다시 돌리거나, 원래 PC 에서 다시 로그인하고 돌린다.
- 갱신 충돌을 피하려면 `claude setup-token` 으로 1년짜리 토큰을 받아 호스트마다 `CLAUDE_CODE_OAUTH_TOKEN` 으로 주는 방법이 있다. 토큰 발급은 브라우저 승인이 필요해 사용자가 직접 한다. 이 스크립트는 그 경로를 다루지 않는다.
- 대상은 파일로 인증을 읽는 호스트(리눅스)다. 대상이 macOS 면 claude 가 키체인을 읽으므로 파일을 써도 반영되지 않는다.
- 원격에 `python3` 가 있어야 한다. 병합 스크립트가 원격에서 돈다.

## 완료 조건

- 모든 호스트가 `same` 또는 `updated` 이고, `--verify` 결과가 `verify ok` 다.
- 보고에는 호스트별 결과 줄과 백업 파일 이름만 적는다. 토큰 값·호스트 주소는 적지 않는다.
