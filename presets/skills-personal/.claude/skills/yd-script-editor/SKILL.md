---
name: yd-script-editor
description: 시연·데모 영상의 내레이션 대본(md 표)을 웹 에디터로 고치고, 줄별 음성 합성(OmniVoice)·시각 맞춤·장면 렌더·배경음 믹싱·장면 클립까지 레포 설정(script-editor.json) 하나로 돌릴 때. 레포마다 에디터 서버(launchd/systemd)와 공개 터널을 구성한다
---

# yd-script-editor

## 역할

시연 영상 제작 파이프라인의 **코드 원천**이다. 레포는 설정 파일 하나와 콘텐츠만 가진다.

| 어디에 | 무엇 |
|---|---|
| 이 스킬 | 에디터(Node 서버 + Vite 화면, `assets/app`), 엔진(음성·시각·렌더·믹스·클립, `assets/engine`), 설치기·CLI(`scripts/`) |
| 레포 | `script-editor.json`, 대본 md·합성 입력 json(`content`), 음성·클립·썸네일, 장면 데이터 `.py`(`render.scenes`), 발음 단어 표 |
| 런타임 `~/.local/share/yd-script-editor` | `app`(+node_modules)·`engine` 복사본, `venv`(Pillow), `dist/<name>`(레포별 빌드) |

**레포의 데이터(대본·장면 좌표·녹화 경로·문구·발음 단어)를 이 스킬에 넣지 않는다.** 이 스킬은 공개 저장소에 있다. 예시·테스트 픽스처는 지어낸 내용만 쓴다.

## 레포 설정 `<레포>/script-editor.json`

```json
{
  "name": "demo",
  "content": "docs/editor",
  "prefix": "대본-",
  "base": "/editor",
  "port": 18750,
  "pronounce": "docs/editor/pronounce.tsv",
  "synth": { "python": "~/.cache/omnivoice-venv/bin/python", "cache": "~/.cache/yd-script-editor/demo" },
  "videos": { "dir": "~/Movies/demo", "pattern": "demo-*.mp4" },
  "render": { "scenes": "docs/editor/render/scenes.py", "out": "~/Movies/demo/build", "music": "~/Movies/demo/music.wav" },
  "public": [
    { "ssh": "relay-host", "url": "https://example.com/editor/" },
    { "ssh": "lan-host", "url": "https://editor.lan.example/editor/" }
  ]
}
```

- `name`: 영소문자·숫자·`-`. 서비스 라벨 `com.<사용자>.script-editor.<name>` 이 된다.
- 상대 경로는 레포 기준, `~` 는 홈이다. `name` 말고는 전부 선택이다.
- `prefix`: 대본 파일 이름 앞부분. 라벨은 `<prefix><라벨>.md` 에서 나온다.
- `base`: 공개 경로. 화면은 레포마다 이 base 로 빌드된다.
- `pronounce`: TSV(`자막 낱말<탭>읽는 말`). 영문 낱말은 앞뒤가 영문이 아닐 때만 바꾼다.
- `videos.pattern`: 완성 영상 이름. `*` 자리가 영상 키다. 영상 비교 페이지와 믹스 출력이 쓴다.
- `render.scenes`: 장면 데이터 모듈. 필요한 이름은 `assets/engine/render/render.py` docstring 에 있다.
- `public`: 공개 대상 `{ssh, url}` 하나 또는 그 배열. `--public` 이면 대상마다 역방향 터널(`autossh -R 127.0.0.1:<port>`)을 서비스 `<라벨>.tunnel.<ssh 호스트>` 로 띄운다.
  - `ssh` 는 SSH 호스트 이름만 쓴다. 그 호스트의 리버스 프록시가 `base/` 를 `127.0.0.1:<port>` 로 넘기고 `Host: 127.0.0.1:<port>` 를 넣어야 한다(서버가 Host 를 검사한다).
  - 원격 sshd 의 GatewayPorts 가 꺼져 있으면 터널은 루프백에만 열린다. 컨테이너(k3s 등) 프록시가 받으려면 원격에서 socat 같은 중계를 따로 둔다.
  - 공개 주소는 프록시 쪽 인증을 붙인다. 에디터 자체에는 로그인이 없다.

## 콘텐츠 폴더 구조

```
<content>/
  <prefix><라벨>.md      대본 표: | # | 시각 | 장면 | [화면 자막 |] 자막·대본 | 읽는 말 | [AI 프롬프트 |]
  <prefix><라벨>.json    음성 합성 입력(ref_audio·lines[start·max·say·speak]). 있을 때만 저장 시 재합성
  ids.json               주소 번호 → 대본 파일(서버가 만든다. /<base>/<번호> 로 연다)
  audio/<라벨>/NN.m4a    줄 음성(+NN.json)
  clips/<라벨>/NN.mp4    장면 영상 · frames/<라벨>/NN.jpg 썸네일
```

머리말의 `목표 길이: N초` 는 시각 맞춤과 렌더의 영상 길이가 된다.

## 워크플로

1. **구성**: `sh <스킬경로>/scripts/setup.sh <레포> [--public]`
   - 런타임을 동기화하고 의존성 설치, 레포별 빌드, 서비스 등록, 응답 확인까지 한다.
   - 다시 돌리면 그게 업데이트다.
   - 상태는 `setup.sh <레포> status`, 제거는 `setup.sh <레포> remove`.
   - 포트를 다른 프로세스가 잡고 있으면 멈춘다. 예전 방식으로 띄운 서버는 먼저 내린다.
2. **조회·수정**: `python3 <스킬경로>/scripts/se.py` 를 쓴다. 대본 md 를 손으로 고치지 않는다(서버가 형식을 검증하고 재합성 대기열에 넣는다).
   - `list`: 번호·라벨·줄 수
   - `show <대본>`: 줄 표
   - `set <대본> <줄> <칸> <값>`: 칸은 `time scene screen say speak prompt same`. 값 안의 줄바꿈은 `\n`.
   - `<대본>` 은 주소 번호·라벨·파일 이름 어느 것이나 된다.
   - `say` 만 고치면 읽는 말은 따라 바뀌지 않는다. 화면에서는 따라가지만 CLI 에서는 `speak` 를 같이 주거나 `same 1` 로 둔다.
3. **음성**: `se.py synth <대본> [줄…|all]` 를 쓴다.
   - 설정 `synth.python` 의 OmniVoice venv 로 돈다.
   - 재전사 유사도가 0.85 미만이면 다시 만든다. 결과 `NN.json` 의 `sim` 을 보고한다.
4. **시각**: `se.py fit <대본>` 로 미리 본 뒤 `--apply` 한다. 실제 음성 길이에 여유를 똑같이 나눠 마지막 줄이 목표 길이에서 끝나게 한다.
5. **영상**:
   - `se.py render <대본> --check`: 줄마다 확인 프레임 `check.jpg` 만 만든다.
   - `se.py render <대본>`: `video-only.mp4` 를 만든다.
   - `se.py intro <대본> <html> <초>`: 1장 HTML 을 녹화해 둔다(선택).
   - `se.py mix <대본>`: 완성 영상을 만들고 장면 클립까지 다시 자른다.
   - 썸네일은 `render --thumbs`.
6. **확인**: `se.py url <대본>` 의 주소를 사용자에게 준다. 공개 주소가 있으면 그것도 준다.

## 엔진을 고칠 때

- 그리기·합성 로직은 `assets/engine/render/render.py`, 공용 바탕은 `base.py` 에 있다.
- 새 연출에 필요한 값(좌표·문구·경로)은 엔진에 상수로 넣지 말고 장면 데이터 모듈의 이름으로 받는다. 엔진 기본값은 빈 문자열·중립 값이다.
- 프레임 색은 장면 데이터의 `THEME`(bg·fg·muted·accent·step_todo·step_todo_bar·panel_line·outro_accent·highlight)로 바꾼다. 단계 표지는 `sign_dim`(누름 색)·`sign_num`·`sign_name`·`sign_sub` 로 따로 받는다(밝은 프레임에서 fg 가 표지 위에서 안 읽힌다). 빠진 키는 엔진 기본값이다.
- 레포 고유 프레임 꾸밈(등급 띠·신호 배지·카드 패널 등)은 장면 데이터의 `decorate_frame(im, draw, ctx)`·`decorate_card(im, draw, ctx)` 에 그린다. 엔진이 프레임·카드를 그린 뒤 부르고, `ctx` 에 줄·단계·카드 종류·좌표·`font`·`tw`·테마를 넘긴다.
- 렌더를 바꾸면 이관 전후 `render --check` 의 `check.jpg` md5, 또는 `--only N` 결과 mp4 의 `ffmpeg -f framemd5` 를 비교해 의도한 차이만 났는지 본다.

## 테스트로 지키는 규칙

- 설정의 상대 경로는 레포 기준이고, 대본은 주소 번호·라벨·파일 이름 어느 것으로도 찾는다
- 설정 파일은 현재 폴더에서 위로 올라가며 찾는다
- `~/` 는 홈으로 편다
- 대본 표의 시각·화면 자막·AI 프롬프트와 목표 길이를 읽고, 인트로는 0초·마지막 줄은 목표 길이까지로 둔다
- 머리말에 목표 길이가 없으면 렌더를 시작하지 않는다
- `se.py set` 은 서버 API 로 etag 와 함께 문서 전체를 저장하고 다른 줄은 건드리지 않는다
- 읽는 말을 직접 주면 '자막과 같음' 을 끈다
- 모르는 칸·없는 줄은 저장하지 않고 실패한다
- 없는 대본은 실패한다
- 설정 파일이 없으면 런타임을 만들기 전에 멈춘다
- 서비스 이름(name)은 영소문자·숫자·- 만 받는다
- `public` 은 대상 하나(객체)나 여러 개(배열)를 받고, 대상마다 터널 서비스를 하나씩 둔다
- 예전 형식(객체 하나)도 그대로 받는다
- `public.ssh` 는 SSH 호스트 이름(영문·숫자·`._@-`)만 받는다

## 완료 조건

- `setup.sh <레포> status` 에서 서비스 running, 로컬 응답. `--public` 이면 대상마다 터널 응답도.
- 수정한 대본은 `se.py show` 로 다시 읽어 바뀐 칸을 확인했다. 재합성이 걸렸으면 `api/synth` 오류가 없다.
- 렌더·믹스 결과 경로와 길이, 음량(믹스 로그의 `output_i`)을 보고했다.
