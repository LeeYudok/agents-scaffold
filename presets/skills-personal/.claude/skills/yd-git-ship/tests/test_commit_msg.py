"""commit-msg.sh 가 SKILL.md 의 커밋 규칙을 지키는지 임시 저장소에서 확인한다."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "commit-msg.sh"
AI = ("claude-ai", "claude-ai@example.com")
HUMAN = ("dok123", "dok123@example.com")


def run_hook(message, author=AI, env_extra=None):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q", d], check=True)
        msg = Path(d, "MSG")
        msg.write_text(message, encoding="utf-8")
        env = {**os.environ, "GIT_AUTHOR_NAME": author[0], "GIT_AUTHOR_EMAIL": author[1],
               "GIT_COMMITTER_NAME": author[0], "GIT_COMMITTER_EMAIL": author[1]}
        env.pop("YD_TRIVIAL", None)
        env.update(env_extra or {})
        return subprocess.run(["sh", str(SCRIPT), str(msg)], cwd=d, env=env,
                              capture_output=True, text=True)


class CommitMsgTest(unittest.TestCase):
    def test_accepts_tagged_subject_with_issue(self):
        r = run_hook("[Claude Opus 5.5] docs: 문서 보강 (#11)\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_accepts_scope_and_body(self):
        r = run_hook("[GPT-6 Sol] fix(api): 오류 수정 (#3)\n\n본문\n", author=("codex-ai", "codex-ai@example.com"))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_rejects_missing_model_tag(self):
        r = run_hook("docs: 모델 태그 없음 (#11)\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("model tag", r.stderr)

    def test_rejects_unknown_type(self):
        r = run_hook("[Claude Opus 5.5] wip: 타입 아님 (#11)\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("type must be one of", r.stderr)

    def test_rejects_missing_issue_number(self):
        r = run_hook("[Claude Opus 5.5] docs: 이슈 번호 없음\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("(#N)", r.stderr)

    def test_trivial_env_allows_missing_issue(self):
        r = run_hook("[Claude Opus 5.5] docs: 오타 수정\n", env_extra={"YD_TRIVIAL": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_trivial_env_does_not_waive_model_tag(self):
        r = run_hook("docs: 태그 없음\n", env_extra={"YD_TRIVIAL": "1"})
        self.assertEqual(r.returncode, 1)

    def test_rejects_co_authored_by_claude(self):
        r = run_hook("[Claude Opus 5.5] docs: 문서 (#1)\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("co-author", r.stderr)

    def test_rejects_generated_with_claude_code_line(self):
        r = run_hook("[Claude Opus 5.5] docs: 문서 (#1)\n\nGenerated with [Claude Code](https://claude.com/claude-code)\n")
        self.assertEqual(r.returncode, 1)

    def test_co_author_rejected_even_for_human_author(self):
        r = run_hook("docs: 사람 커밋\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n", author=HUMAN)
        self.assertEqual(r.returncode, 1)

    def test_rejects_tag_with_human_author(self):
        r = run_hook("[Claude Opus 5.5] docs: 계정 설정 누락 (#1)\n", author=HUMAN)
        self.assertEqual(r.returncode, 1)
        self.assertIn("model tag present", r.stderr)

    def test_human_commit_without_tag_is_not_checked(self):
        r = run_hook("그냥 사람이 쓴 커밋\n", author=HUMAN)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_merge_subject_is_exempt(self):
        r = run_hook("Merge remote-tracking branch 'origin/main' into batch/claude-20261004\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_comment_lines_are_ignored_when_finding_subject(self):
        r = run_hook("# 주석\n[Claude Opus 5.5] chore: 주석 뒤 제목 (#2)\n")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_co_author_text_inside_comment_is_ignored(self):
        r = run_hook("[Claude Opus 5.5] docs: 문서 (#1)\n# Co-Authored-By: Claude\n")
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
