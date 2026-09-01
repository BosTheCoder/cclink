"""Tests for ccl.py.

fixtures.json is shared with the page's JS; the fixture-driven cases here have
a mirror in test/codec.test.js, so a regex loosened on one side fails on the
other rather than shipping links that only work in one direction.
"""

import json
import unittest
from pathlib import Path

import ccl

FIXTURES = json.loads((Path(__file__).parent / "fixtures.json").read_text())


class TestFixtures(unittest.TestCase):
    def test_valid_ids_round_trip_to_link_and_uri(self):
        for case in FIXTURES["valid"]:
            with self.subTest(case["id"]):
                self.assertEqual(ccl.link_for(case["id"], FIXTURES["base"]), case["link"])
                self.assertEqual(ccl.uri_for(case["id"]), case["uri"])
                self.assertEqual(ccl.parse(case["link"], FIXTURES["base"]), case["id"])
                self.assertEqual(ccl.parse(case["uri"], FIXTURES["base"]), case["id"])

    def test_accepted_variants_all_reach_the_same_id(self):
        expected = FIXTURES["valid"][0]["id"]
        for variant in FIXTURES["accepted_variants"]:
            with self.subTest(variant):
                self.assertEqual(ccl.parse(variant, FIXTURES["base"]), expected)

    def test_free_text_from_a_note_yields_the_id(self):
        expected = FIXTURES["valid"][0]["id"]
        for text in FIXTURES["extractable"]:
            with self.subTest(text):
                self.assertEqual(ccl.extract(text, FIXTURES["base"]), expected)

    def test_extract_refuses_text_with_no_session_id_in_it(self):
        for bad in FIXTURES["extract_rejected"]:
            with self.subTest(bad):
                with self.assertRaises(ccl.CclError):
                    ccl.extract(bad, FIXTURES["base"])

    def test_rejected_inputs_raise(self):
        for bad in FIXTURES["rejected"]:
            with self.subTest(bad):
                with self.assertRaises(ccl.CclError):
                    ccl.parse(bad, FIXTURES["base"])


class TestResolveCwd(unittest.TestCase):
    """The id -> directory lookup, which is what makes `--resume` find anything."""

    def _project(self, root, dirname, session_id, cwd, lead_without_cwd=True):
        d = root / dirname
        d.mkdir(parents=True, exist_ok=True)
        lines = []
        if lead_without_cwd:
            # Real transcripts open with a record that has no cwd, so a reader
            # that only looks at line 1 finds nothing.
            lines.append({"type": "last-prompt", "sessionId": session_id})
        lines.append({"type": "user", "sessionId": session_id, "cwd": cwd})
        (d / f"{session_id}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        return d

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_reads_cwd_from_the_transcript_not_the_directory_name(self):
        # The directory name mangles every "/" to "-", so a path segment that
        # already contains a hyphen cannot be recovered by un-mangling. Reading
        # the recorded cwd is the only correct answer.
        sid = FIXTURES["valid"][0]["id"]
        self._project(
            self.root,
            "-home-bosire-projects-personal-win-scheduled-tasks",
            sid,
            "/home/bosire/projects/personal/win-scheduled-tasks",
        )
        self.assertEqual(
            ccl.resolve_cwd(sid, self.root),
            Path("/home/bosire/projects/personal/win-scheduled-tasks"),
        )

    def test_unknown_session_reports_where_it_looked(self):
        with self.assertRaises(ccl.CclError) as ctx:
            ccl.resolve_cwd(FIXTURES["valid"][1]["id"], self.root)
        self.assertIn(str(self.root), str(ctx.exception))

    def test_transcript_without_cwd_fails_rather_than_guessing(self):
        sid = FIXTURES["valid"][0]["id"]
        d = self.root / "-home-bosire"
        d.mkdir(parents=True)
        (d / f"{sid}.jsonl").write_text(json.dumps({"type": "last-prompt"}) + "\n")
        with self.assertRaises(ccl.CclError):
            ccl.resolve_cwd(sid, self.root)

    def test_lookup_validates_before_touching_the_filesystem(self):
        # A traversal attempt must not become a glob against the projects dir.
        with self.assertRaises(ccl.CclError):
            ccl.resolve_cwd("../../../etc/passwd", self.root)


class TestCli(unittest.TestCase):
    def test_bad_input_exits_nonzero_without_a_traceback(self):
        self.assertEqual(ccl.main(["not-a-uuid"]), 1)

    def test_resume_failure_uses_its_own_exit_code(self):
        # The launcher keys the terminal tab staying open off this code, so it
        # must not collapse into claude's own non-zero exits.
        self.assertEqual(ccl.main(["--resume", "not-a-uuid"]), ccl.RESUME_FAILED)
        self.assertNotEqual(ccl.RESUME_FAILED, 1)

    def test_prints_link_for_a_bare_id(self):
        self.assertEqual(ccl.main([FIXTURES["valid"][0]["id"], "--base", FIXTURES["base"]]), 0)


if __name__ == "__main__":
    unittest.main()
