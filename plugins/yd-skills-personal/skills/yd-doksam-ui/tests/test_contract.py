"""doksam-ui 가 SSOT 로 인용하는 ui.doksam.com 엔드포인트 계약 검증 (stdlib only).

이 스킬은 사이트를 단일 진실원천으로 삼고 /llms.txt 를 live-fetch 하라고
지시한다. 그 엔드포인트가 죽거나 형식이 바뀌면 스킬이 조용히 낡으므로
실제 응답을 검증한다.

네트워크가 없거나 사이트가 일시 장애면 fail 이 아니라 skip 한다 — CI 머지
게이트가 외부 사이트 가용성에 볼모 잡히면 안 된다. 대신 문서 자체의 오프라인
계약(URL 표기 일관성)은 항상 검증한다.
"""
import json
import re
import unittest
import urllib.error
import urllib.request
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_MD = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
BASE = "https://ui.doksam.com"
TIMEOUT = 5


def fetch(path):
    """본문을 반환하고, 네트워크·사이트 문제면 None 을 반환한다."""
    try:
        req = urllib.request.Request(
            BASE + path, headers={"User-Agent": "doksam-skills-contract-test"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as res:
            if res.status != 200:
                return None
            return res.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError):
        return None


class TestOfflineContract(unittest.TestCase):
    """네트워크 없이도 항상 검증하는 문서 자체 계약."""

    def test_all_cited_urls_are_on_the_ssot_host(self):
        """SKILL.md 가 인용하는 절대 URL 은 전부 ui.doksam.com 이어야 한다."""
        urls = re.findall(r"https://[a-z0-9.\-]+", SKILL_MD)
        self.assertTrue(urls)
        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(url.startswith(BASE))

    def test_registry_install_command_form(self):
        """설치 명령 표기가 레지스트리 규약과 일치해야 한다."""
        self.assertIn("npx shadcn add https://ui.doksam.com/r/", SKILL_MD)
        self.assertIn('"@doksam-ui": "https://ui.doksam.com/r/{name}.json"',
                      SKILL_MD)


class TestMergedSkillContract(unittest.TestCase):
    """소비자·생산자 두 모드를 한 스킬이 커버하는 구조가 유지되는지."""

    def test_both_modes_are_documented(self):
        for marker in ("모드 A", "모드 B"):
            with self.subTest(marker=marker):
                self.assertIn(marker, SKILL_MD)

    def test_catalog_workflow_reference_exists_and_is_linked(self):
        reference = SKILL_ROOT / "references" / "catalog-workflow.md"
        self.assertTrue(reference.is_file(), f"{reference} 가 없다")
        self.assertIn("references/catalog-workflow.md", SKILL_MD)

    def test_rules_ssot_is_delegated_not_duplicated(self):
        """규칙 원문은 카탈로그 레포의 lib/rules-markdown.ts 에만 있다."""
        self.assertIn("lib/rules-markdown.ts", SKILL_MD)


class TestSelfValidationContract(unittest.TestCase):
    """자가 검증 절이 스스로를 반증하지 않는지."""

    EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⭐⭕️]")

    def test_skill_md_has_no_emoji(self):
        """이모지 0건을 보고하라는 문서가 이모지를 달고 있으면 안 된다."""
        hits = self.EMOJI.findall(SKILL_MD)
        self.assertEqual(hits, [], f"SKILL.md 에 이모지가 있다: {hits}")

    def test_scanner_script_exists_and_is_cited(self):
        script = SKILL_ROOT / "scripts" / "check_standards.py"
        self.assertTrue(script.is_file(), f"{script} 가 없다")
        self.assertIn("check_standards.py", SKILL_MD)

    def test_naive_greps_are_not_prescribed(self):
        """오탐 심한 맨손 grep 을 '검증 절차'로 지시하지 않는다.

        SKILL.md 는 이것들을 반례로만 인용한다 — 지시문이 아니라 금지 근거다.
        """
        naive = "grep -r ' any' src/"
        self.assertIn(naive, SKILL_MD, "반례 설명 자체가 사라졌다")
        head = SKILL_MD.split(naive)[0]
        self.assertIn("맨손 `grep` 으로 대체하지 않는다", head,
                      "맨손 grep 이 금지 근거가 아니라 절차로 읽힌다")

    def test_profile_names_are_not_hardcoded_as_a_list(self):
        """프로필 목록은 llms.txt 가 원천이다 — 문서에 목록을 박으면 낡는다."""
        # profile-css(= lib/profile-css.test.ts) 같은 코드 식별자는 프로필 이름이 아니다.
        names = [n for n in re.findall(r"\bprofile-[a-z0-9-]+", SKILL_MD)
                 if n not in {"profile-css"}]
        # 형식 예시 하나(profile-admin) 정도는 허용하되 목록 나열은 막는다.
        self.assertLessEqual(
            len(set(names)), 1,
            f"프로필 목록이 문서에 박혀 있다: {sorted(set(names))}")
        self.assertIn("llms.txt", SKILL_MD)


class TestLiveEndpoints(unittest.TestCase):
    """인용하는 엔드포인트가 실제로 살아 있고 기대 형식인지 (불가 시 skip)."""

    def test_llms_txt_is_a_machine_readable_catalog(self):
        body = fetch("/llms.txt")
        if body is None:
            self.skipTest("ui.doksam.com/llms.txt 접근 불가 — 네트워크/사이트")
        self.assertIn("npx shadcn add https://ui.doksam.com/r/", body)
        # SKILL.md 는 프로필 목록을 박아두지 않고 이 카탈로그에서 읽으라고
        # 지시한다. 그러므로 특정 프로필 이름이 아니라 "프로필 항목이 실제로
        # 존재하는가" 만 단언한다 — 프로필이 추가·제거돼도 이 테스트는 낡지 않는다.
        self.assertRegex(body, r"profile-[a-z0-9-]+",
                         "카탈로그에 profile-* 항목이 하나도 없다")

    def test_registry_index_is_valid_json(self):
        body = fetch("/r/registry.json")
        if body is None:
            self.skipTest("ui.doksam.com/r/registry.json 접근 불가")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self.fail("/r/registry.json 이 유효한 JSON 이 아니다")
        self.assertTrue(data, "레지스트리 인덱스가 비어 있다")

    def test_rules_md_is_raw_markdown(self):
        body = fetch("/rules.md")
        if body is None:
            self.skipTest("ui.doksam.com/rules.md 접근 불가")
        self.assertTrue(body.lstrip().startswith("#"),
                        "raw markdown 이 아니라 HTML 로 보인다")
        # 다이제스트가 요약해 온 핵심 규칙 표식이 원문에 남아 있어야 한다.
        for marker in ("하드코딩", "shadcn", "Phosphor"):
            with self.subTest(marker=marker):
                self.assertIn(marker, body)


if __name__ == "__main__":
    unittest.main()
