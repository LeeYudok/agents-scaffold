package main

import (
	"fmt"
	"regexp"
	"slices"
	"strings"
	"unicode/utf8"
)

const (
	levelError   = "오류"
	levelWarning = "경고"
	nounEnding   = "명사형 종결"
)

// proseSections 는 --prose 가 검사하는 절이다. 문학 산문은 번역투·피동·중복 수식만 고칠 대상이고,
// 군더더기·doksam 표현·명사형 종결·긴 문장은 실용문 기준이라 건너뛴다 (#126).
// 허용 목록이라 금지 표현 표에 새 절이 생겨도 산문 모드에는 저절로 들어가지 않는다.
var proseSections = []string{"피동형", "중복 수식", "일본어 투", "영어 번역투"}

// CheckMode 는 글 종류별로 건너뛸 검사를 정한다. Chat 은 명사형 종결을, Prose 는 proseSections 밖의 절과 긴 문장을 건너뛴다.
type CheckMode struct {
	Chat   bool
	Prose  bool
	MaxLen int
}

func (m CheckMode) skips(section string, heading bool) bool {
	if m.Prose && !slices.Contains(proseSections, section) {
		return true
	}
	return (m.Chat || heading) && strings.HasPrefix(section, nounEnding)
}

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

func (e *Engine) check(text string, mode CheckMode) []Finding {
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
				if mode.skips(rule.Spec.Section, line.Heading) {
					continue
				}
				for _, found := range rule.findAll(sentence) {
					hint := rule.Spec.Banned + " → " + rule.Spec.Replacement
					out = append(out, newFinding(line.No, levelError, rule.Spec.Section, found, hint, sentence))
				}
			}
			if n := utf8.RuneCountInString(sentence); !line.Heading && !mode.Prose && n > mode.MaxLen {
				out = append(out, newFinding(line.No, levelWarning, "긴 문장", fmt.Sprintf("%d자", n),
					fmt.Sprintf("%d자 이하로 나눈다", mode.MaxLen), sentence))
			}
		}
	}
	return out
}
