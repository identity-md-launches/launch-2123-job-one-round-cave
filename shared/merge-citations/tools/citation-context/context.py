#!/usr/bin/env python3
"""Open a hash-pinned document citation with exact surrounding source lines."""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

_spec = importlib.util.spec_from_file_location(
    "context_anchor", Path(__file__).absolute().parents[1] / "citation-reanchor/reanchor.py")
anchor_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(anchor_tool)
engine = anchor_tool.engine

FORMAT = "citation-context/v1"
MAX_MARGIN = 100
MAX_CONTEXT_BYTES = 262144
MAX_REPORT_BYTES = 1000000


def validate_selection(selection):
    """Accept a complete ancestor anchor or an explicit hash-pinned range."""
    if isinstance(selection, dict) and "format" in selection:
        anchor_tool.validate(selection)
    else:
        fields = {"path", "line_start", "line_end", "sha256"}
        if not isinstance(selection, dict) or set(selection) != fields:
            raise engine.SearchError("invalid citation selection")
    if not engine.valid_relative(selection["path"]):
        raise engine.SearchError("invalid citation source path")
    try:
        if len(selection["path"].encode("utf-8")) > 4096:
            raise engine.SearchError("citation source path exceeds 4096 UTF-8 bytes")
    except UnicodeError:
        raise engine.SearchError("citation source path is not valid Unicode") from None
    start, end = selection["line_start"], selection["line_end"]
    if (type(start) is not int or type(end) is not int
            or not 1 <= start <= end <= engine.MAX_FILE_BYTES
            or end - start + 1 > anchor_tool.MAX_ANCHOR_LINES):
        raise engine.SearchError("invalid citation line range")
    if (not isinstance(selection["sha256"], str)
            or not re.fullmatch("[0-9a-f]{64}", selection["sha256"])):
        raise engine.SearchError("invalid expected source SHA-256")
    return selection


def parse_citation(citation, sha256):
    if not isinstance(citation, str) or len(citation) > 4096:
        raise engine.SearchError("invalid citation string")
    match = re.fullmatch(r"(.+):([1-9][0-9]{0,6})(?:-([1-9][0-9]{0,6}))?", citation)
    if not match:
        raise engine.SearchError("citation must be path:line or path:start-end")
    name, first, last = match.groups()
    return validate_selection({"path": name, "line_start": int(first),
                               "line_end": int(last or first), "sha256": sha256})


def validate_margins(before, after):
    if (type(before) is not int or type(after) is not int
            or not 0 <= before <= MAX_MARGIN or not 0 <= after <= MAX_MARGIN):
        raise engine.SearchError(f"before and after must be integers from 0 to {MAX_MARGIN}")


def section_headings(lines, name, selected_start):
    """Return enclosing ATX headings at the first selected line, outside fences.

    This intentionally recognizes a Markdown subset, not a complete parser.
    Every returned item is an exact source line with its own citation.
    """
    if Path(name).suffix.lower() != ".md":
        return []
    stack, fence_char, fence_length = [], None, 0
    for number, text in enumerate(lines[:selected_start], 1):
        if fence_char is not None:
            close = rf" {{0,3}}{re.escape(fence_char)}{{{fence_length},}}[ \t]*"
            if re.fullmatch(close, text):
                fence_char = None
            continue
        opening = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", text)
        if opening:
            marker, info = opening.groups()
            if marker[0] != "`" or "`" not in info:
                fence_char, fence_length = marker[0], len(marker)
                continue
        heading = re.match(r"^ {0,3}(#{1,6})(?:[ \t]+|$)", text)
        if heading:
            level = len(heading.group(1))
            stack = [item for item in stack if item["level"] < level]
            stack.append({"level": level, "line": number, "text": text,
                          "citation": f"{name}:{number}-{number}"})
    return stack


def inspect_bytes(raw, selection, before=3, after=3):
    """Validate original bytes before making any citation or context available."""
    validate_selection(selection)
    validate_margins(before, after)
    document, lines = anchor_tool.source(raw, selection["path"])
    if document["sha256"] != selection["sha256"]:
        raise engine.SearchError("source SHA-256 changed; review or reanchor the citation first")
    first, last = selection["line_start"], selection["line_end"]
    if last > len(lines):
        raise engine.SearchError("citation lines are outside the source")
    if "text" in selection and "\n".join(lines[first - 1:last]) != selection["text"]:
        raise engine.SearchError("saved citation text contradicts the hash-matching source")
    start, end = max(1, first - before), min(len(lines), last + after)
    context_lines = lines[start - 1:end]
    if len("\n".join(context_lines).encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise engine.SearchError("context exceeds byte limit; request fewer surrounding lines")
    name = selection["path"]
    result = {
        "format": FORMAT, "mode": "bytes", "path": name,
        "sha256": document["sha256"], "source_verified": False,
        "source_line_count": len(lines),
        "selection": {"line_start": first, "line_end": last,
                      "citation": f"{name}:{first}-{last}",
                      "saved_text_checked": "text" in selection},
        "context": {"line_start": start, "line_end": end,
                    "citation": f"{name}:{start}-{end}",
                    "before_requested": before, "after_requested": after,
                    "before_returned": first - start, "after_returned": end - last,
                    "clipped_at_start": start > first - before,
                    "clipped_at_end": end < last + after,
                    "lines": [{"number": number, "selected": first <= number <= last,
                               "text": text}
                              for number, text in enumerate(context_lines, start)]},
        "section_headings": section_headings(lines, name, first),
        "heading_scope": "ATX Markdown headings outside fenced code at the selection start",
    }
    return bounded_report(result)


def bounded_report(result):
    # Bound even JSON escaping of control characters and duplicated heading lines.
    if len(json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")) > MAX_REPORT_BYTES:
        raise engine.SearchError("serialized context exceeds byte limit")
    return result


def inspect_live(root, selection, before=3, after=3):
    validate_selection(selection)
    validate_margins(before, after)
    name = selection["path"]
    result = inspect_bytes(anchor_tool.read_source(root, name), selection, before, after)
    # No partial report escapes if the source changes during context extraction.
    if engine.digest(anchor_tool.read_source(root, name)) != result["sha256"]:
        raise engine.SearchError("source changed during context read; retry with static files")
    result["mode"] = "live"
    result["source_verified"] = True
    return bounded_report(result)


def inspect_snapshot(index, selection, before=3, after=3):
    validate_selection(selection)
    validate_margins(before, after)
    engine.validate_index(index)
    for document in index["documents"]:
        if document["path"] == selection["path"]:
            result = inspect_bytes(document["text"].encode("utf-8"), selection, before, after)
            result["mode"] = "snapshot"
            return bounded_report(result)
    raise engine.SearchError("citation source is absent from the snapshot")


def demo():
    root = Path(__file__).absolute().parents[1] / "evidence-search/examples/docs"
    raw = anchor_tool.read_source(root, "zto.md")
    selection = anchor_tool.capture_bytes(raw, "zto.md", 3, 6)
    # Reuse historical observations; do not make a fresh chain-state claim.
    index = engine.build_index(root)
    return {
        "example": "historical ZTO document; local evidence, not a current chain observation",
        "live": inspect_live(root, selection, before=2, after=9),
        "snapshot": inspect_snapshot(index, selection, before=2, after=9),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command, argument, help_text in [
            ("live", "root", "open a citation against a static local source collection"),
            ("snapshot", "index", "open a citation against an Evidence Search snapshot")]:
        sub = commands.add_parser(command, help=help_text)
        sub.add_argument(argument)
        selection = sub.add_mutually_exclusive_group(required=True)
        selection.add_argument("--anchor", help="saved citation-anchor/v1 JSON file")
        selection.add_argument("--citation", help="path:line or path:start-end")
        sub.add_argument("--sha256", help="whole-source hash required with --citation")
        sub.add_argument("--before", type=int, default=3)
        sub.add_argument("--after", type=int, default=3)
    commands.add_parser("demo", help="read-only historical ZTO example in live and snapshot modes")
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            result = demo()
        else:
            if args.anchor:
                if args.sha256 is not None:
                    raise engine.SearchError("--anchor already contains a hash; omit --sha256")
                selection = anchor_tool.load_anchor(args.anchor)
            else:
                if args.sha256 is None:
                    raise engine.SearchError("--citation requires its expected --sha256")
                selection = parse_citation(args.citation, args.sha256)
            if args.command == "live":
                result = inspect_live(args.root, selection, args.before, args.after)
            else:
                result = inspect_snapshot(engine.load_index(args.index), selection,
                                          args.before, args.after)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
