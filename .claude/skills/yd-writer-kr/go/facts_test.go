package main

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

const factSource = "## 배경\n\n" +
	"2026-11-13 16:00:05.120 에 `check-writing` 빌드가 1.9초 걸렸다. 사업자 610,110건 중 7/30 이 실패했다.\n" +
	"자세한 내용은 #117 과 https://github.com/LeeYudok/agents-scaffold/pull/119 를 본다. 버전은 1.22.0 이다.\n" +
	"다음 점검은 11월 20일이다.\n"

func factMatches(findings []Finding) map[string]string {
	out := map[string]string{}
	for _, f := range findings {
		out[f.Match] = f.Level
	}
	return out
}

func TestSummaryValuesCopiedFromSourcePass(t *testing.T) {
	summary := "- 2026-11-13 16:00 에 `check-writing` 빌드가 1.9초 걸렸다.\n" +
		"- 610110건 중 7/30 실패(#117, #119).\n" +
		"- 다음 점검은 2026년 11월 20일, 버전 1.22.0.\n" +
		"- 근거: https://github.com/LeeYudok/agents-scaffold/pull/119\n"
	if got := newSourceFacts(factSource).compare(summary); len(got) != 0 {
		t.Errorf("원문 값만 옮긴 요약은 통과해야 한다: %+v", got)
	}
}

func TestSummaryValuesMissingFromSourceAreReported(t *testing.T) {
	summary := "- 2026-11-14 17:00 에 `check_writing` 빌드가 2초 걸렸다.\n" +
		"1. 61만 건 중 #118 이 실패했다. https://example.com/x 참고. 11월 21일 재점검, 버전 1.23.0.\n"
	got := factMatches(newSourceFacts(factSource).compare(summary))
	want := map[string]string{
		"2026-11-14": levelError, "17:00": levelError, "check_writing": levelError,
		"#118": levelError, "https://example.com/x": levelError, "11월 21일": levelError,
		"2": levelWarning, "61": levelWarning, "1.23.0": levelWarning,
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("대조 결과\n got  %v\n want %v", got, want)
	}
}

// 원문 날짜·시각·이슈 번호·URL 안의 숫자는 수치로 세지 않는다. 지어낸 "10초"·"118건" 을 통과시키지 않기 위함이다.
func TestDigitsInsideSourceDatesAndRefsAreNotNumbers(t *testing.T) {
	facts := newSourceFacts("2026-11-10 16:30 에 시작했다(#118, https://x.test/pull/77).")
	got := factMatches(facts.compare("- 10초, 30건, 118건, 77건이 걸렸다.\n- 2026년 11월 10일 16:30 시작(#118, #77)."))
	want := map[string]string{"10": levelWarning, "30": levelWarning, "118": levelWarning, "77": levelWarning}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %v, want %v", got, want)
	}
}

func TestIdentifiersAndListMarkersAreNotNumbers(t *testing.T) {
	summary := "1. H100 과 solar-pro4, UTF-8, x86_64 를 쓴다.\n2) 끝.\n"
	if got := newSourceFacts("본문").compare(summary); len(got) != 0 {
		t.Errorf("식별자 안의 숫자와 목록 번호는 수치가 아니다: %+v", got)
	}
}

func TestHangulNeighborsDoNotBreakBoundaries(t *testing.T) {
	facts := newSourceFacts("2026-11-13에 #12를 고쳤다.")
	if got := facts.compare("2026-11-13에 #12를 고쳤다."); len(got) != 0 {
		t.Errorf("한글이 붙어도 날짜·이슈 번호를 찾아야 한다: %+v", got)
	}
	if got := factMatches(facts.compare("2026-11-12에 #13을 고쳤다.")); len(got) != 2 {
		t.Errorf("다른 값은 잡아야 한다: %v", got)
	}
}

func TestLineBudget(t *testing.T) {
	summary := "## 요약\n\n- 하나\n- 둘\n\n- 셋\n- 넷\n"
	if got := lineBudget(summary, 4); len(got) != 0 {
		t.Errorf("제목·빈 줄은 세지 않는다: %+v", got)
	}
	got := lineBudget(summary, 3)
	if len(got) != 1 || got[0].Match != "4줄" || got[0].Line != 7 {
		t.Errorf("넘친 첫 줄에 오류 한 건: %+v", got)
	}
}

func TestSourceOptionThroughCLIAndBridge(t *testing.T) {
	dir := t.TempDir()
	source := filepath.Join(dir, "원문.md")
	if err := os.WriteFile(source, []byte(factSource), 0o600); err != nil {
		t.Fatal(err)
	}
	var stdout, stderr bytes.Buffer
	code := run([]string{"--rules", rulesPath, "--source", source, "--lines", "1", "-"},
		strings.NewReader("빌드가 3초 걸렸다.\n#120 을 본다.\n"), &stdout, &stderr)
	if code != 1 || !strings.Contains(stdout.String(), "'#120'") || !strings.Contains(stdout.String(), "'2줄'") {
		t.Errorf("exit %d\n%s%s", code, stdout.String(), stderr.String())
	}
	if code := run([]string{"--source", "-", "-"}, strings.NewReader(""), &stdout, &stderr); code != 2 {
		t.Errorf("원문·요약 모두 표준 입력이면 exit 2, got %d", code)
	}
	request, _ := json.Marshal(map[string]any{"action": "check", "text": "#120 이다.", "source": "#117 이다.", "lines": 3})
	stdout.Reset()
	if code := run([]string{"--rules", rulesPath, "--bridge"}, bytes.NewReader(request), &stdout, &stderr); code != 0 {
		t.Fatalf("bridge exit %d: %s", code, stderr.String())
	}
	var findings []Finding
	if err := json.Unmarshal(stdout.Bytes(), &findings); err != nil || len(findings) != 1 || findings[0].Match != "#120" {
		t.Errorf("bridge 결과: %s (%v)", stdout.String(), err)
	}
}
