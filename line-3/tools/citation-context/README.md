# Citation Context

Open a saved document citation with its surrounding source lines before relying
on it. The whole source must match the citation's expected SHA-256. The result
preserves exact line numbers, marks the originally selected lines, and shows
nearby qualifications that a short search excerpt may omit. It runs offline
with Python 3.9+ and only the standard library.

From the repository root, one command demonstrates both modes without writing
any files:

```sh
python3 -B line-3/tools/citation-context/context.py demo
```

When tried, the historical real ZTO citation `zto.md:3-6` expanded to
`zto.md:1-15`. Its selected metadata remained marked, while the context exposed
the recorded block number and the source's warning that it is not a current
quote. Live and snapshot modes returned the same 15 source lines. Live mode
reported `source_verified: true`; snapshot mode reported `false`. This reads the
inherited historical observations and makes no new Ethereum request.

Keep this directory together with the sibling
[Evidence Search](../evidence-search/README.md) and
[Citation Reanchor](../citation-reanchor/README.md) directories. The tool reuses
their validated source/index formats, bounded workspace reads and line model.

## Open a search citation

Copy the `citation` and **whole-source** `sha256` from an existing search hit.
Both are required; this tool never substitutes the current file's hash for a
missing expected hash. This complete example uses the actual bundled source:

```sh
python3 -B line-3/tools/citation-context/context.py live line-3/tools/evidence-search/examples/docs --citation zto.md:3-6 --sha256 03a74a78fa9fd52080b1b21385dafb47dc07c2422ff2e6ff327cbf3d94da8009 --before 2 --after 9
```

`--citation` also accepts a single line, such as `zto.md:6`. With an existing
`citation-anchor/v1` file captured by Citation Reanchor, use `--anchor` instead
of `--citation` and `--sha256`:

```sh
python3 -B line-3/tools/citation-context/context.py live line-3/tools/evidence-search/examples/docs --anchor line-3/zto-anchor.json --before 2 --after 9
```

An anchor also supplies the exact saved excerpt. The tool checks it against the
original range in the hash-matching source and rejects a contradiction. Repeated
text elsewhere does not change the selected original range.

For an existing Evidence Search index, replace `live ROOT` with
`snapshot INDEX`. This checks the index's embedded source bytes and expected
hash without reading the source collection:

```sh
python3 -B line-3/tools/citation-context/context.py snapshot line-3/evidence-index.json --citation zto.md:3-6 --sha256 03a74a78fa9fd52080b1b21385dafb47dc07c2422ff2e6ff327cbf3d94da8009 --before 2 --after 9
```

The anchor and index examples require those existing files; the demo requires
no preparation. All commands print JSON and leave inputs untouched. The current
working directory is the workspace boundary, so run from the repository root
or a workspace containing the selected corpus and tool directories.

## Reading the result

`selection.citation` identifies the original inclusive range.
`context.citation` identifies the expanded inclusive range; `context.lines`
contains one object per source line with `number`, `text`, and `selected`.
Margins default to three lines on each side. Requested and returned margins,
plus `clipped_at_start` and `clipped_at_end`, make document-edge clipping explicit.

`section_headings` adds the active Markdown ATX heading ancestry at the first
selected line, with exact heading text and independent line citations. Heading
lines may be outside the expanded range; they do not silently enlarge it.
Headings beginning on the selected first line are included. This is a limited
Markdown aid: it recognizes one to six `#` markers with a following space/tab
or end of line, ignores backtick/tilde fenced code, and allows at most three
leading spaces. It does not parse Setext headings, lists, blockquotes, HTML,
indented-code continuation or all CommonMark nesting. Non-Markdown files have
no heading ancestry. Use the exact source lines when structural context matters.

`source_verified: true` means live mode read the selected file twice and both
reads matched the expected whole-file hash. Snapshot and in-memory API results
always report `false`; their embedded bytes were validated but no live file was
checked. A hash does not authenticate authorship, establish truth, or prove
that the selected passage supports a claim. In particular, historical token
observations do not establish current token state or authorize a payment.

Any change to the whole source, even outside the selected excerpt or a CRLF/LF
conversion, refuses the result. Review the changed source with Citation Reanchor
before deciding whether to capture a new anchor. Citation Context never moves a
citation automatically and never asserts that unchanged words retain their
original meaning.

## Bounds and failure behavior

Each selection contains 1–200 lines. Each margin is an integer from 0–100, so
at most 400 context lines are returned. Context text is limited to 262,144 UTF-8
bytes and each serialized result to 1,000,000 bytes. Requests exceeding these
limits fail rather than dropping selected lines. Source paths are limited to
4,096 UTF-8 bytes. Source and index limits are inherited: one source at most
1,000,000 bytes, 16,000 characters per line; index at most 1,000 documents,
8,000,000 total source bytes and 16,000,000 serialized input bytes. Existing
anchor excerpt and JSON bounds also apply.

Source lines follow the inherited LF-delimited model: one trailing CR is removed
from each line, the final LF does not create an extra line, and other Unicode
separators stay inside the line. The hash always covers the original bytes.
Tabs, spaces, blank lines, case and Unicode code points are otherwise preserved.
Binary/invalid UTF-8 text, NULs, malformed selections, non-finite anchor JSON
numbers, duplicate JSON keys, forged index text and contradictory anchors fail.

Exit code **0** means a complete context report; **2** means invalid input,
changed/missing evidence or an I/O failure. Processing errors are JSON on stderr
with no partial report on stdout. Command syntax errors use argparse's standard
stderr help and also exit 2.

All explicitly selected paths must remain within the current workspace.
Static symlinks, parent traversal, hidden source names and non-document suffixes
are rejected. Keep files static: the double read catches ordinary concurrent
edits but is not an atomic filesystem snapshot or a sandbox against concurrent
path replacement. Nothing executes document content, reads environment values,
accesses a wallet or secret, makes network requests, or sends transactions.

## Checks actually run

```sh
python3 -B line-3/tools/citation-context/test_context.py -v
```

All 17 behavioral tests passed. They cover exact context and selection markers,
edge clipping, zero margins, CRLF/Unicode/blank-line fidelity, changed-source
refusal, forged anchors, duplicate excerpt locations, absent/forged snapshots,
snapshot independence from live files, heading/fence handling, range and output
bounds, invalid Unicode paths, malformed and oversized-number JSON, source
changes during reading, missing files, symlinks, workspace escape rejection,
CLI modes and error output, preserved input bytes and the real historical ZTO
demo. Temporary test files stay under `test/scratch/`.
