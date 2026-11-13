package main

import (
	"fmt"
	"regexp"
	"strings"
	"unicode/utf8"
)

const (
	levelError   = "오류"
	levelWarning = "경고"
	nounEnding   = "명사형 종결"
)

var (
	emoji   = regexp.MustCompile(`[\x{1F000}-\x{1FAFF}☀-➿\x{FE0F}]`)
	isoTime = regexp.MustCompile(digit + `{4}-` + digit + `{2}-` + digit + `{2}T` + digit + `{2}:` + digit + `{2}|` +
		digit + `{2}:` + digit + `{2}(?::` + digit + `{2})?(?:\.` + digit + `+)?[+-]` + digit + `{2}:` + digit + `{2}`)
)

// Finding 은 검사 결과 한 건이다. JSON 필드 이름은 Python 호환 계층과 맞춘다.
type Finding struct {
	Line    int    `json:"line"`
	Level   string `json:"level"`
	Kind    string `json:"kind"`
	Match   string `json:"match"`
	Hint    string `json:"hint"`
	Context string `json:"context"`
}

func newFinding(line int, level, kind, match, hint, context string) Finding {
	return Finding{line, level, kind, match, hint, firstRunes(context, 40)}
}

// Engine 은 컴파일한 금지 표현 규칙으로 글을 검사한다.
type Engine struct {
	rules []Rule
}

func newEngine(specs []RuleSpec) (*Engine, error) {
	rules, err := compileRules(specs)
	if err != nil {
		return nil, err
	}
	return &Engine{rules}, nil
}

func (e *Engine) check(text string, chat bool, maxLen int) []Finding {
	out := []Finding{}
	for _, line := range proseLines(text) {
		for _, found := range emoji.FindAllString(line.Raw, -1) {
			out = append(out, newFinding(line.No, levelError, "이모지", found, "Phosphor 아이콘이나 글로 바꾼다", line.Clean))
		}
		for _, found := range isoTime.FindAllString(line.Raw, -1) {
			out = append(out, newFinding(line.No, levelError, "시각 표기", found, "YYYY-MM-DD HH:MM:SS.mmm (KST)", line.Clean))
		}
		for _, sentence := range sentences(line.Clean) {
			sentence = strings.TrimSpace(sentence)
			if sentence == "" {
				continue
			}
			for i := range e.rules {
				rule := &e.rules[i]
				if (chat || line.Heading) && strings.HasPrefix(rule.Spec.Section, nounEnding) {
					continue
				}
				for _, found := range rule.findAll(sentence) {
					hint := rule.Spec.Banned + " → " + rule.Spec.Replacement
					out = append(out, newFinding(line.No, levelError, rule.Spec.Section, found, hint, sentence))
				}
			}
			if n := utf8.RuneCountInString(sentence); !line.Heading && n > maxLen {
				out = append(out, newFinding(line.No, levelWarning, "긴 문장", fmt.Sprintf("%d자", n),
					fmt.Sprintf("%d자 이하로 나눈다", maxLen), sentence))
			}
		}
	}
	return out
}
