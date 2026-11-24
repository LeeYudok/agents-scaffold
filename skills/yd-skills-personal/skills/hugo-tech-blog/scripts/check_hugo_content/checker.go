package main

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode"
	"unicode/utf8"
)

var (
	requiredKeys = map[string]struct{}{
		"date":                {},
		"draft":               {},
		"title":               {},
		"description":         {},
		"categories":          {},
		"tags":                {},
		"series":              {},
		"showTableOfContents": {},
	}

	topHeadingRE     = regexp.MustCompile(`^##\s+([0-9]+)\.\s+\S`)
	frontmatterKeyRE = regexp.MustCompile(`^([A-Za-z][A-Za-z0-9_-]*)\s*=`)
	titleRE          = regexp.MustCompile(`^title\s*=\s*['"]([^'"]+)['"]`)
	dateRE           = regexp.MustCompile(`^date\s*=\s*'[^']+'`)
	chapterFileRE    = regexp.MustCompile(`^([0-9]{2})-.+\.md$`)
	placeholderRE    = regexp.MustCompile(`(?i)^\s*(([-*+]\s+|[0-9]+[.)]\s+)?(TODO|FIXME):|<!--\s*(TODO|FIXME):)`)
)

// Issue is one structural problem found in a chapter file.
type Issue struct {
	Line    int
	Message string
}

// Result is the validation result for one chapter file.
type Result struct {
	Path   string
	Issues []Issue
}

func (r *Result) add(line int, message string) {
	r.Issues = append(r.Issues, Issue{Line: line, Message: message})
}

// ChapterFiles expands directories to chapter markdown files and keeps explicit
// file paths as provided.
func ChapterFiles(paths []string) []string {
	var found []string
	for _, raw := range paths {
		info, err := os.Stat(raw)
		if err == nil && info.IsDir() {
			var matches []string
			_ = filepath.WalkDir(raw, func(path string, entry fs.DirEntry, walkErr error) error {
				if walkErr != nil {
					return nil
				}
				if entry.IsDir() {
					return nil
				}
				if chapterFileRE.MatchString(entry.Name()) {
					matches = append(matches, path)
				}
				return nil
			})
			sort.Strings(matches)
			found = append(found, matches...)
			continue
		}
		found = append(found, raw)
	}
	return found
}

// CheckFile validates the frontmatter and Markdown structure of one chapter.
func CheckFile(path string) Result {
	result := Result{Path: path}
	raw, err := os.ReadFile(path)
	if err != nil {
		result.add(0, fmt.Sprintf("cannot read file: %v", err))
		return result
	}

	if len(raw) >= 3 && raw[0] == 0xef && raw[1] == 0xbb && raw[2] == 0xbf {
		result.add(1, "UTF-8 BOM is not allowed")
	}
	if strings.ContainsRune(string(raw), '\r') {
		result.add(1, "CR or CRLF line ending found; use LF")
	}
	if !utf8.Valid(raw) {
		result.add(1, "invalid UTF-8")
		return result
	}

	text := string(raw)
	if text != "" && !strings.HasSuffix(text, "\n") {
		result.add(len(splitLines(text)), "file must end with a newline")
	}

	lines := splitLines(text)
	if len(lines) == 0 || strings.TrimSpace(lines[0]) != "+++" {
		result.add(1, "file must start with TOML frontmatter delimiter +++")
		return result
	}

	closing := -1
	for index, line := range lines[1:] {
		if strings.TrimSpace(line) == "+++" {
			closing = index + 1
			break
		}
	}
	if closing < 0 {
		result.add(1, "closing TOML frontmatter delimiter +++ was not found")
		return result
	}

	frontmatter := lines[1:closing]
	keys := make(map[string]struct{})
	var dateValue string
	var titleValue string
	hasDateValue := false
	hasTitleValue := false

	for _, line := range frontmatter {
		if match := frontmatterKeyRE.FindStringSubmatch(line); match != nil {
			keys[match[1]] = struct{}{}
		}
		if strings.HasPrefix(line, "date") {
			dateValue = line
			hasDateValue = true
		}
		if strings.HasPrefix(line, "title") {
			if match := titleRE.FindStringSubmatch(line); match != nil {
				titleValue = match[1]
				hasTitleValue = true
			}
		}
	}

	var missing []string
	for key := range requiredKeys {
		if _, ok := keys[key]; !ok {
			missing = append(missing, key)
		}
	}
	sort.Strings(missing)
	if len(missing) > 0 {
		result.add(2, fmt.Sprintf("missing frontmatter keys: %s", strings.Join(missing, ", ")))
	}

	if hasDateValue && !dateRE.MatchString(dateValue) {
		result.add(2, "date must be a quoted TOML string")
	}

	filenameMatch := chapterFileRE.FindStringSubmatch(filepath.Base(path))
	if filenameMatch != nil && hasTitleValue {
		expectedPrefix := filenameMatch[1] + "장."
		if !strings.HasPrefix(titleValue, expectedPrefix) {
			result.add(2, fmt.Sprintf("title must start with '%s' to match the filename", expectedPrefix))
		}
	}

	fenceCount := 0
	inFence := false
	var topNumbers []int
	headingLocations := make(map[string]int)

	for index := closing + 1; index < len(lines); index++ {
		lineNumber := index + 1
		line := lines[index]

		if strings.HasPrefix(line, "```") {
			fenceCount++
			inFence = !inFence
			continue
		}
		if inFence {
			continue
		}
		if strings.TrimRightFunc(line, unicode.IsSpace) != line {
			result.add(lineNumber, "trailing whitespace")
		}
		if placeholderRE.MatchString(line) {
			result.add(lineNumber, "unfinished TODO or FIXME placeholder")
		}

		if heading, ok := parseHeading(line); ok {
			if first, exists := headingLocations[heading]; exists {
				result.add(lineNumber, fmt.Sprintf("duplicate heading; first seen at line %d", first))
			} else {
				headingLocations[heading] = lineNumber
			}
		}

		if match := topHeadingRE.FindStringSubmatch(line); match != nil {
			topNumbers = append(topNumbers, atoi(match[1]))
		}
	}

	if fenceCount%2 != 0 {
		result.add(closing+1, "code fences are not balanced")
	}

	if !equalNumbers(topNumbers, sequence(len(topNumbers))) {
		result.add(closing+1, fmt.Sprintf("top-level section numbers must be continuous: found %v", topNumbers))
	}

	return result
}

func splitLines(text string) []string {
	if text == "" {
		return nil
	}

	normalized := strings.ReplaceAll(text, "\r\n", "\n")
	normalized = strings.ReplaceAll(normalized, "\r", "\n")
	lines := strings.Split(normalized, "\n")
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}
	return lines
}

func parseHeading(line string) (string, bool) {
	hashes := 0
	for hashes < len(line) && line[hashes] == '#' {
		hashes++
	}
	if hashes < 2 || hashes > 6 {
		return "", false
	}
	if hashes == len(line) || !unicode.IsSpace(rune(line[hashes])) {
		return "", false
	}

	heading := strings.TrimSpace(line[hashes:])
	if heading == "" {
		return "", false
	}
	return heading, true
}

func sequence(length int) []int {
	result := make([]int, length)
	for index := range result {
		result[index] = index + 1
	}
	return result
}

func equalNumbers(left, right []int) bool {
	if len(left) != len(right) {
		return false
	}
	for index := range left {
		if left[index] != right[index] {
			return false
		}
	}
	return true
}

func atoi(value string) int {
	result := 0
	for _, char := range value {
		result = result*10 + int(char-'0')
	}
	return result
}
