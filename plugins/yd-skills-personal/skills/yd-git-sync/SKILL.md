---
name: yd-git-sync
description: 여러 호스트(맥·pig·doksam 등)에 클론해 둔 같은 저장소를 맞춘다 — 각 클론을 git pull --ff-only 로 origin 에 맞추고 추적 파일 수·목록 해시를 비교한 뒤, git 이 관리하지 않는 폴더(docs/원본자료 등)를 지우지 않고 합집합으로 채운다. "서버들 레포 동기화", "파일 갯수 같은지 확인", "pig doksam 싱크", "합집합으로 맞춰" 요청에 쓴다. 작업을 커밋·MR 로 올리는 일은 yd-git-ship 이 맡는다.
---

# yd-git-sync

## 역할

같은 저장소가 여러 호스트에 클론되어 있을 때 둘을 맞춘다.

1. **git 이 추적하는 것**: origin 기준으로 맞추고 같은지 증명한다.
2. **git 이 추적하지 않는 것**: 원본 자료처럼 `.gitignore` 에 있는 폴더다. 호스트 사이에서 합집합으로 채운다.

커밋·푸시·MR 은 하지 않는다. 그것은 `yd-git-ship` 이 맡는다.

## 워크플로

호스트 이름 `local` 은 지금 셸이고, 나머지는 ssh 별칭이다. 저장소 경로는 호스트마다 `$HOME` 기준으로 같다고 본다. 기본값은 지금 저장소의 경로이고, 다르면 `--repo-path` 로 준다. 명령은 대상 저장소 안에서 돌린다.

### 1. git 상태 맞추기

```bash
python3 <skill>/scripts/repo_state.py local pig doksam --pull
```

- 고친 파일이 없는 클론만 `git pull --ff-only` 로 당긴다. 고친 파일이 있는 클론은 건너뛰고 표에 `skip-dirty` 로 남긴다. 그 클론의 변경을 버리거나 stash 하지 않는다. 사용자에게 보고한다.
- 판정은 셋이 같아야 "같음"이다. HEAD, 추적 파일 수, 목록 해시(`git ls-files -s | git hash-object --stdin`)다. 목록 해시는 경로·모드·blob 해시를 다 담으므로 이름과 내용이 같다는 뜻이다.
- **디스크 파일 수(`find -type f`)로 비교하지 않는다.** 추적 심링크는 빠지고, ignore 된 `node_modules`·`.venv` 는 들어가서 호스트마다 다르게 나온다. 표의 `links` 열이 추적 심링크 수다.

### 2. 미추적 폴더 합집합

```bash
python3 <skill>/scripts/union_sync.py local pig doksam --dir docs            # 계획
python3 <skill>/scripts/union_sync.py local pig doksam --dir docs --apply    # 복사 + 재검증
```

먼저 계획을 보여 주고, 사용자가 범위를 정했으면 `--apply` 한다. 규칙은 이렇다.

- **지우지 않고 덮어쓰지 않는다.** 없는 파일만 채운다.
- **같은 경로·다른 내용은 충돌이다.** 어느 쪽에도 복사하지 않고 해시와 함께 보고한다. 어느 판본을 남길지는 사용자가 정한다.
- **한글 파일명은 NFC 로 비교한다.** 맥에서 만든 이름은 NFD 라, 리눅스에서는 같은 이름도 다른 파일이 된다. 원격에는 NFC 이름으로 쓴다. rsync 로 그냥 밀면 NFC·NFD 중복이 생긴다. 맥 기본 rsync 는 openrsync 라 `--iconv` 도 없다.
- 한 호스트에 NFC·NFD 이름이 둘 다 있으면 `NFC/NFD 중복`으로 보고만 한다. 지우는 것은 사용자 확인 뒤다.
- `.DS_Store`·`__pycache__`·`*.pyc`·`.git` 은 기본으로 뺀다. 머신마다 내용이 달라 충돌로만 잡힌다. 더 뺄 것은 `--exclude <패턴>` 이다.
- 복사는 `local` 을 허브로 한다. 원격에만 있는 파일을 로컬로 받은 뒤 다른 원격으로 보낸다. 서버끼리 직접 ssh 가 안 되어도 동작한다.

### 3. 지우기 요청

"DRM 걸린 파일 지워" 같은 삭제는 이 스크립트가 하지 않는다. 대상을 헤더·이름으로 식별해 목록을 먼저 보여 주고, 사용자 지시 범위만 호스트마다 지운다. 식별할 때 내용을 열거나 복호화하지 않는다. 예를 들어 Fasoo DRM 은 파일 앞 8바이트가 `\x9b DRMONE` 이다. Office 비밀번호 암호화(`EncryptionInfo`·`StrongEncryptionDataSpace` 스트림)는 DRM 이 아니므로 따로 보고한다.

## 함정

- `union_sync.py` 원격 쪽은 `python3` 과 GNU tar(`--skip-old-files`)가 필요하다. 원격이 맥이면 tar 가 bsdtar 라 실패한다.
- ssh `ControlPersist` 소켓이 살아 있으면 끊긴 별칭도 되는 것처럼 보인다. 실패하면 별칭부터 의심한다.
- 맥에서 받은 파일은 맥 umask 를 따른다. 다른 계정이 읽어야 하면 그 자리에서 권한을 맞춘다.

## Learned warnings

- (2026-10-15) ews 의 `docs/` 를 맥·pig·doksam 에서 손으로 맞췄다. doksam 에 같은 xlsx 가 NFC·NFD 두 이름으로 남아 있었다. 예전에 맥에서 rsync 로 민 흔적이다. 그래서 비교 키를 NFC 로 두고 원격에는 NFC 이름으로 쓴다 (#248).
- (2026-10-15) 디스크 파일 수로 비교하니 pig 가 2971, 추적 파일은 2975 로 어긋나 보였다. 추적 심링크 4개가 `find -type f` 에서 빠진 것이었다. 목록 해시로 비교한다 (#248).

## 완료 조건

- `repo_state.py` 판정이 "같음"이다. 아니면 어긋난 호스트와 이유를 보고한다.
- `union_sync.py --apply` 재검증에서 채울 것이 0이다. 남은 충돌·NFC/NFD 중복은 경로와 해시로 보고한다.
- 보고에는 호스트별 추적 파일 수와 목록 해시 앞 12자를 적는다.
