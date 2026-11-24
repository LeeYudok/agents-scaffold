package tests

import (
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

var (
	claimIDRE         = regexp.MustCompile(`^[A-Z0-9]+(?:-[A-Z0-9]+)*$`)
	skillPathRE       = regexp.MustCompile(`<스킬경로>/([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)`)
	markdownLinkRE    = regexp.MustCompile(`\]\((references/[A-Za-z0-9_.-]+\.md)\)`)
	frontmatterNameRE = regexp.MustCompile(`(?m)^name:\s*([a-z0-9-]+)\s*$`)
)

type claim struct {
	ID   string `json:"id"`
	Kind string `json:"kind"`
	Rule string `json:"rule"`
	Test string `json:"test"`
}

type claimFile struct {
	Claims []claim `json:"claims"`
}

func skillDir(t *testing.T) string {
	t.Helper()
	root, err := filepath.Abs(filepath.Join(".."))
	if err != nil {
		t.Fatalf("resolve skill root: %v", err)
	}
	return root
}

func documentText(t *testing.T, root string) string {
	t.Helper()
	var builder strings.Builder
	paths := []string{filepath.Join(root, "SKILL.md")}
	references, err := filepath.Glob(filepath.Join(root, "references", "*.md"))
	if err != nil {
		t.Fatalf("glob references: %v", err)
	}
	paths = append(paths, references...)
	for _, path := range paths {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatalf("read %s: %v", path, err)
		}
		builder.Write(data)
		builder.WriteByte('\n')
	}
	return builder.String()
}

func containsTestFunction(t *testing.T, path, name string) bool {
	t.Helper()
	parsed, err := parser.ParseFile(token.NewFileSet(), path, nil, 0)
	if err != nil {
		t.Fatalf("parse test file %s: %v", path, err)
	}
	found := false
	ast.Inspect(parsed, func(node ast.Node) bool {
		decl, ok := node.(*ast.FuncDecl)
		if ok && decl.Name.Name == name && strings.HasPrefix(name, "Test") {
			found = true
			return false
		}
		return true
	})
	return found
}

func TestClaimsAreDocumentedAndHaveRunningTests(t *testing.T) {
	root := skillDir(t)
	data, err := os.ReadFile(filepath.Join(root, "tests", "claims.json"))
	if err != nil {
		t.Fatalf("read claims.json: %v", err)
	}
	var claims claimFile
	if err := json.Unmarshal(data, &claims); err != nil {
		t.Fatalf("parse claims.json: %v", err)
	}

	docs := documentText(t, root)
	kinds := map[string]struct{}{"정상": {}, "실패": {}, "경계": {}, "도구오류": {}, "오탐": {}}
	seenIDs := make(map[string]struct{})
	seenTests := make(map[string]struct{})

	for _, item := range claims.Claims {
		t.Run(item.ID, func(t *testing.T) {
			if !claimIDRE.MatchString(item.ID) {
				t.Fatalf("invalid claim id: %q", item.ID)
			}
			if _, exists := seenIDs[item.ID]; exists {
				t.Fatalf("duplicate claim id: %s", item.ID)
			}
			if _, ok := kinds[item.Kind]; !ok {
				t.Fatalf("invalid claim kind: %s", item.Kind)
			}
			if !strings.Contains(docs, item.Rule) {
				t.Fatalf("claim rule is not documented: %s", item.Rule)
			}

			filename, testName, ok := strings.Cut(item.Test, "::")
			if !ok || filename == "" || testName == "" {
				t.Fatalf("test reference must use path::TestName form: %s", item.Test)
			}
			if _, exists := seenTests[item.Test]; exists {
				t.Fatalf("duplicate test reference: %s", item.Test)
			}
			testPath := filepath.Join(root, filepath.FromSlash(filename))
			if _, err := os.Stat(testPath); err != nil {
				t.Fatalf("referenced test file does not exist: %s", testPath)
			}
			if !containsTestFunction(t, testPath, testName) {
				t.Fatalf("referenced test function does not exist: %s", item.Test)
			}

			seenIDs[item.ID] = struct{}{}
			seenTests[item.Test] = struct{}{}
		})
	}
}

func TestReferencedSkillPathsExist(t *testing.T) {
	root := skillDir(t)
	docs := documentText(t, root)
	targets := make([]string, 0)
	for _, match := range skillPathRE.FindAllStringSubmatch(docs, -1) {
		targets = append(targets, filepath.Join(root, filepath.FromSlash(match[1])))
	}
	for _, match := range markdownLinkRE.FindAllStringSubmatch(docs, -1) {
		targets = append(targets, filepath.Join(root, filepath.FromSlash(match[1])))
	}

	for _, target := range targets {
		t.Run(target, func(t *testing.T) {
			if _, err := os.Stat(target); err != nil {
				t.Fatalf("referenced skill path does not exist: %s", target)
			}
		})
	}
}

func TestFrontmatterNameMatchesDirectory(t *testing.T) {
	root := skillDir(t)
	data, err := os.ReadFile(filepath.Join(root, "SKILL.md"))
	if err != nil {
		t.Fatalf("read SKILL.md: %v", err)
	}
	match := frontmatterNameRE.FindStringSubmatch(string(data))
	if match == nil {
		t.Fatal("SKILL.md frontmatter name was not found")
	}
	if match[1] != filepath.Base(root) {
		t.Fatalf("skill name mismatch: got %s want %s", match[1], filepath.Base(root))
	}
}
