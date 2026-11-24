package main

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

const validChapterText = `+++
date = '2026-11-17'
draft = false
title = '08장. 사용자, 그룹, 파일 권한'
description = '사용자, 그룹, 권한, 특수 권한과 sudo 기초를 확인한다.'
categories = ['linux']
tags = ['rocky-linux', 'linux', 'permissions']
series = ['rocky-linux-9.8']
showTableOfContents = true
+++` + `

## 1. 확인할 질문

권한을 읽고 바꾸는 기준을 확인한다.

` + "```bash" + `
printf 'ok  \n'
SPACE_MARKER
# TODO: trailing spaces and markers inside code fences are fixtures
` + "```" + `

## 2. 실행할 명령

` + "```bash" + `
id
` + "```" + `

## 3. 요약

다음 장에서 계정 정책을 다룬다.
`

func writeChapter(t *testing.T, root, name, text string) string {
	t.Helper()
	path := filepath.Join(root, name)
	if err := os.WriteFile(path, []byte(text), 0o644); err != nil {
		t.Fatalf("write chapter: %v", err)
	}
	return path
}

func messages(result Result) []string {
	resultMessages := make([]string, 0, len(result.Issues))
	for _, issue := range result.Issues {
		resultMessages = append(resultMessages, issue.Message)
	}
	return resultMessages
}

func containsMessage(result Result, want string) bool {
	for _, message := range messages(result) {
		if strings.Contains(message, want) {
			return true
		}
	}
	return false
}

func TestValidChapterPasses(t *testing.T) {
	path := writeChapter(t, t.TempDir(), "08-permissions.md", validChapterText)
	if result := CheckFile(path); len(result.Issues) != 0 {
		t.Fatalf("expected no issues, got %#v", result.Issues)
	}
}

func TestMissingClosingFrontmatterFails(t *testing.T) {
	text := strings.Replace(validChapterText, "\n+++\n\n## 1.", "\n\n## 1.", 1)
	path := writeChapter(t, t.TempDir(), "08-permissions.md", text)
	if !containsMessage(CheckFile(path), "closing TOML frontmatter delimiter +++ was not found") {
		t.Fatal("expected missing closing frontmatter issue")
	}
}

func TestTitleFilenameMismatchFails(t *testing.T) {
	text := strings.Replace(validChapterText, "'08장.", "'09장.", 1)
	path := writeChapter(t, t.TempDir(), "08-permissions.md", text)
	if !containsMessage(CheckFile(path), "title must start with '08장.'") {
		t.Fatal("expected filename/title mismatch issue")
	}
}

func TestBomAndCrlfFail(t *testing.T) {
	path := writeChapter(t, t.TempDir(), "08-permissions.md", validChapterText)
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read chapter: %v", err)
	}
	raw = append([]byte{0xef, 0xbb, 0xbf}, []byte(strings.ReplaceAll(string(raw), "\n", "\r\n"))...)
	if err := os.WriteFile(path, raw, 0o644); err != nil {
		t.Fatalf("write chapter: %v", err)
	}
	result := CheckFile(path)
	if !containsMessage(result, "UTF-8 BOM is not allowed") {
		t.Fatal("expected BOM issue")
	}
	if !containsMessage(result, "CR or CRLF line ending found; use LF") {
		t.Fatal("expected CRLF issue")
	}
}

func TestTopLevelHeadingsMustBeContinuous(t *testing.T) {
	text := strings.Replace(validChapterText, "## 2.", "## 3.", 1)
	path := writeChapter(t, t.TempDir(), "08-permissions.md", text)
	if !containsMessage(CheckFile(path), "top-level section numbers must be continuous") {
		t.Fatal("expected heading continuity issue")
	}
}

func TestUnbalancedFenceFails(t *testing.T) {
	path := writeChapter(t, t.TempDir(), "08-permissions.md", validChapterText+"\n```\n")
	if !containsMessage(CheckFile(path), "code fences are not balanced") {
		t.Fatal("expected unbalanced fence issue")
	}
}

func TestFencedContentIsIgnored(t *testing.T) {
	text := strings.Replace(validChapterText, "SPACE_MARKER", "echo keep-space  ", 1)
	path := writeChapter(t, t.TempDir(), "08-permissions.md", text)
	if result := CheckFile(path); len(result.Issues) != 0 {
		t.Fatalf("expected fenced content to be ignored, got %#v", result.Issues)
	}
}

func TestStandaloneTodoPlaceholderFails(t *testing.T) {
	path := writeChapter(t, t.TempDir(), "08-permissions.md", validChapterText+"\nTODO: replace this paragraph.\n")
	if !containsMessage(CheckFile(path), "unfinished TODO or FIXME placeholder") {
		t.Fatal("expected TODO placeholder issue")
	}
}

func TestTodoExamplesAreNotPlaceholders(t *testing.T) {
	example := "예를 들어 TODO 표시를 FIXME로 바꾼다.\n\n| 명령 | 의미 |\n|---|---|\n| `:g/^TODO:/normal! A # REVIEW` | 검토 표시를 붙인다. |\n\n"
	text := strings.Replace(validChapterText, "## 3.", example+"## 3.", 1)
	path := writeChapter(t, t.TempDir(), "08-permissions.md", text)
	if result := CheckFile(path); len(result.Issues) != 0 {
		t.Fatalf("expected TODO examples not to be placeholders, got %#v", result.Issues)
	}
}

func TestDirectoryScanIgnoresNonChapterMarkdown(t *testing.T) {
	root := t.TempDir()
	chapter := writeChapter(t, root, "08-permissions.md", validChapterText)
	if err := os.WriteFile(filepath.Join(root, "README.md"), []byte("not a course chapter\n"), 0o644); err != nil {
		t.Fatalf("write README: %v", err)
	}
	notes := filepath.Join(root, "notes")
	if err := os.Mkdir(notes, 0o755); err != nil {
		t.Fatalf("create notes directory: %v", err)
	}
	nested := writeChapter(t, notes, "09-draft.md", strings.Replace(validChapterText, "08장.", "09장.", 1))
	want := []string{chapter, nested}
	if got := ChapterFiles([]string{root}); !reflect.DeepEqual(got, want) {
		t.Fatalf("chapter files mismatch: got %v want %v", got, want)
	}
}
