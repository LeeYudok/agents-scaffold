# dok123 Linux Course

Read this file before editing the Rocky Linux 9.8 course.

## Repository

| Item | Value |
|---|---|
| WSL checkout | `/home/dok123/workspace/jefecito/dok123` |
| Git remote | `http://localhost:3000/225090/dok123.git` |
| Content root | `hugo_home/content/linux` |
| Hugo root | `hugo_home` |
| Hugo version | `0.170.0` in `localhost/hugo:0.170.0` |
| Preview | `http://localhost:1313/` through the `hugo-blog` container |

The repository keeps its own `AGENTS.md` and `AGENTS.yaml`. Read them before changing repository structure, commands, or workflow documentation.

## Chapter Map

| No. | Title |
|---:|---|
| 01 | Rocky Linux 9.8과 RHEL 호환 생태계 |
| 02 | 가상 머신과 설치 ISO 준비 |
| 03 | 설치 프로그램과 디스크 구성 |
| 04 | 설치 직후 기준 상태 만들기 |
| 05 | WSL2로 Rocky Linux 9.8 활용하기 |
| 06 | 셸, 경로, 파일 탐색 |
| 07 | vi / vim 편집기 실전 활용 |
| 08 | 사용자, 그룹, 파일 권한 |
| 09 | 프로세스, 포트, 로그 확인 |
| 10 | dnf와 저장소 관리 |
| 11 | systemd 서비스와 타깃 |
| 12 | 계정과 sudo 정책 |
| 13 | SSH 키와 접속 제한 |
| 14 | SELinux 이해와 복구 |
| 15 | firewalld와 서비스 공개 |
| 16 | 서버 보안 기준 점검 |
| 17 | 디스크, 파티션, 파일시스템 |
| 18 | LVM으로 공간 확장하기 |
| 19 | XFS, /etc/fstab, 스왑 |
| 20 | NetworkManager와 nmcli |
| 21 | 스토리지·네트워크 장애 진단 |
| 22 | nginx 웹 서비스와 TLS |
| 23 | PostgreSQL 데이터 보존 |
| 24 | Docker 설치와 컨테이너 운영 |
| 25 | Podman으로 서비스 격리 |
| 26 | Quadlet과 자동 시작 |
| 27 | 백업과 systemd 타이머 |
| 28 | 안전한 Bash 운영 스크립트 |
| 29 | Ansible로 반복 설정 줄이기 |
| 30 | 패치와 롤백 절차 |
| 31 | 장애 대응 런북과 종합 실습 |

## Progress

On 2026-11-17, chapters 01 through 09 are written and chapters 10 through 31 are still skeletons. A skeleton still contains the `집필 골격` line and the `집필 완료 체크` list. Recheck and start at the first skeleton:

```bash
for f in hugo_home/content/linux/[0-9][0-9]-*.md; do
  printf '%-42s stub=%s\n' "$(basename "$f")" "$(grep -c '집필 골격\|집필 완료 체크' "$f")"
done
```

## Content Conventions

Chapter files are named `NN-topic.md` and begin with TOML frontmatter.

```toml
+++
date = '2026-11-17'
draft = false
title = '08장. 사용자, 그룹, 파일 권한'
description = '사용자, 그룹, 권한, 특수 권한과 sudo 기초를 확인한다.'
categories = ['linux']
tags = ['rocky-linux', 'linux', 'permissions']
series = ['rocky-linux-9.8']
showTableOfContents = true
+++
```

Keep these rules:

- Use one sentence per line where practical.
- Keep UTF-8 without BOM and LF line endings.
- Number top-level sections continuously: `## 1.`, `## 2.`, and so on.
- Keep code fences balanced and include a language when useful.
- Distinguish commands the reader runs from expected output.
- Use the actual chapter numbers when linking advanced follow-up work.
- Do not add secrets, personal data, or private session output.

Closed-network chapters should distinguish platform selection from compliance claims. Explain technical reasons such as RHEL compatibility, RPM repository mirroring, long-lived major versions, SELinux, `firewalld`, systemd, patch provenance, and support risk. Do not state that a distribution itself provides financial regulatory certification.

## Checker Contract

`<스킬경로>/scripts/check_hugo_content` is the Go checker for every changed chapter. The Go regression and contract tests in `scripts/check_hugo_content/` and `tests/` treat these statements as the current contract:

- Chapter files are named `NN-topic.md` and begin with TOML frontmatter.
- A chapter is invalid when the closing TOML frontmatter delimiter `+++` is missing.
- A chapter is invalid when its filename chapter number and `title` prefix disagree.
- Keep UTF-8 without BOM and LF line endings.
- Number top-level sections continuously: `## 1.`, `## 2.`, and so on.
- Keep code fences balanced and include a language when useful.
- Ignore trailing whitespace and TODO/FIXME markers inside fenced code blocks.
- Outside code fences, `TODO:` and `FIXME:` placeholders are invalid; prose or examples that mention TODO/FIXME are allowed.
- A directory scan ignores Markdown files that do not match `NN-topic.md`.

## Edit Workflow

1. Check repository state with `git status --short --branch`.
2. Read the target chapter and adjacent chapters before changing it.
3. Edit the chapter directly in the WSL checkout. The `hugo-blog` container mounts the content root, so a saved file is rebuilt and served on `http://localhost:1313/` without a separate copy step.
4. Keep UTF-8 without BOM and LF line endings. If a file arrives with CRLF, normalize it with `sed -i 's/\r$//' <file>`.
5. Run the bundled Go checker and `git diff --check`.
6. Commit and push only when explicitly requested.

Use explicit file paths with `git add`. Do not stage with `git add -A`.

```bash
go run "<스킬경로>/scripts/check_hugo_content" <chapter.md>
cd "<스킬경로>" && go test ./...
```

## Hugo Build

The host does not currently have the `hugo` binary. The live preview container `hugo-blog` (verified 2026-11-17 with `podman inspect`) mounts `hugo_home` at `/site` and runs:

```text
hugo server --bind 0.0.0.0 --port 1313 --buildDrafts --baseURL http://localhost:1313/ --disableFastRender
```

It runs with `--buildDrafts`, so a draft chapter is also served. For a one-off build through Podman when the image is available:

```bash
podman run --rm --entrypoint hugo \
  -v /home/dok123/workspace/jefecito/dok123/hugo_home:/src:Z \
  -w /src localhost/hugo:0.170.0
```

For preview verification:

```bash
podman start hugo-blog
podman logs -f hugo-blog
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:1313/
```

If the container or image is unavailable, report that rendering was not verified.

## Lab Host Notes

The Rocky Linux 9.8 lab host did not ship `ps`, `ss`, `pstree`, or `lsof` by default. Install them before gathering real command output for a chapter:

```bash
sudo dnf install -y procps-ng iproute psmisc lsof
```

The live preview container `hugo-blog` already mounts `hugo_home`, so a saved chapter is rebuilt and served on `http://localhost:1313/`. Confirm a page with its status code and title:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' http://localhost:1313/linux/09-processes-ports-logs/
curl -fsS http://localhost:1313/linux/09-processes-ports-logs/ | grep -o '<title>[^<]*</title>'
```

## Repository Boundaries

- `hugo_home/themes/**` is an upstream theme boundary. Do not edit it for ordinary chapter work.
- `.agents/skills/**`, `.claude/**`, and generated agent files are infrastructure. Do not change them unless the request includes that scope.
- Update `AGENTS.md` and `AGENTS.yaml` together only when a documented path, command, version, or contract changes.
- Keep generated `hugo_home/public/**` changes out of chapter-only commits unless the user explicitly asks to publish build output.
