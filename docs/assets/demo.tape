# agents-scaffold 30초 데모 (#98) — 레포 루트에서 `vhs docs/assets/demo.tape`
# 명령 한 번 → AGENTS.md + Claude Code·Codex·Antigravity 층 → 실제 git 훅이 시크릿 커밋을 막는다.
Output docs/assets/demo.gif

Set FontSize 15
Set Width 960
Set Height 620
Set Padding 16
Set TypingSpeed 30ms
Set Theme "Catppuccin Mocha"
Set Shell bash

Hide
Type `SCAFFOLD="$PWD/bin/agents-scaffold.sh"; agents-scaffold.sh(){ bash "$SCAFFOLD" "$@"; }; export GIT_AUTHOR_NAME=demo GIT_AUTHOR_EMAIL=demo@example.com GIT_COMMITTER_NAME=demo GIT_COMMITTER_EMAIL=demo@example.com; work="$(mktemp -d)"; cd "$work"; mkdir demo-app && git -C demo-app init -q; export PS1='$ '; clear`
Enter
Show

Type "# 1) One command: guardrails for Claude Code, Codex and Antigravity"
Enter
Sleep 600ms
Type "agents-scaffold.sh demo-app --harness all --stack nextjs --yes 2>&1 | tail -4"
Enter
Wait+Screen@30s /Done\. Fill in AGENTS\.md/
Sleep 3s

Hide
Type "clear"
Enter
Show
Type "# 2) One AGENTS.md, plus each harness's native layer, as plain files you own"
Enter
Sleep 600ms
Type "tree -a -L 2 --noreport -I '.git|.gitattributes' demo-app"
Enter
Sleep 4500ms

Hide
Type "clear"
Enter
Show
Type "# 3) A secret slips in. The real git hook blocks the commit, whoever commits"
Enter
Sleep 600ms
Type "cd demo-app && echo 'API_KEY=oops' > .env && git add -f .env"
Enter
Sleep 800ms
Type `git commit -m "feat: add config"`
Enter
Sleep 4s
