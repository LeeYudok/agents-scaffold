package main

import (
	"fmt"
	"regexp"
	"slices"
	"strings"
	"unicode"
)

// 문장 하나로는 보이지 않는 패턴을 본다 (#132). 문단은 줄 번호가 이어지는 산문 줄 묶음이다.
// 제목, 빈 줄, 표, 코드 블록, 목록과 본문의 경계에서 문단이 끊긴다.
const (
	levelNote      = "참고"
	endingRun      = 3 // 같은 말로 끝나는 문장이 이만큼 이어지면 경고
	conjunctionMax = 3 // 한 문단에서 접속사로 시작하는 문장이 이만큼이면 경고
	boundNounMax   = 3 // 한 문장에 의존명사 것·수·점이 이만큼이면 참고
	boldListRun    = 3 // 굵은 머리말로 시작하는 목록 항목이 이만큼 이어지면 참고
)

var (
	conjunction = regexp.MustCompile(`^(또한|그리고|하지만|그러나|따라서|그래서|그런데|게다가|아울러|더불어)(?:[,` + space + `]|$)`)
	boundNoun   = regexp.MustCompile(`^(것|수|점)(이|을|은|도|의|에|과|만|이다|이며|이고|입니다|이라|으로|에서|인데)?$`)
	colonLead   = regexp.MustCompile(`(다|요|죠)[:：]$`)
	boldLead    = regexp.MustCompile(`^[` + space + `]*(?:[-*+]|` + digit + `+[.)])[` + space + `]+(?:\*\*|__)[^*_]+(?:\*\*|__)`)
)

func isHangul(r rune) bool { return r >= '가' && r <= '힣' }

// endingKey 는 문장 마지막 어절의 끝 세 음절이다. 한글로 끝나지 않으면 빈 문자열이다.
func endingKey(sentence string) string {
	trimmed := strings.TrimRightFunc(sentence, func(r rune) bool { return !isHangul(r) && !unicode.IsLetter(r) && !unicode.IsDigit(r) })
	fields := strings.Fields(trimmed)
	if len(fields) == 0 {
		return ""
	}
	runes := []rune(fields[len(fields)-1])
	if len(runes) > 3 {
		runes = runes[len(runes)-3:]
	}
	if len(runes) < 2 || !slices.ContainsFunc(runes, isHangul) {
		return ""
	}
	for _, r := range runes {
		if !isHangul(r) {
			return ""
		}
	}
	return string(runes)
}

func boundNouns(sentence string) int {
	count := 0
	for _, field := range strings.Fields(sentence) {
		if boundNoun.MatchString(strings.TrimFunc(field, func(r rune) bool { return !isHangul(r) })) {
			count++
		}
	}
	return count
}

// paragraphs 는 산문 줄을 문단으로 묶는다. 제목은 문단에 넣지 않는다.
func paragraphs(lines []ProseLine) [][]ProseLine {
	var out [][]ProseLine
	var current []ProseLine
	flush := func() {
		if len(current) > 0 {
			out = append(out, current)
			current = nil
		}
	}
	for _, line := range lines {
		if line.Heading {
			flush()
			continue
		}
		if n := len(current); n > 0 && (line.No != current[n-1].No+1 || line.List != current[n-1].List) {
			flush()
		}
		current = append(current, line)
	}
	flush()
	return out
}

func paragraphFindings(lines []ProseLine, mode CheckMode) []Finding {
	var out []Finding
	for _, paragraph := range paragraphs(lines) {
		lastKey, run, starts := "", 0, 0
		for _, line := range paragraph {
			for _, sentence := range sentences(line.Clean) {
				sentence = strings.TrimSpace(sentence)
				if sentence == "" {
					continue
				}
				if found := conjunction.FindStringSubmatch(sentence); found != nil {
					if starts++; starts == conjunctionMax {
						out = append(out, newFinding(line.No, levelWarning, "문두 접속사", found[1],
							fmt.Sprintf("한 문단에 접속사로 시작하는 문장이 %d개다. 접속사를 빼고 문장 순서로 잇는다", starts), sentence))
					}
				}
				if mode.Chat || line.List {
					continue
				}
				key := endingKey(sentence)
				if key == "" || key != lastKey {
					lastKey, run = key, 1
					continue
				}
				if run++; run == endingRun {
					out = append(out, newFinding(line.No, levelWarning, "종결 반복", key,
						fmt.Sprintf("%d문장이 같은 말로 끝난다. 문장을 합치거나 서술어를 바꾼다", run), sentence))
				}
			}
		}
	}
	return out
}

// listFindings 는 정리 전 원문 줄에서 목록 모양을 본다. 굵은 글씨 표시와 목록 표시는 정리 단계에서 지워진다.
func listFindings(text string) []Finding {
	var out []Finding
	lines := bodyLines(text)
	bold := 0
	for i, line := range lines {
		stripped := strings.TrimSpace(line.Raw)
		if strings.Contains(line.Raw, "writer:allow") || strings.HasPrefix(stripped, "|") || strings.HasPrefix(stripped, ">") {
			continue
		}
		switch {
		case boldLead.MatchString(line.Raw):
			if bold++; bold == boldListRun {
				out = append(out, newFinding(line.No, levelNote, "굵은 머리말 목록", fmt.Sprintf("%d항목", bold),
					"항목마다 굵은 머리말을 붙였다. 표로 바꾸거나 머리말 없이 문장으로 쓴다", stripped))
			}
		case stripped == "" || (line.Raw != strings.TrimLeftFunc(line.Raw, unicode.IsSpace) && !listMark.MatchString(line.Raw)):
			// 빈 줄과 들여쓴 이어지는 줄은 목록을 끊지 않는다.
		default:
			bold = 0
		}
		if heading.MatchString(line.Raw) || listMark.MatchString(line.Raw) {
			continue
		}
		lead := strings.TrimSpace(emphasis.ReplaceAllString(inlineCode.ReplaceAllString(comments.ReplaceAllString(line.Raw, ""), ""), ""))
		if !colonLead.MatchString(lead) || strings.HasSuffix(strings.TrimRight(lead, ":："), "마다") { // "때마다:" 는 서술어가 아니다
			continue
		}
		for _, next := range lines[i+1:] {
			if strings.TrimSpace(next.Raw) == "" {
				continue
			}
			if next.No-line.No <= 2 && listMark.MatchString(next.Raw) {
				out = append(out, newFinding(line.No, levelWarning, "콜론 뒤 목록", lastRunes(lead, 4),
					"서술어 뒤 콜론으로 목록을 열지 않는다. 마침표로 문장을 끝낸다", lead))
			}
			break
		}
	}
	return out
}

func lastRunes(text string, n int) string {
	runes := []rune(text)
	if len(runes) > n {
		runes = runes[len(runes)-n:]
	}
	return string(runes)
}
