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

// #137 에서 더한 규칙이다. 규칙마다 잡아야 할 예문과 잡지 말아야 할 예문(오탐)을 fixture 에 둔다.
// 예문은 모두 직접 쓴 문장이다. 책의 문장은 넣지 않는다 (#126).
// expansionCase 는 tests/fixtures/expansion-cases.json 의 한 건이다. Go 테스트와 Python 테스트가 같은 예문을 쓴다.
type expansionCase struct {
	Banned  string   `json:"banned"` // 금지 칸. 같은 절의 다른 규칙과 구별한다
	Level   string   `json:"level"`
	Want    string   `json:"want"`
	Flagged []string `json:"flagged"`
	Passed  []string `json:"passed"`
}

func loadExpansionCases(t *testing.T) []expansionCase {
	t.Helper()
	data, err := os.ReadFile("../tests/fixtures/expansion-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []expansionCase
	if err := json.Unmarshal(data, &cases); err != nil {
		t.Fatal(err)
	}
	return cases
}

// byBanned 는 금지 칸이 banned 인 규칙이 낸 결과만 모은다.
func byBanned(findings []Finding, banned string) []Finding {
	var out []Finding
	for _, f := range findings {
		if strings.HasPrefix(f.Hint, banned+" → ") {
			out = append(out, f)
		}
	}
	return out
}

func TestExpansionRulesCatchAndSpare(t *testing.T) {
	engine := testEngine(t)
	for _, c := range loadExpansionCases(t) {
		for _, text := range c.Flagged {
			got := byBanned(engine.check(text, plain), c.Banned)
			if len(got) != 1 || got[0].Match != c.Want || got[0].Level != c.Level {
				t.Errorf("%q 는 [%s] %s %q 로 잡아야 한다: %v", text, c.Banned, c.Level, c.Want, got)
			}
		}
		for _, text := range c.Passed {
			if got := byBanned(engine.check(text, plain), c.Banned); len(got) != 0 {
				t.Errorf("%q 는 [%s] 로 잡지 않는다: %v", text, c.Banned, got)
			}
		}
	}
}

// #137 에서 더한 절의 모든 규칙에 예문이 있어야 한다. 표에 행을 더하고 예문을 빼먹으면 이 테스트가 깨진다.
func TestEveryExpansionRuleHasCases(t *testing.T) {
	specs, err := loadRules(rulesPath)
	if err != nil {
		t.Fatal(err)
	}
	sections := []string{"겹말", "조사 겹침·일본어 투 보강", "늘어지는 서술어", "군더더기 낱말", "남용 (한 문장 안의 횟수)"}
	covered := map[string]bool{}
	for _, c := range loadExpansionCases(t) {
		if len(c.Flagged) == 0 || len(c.Passed) == 0 {
			t.Errorf("%q 는 잡을 예문과 오탐 예문이 모두 있어야 한다", c.Banned)
		}
		covered[c.Banned] = true
	}
	seen := map[string]int{}
	for _, spec := range specs {
		for _, section := range sections {
			if spec.Section == section {
				seen[section]++
				if !covered[spec.Banned] {
					t.Errorf("[%s] %q 규칙에 예문이 없다", section, spec.Banned)
				}
			}
		}
	}
	for _, section := range sections {
		if seen[section] == 0 {
			t.Errorf("금지 표현 표에 %q 절이 없다", section)
		}
	}
}

// 새 절은 산문 모드에서 보지 않는다. 문학 산문 규칙은 #137 범위 밖이다.
func TestExpansionRulesAreSkippedInProseMode(t *testing.T) {
	engine := testEngine(t)
	prose := CheckMode{Prose: true, MaxLen: 60}
	for _, c := range loadExpansionCases(t) {
		for _, text := range c.Flagged {
			if got := byBanned(engine.check(text, prose), c.Banned); len(got) != 0 {
				t.Errorf("산문 모드는 %q 의 [%s] 를 보지 않는다: %v", text, c.Banned, got)
			}
		}
	}
}

func TestWarningRulesDoNotFailWithoutStrict(t *testing.T) {
	for args, code := range map[string]int{"": 0, "--strict": 1} {
		var stdout, stderr bytes.Buffer
		argv := append(strings.Fields("--rules "+rulesPath+" "+args), "-")
		if got := run(argv, strings.NewReader("여러 파일들을 지웠다."), &stdout, &stderr); got != code {
			t.Errorf("%q: exit %d, want %d (%s%s)", args, got, code, stdout.String(), stderr.String())
		}
		if !strings.Contains(stdout.String(), "오류 0건, 경고 1건") {
			t.Errorf("%q: 경고 1건이어야 한다: %s", args, stdout.String())
		}
	}
}

func TestCheckCellOptions(t *testing.T) {
	cases := []struct {
		cell, pattern, level string
		count                int
	}{
		{"`foo`", "foo", "", 0},
		{"`foo` 경고", "foo", levelWarning, 0},
		{"`foo` 3회", "foo", "", 3},
		{"`foo` 경고 3회", "foo", levelWarning, 3},
		{"`a` 오류", "a", "", 0},
	}
	for _, c := range cases {
		pattern, level, count, err := parseCheck(c.cell)
		if err != nil || pattern != c.pattern || level != c.level || count != c.count {
			t.Errorf("parseCheck(%q) = %q %q %d %v", c.cell, pattern, level, count, err)
		}
	}
	for _, cell := range []string{"`foo` 주의", "`foo` 1회", "`foo` 0회"} {
		if _, _, _, err := parseCheck(cell); err == nil {
			t.Errorf("parseCheck(%q) 는 오류여야 한다", cell)
		}
	}
}

func writeFile(t *testing.T, dir, name, text string) string {
	t.Helper()
	path := filepath.Join(dir, name)
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
	return path
}

// --profile 을 주지 않은 결과는 프로필을 나누기 전과 같아야 한다.
func TestDefaultProfileEqualsBuiltin(t *testing.T) {
	fromFile, err := loadProfile("", rulesPath)
	if err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(fromFile, builtinProfile()) {
		t.Errorf("references/profiles/doksam.md 가 내장 기본값과 다르다: %+v", fromFile)
	}
	// 규칙 파일만 따로 둔 곳에는 프로필 파일이 없다. 내장 기본값을 쓴다.
	lone := writeFile(t, t.TempDir(), "rules.md", "## 시험\n| foo | bar | `foo` |\n")
	if got, err := loadProfile("", lone); err != nil || !reflect.DeepEqual(got, builtinProfile()) {
		t.Errorf("프로필 파일이 없으면 내장 기본값이어야 한다: %+v %v", got, err)
	}
	if _, err := loadProfile("acme", lone); err == nil {
		t.Error("이름을 준 프로필이 없으면 오류여야 한다")
	}
}

func TestProfileSwitchesNotationChecksAndAddsRules(t *testing.T) {
	dir := t.TempDir()
	rules := writeFile(t, dir, "rules.md", "## 시험\n| foo | bar | `foo` |\n")
	writeFile(t, dir, "profiles/acme.md", "# acme\n\n## 표기 검사\n\n| 검사 | 수준 | 안내 |\n|---|---|---|\n"+
		"| 이모지 | 경고 | 글로 바꾼다 |\n| 시각 표기 | 끔 | - |\n\n## acme 표현\n\n| 금지 | 대체 | 검사 |\n|---|---|---|\n| 금일 | 오늘 | `금일` |\n")
	text := "금일 2026-11-17T09:00:00+09:00 에 foo 를 배포한다 \U0001F680"
	check := func(args ...string) (int, string) {
		var stdout, stderr bytes.Buffer
		code := run(append(args, "-"), strings.NewReader(text), &stdout, &stderr)
		return code, stdout.String() + stderr.String()
	}
	code, out := check("--rules", rules)
	if code != 1 || !strings.Contains(out, "[시각 표기]") || !strings.Contains(out, "오류 [이모지]") || strings.Contains(out, "금일 → 오늘") {
		t.Errorf("기본 프로필: exit %d\n%s", code, out)
	}
	code, out = check("--rules", rules, "--profile", "acme")
	if code != 1 || strings.Contains(out, "[시각 표기]") || !strings.Contains(out, "경고 [이모지]") || !strings.Contains(out, "금일 → 오늘") ||
		!strings.Contains(out, "오류 2건, 경고 1건") {
		t.Errorf("acme 프로필: exit %d\n%s", code, out)
	}
	if code, out = check("--rules", rules, "--profile="+filepath.Join(dir, "profiles", "acme.md")); code != 1 || !strings.Contains(out, "금일 → 오늘") {
		t.Errorf("프로필 경로: exit %d\n%s", code, out)
	}
	if code, out = check("--rules", rules, "--profile", "none"); code != 2 || !strings.Contains(out, "프로필 none") {
		t.Errorf("없는 프로필: exit %d\n%s", code, out)
	}
	for _, row := range []string{"| 맞춤법 | 오류 | - |", "| 이모지 | 주의 | - |", "| 이모지 | 오류 |"} {
		writeFile(t, dir, "profiles/bad.md", "## 표기 검사\n| 검사 | 수준 | 안내 |\n|---|---|---|\n"+row+"\n")
		if code, out = check("--rules", rules, "--profile", "bad"); code != 2 || !strings.Contains(out, "bad.md:4") {
			t.Errorf("%s: exit %d\n%s", row, code, out)
		}
	}
}

// 윈도우 편집기는 BOM 을 붙이거나 CP949 로 저장한다 (#137).
func TestInputEncoding(t *testing.T) {
	dir := t.TempDir()
	bom := writeFile(t, dir, "bom.md", "\uFEFF---\ntitle: 시험\n---\n배포를 완료함.\r\n")
	var stdout, stderr bytes.Buffer
	if code := run([]string{"--rules", rulesPath, bom}, strings.NewReader(""), &stdout, &stderr); code != 1 || !strings.Contains(stdout.String(), "bom.md:4:") {
		t.Errorf("BOM 을 떼고 front matter 를 건너뛰어야 한다: exit %d %s", code, stdout.String())
	}
	cp949 := writeFile(t, dir, "cp949.md", "\xb9\xe8\xc6\xf7")
	stdout.Reset()
	if code := run([]string{"--rules", rulesPath, cp949}, strings.NewReader(""), &stdout, &stderr); code != 2 || !strings.Contains(stderr.String(), "UTF-8") {
		t.Errorf("UTF-8 이 아니면 실행 불가여야 한다: exit %d %s", code, stderr.String())
	}
}

func TestRulesPathFromEnvironment(t *testing.T) {
	rules := writeFile(t, t.TempDir(), "rules.md", "## 시험\n| foo | bar | `foo` |\n")
	t.Setenv("CHECK_WRITING_RULES", rules)
	var stdout, stderr bytes.Buffer
	if code := run([]string{"-"}, strings.NewReader("foo"), &stdout, &stderr); code != 1 || !strings.Contains(stdout.String(), "foo → bar") {
		t.Errorf("CHECK_WRITING_RULES 를 읽어야 한다: exit %d %s%s", code, stdout.String(), stderr.String())
	}
}
