---
name: feedback_secret-redaction-bsd-sed
description: 시크릿 파일을 grep 으로 볼 때 sed 마스킹에 기대지 않는다 — macOS BSD sed 는 \s 를 몰라 `KEY = "값"` 형식이 그대로 출력됐다 (2026-11-14 네이버 API 시크릿 노출)
metadata:
  type: feedback
---

2026-11-14 `~/workspace/.env.toml` 에서 네이버 개발자센터 키 위치를 찾으며 `grep -i naver | sed -E 's/(=|:)\s*.../<redacted>/'` 로 값을 가리려 했다.
macOS 의 BSD sed 는 `\s` 를 공백으로 해석하지 않는다. 그래서 `KEY = "값"` 처럼 `=` 뒤에 공백이 있는 TOML 줄은 치환되지 않았고 `NAVER_CLIENT_SECRET` 원문이 대화에 찍혔다. 사용자에게 재발급을 권했다.

**Why:** 마스킹이 실패해도 명령은 성공으로 끝나서 출력이 나간 뒤에야 안다. 시크릿 노출은 되돌릴 수 없다.

**How to apply:**
- 시크릿 파일에서는 값을 출력하는 명령 자체를 쓰지 않는다. 키 이름만 뽑는다: `grep -oE '^[A-Za-z0-9_]+' file` 또는 `grep -oE '^\s*[A-Z0-9_]+\s*=' file | tr -d ' ='` 처럼 `=` 앞만 잘라 낸다.
- 섹션·키 존재 확인은 `python3 -c` 로 파싱해 키 이름만 출력한다(값 변수는 print 하지 않는다).
- sed 마스킹이 꼭 필요하면 `[[:space:]]` 를 쓰고, 먼저 가짜 값 파일로 시험한다.
