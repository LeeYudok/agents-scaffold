// check-writing 은 yd-writer-kr 의 한국어 글 검사기다 (#117). --source 는 요약을 원문과 대조한다 (#118).
//
// 표준 라이브러리만 쓴다. 외부 모듈이 없어 첫 빌드에 네트워크가 필요 없고 몇 초 안에 끝난다.
// Rust 판(#115)은 release 빌드가 CPU 를 오래 점유해 Go 로 옮겼다.
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strconv"
	"strings"
)

const version = "0.2.0"

const usage = `yd-writer-kr 글 검사기
Usage: check-writing [--chat] [--strict] [--max-len N] [--rules FILE] [--json]
                     [--source 원문] [--lines N] FILE...
  -             표준 입력
  --source F    요약을 원문 F 와 대조한다. 날짜·시각·이슈 번호·코드·URL 이 원문에 없으면 오류, 수치는 경고
  --lines N     요약 줄 수(제목·빈 줄 제외)가 N 을 넘으면 오류
종료 코드: 0 오류 없음, 1 글 검사 위반, 2 실행 불가`

type options struct {
	paths  []string
	rules  string
	chat   bool
	strict bool
	maxLen int
	json   bool
	bridge bool
	source string
	lines  int
}

type request struct {
	Action    string      `json:"action"`
	Text      string      `json:"text"`
	Chat      bool        `json:"chat"`
	MaxLen    *int        `json:"max_len"`
	Rules     *[]RuleSpec `json:"rules"`
	RulesPath *string     `json:"rules_path"`
	Source    *string     `json:"source"`
	Lines     int         `json:"lines"`
}

var errHelp = errors.New("help")

func marshal(value any) ([]byte, error) {
	var buf bytes.Buffer
	encoder := json.NewEncoder(&buf)
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(value); err != nil {
		return nil, err
	}
	return bytes.TrimRight(buf.Bytes(), "\n"), nil
}

func defaultRules() string {
	if executable, err := os.Executable(); err == nil {
		dir := filepath.Dir(executable)
		for range 2 {
			dir = filepath.Dir(dir)
			if path := filepath.Join(dir, "references", "banned-expressions.md"); fileExists(path) {
				return path
			}
		}
	}
	return filepath.Join("..", "references", "banned-expressions.md")
}

func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}

func positive(name, value string) (int, error) {
	n, err := strconv.Atoi(value)
	if err != nil || n <= 0 {
		return 0, fmt.Errorf("%s 은 양의 정수여야 한다", name)
	}
	return n, nil
}

func parseArgs(args []string, stdout io.Writer) (*options, error) {
	opts := &options{rules: defaultRules(), maxLen: 60}
	var expanded []string
	for _, arg := range args {
		if key, value, ok := strings.Cut(arg, "="); ok && (key == "--max-len" || key == "--rules" || key == "--source" || key == "--lines") {
			expanded = append(expanded, key, value)
		} else {
			expanded = append(expanded, arg)
		}
	}
	next := func(i *int, name string) (string, error) {
		if *i+1 >= len(expanded) {
			return "", fmt.Errorf("%s 값이 없다", name)
		}
		*i++
		return expanded[*i], nil
	}
	for i := 0; i < len(expanded); i++ {
		arg := expanded[i]
		switch {
		case arg == "--help" || arg == "-h":
			fmt.Fprintln(stdout, usage)
			return nil, errHelp
		case arg == "--version" || arg == "-V":
			fmt.Fprintln(stdout, "check-writing", version)
			return nil, errHelp
		case arg == "--chat":
			opts.chat = true
		case arg == "--strict":
			opts.strict = true
		case arg == "--json":
			opts.json = true
		case arg == "--bridge":
			opts.bridge = true
		case arg == "--rules":
			value, err := next(&i, "--rules")
			if err != nil {
				return nil, err
			}
			opts.rules = value
		case arg == "--max-len":
			value, err := next(&i, "--max-len")
			if err != nil {
				return nil, err
			}
			if opts.maxLen, err = positive("--max-len", value); err != nil {
				return nil, err
			}
		case arg == "--source":
			value, err := next(&i, "--source")
			if err != nil {
				return nil, err
			}
			opts.source = value
		case arg == "--lines":
			value, err := next(&i, "--lines")
			if err != nil {
				return nil, err
			}
			if opts.lines, err = positive("--lines", value); err != nil {
				return nil, err
			}
		case arg == "--":
			opts.paths = append(opts.paths, expanded[i+1:]...)
			i = len(expanded)
		case arg == "-":
			opts.paths = append(opts.paths, arg)
		case strings.HasPrefix(arg, "-"):
			return nil, fmt.Errorf("알 수 없는 옵션: %s", arg)
		default:
			opts.paths = append(opts.paths, arg)
		}
	}
	if len(opts.paths) == 0 && !opts.bridge {
		return nil, errors.New("검사할 파일을 지정한다. 표준 입력은 - 를 쓴다")
	}
	if opts.source == "-" && slices.Contains(opts.paths, "-") {
		return nil, errors.New("원문과 요약을 모두 표준 입력으로 받을 수 없다")
	}
	return opts, nil
}

func readInput(path string, stdin io.Reader) (string, error) {
	if path == "-" {
		data, err := io.ReadAll(stdin)
		if err != nil {
			return "", fmt.Errorf("표준 입력: %w", err)
		}
		return string(data), nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("%s: 파일을 읽을 수 없다: %w", path, err)
	}
	return string(data), nil
}

func bridge(opts *options, stdin io.Reader) (any, error) {
	data, err := io.ReadAll(stdin)
	if err != nil {
		return nil, fmt.Errorf("표준 입력: %w", err)
	}
	var req request
	if err := json.Unmarshal(data, &req); err != nil {
		return nil, fmt.Errorf("잘못된 JSON 요청: %w", err)
	}
	switch req.Action {
	case "prose":
		return nonNil(proseLines(req.Text)), nil
	case "sentences":
		return sentences(req.Text), nil
	case "split_row":
		return splitRow(req.Text), nil
	case "rules", "check":
		var specs []RuleSpec
		if req.Rules != nil {
			specs = *req.Rules
		} else {
			path := opts.rules
			if req.RulesPath != nil {
				path = *req.RulesPath
			}
			if specs, err = loadRules(path); err != nil {
				return nil, err
			}
		}
		engine, err := newEngine(specs)
		if err != nil {
			return nil, err
		}
		if req.Action == "rules" {
			return nonNil(specs), nil
		}
		maxLen := 60
		if req.MaxLen != nil {
			maxLen = *req.MaxLen
		}
		var source *sourceFacts
		if req.Source != nil {
			source = newSourceFacts(*req.Source)
		}
		return withSummaryChecks(engine.check(req.Text, req.Chat, maxLen), req.Text, source, req.Lines), nil
	}
	return nil, fmt.Errorf("알 수 없는 요청: %s", req.Action)
}

func nonNil[T any](items []T) []T {
	if items == nil {
		return []T{}
	}
	return items
}

func report(opts *options, stdin io.Reader, stdout io.Writer) (int, error) {
	if opts.bridge {
		result, err := bridge(opts, stdin)
		if err != nil {
			return 0, err
		}
		data, err := marshal(result)
		if err != nil {
			return 0, err
		}
		fmt.Fprintln(stdout, string(data))
		return 0, nil
	}
	specs, err := loadRules(opts.rules)
	if err != nil {
		return 0, err
	}
	engine, err := newEngine(specs)
	if err != nil {
		return 0, err
	}
	type fileReport struct {
		Path     string    `json:"path"`
		Findings []Finding `json:"findings"`
	}
	var source *sourceFacts
	if opts.source != "" {
		text, err := readInput(opts.source, stdin)
		if err != nil {
			return 0, err
		}
		source = newSourceFacts(text)
	}
	errorsCount, warnings := 0, 0
	var reports []fileReport
	for _, path := range opts.paths {
		name := path
		if path == "-" {
			name = "<stdin>"
		}
		text, err := readInput(path, stdin)
		if err != nil {
			return 0, err
		}
		findings := withSummaryChecks(engine.check(text, opts.chat, opts.maxLen), text, source, opts.lines)
		for _, f := range findings {
			if f.Level == levelError {
				errorsCount++
			} else {
				warnings++
			}
			if !opts.json {
				fmt.Fprintf(stdout, "%s:%d: %s [%s] '%s' — %s  | %s\n", name, f.Line, f.Level, f.Kind, f.Match, f.Hint, f.Context)
			}
		}
		reports = append(reports, fileReport{name, findings})
	}
	if opts.json {
		data, err := marshal(map[string]any{"files": reports, "errors": errorsCount, "warnings": warnings})
		if err != nil {
			return 0, err
		}
		fmt.Fprintln(stdout, string(data))
	} else {
		suffix := ""
		if opts.strict {
			suffix = " (--strict)"
		}
		fmt.Fprintf(stdout, "오류 %d건, 경고 %d건%s\n", errorsCount, warnings, suffix)
	}
	if errorsCount > 0 || (opts.strict && warnings > 0) {
		return 1, nil
	}
	return 0, nil
}

func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int {
	opts, err := parseArgs(args, stdout)
	if errors.Is(err, errHelp) {
		return 0
	}
	if err == nil {
		var code int
		if code, err = report(opts, stdin, stdout); err == nil {
			return code
		}
	}
	fmt.Fprintf(stderr, "check-writing: %v\n", err)
	return 2
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
