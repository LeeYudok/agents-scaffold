package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: check_hugo_content <chapter.md|content-directory>...")
		os.Exit(2)
	}

	files := ChapterFiles(os.Args[1:])
	if len(files) == 0 {
		fmt.Fprintln(os.Stderr, "No chapter markdown files found.")
		os.Exit(2)
	}

	failed := false
	for _, file := range files {
		result := CheckFile(file)
		if len(result.Issues) == 0 {
			fmt.Printf("OK %s\n", file)
			continue
		}

		failed = true
		for _, issue := range result.Issues {
			fmt.Printf("%s:%d: %s\n", file, issue.Line, issue.Message)
		}
	}

	if failed {
		os.Exit(1)
	}
}
