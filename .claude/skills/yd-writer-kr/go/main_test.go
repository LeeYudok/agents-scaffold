package main

import (
	"bytes"
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"
)

const rulesPath = "../references/banned-expressions.md"

func testEngine(t *testing.T) *Engine {
	t.Helper()
	specs, err := loadRules(rulesPath)
	if err != nil {
		t.Fatal(err)
	}
	engine, err := newEngine(specs)
	if err != nil {
		t.Fatal(err)
	}
	return engine
}

// roundTrip 은 값을 JSON 으로 바꿨다가 다시 읽는다. 기존 결과 JSON 과 같은 모양으로 비교하려는 것이다.
func roundTrip(t *testing.T, value any) any {
	t.Helper()
	data, err := marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	var out any
	if err := json.Unmarshal(data, &out); err != nil {
		t.Fatal(err)
	}
	return out
}

// 기존 Python 검사기가 낸 결과(#115 에서 저장한 64개 사례)와 같아야 한다.
func TestPythonBaselineFindingsAndProseMatch(t *testing.T) {
	data, err := os.ReadFile("../tests/fixtures/python-baseline.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Text     string `json:"text"`
		Chat     bool   `json:"chat"`
		MaxLen   int    `json:"max_len"`
		Findings any    `json:"findings"`
		Prose    any    `json:"prose"`
	}
	if err := json.Unmarshal(data, &cases); err != nil {
		t.Fatal(err)
	}
	if len(cases) < 60 {
		t.Fatalf("기존 사례가 %d개뿐이다", len(cases))
	}
	engine := testEngine(t)
	for _, c := range cases {
		if got := roundTrip(t, engine.check(c.Text, c.Chat, c.MaxLen)); !reflect.DeepEqual(got, c.Findings) {
			t.Errorf("findings text=%q chat=%v\n got  %v\n want %v", c.Text, c.Chat, got, c.Findings)
		}
		if got := roundTrip(t, nonNil(proseLines(c.Text))); !reflect.DeepEqual(got, c.Prose) {
			t.Errorf("prose text=%q\n got  %v\n want %v", c.Text, got, c.Prose)
		}
	}
}

func TestLookaroundRulesAndHangulLength(t *testing.T) {
	engine := testEngine(t)
	for _, text := range []string{"설정 파일도 포함.", "일단락됐다.", "협함."} {
		if got := engine.check(text, false, 60); len(got) != 0 {
			t.Errorf("%q 는 통과해야 한다: %v", text, got)
		}
	}
	if got := engine.check("일단 고친다.", false, 60); len(got) != 1 || got[0].Match != "일단" {
		t.Errorf("앞 경계가 없는 일단은 잡아야 한다: %v", got)
	}
	if got := engine.check("통일단계다.", false, 60); len(got) != 0 {
		t.Errorf("한글 뒤의 일단은 잡지 않는다: %v", got)
	}
	got := engine.check(strings.Repeat("가", 61), false, 60)
	if len(got) != 1 || got[0].Match != "61자" {
		t.Errorf("한글 길이는 글자 수로 센다: %v", got)
	}
}

func TestGuardsAreSplitFromCorePattern(t *testing.T) {
	rule, err := compileRule(RuleSpec{Pattern: `(?<![가-힣(])a(b|c)(?![)d])`})
	if err != nil {
		t.Fatal(err)
	}
	if rule.core.String() != "a(b|c)" || rule.before == nil || rule.after == nil {
		t.Fatalf("경계 분리 실패: core=%s", rule.core)
	}
	if got := rule.findAll("가ab ab (ac acd ab"); !reflect.DeepEqual(got, []string{"ab", "ab"}) {
		t.Errorf("findAll = %v", got)
	}
	positive, err := compileRule(RuleSpec{Pattern: `(?<=x)y`})
	if err != nil {
		t.Fatal(err)
	}
	if got := positive.findAll("ay xy"); !reflect.DeepEqual(got, []string{"y"}) {
		t.Errorf("긍정 앞 경계 = %v", got)
	}
	if _, err := compileRule(RuleSpec{Pattern: `a(?!b)c`}); err == nil || !strings.Contains(err.Error(), "맨 앞") {
		t.Errorf("중간의 전후방 탐색은 안내와 함께 오류여야 한다: %v", err)
	}
}

func TestBadPatternsAndRowsAreErrors(t *testing.T) {
	specs, err := loadRules(rulesPath)
	if err != nil {
		t.Fatal(err)
	}
	specs[0].Pattern = "(?"
	if _, err := newEngine(specs); err == nil {
		t.Error("잘못된 정규식은 오류여야 한다")
	}
	if got := splitRow(`| a | b | ` + "`x\\|y`" + ` |`); !reflect.DeepEqual(got, []string{"a", "b", "`x|y`"}) {
		t.Errorf("splitRow = %v", got)
	}
}

func TestInvalidArgumentsAreErrors(t *testing.T) {
	for _, args := range [][]string{{}, {"--unknown"}, {"--rules"}, {"--max-len", "-1", "-"}, {"--max-len", "0", "-"}} {
		if _, err := parseArgs(args, &bytes.Buffer{}); err == nil {
			t.Errorf("%v 는 오류여야 한다", args)
		}
	}
}

func TestSentenceBoundariesMatchPythonWhitespaceSplit(t *testing.T) {
	got := sentences("첫 문장.  다음!\t셋째?\n")
	if want := []string{"첫 문장.", "다음!", "셋째?", ""}; !reflect.DeepEqual(got, want) {
		t.Errorf("sentences = %q", got)
	}
}

func TestRunExitCodes(t *testing.T) {
	cases := []struct {
		args  []string
		input string
		code  int
	}{
		{[]string{"--rules", rulesPath, "-"}, "본문이다.", 0},
		{[]string{"--rules", rulesPath, "-"}, "배포를 완료함.", 1},
		{[]string{"--rules", rulesPath, "--chat", "-"}, "배포를 완료함.", 0},
		{[]string{"--rules", rulesPath, "--strict", "-"}, strings.Repeat("가", 61), 1},
		{[]string{"--rules", "missing.md", "-"}, "본문이다.", 2},
		{[]string{"--version"}, "", 0},
	}
	for _, c := range cases {
		var stdout, stderr bytes.Buffer
		if code := run(c.args, strings.NewReader(c.input), &stdout, &stderr); code != c.code {
			t.Errorf("%v: exit %d, want %d (stderr %s)", c.args, code, c.code, stderr.String())
		}
	}
}
