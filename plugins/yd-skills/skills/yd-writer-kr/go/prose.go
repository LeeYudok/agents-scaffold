package main

import (
	"regexp"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Go 의 \s·\d 는 ASCII 만 본다. 기존 Python·Rust 결과와 맞추려고 유니코드 공백·숫자를 직접 적는다.
const (
	space = `\s\v\x{85}\p{Z}`
	digit = `\p{Nd}`
)

var (
	lineBreaks = regexp.MustCompile(`\r\n|[\n\r\x0B\x0C\x1C-\x1E\x{85}\x{2028}\x{2029}]`)
	comments   = regexp.MustCompile(`<!--.*?-->`)
	inlineCode = regexp.MustCompile("`[^`\\n]*`")
	mdLink     = regexp.MustCompile(`!?\[([^\]]*)\]\([^)]*\)`)
	bareURL    = regexp.MustCompile(`https?://[^` + space + `]+`)
	emphasis   = regexp.MustCompile(`\*\*|__`)
	heading    = regexp.MustCompile(`^[` + space + `]*#{1,6}[` + space + `]+`)
	listMark   = regexp.MustCompile(`^[` + space + `]*(?:[-*+]|` + digit + `+[.)])[` + space + `]+(?:\[[ xX]\][` + space + `]+)?`)
)

// BodyLine 은 front matter·코드 블록·여러 줄 주석 밖의 줄이다. No 는 1부터 센다.
type BodyLine struct {
	No  int
	Raw string
}

// bodyLines 는 글 검사와 원문 대조가 함께 쓰는 1차 걸러내기다.
func bodyLines(text string) []BodyLine {
	lines := lineBreaks.Split(text, -1)
	start := 0
	if len(lines) > 0 && strings.TrimSpace(lines[0]) == "---" {
		for i := 1; i < len(lines); i++ {
			if strings.TrimSpace(lines[i]) == "---" {
				start = i + 1
				break
			}
		}
	}
	var out []BodyLine
	fence := ""
	inComment := false
	for index := start; index < len(lines); index++ {
		raw := lines[index]
		stripped := strings.TrimSpace(raw)
		if fence != "" {
			if strings.HasPrefix(stripped, fence) {
				fence = ""
			}
			continue
		}
		if strings.HasPrefix(stripped, "```") || strings.HasPrefix(stripped, "~~~") {
			fence = stripped[:3]
			continue
		}
		if inComment {
			if strings.Contains(raw, "-->") {
				inComment = false
			}
			continue
		}
		if strings.HasPrefix(stripped, "<!--") && !strings.Contains(stripped, "-->") {
			inComment = true
			continue
		}
		out = append(out, BodyLine{index + 1, raw})
	}
	return out
}

// ProseLine 은 [줄 번호, 원문 줄, 정리한 글, 제목 여부] 다. JSON 배열로 내보낸다.
type ProseLine struct {
	No      int
	Raw     string
	Clean   string
	Heading bool
}

func (p ProseLine) MarshalJSON() ([]byte, error) {
	return marshal([]any{p.No, p.Raw, p.Clean, p.Heading})
}

// proseLines 는 검사할 산문 줄만 돌려준다. 표·인용·빈 줄·writer:allow 줄은 뺀다.
func proseLines(text string) []ProseLine {
	var out []ProseLine
	for _, line := range bodyLines(text) {
		stripped := strings.TrimSpace(line.Raw)
		if stripped == "" || strings.HasPrefix(stripped, "|") || strings.HasPrefix(stripped, ">") ||
			strings.Contains(line.Raw, "writer:allow") {
			continue
		}
		clean := comments.ReplaceAllString(line.Raw, "")
		clean = inlineCode.ReplaceAllString(clean, "")
		clean = mdLink.ReplaceAllString(clean, "${1}")
		clean = bareURL.ReplaceAllString(clean, "")
		clean = emphasis.ReplaceAllString(clean, "")
		isHeading := heading.MatchString(clean)
		clean = heading.ReplaceAllString(clean, "")
		clean = listMark.ReplaceAllString(strings.TrimRightFunc(clean, unicode.IsSpace), "")
		if strings.TrimSpace(clean) != "" {
			out = append(out, ProseLine{line.No, line.Raw, strings.TrimSpace(clean), isHeading})
		}
	}
	return out
}

// sentences 는 . ? ! 뒤 공백에서 나눈다. 연속 공백은 한 경계로 본다.
func sentences(text string) []string {
	var result []string
	start := 0
	previousEnd := false
	splitting := false
	for index, ch := range text {
		if unicode.IsSpace(ch) && (previousEnd || splitting) {
			if !splitting {
				result = append(result, text[start:index])
			}
			start = index + utf8.RuneLen(ch)
			splitting = true
		} else {
			splitting = false
		}
		previousEnd = ch == '.' || ch == '?' || ch == '!'
	}
	return append(result, text[start:])
}

func firstRunes(text string, n int) string {
	runes := []rune(text)
	if len(runes) > n {
		runes = runes[:n]
	}
	return string(runes)
}
