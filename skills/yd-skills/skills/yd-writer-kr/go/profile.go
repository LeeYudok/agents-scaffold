package main

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// 표기 프로필 (#137). 조직마다 다른 표기 규칙(시각 형식, 이모지)을 references/profiles/<이름>.md 로 뺐다.
// 프로필의 `## 표기 검사` 표가 내장 검사를 켜고 끄며, 그 밖의 `금지 | 대체 | 검사` 표는 금지 표현 뒤에 잇는다.
const (
	defaultProfileName = "doksam"
	notationSection    = "표기 검사"
	notationOff        = "끔"
	kindEmoji          = "이모지"
	kindISOTime        = "시각 표기"
)

// notationChecks 는 프로필이 켜고 끌 수 있는 내장 검사다. 순서가 결과 순서다.
var notationChecks = []struct {
	kind string
	re   *regexp.Regexp
}{{kindEmoji, emoji}, {kindISOTime, isoTime}}

// Notation 은 내장 표기 검사 하나의 수준과 안내다.
type Notation struct {
	Level string
	Hint  string
}

// Profile 은 조직별 표기 규칙이다. Checks 에 없는 내장 검사는 끈다.
type Profile struct {
	Checks map[string]Notation
	Rules  []RuleSpec
}

// builtinProfile 은 프로필 파일이 없을 때 쓰는 doksam 기본값이다. references/profiles/doksam.md 와 같아야 한다.
func builtinProfile() Profile {
	return Profile{Checks: map[string]Notation{
		kindEmoji:   {levelError, "Phosphor 아이콘이나 글로 바꾼다"},
		kindISOTime: {levelError, "YYYY-MM-DD HH:MM:SS.mmm (KST)"},
	}, Rules: []RuleSpec{
		{Section: "고유명사 표기", Banned: "앤스로픽", Replacement: "앤트로픽", Pattern: "앤스로픽"},
	}}
}

// profilePath 는 이름을 규칙 파일 옆 profiles/<이름>.md 로 푼다. 경로 구분자가 있거나 .md 로 끝나면 경로로 본다.
func profilePath(name, rulesPath string) string {
	if strings.ContainsAny(name, `/\`) || strings.HasSuffix(name, ".md") {
		return name
	}
	return filepath.Join(filepath.Dir(rulesPath), "profiles", name+".md")
}

// loadProfile 은 name 이 비면 doksam 프로필을 읽고, 그 파일이 없으면 내장 기본값을 쓴다.
// 규칙 파일만 따로 들고 다니는 기존 사용법의 결과를 바꾸지 않으려는 것이다.
func loadProfile(name, rulesPath string) (Profile, error) {
	explicit := name != ""
	if !explicit {
		name = defaultProfileName
	}
	path := profilePath(name, rulesPath)
	data, err := os.ReadFile(path)
	if err != nil {
		if !explicit && errors.Is(err, fs.ErrNotExist) {
			return builtinProfile(), nil
		}
		return Profile{}, fmt.Errorf("프로필 %s: %w", name, err)
	}
	return parseProfile(path, string(data))
}

func parseProfile(path, text string) (Profile, error) {
	profile := Profile{Checks: map[string]Notation{}}
	section := ""
	for index, line := range strings.Split(strings.TrimPrefix(text, "\uFEFF"), "\n") {
		line = strings.TrimSuffix(line, "\r")
		if title, ok := strings.CutPrefix(line, "## "); ok {
			section = strings.TrimSpace(title)
		}
		if section != notationSection || !strings.HasPrefix(line, "|") || strings.Trim(line, "|- \t") == "" {
			continue
		}
		cells := splitRow(line)
		if cells[0] == "검사" {
			continue
		}
		if len(cells) != 3 {
			return profile, fmt.Errorf("%s:%d: 검사 | 수준 | 안내 세 칸이어야 한다", path, index+1)
		}
		if cells[0] != kindEmoji && cells[0] != kindISOTime {
			return profile, fmt.Errorf("%s:%d: 알 수 없는 표기 검사: %s (%s, %s 만 쓴다)", path, index+1, cells[0], kindEmoji, kindISOTime)
		}
		switch cells[1] {
		case levelError, levelWarning:
			profile.Checks[cells[0]] = Notation{cells[1], cells[2]}
		case notationOff:
		default:
			return profile, fmt.Errorf("%s:%d: 수준은 %s·%s·%s 가운데 하나다: %s", path, index+1, levelError, levelWarning, notationOff, cells[1])
		}
	}
	rules, err := parseRules(path, text)
	profile.Rules = rules
	return profile, err
}
