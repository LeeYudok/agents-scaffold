---
paths:
  - "Dockerfile"
  - "Containerfile"
  - "*.dockerfile"
  - "docker-compose*.yml"
  - "docker-compose*.yaml"
  - "**/*.container"
  - "**/*.service"
  - "**/*.network"
  - "quadlet/**"
  - "playbooks/**/*.yml"
  - "playbooks/**/*.yaml"
  - "ansible/**/*.yml"
---

# Docker/Podman/Ops 규칙

## 컨테이너 표준
- **런타임**: rootless **podman** + **Quadlet** (`systemctl --user`, linger=yes).
- `docker run` 직접 실행 금지 → `.container` Quadlet 유닛으로 관리.
- 호스트 → 컨테이너: nginx 리버스프록시 (`127.0.0.1:<port>`) + certbot TLS.

## 네트워킹 (pasta)
- 컨테이너 → 호스트 서비스: `host.docker.internal` (pasta 네트워킹, `127.0.0.1` 아님).
- 신규 컨테이너 볼륨: SELinux `:z`(공유) 또는 `:Z`(전용) 레이블 명시 필수.
- `--network=host` 금지 (rootless podman에서 제한적).

## Containerfile 린트
- `hadolint Containerfile` — CI에서 통과 필수.
- `DL` 규칙 ignore 시 주석 사유 명시: `# hadolint ignore=DL3008`.
- 멀티스테이지 빌드 권장 — 빌드 의존성을 런타임 이미지에 포함 금지.
- 베이스 이미지: 태그 고정 (`latest` 금지). digest 핀 권장 (보안 중요 환경).

## 보안 스캔
- `trivy image --severity CRITICAL --exit-code 1` — CRITICAL 0건 필수.
- HIGH 취약점: 경고, 차단 아님. 단 CRITICAL은 배포 차단.
- `grype` 또는 `trivy` 중 하나 CI에 필수.

## YAML / Ansible
- `yamllint` — `.yamllint.yml` 기준.
- `ansible-lint` — playbook 변경 시 필수.
- `ansible-playbook --syntax-check` — 커밋 전.
- dry-run: `--check --diff` — 실제 배포 전 반드시 확인.

## Quadlet 유닛
- 유닛 파일 변경 시 `systemd-analyze verify <파일>` 먼저.
- 재시작 정책: `Restart=on-failure` 기본. `always`는 이유 명시.
- 환경변수: `EnvironmentFile=%h/deploy/<svc>/.env` 패턴. 유닛 파일 내 하드코딩 금지.

## P0
- 시크릿/토큰 Containerfile·playbook·유닛 파일 내 하드코딩 금지
- `hadolint` CRITICAL 에러 없이 커밋
- `.env` git 스테이징 금지

## P1
- `trivy` CRITICAL 0건 없이 이미지 배포 금지
- 신규 서브도메인: nginx conf 추가 + certbot 인증서 발급 확인 후 배포
- Quadlet 유닛 변경 시 `systemctl --user daemon-reload` 후 `systemctl --user restart <unit>` 순서 준수

## P2 (권장)
- 이미지 레이어 분석: `dive` 로 불필요한 파일 포함 확인
- `.dockerignore` / `.containerignore` 유지 — 빌드 컨텍스트 최소화
