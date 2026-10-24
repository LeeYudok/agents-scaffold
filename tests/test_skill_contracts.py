"""스킬 계약 검사 (stdlib only) — doksam-skills 루트 테스트 이식 (agents-scaffold #78).

1. claims.json — 문서 단언(rule)이 SKILL.md·references/*.md 에 그대로 있고, 짝 테스트가 unittest 로 실제 실행되는가
   (doksam-skills scripts/score_skills.py 의 정적 검사).
2. 문서가 가리키는 스크립트·참조 경로가 실제로 있는가 — 경로가 틀리면 에이전트는 오류 없이 그 단계를 건너뛴다.
3. 이미 있는 스킬을 "(추가 예정)" 으로 적어 두지 않았는가.
4. 스킬 description(트리거)끼리 판별 어휘가 겹치지 않는가 — 겹치면 한 요청에 여러 스킬이 뜬다.

대상: .claude/skills/*(기본)·presets/skills/personal/.claude/skills/*(옵트인). 영어 오버레이는 대상이 아니다.
"""
import ast
import itertools
import json
import re
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOTS = (REPO / ".claude" / "skills", REPO / "presets" / "skills" / "personal" / ".claude" / "skills")
KINDS = ("정상", "실패", "경계", "도구오류", "오탐")
ID_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")


def skill_dirs():
    return sorted((d for root in SKILL_ROOTS if root.is_dir() for d in root.iterdir()
                   if (d / "SKILL.md").is_file()), key=lambda d: d.name)


def find_skill(name):
    for root in SKILL_ROOTS:
        if (root / name / "SKILL.md").is_file():
            return root / name
    return None


def collected_tests(path: Path) -> set[str]:
    """unittest 가 실제로 모으는 이름 — TestCase 하위 클래스 안의 test_ 메서드만.

    파일에 'def test_' 문자열이 있다는 것만으로는 부족하다. 모듈 수준 함수나 테스트
    파일이 아닌 곳의 함수는 실행되지 않는데 점수에 들어간다(PR #202 리뷰).
    클래스가 TestCase 를 상속하는지는 이름으로 판단한다 — 같은 파일 안의 다른 클래스를
    거쳐 상속하는 경우도 따라간다.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}

    def is_case(cls: ast.ClassDef, seen: frozenset = frozenset()) -> bool:
        for base in cls.bases:
            name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
            if name.endswith("TestCase"):
                return True
            if name in classes and name not in seen and is_case(classes[name], seen | {cls.name}):
                return True
        return False

    return {f.name for c in classes.values() if is_case(c)
            for f in c.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))
            and f.name.startswith("test")}



def claim_errors(skill):
    path = skill / "tests" / "claims.json"
    if not path.exists():
        return []
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["claims"]
    except (ValueError, KeyError, TypeError) as e:
        return [f"{path.relative_to(REPO)}: 읽을 수 없다 ({e})"]
    docs = "\n".join(p.read_text(encoding="utf-8")
                     for p in [skill / "SKILL.md", *sorted(skill.glob("references/*.md"))])
    errors, ids, tests = [], set(), set()
    for c in entries:
        where = f"{skill.name} {c.get('id', '?')}"
        rule, test = c.get("rule", ""), c.get("test", "")
        problems = []
        if not ID_RE.match(c.get("id", "")):
            problems.append("id 형식")
        if c.get("id") in ids:
            problems.append("id 중복")
        if c.get("kind") not in KINDS:
            problems.append(f"kind 는 {'/'.join(KINDS)} 중 하나")
        if len(rule) < 6 or "\n" in rule or rule != rule.strip() or rule not in docs:
            problems.append(f"rule 이 문서에 그대로 없다: {rule[:40]}")
        file, _, name = test.partition("::")
        tfile = skill / "tests" / file
        if not (re.fullmatch(r"test_\w+\.py", file) and name.startswith("test_") and tfile.is_file()
                and name in collected_tests(tfile)):
            problems.append(f"unittest 가 실행하는 test 메서드가 없다: {test}")
        if test in tests:
            problems.append("test 중복")
        ids.add(c.get("id"))
        tests.add(test)
        if problems:
            errors.append(f"{where}: {', '.join(problems)}")
    return errors


class TestClaims(unittest.TestCase):
    def test_every_claim_is_in_the_docs_and_has_a_running_test(self):
        errors = [e for d in skill_dirs() for e in claim_errors(d)]
        self.assertEqual(errors, [], "\n".join(errors))


REPO_ROOTED = re.compile(r"\bskills/([a-z0-9-]+)/([A-Za-z0-9_/.-]+\.(?:py|js|md|html))")
OWN_SKILL = re.compile(r"<스킬경로>/([A-Za-z0-9_/.-]+\.(?:py|js))")
NAMED_SKILL = re.compile(r"<(?:설치된-)?([a-z0-9-]+?)-스킬(?:경로)?>/([A-Za-z0-9_/.-]+\.(?:py|js))")
MD_LINK = re.compile(r"\]\((references/[A-Za-z0-9_.-]+\.md)\)")


def skill_docs():
    for skill in skill_dirs():
        for path in sorted(skill.rglob("*.md")):
            if "tests/fixtures" in path.as_posix():
                continue  # 픽스처는 산출물 예시라 문서가 아니다
            yield skill, path


class TestReferencedPaths(unittest.TestCase):
    def test_all_referenced_paths_exist(self):
        missing = []
        for skill, doc in skill_docs():
            text = doc.read_text(encoding="utf-8")
            pairs = REPO_ROOTED.findall(text) + NAMED_SKILL.findall(text)
            targets = [(find_skill(n) or Path("<없는 스킬:" + n + ">")) / rest for n, rest in pairs]
            targets += [skill / rest for rest in OWN_SKILL.findall(text)]
            targets += [doc.parent / rest for rest in MD_LINK.findall(text)]
            for target in targets:
                if not target.exists():
                    missing.append(f"{doc.relative_to(REPO)} → {target}")
        self.assertEqual(missing, [], "문서가 없는 경로를 가리킨다:\n" + "\n".join(missing))

    def test_pipeline_gates_are_not_left_as_todo(self):
        existing = {d.name for d in skill_dirs()}
        for _, doc in skill_docs():
            text = doc.read_text(encoding="utf-8")
            for name in existing:
                pattern = re.compile(rf"`{re.escape(name)}`[^\n]*\((?:추가 예정|미구현|TODO)\)")
                with self.subTest(doc=str(doc.relative_to(REPO)), skill=name):
                    self.assertIsNone(pattern.search(text), f"{doc.relative_to(REPO)} 가 이미 있는 스킬 {name} 를 미구현으로 적었다")


#: 겹침이 이 값을 넘고 서로를 명시하지도 않으면 경계가 흐린 것으로 본다.
#: 2026-08-17 기준 서로를 명시하지 않은 쌍의 최대치는 0.167 이고, 서로를
#: 명시한 두 쌍(yd-mobile-web-planner↔yd-nextjs-implementer, yd-db-expert↔yd-sqlite-expert)
#: 은 면제된다.
OVERLAP_THRESHOLD = 0.30

#: 한글 조사·어미. 긴 것부터 떼야 "으로" 가 "로" 에 먼저 잘리지 않는다.
JOSA = (
    "으로서", "으로", "로서", "에서", "에게", "이나", "하고", "까지", "부터",
    "이란", "라고", "이라", "와", "과", "을", "를", "이", "가", "은", "는",
    "의", "에", "로", "도", "만", "나", "며", "고",
)

#: 트리거를 가르지 못하는 기능어. 빈도 필터로도 걸러지지만, 스킬 수가
#: 적을 때는 빈도만으로 부족해 명시한다.
STOPWORDS = {
    "사용한다", "사용", "때", "것", "등", "및", "또는", "그리고", "쓴다", "한다",
    "하거나", "다룰", "요청", "요청할", "말할", "작업", "문제", "경우", "위한",
    "자체", "고유", "직접", "함께", "같은", "모든", "다음", "이것", "그것",
    "스킬", "사용자", "사용자가", "쓰지", "않는다", "대상", "대상이다",
}


def description(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"{skill} 에 description 이 없다")
    return match.group(1).strip()


def strip_josa(word: str) -> str:
    for josa in JOSA:
        if len(word) > len(josa) + 1 and word.endswith(josa):
            return word[: -len(josa)]
    return word


def keywords(text: str) -> set:
    """description 에서 판별 후보 낱말을 뽑는다."""
    found = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9.+#/_-]*", text):
        if len(token) > 1:
            found.add(token.lower())
    for token in re.findall(r"[가-힣]+", text):
        token = strip_josa(token)
        if len(token) >= 2 and token not in STOPWORDS:
            found.add(token)
    return found


def discriminative(keyword_sets: dict) -> dict:
    """스킬 1/3 이상에 나타나는 일반어를 걷어낸 키워드 집합."""
    frequency = Counter()
    for words in keyword_sets.values():
        frequency.update(words)
    limit = max(1, len(keyword_sets) // 3)
    generic = {word for word, count in frequency.items() if count > limit}
    return {name: words - generic for name, words in keyword_sets.items()}


def names_each_other(name_a: str, desc_a: str, name_b: str, desc_b: str) -> bool:
    """한쪽이 상대 스킬 이름을 불러 경계를 명시했는가."""
    def mentions(desc: str, name: str) -> bool:
        return name in desc or name.replace("-", " ") in desc
    return mentions(desc_a, name_b) or mentions(desc_b, name_a)


def overlaps(descriptions: dict):
    """(겹침, a, b, 공유 키워드) 목록. 서로를 명시한 쌍은 제외한다."""
    sets = discriminative({name: keywords(d) for name, d in descriptions.items()})
    result = []
    for a, b in itertools.combinations(sorted(sets), 2):
        if names_each_other(a, descriptions[a], b, descriptions[b]):
            continue
        shared = sets[a] & sets[b]
        if not shared or not sets[a] or not sets[b]:
            continue
        score = len(shared) / min(len(sets[a]), len(sets[b]))
        result.append((score, a, b, sorted(shared)))
    return sorted(result, reverse=True)



class TestTriggerBoundaries(unittest.TestCase):
    def setUp(self):
        self.descriptions = {d.name: description(d) for d in skill_dirs()}

    def test_no_two_skills_share_a_trigger(self):
        for score, a, b, shared in overlaps(self.descriptions):
            with self.subTest(pair=f"{a} x {b}"):
                self.assertLess(score, OVERLAP_THRESHOLD,
                                f"{a} 와 {b} 의 description 이 트리거를 공유한다 (겹침 {score:.2f}): {', '.join(shared)}. "
                                "작업 단위로 경계를 다시 긋거나, 한쪽 description 이 상대 스킬 이름을 불러 맡지 않는 것을 명시하라.")

    def test_detects_a_planted_collision(self):
        planted = dict(self.descriptions)
        planted["fake-a"] = "고래 상어 해파리 산호초 를 다룰 때 사용한다."
        planted["fake-b"] = "고래 상어 해파리 산호초 조사를 할 때 사용한다."
        scores = [s for s, a, b, _ in overlaps(planted) if {a, b} == {"fake-a", "fake-b"}]
        self.assertTrue(scores and scores[0] >= OVERLAP_THRESHOLD)

    def test_naming_the_other_skill_exempts_the_pair(self):
        planted = dict(self.descriptions)
        planted["fake-a"] = "고래 상어 해파리 산호초 를 다룰 때 사용한다. 심해는 fake-b 를 쓴다."
        planted["fake-b"] = "고래 상어 해파리 산호초 조사를 할 때 사용한다."
        self.assertFalse([(a, b) for _, a, b, _ in overlaps(planted) if {a, b} == {"fake-a", "fake-b"}])


if __name__ == "__main__":
    unittest.main()
