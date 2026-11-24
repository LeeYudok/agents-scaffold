---
name: hugo-tech-blog
description: "Write, expand, validate, and safely publish Korean Hugo technical-course chapters in the dok123 Rocky Linux blog. Use `yd-writer-kr` for sentence-level Korean style."
metadata:
  internal: true
---

# Hugo Tech Blog

Use this skill for Korean technical-course work in the `dok123` Hugo blog: creating or expanding chapters, making whole-course skeletons, reviewing consistency, validating Markdown, and committing or pushing when explicitly requested. Do not use it for unrelated Hugo theme, CSS, or deployment work.

Read [references/dok123-linux-course.md](references/dok123-linux-course.md) before editing. Treat the repository's `AGENTS.md` as authoritative when it is stricter than this skill.
This skill governs the course structure and validation; for sentence-level Korean style, follow the `yd-writer-kr` skill.

## Working Rules

- Inspect the target chapter, adjacent chapters, the Linux section index, and `git status --short --branch` before editing.
- Start at the first skeleton chapter. The Progress section in the project reference lists what is written and what is still a skeleton.
- Preserve the existing TOML frontmatter and chapter numbering. Update `description` and `tags` when the chapter gains a substantial topic.
- Edit the chapter directly in the WSL checkout. The `hugo-blog` container mounts the content root, so a saved file is rebuilt and served on `http://localhost:1313/` with no separate copy step.
- Do not overwrite unrelated uncommitted changes. Stage only files changed for the requested task.
- Keep Korean prose natural and practical. Commands, paths, identifiers, and error messages stay literal.
- Do not invent command output, vendor support, certifications, or compliance guarantees. State uncertainty or mark a result as unverified.
- Connect advanced material to the correct later chapter instead of duplicating it in an introductory chapter.

## Chapter Shape

Match nearby chapters. Unless the user requests another structure, use this progression:

1. `이 장에서 확인할 질문`
2. `필요한 배경과 위험`
3. `실행할 명령`
4. `예상 결과와 확인 기준`
5. `실패했을 때 되돌리는 방법`
6. `운영 환경에 적용할 때의 차이`
7. `요약과 다음 장 연결`

Prefer concrete workflows, comparison tables, verification commands, failure recovery, and operational tradeoffs over generic explanations. The writing should help a reader run and verify the lesson, not merely read it.

## Validation

Run the bundled checker against every changed chapter:

```bash
go run "<스킬경로>/scripts/check_hugo_content" <chapter.md>
```

Resolve `<스킬경로>` to the directory containing this `SKILL.md`.

Then run:

```bash
git diff --check
```

If `AGENTS.md` or `AGENTS.yaml` changed, also run `./tests/check-agents-yaml.sh`. If Hugo or the project's Podman image is available, build the site with the command documented in the project reference. Report any validation that could not be run.

When changing the bundled checker or its contract, run:

```bash
cd "<스킬경로>"
go test ./...
```

## Git Boundary

Commit and push only when the user explicitly asks for it. Before committing, confirm that the diff contains only the intended chapter or documentation changes and that validation passed. Match the repository's history with an ASCII message such as `docs(hugo): add Rocky Linux 9.8 lesson 09` or `docs(hugo): expand lesson 03 disk partitioning`.

After pushing, verify that local `HEAD` and `origin/main` resolve to the same commit. Never use force push or destructive reset operations.

## Learned warnings

- (2026-11-17) The first draft required opening the target file in Sublime Text and staging it on a D-drive path. No `AGENTS.md` rule asks for either. Edit the chapter directly in the WSL checkout; the `hugo-blog` container rebuilds it on save.
- (2026-11-17) The host has no `hugo` binary. Build through the `localhost/hugo:0.170.0` Podman container, and verify the running `hugo-blog` container on `http://localhost:1313/`.
- (2026-11-17) `ps`, `ss`, `pstree`, and `lsof` were missing from the Rocky 9.8 lab host, so real command output could not be gathered. Install them first with `dnf install procps-ng iproute psmisc lsof`.
