import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("citation_context", Path(__file__).with_name("context.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


class ContextTests(unittest.TestCase):
    raw = b"# Title\n\nalpha\nbeta\n\n## Detail\ngamma\n"

    def selection(self, raw=None, start=3, end=4, path="source.md"):
        raw = self.raw if raw is None else raw
        return c.parse_citation(f"{path}:{start}-{end}", c.engine.digest(raw))

    def scratch(self):
        Path("test/scratch").mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir="test/scratch")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", c.__file__, *map(str, args)],
                              capture_output=True, text=True)

    def test_exact_numbered_context_and_selection(self):
        selected = self.selection()
        original = copy.deepcopy(selected)
        result = c.inspect_bytes(self.raw, selected, before=1, after=2)
        self.assertEqual(result["context"]["citation"], "source.md:2-6")
        self.assertEqual(result["context"]["lines"], [
            {"number": 2, "selected": False, "text": ""},
            {"number": 3, "selected": True, "text": "alpha"},
            {"number": 4, "selected": True, "text": "beta"},
            {"number": 5, "selected": False, "text": ""},
            {"number": 6, "selected": False, "text": "## Detail"},
        ])
        self.assertFalse(result["source_verified"])
        self.assertFalse(result["selection"]["saved_text_checked"])
        self.assertEqual(result["source_line_count"], 7)
        self.assertEqual(selected, original)

    def test_edges_are_clipped_explicitly_and_zero_margin(self):
        result = c.inspect_bytes(self.raw, self.selection(), 100, 100)["context"]
        self.assertTrue(result["clipped_at_start"])
        self.assertTrue(result["clipped_at_end"])
        self.assertEqual((result["before_returned"], result["after_returned"]), (2, 3))
        exact = c.inspect_bytes(self.raw, self.selection(), 0, 0)["context"]
        self.assertEqual(exact["citation"], "source.md:3-4")
        self.assertFalse(exact["clipped_at_start"])
        self.assertFalse(exact["clipped_at_end"])
        self.assertTrue(all(item["selected"] for item in exact["lines"]))

    def test_crlf_unicode_tabs_and_final_blank_line(self):
        raw = "# T\r\n\té\u2028x\r\n\r\n".encode()
        anchor = c.anchor_tool.capture_bytes(raw, "a.md", 2, 3)
        result = c.inspect_bytes(raw, anchor, 0, 0)
        self.assertEqual(result["source_line_count"], 3)
        self.assertEqual([line["text"] for line in result["context"]["lines"]], ["\té\u2028x", ""])
        self.assertTrue(result["selection"]["saved_text_checked"])
        with self.assertRaisesRegex(c.engine.SearchError, "SHA-256 changed"):
            c.inspect_bytes(raw.replace(b"\r\n", b"\n"), anchor)

    def test_change_outside_cited_lines_refuses_context(self):
        with self.assertRaisesRegex(c.engine.SearchError, "SHA-256 changed"):
            c.inspect_bytes(self.raw.replace(b"gamma", b"changed"), self.selection())

    def test_saved_text_checked_and_duplicate_range_not_relocated(self):
        raw = b"repeat\nrepeat\nrepeat\n"
        anchor = c.anchor_tool.capture_bytes(raw, "a.md", 2, 2)
        result = c.inspect_bytes(raw, anchor, 0, 0)
        self.assertEqual(result["selection"]["citation"], "a.md:2-2")
        anchor["text"] = "forged"
        with self.assertRaisesRegex(c.engine.SearchError, "contradicts"):
            c.inspect_bytes(raw, anchor)

    def test_missing_empty_and_past_end_source(self):
        for raw, start, end in [(b"", 1, 1), (b"one\n", 1, 2), (self.raw, 8, 8)]:
            with self.assertRaisesRegex(c.engine.SearchError, "outside"):
                c.inspect_bytes(raw, self.selection(raw, start, end))
        # A blank line is still an exact line for an explicit range.
        result = c.inspect_bytes(b"\n", self.selection(b"\n", 1, 1), 0, 0)
        self.assertEqual(result["context"]["lines"][0]["text"], "")

    def test_snapshot_never_reads_live_source_and_preserves_input(self):
        selected = self.selection()
        index = {"format": c.engine.FORMAT, "documents": [
            {"path": selected["path"], "sha256": selected["sha256"], "text": self.raw.decode()}]}
        original = copy.deepcopy(index)
        with patch.object(c.anchor_tool, "read_source", side_effect=AssertionError("unexpected live read")):
            result = c.inspect_snapshot(index, selected)
        self.assertFalse(result["source_verified"])
        self.assertEqual(result["mode"], "snapshot")
        self.assertEqual(index, original)

    def test_snapshot_missing_forged_text_and_stale_expected_hash(self):
        selected = self.selection()
        with self.assertRaisesRegex(c.engine.SearchError, "absent"):
            c.inspect_snapshot({"format": c.engine.FORMAT, "documents": []}, selected)
        doc = {"path": "source.md", "sha256": selected["sha256"], "text": "altered"}
        index = {"format": c.engine.FORMAT, "documents": [doc]}
        with self.assertRaisesRegex(c.engine.SearchError, "SHA-256"):
            c.inspect_snapshot(index, selected)
        doc["sha256"] = c.engine.digest(doc["text"].encode())
        with self.assertRaisesRegex(c.engine.SearchError, "SHA-256 changed"):
            c.inspect_snapshot(index, selected)

    def test_heading_ancestry_includes_start_and_resets_same_level(self):
        raw = b"# Root\n## Old\n### Child\n## New\nbody\n### Selected\n"
        result = c.inspect_bytes(raw, self.selection(raw, 6, 6), 0, 0)
        self.assertEqual([(item["line"], item["level"]) for item in result["section_headings"]],
                         [(1, 1), (4, 2), (6, 3)])
        self.assertEqual(result["section_headings"][-1]["text"], "### Selected")
        self.assertEqual(result["section_headings"][-1]["citation"], "source.md:6-6")

    def test_heading_fences_and_plaintext(self):
        raw = (b"# Root\n````lang\n## Fake\n```\n## Still fake\n````\n"
               b"~~~\n# Also fake\n~~~~\n    # Indented\n####### Too many\n#No space\nbody\n")
        result = c.inspect_bytes(raw, self.selection(raw, 13, 13), 0, 0)
        self.assertEqual([item["text"] for item in result["section_headings"]], ["# Root"])
        plain = c.inspect_bytes(raw, self.selection(raw, 13, 13, "source.txt"))
        self.assertEqual(plain["section_headings"], [])

    def test_bad_selection_and_margin_types(self):
        selected = self.selection()
        for key, value in [("path", "../a.md"), ("path", ".a.md"), ("path", "a.py"),
                           ("path", "/a.md"), ("path", "a\ud800.md"),
                           ("path", "a" * 4096 + ".md"),
                           ("sha256", "A" * 64), ("sha256", None),
                           ("line_start", True), ("line_start", 0), ("line_end", 2),
                           ("line_end", 203), ("line_end", 4.0)]:
            with self.assertRaises(c.engine.SearchError, msg=(key, repr(value))):
                c.inspect_bytes(self.raw, dict(selected, **{key: value}))
        for bad in [None, [], {}, dict(selected, extra=1)]:
            with self.assertRaises(c.engine.SearchError):
                c.inspect_bytes(self.raw, bad)
        for before, after in [(-1, 0), (0, -1), (101, 0), (0, 101), (True, 0), (0, 2.0)]:
            with self.assertRaises(c.engine.SearchError):
                c.inspect_bytes(self.raw, selected, before, after)

    def test_citation_parser(self):
        sha = c.engine.digest(self.raw)
        self.assertEqual(c.parse_citation("source.md:3", sha)["line_end"], 3)
        self.assertEqual(c.parse_citation("nested/a:b.md:3-4", sha)["path"], "nested/a:b.md")
        for value in [None, "source.md", "source.md:03", "source.md:0", "source.md:4-3",
                      "source.md:1-1000000000", "source.md:1-2\n", "source.md:-1", "../a.md:1"]:
            with self.assertRaises(c.engine.SearchError, msg=repr(value)):
                c.parse_citation(value, sha)

    def test_source_and_output_bounds(self):
        for raw in [b"\xff", b"\x00", b"x" * (c.engine.MAX_FILE_BYTES + 1),
                    b"x" * (c.engine.MAX_LINE_CHARS + 1)]:
            with self.assertRaises(c.engine.SearchError):
                c.inspect_bytes(raw, self.selection(raw, 1, 1))
        with patch.object(c, "MAX_CONTEXT_BYTES", 5):
            with self.assertRaisesRegex(c.engine.SearchError, "context exceeds byte limit"):
                c.inspect_bytes(self.raw, self.selection(), 0, 0)
        with patch.object(c, "MAX_REPORT_BYTES", 10):
            with self.assertRaisesRegex(c.engine.SearchError, "serialized context"):
                c.inspect_bytes(self.raw, self.selection(), 0, 0)

    def test_live_double_read_changed_missing_and_paths(self):
        with self.scratch() as folder:
            root = Path(folder)
            source = root / "source.md"
            source.write_bytes(self.raw)
            result = c.inspect_live(root, self.selection())
            self.assertTrue(result["source_verified"])
            self.assertEqual(result["mode"], "live")
            self.assertEqual(source.read_bytes(), self.raw)
            with patch.object(c.anchor_tool, "read_source", side_effect=[self.raw, b"changed"]):
                with self.assertRaisesRegex(c.engine.SearchError, "changed during"):
                    c.inspect_live(root, self.selection())
            source.unlink()
            with self.assertRaises(c.engine.SearchError):
                c.inspect_live(root, self.selection())
            source.symlink_to("absent.md")
            with self.assertRaisesRegex(c.engine.SearchError, "symlink"):
                c.inspect_live(root, self.selection())
            for invalid in ["../outside", "/outside-workspace"]:
                with self.assertRaises(c.engine.SearchError):
                    c.inspect_live(invalid, self.selection())

    def test_cli_explicit_anchor_and_snapshot_preserve_files(self):
        with self.scratch() as folder:
            root = Path(folder)
            source = root / "source.md"
            source.write_bytes(self.raw)
            anchor = root / "anchor.json"
            anchor.write_text(json.dumps(c.anchor_tool.capture_bytes(self.raw, "source.md", 3, 4)))
            index = root / "index.json"
            index.write_text(json.dumps(c.engine.build_index(root)))
            original = {p.name: p.read_bytes() for p in root.iterdir()}
            args = ["--citation", "source.md:3-4", "--sha256", self.selection()["sha256"]]
            for command, input_path, selection, verified in [
                    ("live", root, args, True),
                    ("live", root, ["--anchor", anchor], True),
                    ("snapshot", index, args, False),
                    ("snapshot", index, ["--anchor", anchor], False)]:
                result = self.cli(command, input_path, *selection, "--before", 0, "--after", 0)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(report["source_verified"], verified)
                self.assertEqual(report["context"]["citation"], "source.md:3-4")
            self.assertEqual({p.name: p.read_bytes() for p in root.iterdir()}, original)

    def test_cli_failure_outputs_no_partial_context(self):
        with self.scratch() as folder:
            root = Path(folder)
            source = root / "source.md"
            source.write_bytes(self.raw)
            anchor = root / "anchor.json"
            for data in [b'{"format":1,"format":2}', b'{"format":NaN}', b"\xff", b"[]"]:
                anchor.write_bytes(data)
                result = self.cli("live", root, "--anchor", anchor)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error", json.loads(result.stderr))
            anchor.write_bytes(b'{"line_start":' + b"1" * 5000 + b"}")
            oversized_integer = self.cli("live", root, "--anchor", anchor)
            self.assertEqual(oversized_integer.returncode, 2)
            self.assertEqual(oversized_integer.stdout, "")
            self.assertIn("error", json.loads(oversized_integer.stderr))
            expected = self.selection()["sha256"]
            for extra in [["--citation", "source.md:3-4"],
                          ["--citation", "source.md:3-4", "--sha256", expected, "--before", -1],
                          ["--anchor", anchor, "--sha256", expected]]:
                result = self.cli("live", root, *extra)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("error", json.loads(result.stderr))
            source.write_bytes(self.raw + b"changed\n")
            result = self.cli("live", root, "--citation", "source.md:3-4", "--sha256", expected)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("SHA-256 changed", result.stderr)

    def test_historical_zto_demo_and_cli(self):
        result = c.demo()
        self.assertEqual(result["live"]["selection"]["citation"], "zto.md:3-6")
        self.assertEqual(result["live"]["context"]["citation"], "zto.md:1-15")
        self.assertTrue(result["live"]["source_verified"])
        self.assertFalse(result["snapshot"]["source_verified"])
        self.assertEqual(result["live"]["context"], result["snapshot"]["context"])
        text = "\n".join(item["text"] for item in result["live"]["context"]["lines"])
        self.assertIn("0xd782bdea4ef02a0bd391eb9089470c8080f0a68e", text)
        self.assertIn("not an independent proof or a current quote", text)
        executed = self.cli("demo")
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(json.loads(executed.stdout), result)


if __name__ == "__main__":
    unittest.main()
