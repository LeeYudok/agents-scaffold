"""check_handoff.py 가 SKILL.md 의 핸드오프 형식 단언을 판정하는지 본다 (stdlib only, 이슈 #201)."""

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_handoff", SKILL / "scripts" / "check_handoff.py")
m = importlib.util.module_from_spec(spec)
sys.modules["check_handoff"] = m
spec.loader.exec_module(m)

FAKE_PAT = "glpat-" + "ZZZZ1111aaaa2222bbbb"


def body(**over):
    f = {"이슈": "https://gitlab.example.com/a/b/-/issues/7", "작성": "2026-10-04 15:30:12.345",
         "작업 이슈/PR": "#7 (열림)", "브랜치": "`batch/claude-20261004`  ·  워크트리: 없음 — 새로 만들 것",
         "HEAD": "`abc1234` (push 됨)"}
    f.update(over)
    head = "\n".join(f"- {k}: {v}" for k, v in f.items())
    return f"""# HANDOFF — 테스트 요약

{head}

## 지금 어디까지

로그인 화면까지 끝냈다.

## 검증 결과 (원문)

```
Ran 3 tests ... OK
```

## 실행 중인 것

| 대상 | 주소 | 어떻게 띄웠나 |
| --- | --- | --- |
| dev 서버 | http://127.0.0.1:5173 | pnpm dev |

## 미결 판단

없음

## 다음에 칠 명령

```bash
cd /Users/me/repo
pnpm test
```

## 함정

포트가 점유돼 있으면 옮겨 간다.
"""


POINTER = """# HANDOFF (포인터)

세션 인계 본문은 GitLab 이슈에 있다. 이 파일은 그 위치만 가리킨다.

- 현재 핸드오프: https://gitlab.example.com/a/b/-/issues/9
- 작성: 2026-10-04 15:30:12.345
- 요약: 리뷰 답글 대기
- 전체 목록: https://gitlab.example.com/a/b/-/issues?label_name=handoff
"""


def run(argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main(argv)
    finally:
        sys.stdin = old
    return code, out.getvalue(), err.getvalue()


class CheckHandoff(unittest.TestCase):
    def test_filled_body_passes(self):
        code, out, _ = run(["-"], stdin=body())
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_iso_timestamp_rejected(self):
        for ts in ("2026-10-04T15:30:12+09:00", "2026-10-04 15:30:12"):
            code, out, _ = run(["-"], stdin=body(작성=ts))
            self.assertEqual(code, 1, ts)
            self.assertIn("작성 시각", out)

    def test_iso_in_prose_rejected_but_plain_date_ok(self):
        text = body().replace("로그인 화면까지", "2026-10-04T15:30:12.000+09:00 에 로그인 화면까지")
        self.assertIn("ISO 8601", run(["-"], stdin=text)[1])
        ok = body().replace("로그인 화면까지", "2026-10-04 에 로그인 화면까지")
        self.assertEqual(run(["-"], stdin=ok)[0], 0)

    def test_missing_section_and_field(self):
        text = body().replace("## 함정", "## 기타")
        text = text.replace("- HEAD: `abc1234` (push 됨)\n", "")
        code, out, _ = run(["-"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("섹션 `## 함정` 이 없다", out)
        self.assertIn("필드 `HEAD`", out)

    def test_unfilled_template_placeholders(self):
        code, out, _ = run(["-"], stdin=body(브랜치="`<branch>`").replace("pnpm test", "<command>"))
        self.assertEqual(code, 1)
        self.assertIn("자리표시자", out)

    def test_relative_command_dir_rejected(self):
        text = body().replace("cd /Users/me/repo", "cd repo")
        self.assertIn("절대경로 `cd`", run(["-"], stdin=text)[1])

    def test_empty_verification_block_rejected(self):
        text = body().replace("Ran 3 tests ... OK", "")
        self.assertIn("검증 결과", run(["-"], stdin=text)[1])
        # 안 돌렸다는 사실은 원문 자리에 적으면 통과한다.
        self.assertEqual(run(["-"], stdin=body().replace("Ran 3 tests ... OK", "안 돌림"))[0], 0)

    def test_secret_reported_by_position_never_value(self):
        text = body().replace("포트가 점유돼", f"토큰은 {FAKE_PAT} 이고 포트가 점유돼")
        code, out, err = run(["-"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("[glpat]", out)
        self.assertRegex(out, r"줄 \d+: 시크릿")
        self.assertNotIn(FAKE_PAT, out + err)
        self.assertNotIn("ZZZZ", out + err)

    def test_env_var_references_are_not_secrets(self):
        text = body().replace("pnpm test", 'export GITLAB_TOKEN=$(cat t)\ncurl -H "Authorization: token $FORGEJO_TOKEN" x')
        self.assertEqual(run(["-"], stdin=text)[0], 0)

    def test_pointer_form_passes(self):
        self.assertEqual(run(["-"], stdin=POINTER)[0], 0)

    def test_body_in_repo_handoff_md_rejected_when_tracker_exists(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t, "HANDOFF.md")
            p.write_text(body(), encoding="utf-8")
            code, out, _ = run([str(p), "--as-file"])
            self.assertEqual(code, 1)
            self.assertIn("포인터만", out)
            # 파일 모드(트래커 없음)는 본문이 원본이므로 통과한다.
            p.write_text(body(이슈="없음 — 이 파일이 원본"), encoding="utf-8")
            self.assertEqual(run([str(p), "--as-file"])[0], 0)

    def test_pointer_must_not_carry_body(self):
        text = POINTER + "\n## 다음에 칠 명령\n\n```bash\ncd /x\n```\n"
        code, out, _ = run(["-"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("포인터에 본문 섹션", out)

    def test_pointer_without_url_rejected(self):
        code, out, _ = run(["-"], stdin=POINTER.replace("https://gitlab.example.com/a/b/-/issues/9", "곧 만듦"))
        self.assertEqual(code, 1)
        self.assertIn("URL", out)

    def test_file_mode_requires_explicit_marker(self):
        code, out, _ = run(["-"], stdin=body(이슈="없음"))
        self.assertEqual(code, 1)
        self.assertIn("이 파일이 원본", out)

    def test_unreadable_input_is_tool_error(self):
        code, _, err = run(["/no/such/file.md"])
        self.assertEqual(code, 2)
        self.assertIn("읽지 못했다", err)


def git(d, *a):
    return subprocess.run(["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@e.com", *a],
                          check=True, capture_output=True, text=True).stdout.strip()


class VerifyGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.d = self.tmp.name
        git(self.d, "init", "-q", "-b", "main")
        git(self.d, "commit", "-q", "--allow-empty", "-m", "one")
        git(self.d, "checkout", "-q", "-b", "work")
        git(self.d, "commit", "-q", "--allow-empty", "-m", "two")
        self.head = git(self.d, "rev-parse", "HEAD")

    def verify(self, **over):
        over.setdefault("브랜치", "`work`")
        over.setdefault("HEAD", f"`{self.head[:10]}`")
        return run(["-", "--verify-git", self.d], stdin=body(**over))

    def test_matching_branch_and_head_pass(self):
        code, out, _ = self.verify()
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_branch_ahead_is_warning_only(self):
        git(self.d, "commit", "-q", "--allow-empty", "-m", "three")
        code, out, _ = self.verify()
        self.assertEqual(code, 0)
        self.assertIn("1커밋 앞서", out)

    def test_diverged_head_is_violation(self):
        git(self.d, "checkout", "-q", "main")
        git(self.d, "checkout", "-q", "-b", "other")
        git(self.d, "commit", "-q", "--allow-empty", "-m", "side")
        side = git(self.d, "rev-parse", "HEAD")
        code, out, _ = self.verify(HEAD=f"`{side[:10]}`")  # work 의 조상이 아니다
        self.assertEqual(code, 1)
        self.assertIn("조상이 아니다", out)

    def test_missing_branch_and_unknown_commit(self):
        code, out, _ = self.verify(브랜치="`gone`")
        self.assertEqual(code, 1)
        self.assertIn("어디에도 없다", out)
        code, out, _ = self.verify(HEAD="`deadbeef`")
        self.assertEqual(code, 1)
        self.assertIn("커밋이 이 레포에 없다", out)

    def test_verify_does_not_change_repo(self):
        before = git(self.d, "status", "--porcelain=v1", "-b") + git(self.d, "rev-parse", "HEAD")
        self.verify()
        after = git(self.d, "status", "--porcelain=v1", "-b") + git(self.d, "rev-parse", "HEAD")
        self.assertEqual(before, after)

    def test_not_a_git_repo_is_tool_error(self):
        with tempfile.TemporaryDirectory() as t:
            code, _, err = run(["-", "--verify-git", t], stdin=body())
        self.assertEqual(code, 2)
        self.assertIn("git 대조를 하지 못했다", err)


YAML_GOOD = """schema_version: "1"
meta:
  written_at: "2026-10-04 15:30:12.345"
  location: "/Users/me/repo"
  issue: "https://gitlab.example.com/a/b/-/issues/7"
  branch: "batch/claude-20261004"
  head: "abc1234"
  read_first: ["AGENTS.md"]
state:
  dev_server:
    port: 5173
    version: "1.10"
last_verification:
  - check: "단위 테스트"
    result: "Ran 3 tests ... OK"
    verified_after_fix: true
next_steps:
  - id: "1"
    do: "리뷰 답글 반영"
    check: "gh pr view 7"
    needs_user_confirmation: false
open_decisions: []
cautions:
  - "포트가 점유돼 있으면 옮겨 간다"
"""


def yaml_doc(**sub):
    text = YAML_GOOD
    for old, new in sub.items():
        old = old.replace("__", " ")
        assert old in text, old
        text = text.replace(old, new)
    return text


def with_yaml_section(yaml_text):
    return body() + "\n## 기계 판독용 상태\n\n```yaml\n" + yaml_text + "```\n"


class HandoffYaml(unittest.TestCase):
    def test_filled_yaml_passes(self):
        code, out, _ = run(["-", "--yaml"], stdin=YAML_GOOD)
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_unquoted_date_version_and_bool_rejected(self):
        for old, new, why in (('written_at: "2026-10-04 15:30:12.345"', "written_at: 2026-10-04 15:30:12.345", "날짜·시각"),
                              ('version: "1.10"', "version: 1.10", "소수"),
                              ('location: "/Users/me/repo"', "location: yes", "불리언")):
            code, out, _ = run(["-", "--yaml"], stdin=yaml_doc(**{old.replace(" ", "__"): new}))
            self.assertEqual(code, 1, old)
            self.assertIn(why, out)

    def test_quoted_values_and_plain_ints_pass(self):
        text = yaml_doc(**{'version: "1.10"': 'version: "2026-10-04"', "port: 5173": "port: 8080"})
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_real_float_in_state_passes(self):
        text = yaml_doc(**{"port: 5173": "port: 5173\n    progress: 0.5\n    load: 1.25"})
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))
        for key in ("version", "release_tag", "api_revision"):
            code, out, _ = run(["-", "--yaml"], stdin=yaml_doc(**{"port: 5173": f"port: 5173\n    {key}: 3.10"}))
            self.assertEqual(code, 1, key)
            self.assertIn("소수", out)

    def test_duplicate_keys_rejected(self):
        code, out, _ = run(["-", "--yaml"], stdin=YAML_GOOD + 'meta:\n  branch: "other"\n  head: "fff9999"\n')
        self.assertEqual(code, 1)
        self.assertIn("최상위 키 `meta`", out)
        dup = YAML_GOOD.replace('  branch: "batch/claude-20261004"\n', '  branch: "batch/claude-20261004"\n  branch: "other"\n')
        code, out, _ = run(["-", "--yaml"], stdin=dup)
        self.assertEqual(code, 1)
        self.assertIn("meta.branch 가 두 번", out)

    def test_schema_version_and_head_must_be_quoted(self):
        for old, new, key in (('schema_version: "1"', "schema_version: 1", "schema_version"),
                              ('head: "abc1234"', "head: 1234567", "meta.head")):
            code, out, _ = run(["-", "--yaml"], stdin=yaml_doc(**{old.replace(" ", "__"): new}))
            self.assertEqual(code, 1, old)
            self.assertIn(key, out)

    def test_missing_required_key_rejected(self):
        text = YAML_GOOD.replace("open_decisions: []\n", "").replace("next_steps:", "steps:")
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("최상위 키 `next_steps` 가 없다", out)

    def test_next_step_needs_check_command(self):
        text = yaml_doc(**{'    check: "gh pr view 7"\n': ""})
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("next_steps[0] 에 `check`", out)

    def test_next_step_check_is_counted_per_item_not_in_total(self):
        # do 2개·check 2개라 개수는 맞지만, 첫 항목엔 do 만, 둘째 항목엔 check 만 있다
        text = YAML_GOOD.split("next_steps:")[0] + (
            'next_steps:\n  - id: "1"\n    do: "첫 일"\n    note: "대조 명령 없음"\n'
            '  - id: "2"\n    check: "gh pr view 7"\n    do_not: "x"\n    do: "둘째 일"\n    check_again: "y"\n')
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("next_steps[0] 에 `check`", out)
        self.assertNotIn("next_steps[1]", out)
        text = text.replace('    do: "둘째 일"\n', "")
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertIn("next_steps[1] 에 `do`", out)

    def test_empty_next_steps_rejected(self):
        text = YAML_GOOD.split("next_steps:")[0] + "next_steps: []\nopen_decisions: []\n"
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("next_steps 에 항목이 없다", out)

    def test_secret_in_yaml_rejected_by_position_never_value(self):
        text = yaml_doc(**{'result: "Ran 3 tests ... OK"': f'result: "token ok {FAKE_PAT}"'})
        code, out, _ = run(["-", "--yaml"], stdin=text)
        self.assertEqual(code, 1)
        self.assertIn("시크릿 모양", out)
        self.assertNotIn(FAKE_PAT, out)

    def test_tab_indent_rejected(self):
        code, out, _ = run(["-", "--yaml"], stdin=YAML_GOOD.replace("  port: 5173", "\tport: 5173"))
        self.assertEqual(code, 1)
        self.assertIn("탭", out)

    def test_pair_matching_passes(self):
        with tempfile.TemporaryDirectory() as t:
            md = Path(t) / "HANDOFF.md"
            md.write_text(body(브랜치="`batch/claude-20261004`", HEAD="`abc1234def`"), encoding="utf-8")
            code, out, _ = run(["-", "--yaml", "--pair", str(md)], stdin=YAML_GOOD)
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_pair_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            md = Path(t) / "HANDOFF.md"
            md.write_text(body(작성="2026-10-05 09:00:00.000", 브랜치="`other`", HEAD="`fff9999`"), encoding="utf-8")
            code, out, _ = run(["-", "--yaml", "--pair", str(md)], stdin=YAML_GOOD)
        self.assertEqual(code, 1)
        for name in ("작성", "브랜치", "HEAD"):
            self.assertIn(f"HANDOFF.md 의 {name}", out)

    def test_yaml_block_in_issue_body_is_checked(self):
        code, out, _ = run(["-"], stdin=with_yaml_section(YAML_GOOD))
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))
        bad = with_yaml_section(yaml_doc(**{'version: "1.10"': "version: 1.10"}))
        code, out, _ = run(["-"], stdin=bad)
        self.assertEqual(code, 1)
        line = bad.splitlines().index("    version: 1.10") + 1
        self.assertIn(f"줄 {line}:", out)

    def test_section_without_closed_yaml_block_rejected(self):
        for tail in ("\n## 기계 판독용 상태\n\n(작성 예정)\n",
                     "\n## 기계 판독용 상태\n\n```json\n{}\n```\n",
                     "\n## 기계 판독용 상태\n\n```yaml\n" + YAML_GOOD):
            code, out, _ = run(["-"], stdin=body() + tail)
            self.assertEqual(code, 1, tail[:30])
            self.assertIn("닫힌 ```yaml 블록이 없다", out)

    def test_yaml_block_drift_from_body_rejected(self):
        text = with_yaml_section(yaml_doc(**{'branch: "batch/claude-20261004"': 'branch: "other"',
                                              'head: "abc1234"': 'head: "fff9999"',
                                              'written_at: "2026-10-04 15:30:12.345"': 'written_at: "2026-10-05 09:00:00.000"'}))
        code, out, _ = run(["-"], stdin=text)
        self.assertEqual(code, 1)
        for name in ("작성", "브랜치", "HEAD"):
            self.assertIn(f"HANDOFF.md 의 {name}", out)

    def test_body_without_yaml_still_passes(self):
        code, out, _ = run(["-"], stdin=body())
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_yaml_verify_git_reads_branch_and_head(self):
        with tempfile.TemporaryDirectory() as t:
            git(t, "init", "-q", "-b", "main")
            git(t, "commit", "-q", "--allow-empty", "-m", "one")
            head = git(t, "rev-parse", "HEAD")
            text = yaml_doc(**{'branch: "batch/claude-20261004"': 'branch: "main"', 'head: "abc1234"': f'head: "{head[:10]}"'})
            code, out, _ = run(["-", "--yaml", "--verify-git", t], stdin=text)
        self.assertEqual((code, out.strip()), (0, "위반 0건, 경고 0건"))

    def test_real_parse_flags_broken_yaml_when_pyyaml_present(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML 이 없다 — 어휘 검사만 돈다")
        code, out, _ = run(["-", "--yaml"], stdin=YAML_GOOD + "broken: [unclosed\n")
        self.assertEqual(code, 1)
        self.assertIn("파싱 실패", out)


if __name__ == "__main__":
    unittest.main()
