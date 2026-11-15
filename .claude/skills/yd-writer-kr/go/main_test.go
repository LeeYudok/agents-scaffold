package main

import (
	"bytes"
	"encoding/json"
	"os"
	"reflect"
	"slices"
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
		if got := roundTrip(t, engine.check(c.Text, CheckMode{Chat: c.Chat, MaxLen: c.MaxLen})); !reflect.DeepEqual(got, c.Findings) {
			t.Errorf("findings text=%q chat=%v\n got  %v\n want %v", c.Text, c.Chat, got, c.Findings)
		}
		if got := roundTrip(t, nonNil(proseLines(c.Text))); !reflect.DeepEqual(got, c.Prose) {
			t.Errorf("prose text=%q\n got  %v\n want %v", c.Text, got, c.Prose)
		}
	}
}

var plain = CheckMode{MaxLen: 60}

func TestLookaroundRulesAndHangulLength(t *testing.T) {
	engine := testEngine(t)
	for _, text := range []string{"설정 파일도 포함.", "일단락됐다.", "협함."} {
		if got := engine.check(text, plain); len(got) != 0 {
			t.Errorf("%q 는 통과해야 한다: %v", text, got)
		}
	}
	if got := engine.check("일단 고친다.", plain); len(got) != 1 || got[0].Match != "일단" {
		t.Errorf("앞 경계가 없는 일단은 잡아야 한다: %v", got)
	}
	if got := engine.check("통일단계다.", plain); len(got) != 0 {
		t.Errorf("한글 뒤의 일단은 잡지 않는다: %v", got)
	}
	got := engine.check(strings.Repeat("가", 61), plain)
	if len(got) != 1 || got[0].Match != "61자" {
		t.Errorf("한글 길이는 글자 수로 센다: %v", got)
	}
}

// matches 는 kind 절 규칙이 잡은 문자열만 모은다.
func matches(findings []Finding, kind string) []string {
	var out []string
	for _, f := range findings {
		if f.Kind == kind {
			out = append(out, f.Match)
		}
	}
	return out
}

// 예문은 직접 쓴 문장이다. 출판물 원문은 저작권 때문에 넣지 않는다 (#126).
func expectRule(t *testing.T, kind, want string, flagged, passed []string) {
	t.Helper()
	engine := testEngine(t)
	for _, text := range flagged {
		if got := matches(engine.check(text, plain), kind); !reflect.DeepEqual(got, []string{want}) {
			t.Errorf("%q 는 [%s] %q 로 잡아야 한다: %v", text, kind, want, got)
		}
	}
	for _, text := range passed {
		if got := matches(engine.check(text, plain), kind); len(got) != 0 {
			t.Errorf("%q 는 [%s] 로 잡지 않는다: %v", text, kind, got)
		}
	}
}

func TestEitsseoSkipsExistentialReasonClause(t *testing.T) {
	expectRule(t, "일본어 투", "에 있어서",
		[]string{"공동생활에 있어서는 인내가 필요하다.", "교육에 있어서 중요한 것은 습관이다.",
			"신화에 있어서의 신은 다르다.", "적용 범위에 있어서 차이가 난다.", "현안에 있어서는 이견이 없다."},
		[]string{"깃대가 마당 한가운데에 있어서 어느 창에서도 보인다.", "설정이 서버에 있어서 권한이 필요하다.",
			"비밀번호가 코드에 있어서는 안 된다.", "전화기가 복도에 있어서, 모두 그곳을 쓴다.", "고양이가 방 안에 있어서 조용하다."})
}

func TestDoublePassiveWithEojida(t *testing.T) {
	engine := testEngine(t)
	for text, want := range map[string]string{"기억에서 잊혀진 이름이다.": "잊혀진", "편지가 서랍에 담겨진 채였다.": "담겨진", "문이 저절로 닫혀졌다.": "닫혀졌"} {
		if got := matches(engine.check(text, plain), "피동형"); !reflect.DeepEqual(got, []string{want}) {
			t.Errorf("%q 는 %q 로 잡아야 한다: %v", text, want, got)
		}
	}
	for _, text := range []string{"잊힌 이름이다.", "개선의 여지가 있다.", "편지가 서랍에 담긴 채였다."} {
		if got := matches(engine.check(text, plain), "피동형"); len(got) != 0 {
			t.Errorf("%q 는 통과해야 한다: %v", text, got)
		}
	}
}

func TestHaeBeoridaSkipsCompoundVerbsAndParticles(t *testing.T) {
	engine := testEngine(t)
	for text, want := range map[string]string{"배포를 실수로 해 버렸다.": "해 버렸", "그는 소파에서 잠들어 버렸다.": "어 버렸", "로그를 지워버렸다.": "워버렸"} {
		if got := matches(engine.check(text, plain), "일본어 투"); !reflect.DeepEqual(got, []string{want}) {
			t.Errorf("%q 는 %q 로 잡아야 한다: %v", text, want, got)
		}
	}
	for _, text := range []string{"열쇠를 잊어버렸다.", "지갑을 잃어버린 날이다.", "아버지가 왔다.", "쓰레기를 내다 버렸다.", "그가 버린 편지다."} {
		if got := matches(engine.check(text, plain), "일본어 투"); len(got) != 0 {
			t.Errorf("%q 는 통과해야 한다: %v", text, got)
		}
	}
}

func TestProseModeKeepsTranslationeseOnly(t *testing.T) {
	engine := testEngine(t)
	prose := CheckMode{Prose: true, MaxLen: 60}
	for _, text := range []string{"그 말에 그는 웃지 않을 수 없었다.", "보고서를 확인함.", "그녀는 완벽하게 준비를 마쳤다.", strings.Repeat("가", 120) + "."} {
		if got := engine.check(text, prose); len(got) != 0 {
			t.Errorf("산문 모드는 %q 를 통과시켜야 한다: %v", text, got)
		}
		if got := engine.check(text, plain); len(got) == 0 {
			t.Errorf("기본 모드는 %q 를 잡아야 한다", text)
		}
	}
	for text, kind := range map[string]string{"공동생활에 있어서는 인내가 필요했다.": "일본어 투", "그 일에 대해 생각했다.": "영어 번역투",
		"기억에서 잊혀진 이름이었다.": "피동형", "남은 여생을 보냈다.": "중복 수식"} {
		if got := matches(engine.check(text, prose), kind); len(got) != 1 {
			t.Errorf("산문 모드도 %q 의 [%s] 를 잡아야 한다: %v", text, kind, got)
		}
	}
}

// proseSections 는 금지 표현 표의 절 이름과 글자까지 같아야 한다. 절 이름을 바꾸면 이 테스트가 깨진다.
func TestProseSectionsExistInRules(t *testing.T) {
	specs, err := loadRules(rulesPath)
	if err != nil {
		t.Fatal(err)
	}
	for _, section := range proseSections {
		if !slices.ContainsFunc(specs, func(s RuleSpec) bool { return s.Section == section }) {
			t.Errorf("금지 표현 표에 %q 절이 없다", section)
		}
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
		{[]string{"--rules", rulesPath, "-"}, "그는 웃지 않을 수 없었다.", 1},
		{[]string{"--rules", rulesPath, "--prose", "-"}, "그는 웃지 않을 수 없었다.", 0},
		{[]string{"--rules", rulesPath, "--prose", "--strict", "-"}, strings.Repeat("가", 61), 0},
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
