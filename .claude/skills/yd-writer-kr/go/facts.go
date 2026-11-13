package main

import (
	"fmt"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// 요약 원문 대조 (#118). 요약에 나온 날짜·시각·이슈 번호·코드·URL·수치가 원문에 있는지 본다.
// 옮겨 적어야 하는 값(날짜·시각·이슈 번호·코드·URL)이 원문에 없으면 오류다.
// 수치는 요약하며 세거나 계산한 값일 수 있어 경고로 낸다. 확인은 사람·에이전트가 한다.

const factKind = "원문 대조"

var (
	factCode    = regexp.MustCompile("`([^`\\n]+)`")
	factURL     = regexp.MustCompile("https?://[^\\s<>()\\[\\]\"'`\\x{80}-\\x{10FFFF}]+")
	factDate    = regexp.MustCompile(`([0-9]{4})(?:[-/]|\. ?)([0-9]{1,2})(?:[-/]|\. ?)([0-9]{1,2})|([0-9]{4})년 ?([0-9]{1,2})월 ?([0-9]{1,2})일|([0-9]{1,2})월 ?([0-9]{1,2})일`)
	factTime    = regexp.MustCompile(`([0-9]{1,2}):([0-9]{2})(?::([0-9]{2})(?:\.([0-9]{1,6}))?)?`)
	factRef     = regexp.MustCompile(`([#!])([0-9]+)`)
	factRefURL  = regexp.MustCompile(`/(issues|pull|pulls|merge_requests)/([0-9]+)`)
	factVersion = regexp.MustCompile(`v?[0-9]+(?:\.[0-9]+){2,}`)
	factNumber  = regexp.MustCompile(`[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?`)
	anyNumber   = regexp.MustCompile(`[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?`)
	tableRule   = regexp.MustCompile(`^\|?[\s:|-]+\|?$`)
)

// sourceFacts 는 원문에서 뽑은 대조 기준이다.
type sourceFacts struct {
	text      string
	numbers   map[string]bool
	years     map[string]bool
	dates     map[string]bool
	monthDays map[string]bool
	times     []string
	refs      map[string]bool
}

func isDigit(b byte) bool  { return b >= '0' && b <= '9' }
func isLetter(b byte) bool { return b >= 'a' && b <= 'z' || b >= 'A' && b <= 'Z' || b == '_' }

func byteAt(s string, i int) byte {
	if i < 0 || i >= len(s) {
		return ' '
	}
	return s[i]
}

// digitBounded 는 일치 앞뒤가 숫자로 이어지지 않는지 본다. 한글 바이트는 숫자가 아니다.
func digitBounded(s string, start, end int) bool {
	return !isDigit(byteAt(s, start-1)) && !isDigit(byteAt(s, end))
}

func normalizeNumber(n string) string {
	n = strings.ReplaceAll(n, ",", "")
	whole, frac, hasFrac := strings.Cut(n, ".")
	whole = strings.TrimLeft(whole, "0")
	if whole == "" {
		whole = "0"
	}
	if frac = strings.TrimRight(frac, "0"); hasFrac && frac != "" {
		return whole + "." + frac
	}
	return whole
}

func group(s string, m []int, i int) string {
	if m[2*i] < 0 {
		return ""
	}
	return s[m[2*i]:m[2*i+1]]
}

func atoi(s string) int {
	n, _ := strconv.Atoi(s)
	return n
}

// dateKey 는 날짜 일치를 "y-m-d" 또는 연도 없는 "m-d" 로 바꾼다.
func dateKey(s string, m []int) (full, monthDay string) {
	switch {
	case m[2] >= 0:
		y, mo, d := atoi(group(s, m, 1)), atoi(group(s, m, 2)), atoi(group(s, m, 3))
		return fmt.Sprintf("%d-%d-%d", y, mo, d), fmt.Sprintf("%d-%d", mo, d)
	case m[8] >= 0:
		y, mo, d := atoi(group(s, m, 4)), atoi(group(s, m, 5)), atoi(group(s, m, 6))
		return fmt.Sprintf("%d-%d-%d", y, mo, d), fmt.Sprintf("%d-%d", mo, d)
	default:
		return "", fmt.Sprintf("%d-%d", atoi(group(s, m, 7)), atoi(group(s, m, 8)))
	}
}

func timeKey(s string, m []int) string {
	key := fmt.Sprintf("%02d:%s", atoi(group(s, m, 1)), group(s, m, 2))
	if sec := group(s, m, 3); sec != "" {
		key += ":" + sec
		if frac := group(s, m, 4); frac != "" {
			key += "." + frac
		}
	}
	return key
}

func timeBounded(s string, start, end int) bool {
	return digitBounded(s, start, end) && byteAt(s, start-1) != ':' && byteAt(s, end) != ':'
}

func refBounded(s string, start, end int) bool {
	prev := byteAt(s, start-1)
	return !isDigit(byteAt(s, end)) && !isDigit(prev) && !isLetter(prev) && prev != '&' && prev != '/'
}

func newSourceFacts(text string) *sourceFacts {
	f := &sourceFacts{text: text, numbers: map[string]bool{}, years: map[string]bool{}, dates: map[string]bool{},
		monthDays: map[string]bool{}, refs: map[string]bool{}}
	// URL·날짜·시각·이슈 번호 안의 숫자는 수치로 세지 않는다. 세면 "2026-11-10" 의 10 이
	// 요약이 지어낸 "10초" 를 통과시킨다(2026-11-13 시험에서 확인).
	rest := take(text, factURL, nil, func(m []int) {
		for _, ref := range factRefURL.FindAllStringSubmatch(text[m[0]:m[1]], -1) {
			if ref[1] == "merge_requests" {
				f.refs["!"+ref[2]] = true
			} else {
				f.refs["#"+ref[2]] = true
			}
		}
	})
	rest = take(rest, factDate, digitBounded, func(m []int) {
		full, monthDay := dateKey(rest, m)
		if full != "" {
			f.dates[full] = true
			f.years[strings.SplitN(full, "-", 2)[0]] = true
		}
		f.monthDays[monthDay] = true
	})
	rest = take(rest, factTime, timeBounded, func(m []int) {
		f.times = append(f.times, timeKey(rest, m))
	})
	rest = take(rest, factRef, refBounded, func(m []int) {
		f.refs[rest[m[0]:m[1]]] = true
	})
	for _, n := range anyNumber.FindAllString(rest, -1) {
		f.numbers[normalizeNumber(n)] = true
	}
	return f
}

// take 는 bounded 를 통과한 일치마다 visit 을 부르고, 그 자리를 공백으로 지운 줄을 돌려준다.
// 지운 자리는 다음 단계(수치)에서 다시 세지 않는다.
func take(line string, re *regexp.Regexp, bounded func(string, int, int) bool, visit func([]int)) string {
	var b strings.Builder
	last := 0
	for _, m := range re.FindAllStringSubmatchIndex(line, -1) {
		if bounded != nil && !bounded(line, m[0], m[1]) {
			continue
		}
		visit(m)
		b.WriteString(line[last:m[0]])
		b.WriteByte(' ')
		last = m[1]
	}
	b.WriteString(line[last:])
	return b.String()
}

func (f *sourceFacts) hasTime(key string) bool {
	for _, t := range f.times {
		if strings.HasPrefix(t, key) {
			return true
		}
	}
	return false
}

// compare 는 요약 글의 값을 원문과 대조한다. 코드 블록·front matter·writer:allow 줄은 보지 않는다.
func (f *sourceFacts) compare(summary string) []Finding {
	var out []Finding
	for _, body := range bodyLines(summary) {
		if strings.Contains(body.Raw, "writer:allow") || strings.TrimSpace(body.Raw) == "" {
			continue
		}
		line := comments.ReplaceAllString(body.Raw, "")
		context := strings.TrimSpace(line)
		missing := func(level, label, value string) {
			hint := fmt.Sprintf("원문에 없는 %s — 원문 값으로 고치거나 뺀다", label)
			if level == levelWarning {
				hint = fmt.Sprintf("원문에 없는 %s — 세거나 계산한 값이면 근거를 남기고, 아니면 원문 값으로 고친다", label)
			}
			out = append(out, newFinding(body.No, level, factKind, value, hint, context))
		}
		line = take(line, factCode, nil, func(m []int) {
			if code := strings.TrimSpace(group(line, m, 1)); code != "" && !strings.Contains(f.text, code) {
				missing(levelError, "코드·식별자", code)
			}
		})
		line = take(line, factURL, nil, func(m []int) {
			url := strings.TrimRight(line[m[0]:m[1]], ".,;:!?")
			if !strings.Contains(f.text, strings.TrimRight(url, "/")) {
				missing(levelError, "URL", url)
			}
		})
		line = take(line, factDate, digitBounded, func(m []int) {
			full, monthDay := dateKey(line, m)
			year := ""
			if full != "" {
				year = strings.SplitN(full, "-", 2)[0]
			}
			ok := f.monthDays[monthDay]
			if full != "" {
				ok = f.dates[full] || ok && (f.years[year] || f.numbers[year])
			}
			if !ok {
				missing(levelError, "날짜", line[m[0]:m[1]])
			}
		})
		line = take(line, factTime, timeBounded, func(m []int) {
			if !f.hasTime(timeKey(line, m)) {
				missing(levelError, "시각", line[m[0]:m[1]])
			}
		})
		line = take(line, factRef, refBounded, func(m []int) {
			if ref := line[m[0]:m[1]]; !f.refs[ref] {
				missing(levelError, "이슈·PR 번호", ref)
			}
		})
		line = listMark.ReplaceAllString(heading.ReplaceAllString(strings.TrimSpace(line), ""), "")
		line = take(line, factVersion, numberBounded, func(m []int) {
			if version := line[m[0]:m[1]]; !strings.Contains(f.text, version) {
				missing(levelWarning, "버전", version)
			}
		})
		take(line, factNumber, numberBounded, func(m []int) {
			if n := line[m[0]:m[1]]; !f.numbers[normalizeNumber(n)] {
				missing(levelWarning, "수치", n)
			}
		})
	}
	return out
}

// numberBounded 는 식별자 안의 숫자(H100, solar-pro4, UTF-8, x86_64)를 수치로 보지 않는다.
func numberBounded(s string, start, end int) bool {
	prev := byteAt(s, start-1)
	if isLetter(prev) || isDigit(prev) || isDigit(byteAt(s, end)) {
		return false
	}
	if prev == '-' && isLetter(byteAt(s, start-2)) {
		return false
	}
	return !(prev == '.' && isDigit(byteAt(s, start-2)))
}

// lineBudget 은 제목·표 구분선·빈 줄을 뺀 요약 줄 수가 limit 를 넘으면 오류 한 건을 낸다.
func lineBudget(summary string, limit int) []Finding {
	count := 0
	var first *BodyLine
	for _, body := range bodyLines(summary) {
		stripped := strings.TrimSpace(body.Raw)
		if stripped == "" || heading.MatchString(stripped) || tableRule.MatchString(stripped) {
			continue
		}
		count++
		if count == limit+1 {
			line := body
			first = &line
		}
	}
	if first == nil {
		return nil
	}
	return []Finding{newFinding(first.No, levelError, "요약 분량", fmt.Sprintf("%d줄", count),
		fmt.Sprintf("%d줄 이하로 줄인다", limit), strings.TrimSpace(first.Raw))}
}

// withSummaryChecks 는 글 검사 결과에 원문 대조·분량 결과를 더하고 줄 순서로 정렬한다.
func withSummaryChecks(findings []Finding, summary string, source *sourceFacts, lines int) []Finding {
	if source != nil {
		findings = append(findings, source.compare(summary)...)
	}
	if lines > 0 {
		findings = append(findings, lineBudget(summary, lines)...)
	}
	sort.SliceStable(findings, func(i, j int) bool { return findings[i].Line < findings[j].Line })
	return findings
}
