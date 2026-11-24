"""스킬 계약 검사 (stdlib only) — doksam-skills 루트 테스트 이식 (agents-scaffold #78).

1. claims.json — 문서 단언(rule)이 SKILL.md·references/*.md 에 그대로 있고, 짝 테스트가 unittest 로 실제 실행되는가
   (doksam-skills scripts/score_skills.py 의 정적 검사).
2. 문서가 가리키는 스크립트·참조 경로가 실제로 있는가 — 경로가 틀리면 에이전트는 오류 없이 그 단계를 건너뛴다.
3. 이미 있는 스킬을 "(추가 예정)" 으로 적어 두지 않았는가.
4. 스킬 description(트리거)끼리 판별 어휘가 겹치지 않는가 — 겹치면 한 요청에 여러 스킬이 뜬다.
5. agentskills 규격 한도 — name·description 길이, SKILL.md 500줄 미만, references 한 단계(#130).

대상: .claude/skills/*(기본)·presets/skills/personal/.claude/skills/*(옵트인). 영어 오버레이는 5번(규격 한도)만 대상이다.
"""
import ast
import itertools
import json
import re
import unittest
from collections import Counter
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
SKILL_ROOTS = (
    REPO / "skills" / "core",
    REPO / "skills" / "yd-skills" / "skills",
    REPO / "skills" / "yd-skills-personal" / "skills",
)
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


def collected_go_tests(path: Path) -> set[str]:
    """`go test` 가 실행하는 이름 — 패키지 안의 TestXxx 함수."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(re.findall(r"(?m)^func\s+(Test[A-Za-z0-9_]*)\s*\(", text))


def claim_test_path(skill: Path, file: str) -> Optional[Path]:
    """claims.json 의 테스트 경로를 푼다.

    Python 계약 테스트는 기존처럼 tests/test_*.py 로 두고, Go 스킬은 스킬 루트
    기준 경로(scripts/.../checker_test.go)를 쓸 수 있게 한다.
    """
    if re.fullmatch(r"test_\w+\.py", file):
        return skill / "tests" / file
    if re.fullmatch(r"[A-Za-z0-9_/.-]+_test\.go", file):
        return skill / file
    return None


def has_running_claim_test(path: Path, name: str) -> bool:
    if path.suffix == ".py":
        return name.startswith("test_") and name in collected_tests(path)
    if path.suffix == ".go":
        return name.startswith("Test") and name in collected_go_tests(path)
    return False



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
        tfile = claim_test_path(skill, file)
        if tfile is None or not tfile.is_file() or not has_running_claim_test(tfile, name):
            problems.append(f"unittest 또는 go test 가 실행하는 테스트가 없다: {test}")
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


EN_ROOT = REPO / "presets" / "lang" / "en" / "base" / ".claude" / "skills"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
NAME_MAX, DESCRIPTION_MAX, SKILL_MD_MAX_LINES = 64, 1024, 500


def spec_dirs():
    """규격 한도는 설치되는 모든 SKILL.md 가 대상이다 — 영어 오버레이도 그대로 배포된다."""
    en = sorted(d for d in EN_ROOT.iterdir() if (d / "SKILL.md").is_file()) if EN_ROOT.is_dir() else []
    return skill_dirs() + en


def frontmatter_value(skill: Path, key: str) -> str:
    """frontmatter 의 한 줄 값(따옴표 제거). 값이 여러 줄이면 이어 붙인다."""
    front = (skill / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[1]
    match = re.search(rf"^{key}:[ \t]*(.*(?:\n[ \t]+.*)*)", front, re.M)
    if not match:
        return ""
    value = " ".join(match.group(1).split())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].replace('\\"', '"')
    return value.lstrip(">|- ").strip()


class TestSpecLimits(unittest.TestCase):
    """agentskills 규격 한도(#130): name·description 길이, SKILL.md 줄 수, references 깊이."""

    def test_names_match_directory_and_fit_the_spec(self):
        bad = []
        for skill in spec_dirs():
            name = frontmatter_value(skill, "name")
            if name != skill.name or not NAME_RE.match(name) or len(name) > NAME_MAX:
                bad.append(f"{skill.relative_to(REPO)}: name={name!r}")
        self.assertEqual(bad, [], "name 은 폴더명과 같고 소문자·숫자·하이픈 64자 이하여야 한다:\n" + "\n".join(bad))

    def test_descriptions_fit_the_spec(self):
        bad = []
        for skill in spec_dirs():
            size = len(frontmatter_value(skill, "description"))
            if not 1 <= size <= DESCRIPTION_MAX:
                bad.append(f"{skill.relative_to(REPO)}: {size}자")
        self.assertEqual(bad, [], f"description 은 1~{DESCRIPTION_MAX}자여야 한다:\n" + "\n".join(bad))

    def test_skill_md_stays_under_500_lines(self):
        bad = []
        for skill in spec_dirs():
            lines = len((skill / "SKILL.md").read_text(encoding="utf-8").splitlines())
            if lines >= SKILL_MD_MAX_LINES:
                bad.append(f"{skill.relative_to(REPO)}: {lines}줄")
        self.assertEqual(bad, [], "SKILL.md 가 500줄 이상이다 — 상세 내용을 references/ 로 옮긴다:\n" + "\n".join(bad))

    def test_references_are_one_level_deep(self):
        # 도구가 이름으로 골라 읽는 자료 폴더만 예외로 둔다. 문서를 폴더로 한 단계 더 나누는 것은 막는다.
        # yd-writer-kr 의 profiles/ 는 검사기가 --profile 이름으로 찾는 표기 프로필이다(#137).
        data_dirs = {"yd-writer-kr/references/profiles"}
        nested = [str(d.relative_to(REPO)) for skill in spec_dirs()
                  for d in (skill / "references").glob("*/")
                  if d.is_dir() and f"{skill.name}/references/{d.name}" not in data_dirs]
        self.assertEqual(nested, [], "references/ 아래에 하위 폴더를 두지 않는다:\n" + "\n".join(nested))

    def test_frontmatter_value_reads_quoted_and_folded_values(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "demo"
            skill.mkdir()
            (skill / "SKILL.md").write_text(
                '---\nname: demo\ndescription: "a \\"b\\" c"\nmetadata:\n  internal: true\n---\n', encoding="utf-8")
            self.assertEqual(frontmatter_value(skill, "name"), "demo")
            self.assertEqual(frontmatter_value(skill, "description"), 'a "b" c')
            (skill / "SKILL.md").write_text("---\nname: demo\ndescription: >-\n  one\n  two\n---\n", encoding="utf-8")
            self.assertEqual(frontmatter_value(skill, "description"), "one two")


if __name__ == "__main__":
    unittest.main()
