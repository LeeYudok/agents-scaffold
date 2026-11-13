package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"
	"unicode/utf8"
)

// RuleSpec 은 금지 표현 표의 한 행이다.
type RuleSpec struct {
	Section     string `json:"section"`
	Banned      string `json:"banned"`
	Replacement string `json:"replacement"`
	Pattern     string `json:"pattern"`
}

// Rule 은 컴파일한 규칙이다.
// Go regexp(RE2)는 전후방 탐색이 없다. 표가 쓰는 맨 앞 (?<!X)·(?<=X) 와 맨 뒤 (?!X)·(?=X) 만
// 떼어 내 일치 앞뒤 문자열에 따로 맞춰 본다.
type Rule struct {
	Spec   RuleSpec
	core   *regexp.Regexp
	before *guard
	after  *guard
}

type guard struct {
	re       *regexp.Regexp
	negative bool
}

func (g *guard) allows(text string) bool {
	return g == nil || g.re.MatchString(text) != g.negative
}

func splitRow(row string) []string {
	row = strings.TrimSpace(row)
	row = strings.TrimRight(strings.TrimLeft(row, "|"), "|")
	var cells []string
	var cell strings.Builder
	runes := []rune(row)
	for i := 0; i < len(runes); i++ {
		switch {
		case runes[i] == '\\' && i+1 < len(runes) && runes[i+1] == '|':
			cell.WriteRune('|')
			i++
		case runes[i] == '|':
			cells = append(cells, strings.TrimSpace(cell.String()))
			cell.Reset()
		default:
			cell.WriteRune(runes[i])
		}
	}
	return append(cells, strings.TrimSpace(cell.String()))
}

func loadRules(path string) ([]RuleSpec, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", path, err)
	}
	var specs []RuleSpec
	section := ""
	for index, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSuffix(line, "\r")
		if title, ok := strings.CutPrefix(line, "## "); ok {
			section = strings.TrimSpace(title)
		}
		if !strings.HasPrefix(line, "|") || strings.Trim(line, "|- \t") == "" {
			continue
		}
		cells := splitRow(line)
		if cells[0] == "금지" {
			continue
		}
		if len(cells) != 3 {
			return nil, fmt.Errorf("%s:%d: 금지 | 대체 | 검사 세 칸이어야 한다", path, index+1)
		}
		if cells[2] == "" || cells[2] == "-" {
			continue
		}
		specs = append(specs, RuleSpec{section, cells[0], cells[1], strings.Trim(cells[2], "`")})
	}
	if len(specs) == 0 {
		return nil, fmt.Errorf("%s: 검사 규칙이 없다", path)
	}
	return specs, nil
}

func compileRules(specs []RuleSpec) ([]Rule, error) {
	rules := make([]Rule, 0, len(specs))
	for _, spec := range specs {
		rule, err := compileRule(spec)
		if err != nil {
			return nil, fmt.Errorf("%s: 잘못된 정규식: %w", spec.Banned, err)
		}
		rules = append(rules, rule)
	}
	return rules, nil
}

func compileRule(spec RuleSpec) (Rule, error) {
	pattern := spec.Pattern
	rule := Rule{Spec: spec}
	for _, prefix := range []string{"(?<!", "(?<="} {
		if strings.HasPrefix(pattern, prefix) {
			end, err := groupEnd(pattern, len(prefix))
			if err != nil {
				return rule, err
			}
			re, err := regexp.Compile("(?:" + pattern[len(prefix):end] + ")$")
			if err != nil {
				return rule, err
			}
			rule.before = &guard{re, prefix == "(?<!"}
			pattern = pattern[end+1:]
			break
		}
	}
	for _, prefix := range []string{"(?!", "(?="} {
		start := lastGroupStart(pattern, prefix)
		if start < 0 {
			continue
		}
		re, err := regexp.Compile("^(?:" + pattern[start+len(prefix):len(pattern)-1] + ")")
		if err != nil {
			return rule, err
		}
		rule.after = &guard{re, prefix == "(?!"}
		pattern = pattern[:start]
		break
	}
	core, err := regexp.Compile(pattern)
	if err != nil {
		return rule, fmt.Errorf("%w (Go 정규식의 전후방 탐색은 맨 앞 (?<!…)·(?<=…), 맨 뒤 (?!…)·(?=…) 만 쓸 수 있다)", err)
	}
	rule.core = core
	return rule, nil
}

// groupEnd 는 from 위치에서 시작한 그룹 내용을 닫는 ) 의 위치를 찾는다. 이스케이프와 [...] 안은 건너뛴다.
func groupEnd(pattern string, from int) (int, error) {
	depth := 0
	inClass := false
	for i := from; i < len(pattern); i++ {
		switch c := pattern[i]; {
		case c == '\\':
			i++
		case inClass:
			if c == ']' {
				inClass = false
			}
		case c == '[':
			inClass = true
		case c == '(':
			depth++
		case c == ')':
			if depth == 0 {
				return i, nil
			}
			depth--
		}
	}
	return 0, fmt.Errorf("닫히지 않은 그룹: %s", pattern)
}

// lastGroupStart 는 패턴 끝을 닫는 그룹이 prefix 로 시작하면 그 시작 위치를 돌려준다.
func lastGroupStart(pattern, prefix string) int {
	for start := strings.LastIndex(pattern, prefix); start >= 0; start = strings.LastIndex(pattern[:start], prefix) {
		if end, err := groupEnd(pattern, start+len(prefix)); err == nil && end == len(pattern)-1 {
			return start
		}
	}
	return -1
}

// findAll 은 겹치지 않는 일치를 왼쪽부터 찾는다. 경계 조건이 맞지 않는 후보는 한 글자 뒤에서 다시 찾는다.
func (r *Rule) findAll(text string) []string {
	if r.before == nil && r.after == nil {
		return r.core.FindAllString(text, -1)
	}
	var out []string
	for pos := 0; pos <= len(text); {
		loc := r.core.FindStringIndex(text[pos:])
		if loc == nil {
			break
		}
		start, end := pos+loc[0], pos+loc[1]
		if r.before.allows(text[:start]) && r.after.allows(text[end:]) {
			out = append(out, text[start:end])
			if end > start {
				pos = end
				continue
			}
		}
		_, size := utf8.DecodeRuneInString(text[start:])
		pos = start + max(size, 1)
	}
	return out
}
