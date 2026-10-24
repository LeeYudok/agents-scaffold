"""union_sync.py 의 계획·압축 해제 로직 (stdlib only).

원격 접속 없이 매니페스트를 직접 만들어 판정을 본다.
"""
import io
import json
import sys
import tarfile
import tempfile
import unicodedata
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import union_sync as us  # noqa: E402

NFD = unicodedata.normalize("NFD", "docs/원본/보고서.xlsx")
NFC = unicodedata.normalize("NFC", NFD)


def man(**files):
    m = us.Manifest()
    m.files.update(files)
    return m


class PlanTest(unittest.TestCase):
    def test_fills_missing_from_first_host_that_has_it(self):
        plan = us.make_plan({
            "local": man(**{"docs/a": "1"}),
            "pig": man(**{"docs/b": "2"}),
            "doksam": man(**{"docs/a": "1", "docs/b": "2"}),
        })
        self.assertEqual(plan.copies["local"], [("pig", "docs/b")])
        self.assertEqual(plan.copies["pig"], [("local", "docs/a")])
        self.assertEqual(plan.copies["doksam"], [])
        self.assertEqual(plan.union, 2)

    def test_nfd_and_nfc_names_are_the_same_file(self):
        plan = us.make_plan({"local": man(**{NFD: "h"}), "pig": man(**{NFC: "h"})})
        self.assertEqual(plan.union, 1)
        self.assertEqual(sum(len(v) for v in plan.copies.values()), 0)

    def test_conflict_is_reported_and_never_copied(self):
        plan = us.make_plan({
            "local": man(**{"docs/c": "x"}),
            "pig": man(**{"docs/c": "y"}),
            "doksam": man(),
        })
        self.assertEqual(plan.conflicts, {"docs/c": {"local": "x", "pig": "y"}})
        self.assertEqual(plan.copies["doksam"], [])

    def test_default_excludes_skip_machine_caches(self):
        plan = us.make_plan({
            "local": man(**{"docs/.DS_Store": "1", "docs/x/__pycache__/m.cpython-312.pyc": "2", "docs/m.pyc": "3"}),
            "pig": man(),
        })
        self.assertEqual(plan.union, 0)
        self.assertEqual(plan.conflicts, {})

    def test_extra_exclude_pattern(self):
        plan = us.make_plan({"local": man(**{"docs/.playwright-mcp/a.log": "1"}), "pig": man()},
                            us.DEFAULT_EXCLUDES + (".playwright-mcp",))
        self.assertEqual(plan.union, 0)

    def test_same_host_nfc_nfd_pair_is_duplicate_and_nfc_name_is_source(self):
        plan = us.make_plan({"doksam": man(**{NFD: "h", NFC: "h"}), "pig": man()})
        self.assertEqual(plan.duplicates, {"doksam": [NFC]})
        self.assertEqual(plan.copies["pig"], [("doksam", NFC)])


class ManifestTest(unittest.TestCase):
    def test_parse_separates_links(self):
        text = "\n".join([
            json.dumps({"p": "docs/a", "h": "1", "s": 1}),
            json.dumps({"p": "docs/l", "link": True}),
            "",
        ])
        m = us.parse_manifest(text)
        self.assertEqual(m.files, {"docs/a": "1"})
        self.assertEqual(m.links, ["docs/l"])


class ExtractTest(unittest.TestCase):
    def _tar(self, entries):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for name, data in entries:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        buf.seek(0)
        return buf

    def test_writes_new_files_and_keeps_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "docs/keep").write_bytes(b"old")
            stream = self._tar([("docs/keep", b"new"), ("docs/sub/new", b"n")])
            written, skipped = us.extract_stream(stream, root, "docs")
            self.assertEqual((written, skipped), (1, 1))
            self.assertEqual((root / "docs/keep").read_bytes(), b"old")
            self.assertEqual((root / "docs/sub/new").read_bytes(), b"n")

    def test_rejects_paths_outside_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            stream = self._tar([("../evil", b"x"), ("other/x", b"x"), ("/abs", b"x")])
            written, skipped = us.extract_stream(stream, root, "docs")
            self.assertEqual((written, skipped), (0, 3))
            self.assertFalse((Path(tmp) / "evil").exists())


class CliTest(unittest.TestCase):
    def test_apply_without_local_hub_is_refused(self):
        rc = us.main(["pig", "doksam", "--dir", "docs", "--apply", "--repo-path", "x"])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
