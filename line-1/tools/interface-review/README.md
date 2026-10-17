# Interface Review

Find callable interface differences between a recomputed Python merge candidate
and each contributor's branch. A clean text merge can produce a function
signature neither contributor reviewed. This tool names that function and shows
the parameters, kinds, required/default status, annotations, decorators and async
status in base, ours, theirs and candidate. It never executes candidate code.
Python 3.10+ and standard library only; no installation or network needed.

One command from the workspace root shows it working, including real filesystem
checks and expected rejection cases:

```sh
python3 -B line-1/tools/interface-review/test_interfaces.py
```

Observed: **21 tests passed**. The illustrative demo renames one parameter in
ours and adds a keyword-only option in theirs. The text merges cleanly, but its
combined signature differs from both branches:

```sh
python3 -B line-1/tools/interface-review/interfaces.py --demo
```

This intentionally exits **1**, with `text_merge_clean: true`,
`review_required: true` and `differs_from: ["ours", "theirs"]` for `merge`.
It does not claim that the changed signature is broken or compatible.

For your own stable directories, run from a workspace containing all inputs:

```sh
python3 -B line-1/tools/interface-review/interfaces.py BASE_DIR OURS_DIR THEIRS_DIR
```

Replace the three uppercase paths with your actual directories. The tool reads
only those trees and the explicitly named sibling tools. Keep `tree-review`,
`merge-review` and `threeway` beside this folder. No files are written. If saving
stdout, choose a path outside all input trees so shell redirection cannot alter
an input before checking starts.

The JSON report binds input manifests and candidate hashes to exact UTF-8 bytes.
For `.py` and `.pyi` files it compares direct module functions and class methods,
including nested classes. Local functions are ignored. Expressions in defaults,
annotations and decorators are represented by SHA-256 of normalized AST syntax;
their source strings and values are not printed. Comments, source line movement
and body-only edits do not change signatures. Line numbers locate each version
but are not compared as interface content.

Each changed symbol lists `differs_from` branches, all four signature versions,
and `kind` (`added`, `removed`, `changed`, relative to base). Whole-file deletion
is inspected too. A change agreed by both branches is not flagged solely for
differing from base. New functions present in only one branch are flagged for
the other contributor to review. Conditional/duplicate declarations (including
overloads and property getter/setter pairs) and invalid Python produce an
`incomplete` file, never a claim of no differences. Conflicts in **any** format
block the report; other clean non-Python files are explicitly `skipped`.

Exit **0**: no differences in the selected interfaces relative to either branch,
no incomplete inventories or merge conflicts. Exit **1**: review required for
differences, incomplete inventories or conflicts. Exit **2**: invalid arguments,
unsupported paths/encoding/size or read failure; no partial JSON is printed.
No exit code means approval or establishes runtime correctness.

A second reproducible command operates on copies of all six real inherited
Threeway files under disposable `test/scratch/` directories:

```sh
python3 -B line-1/tools/interface-review/trial.py
```

Observed: the two independent signature edits merged cleanly, and `edits` and
`section` were each flagged relative to the other contributor's branch. Original
and trial input bytes were unchanged by inspection. This trial returns 0 after
asserting those expected results; the copied candidate is never executed.
`../../REAL-TRIAL-30.json` records the hashes and observations.

## Limits

This is a review aid, not a compatibility checker. It ignores class bases,
inheritance, dynamic decorators, assignments, aliases, exports, attributes,
call sites, imports and bodies. Identical signatures can behave differently;
different syntax can mean the same thing. A changed method receiver name is
reported conservatively. AST syntax and compilation follow the current Python
interpreter. Compilation checks syntax/scope but never runs code or resolves
imports. Conditional definitions and duplicates are deliberately incomplete
even where a person can resolve them. Hashes identify bytes, not authors.

Inherited bounds: stable UTF-8 without NUL, 128 files and 256 directories per
tree, 16 directory levels, 1 MiB/4,000 lines per file, 8 MiB combined inputs.
No binary merge, rename inference, permissions or atomic filesystem snapshot.
Symlinks and paths outside the current workspace are rejected; concurrent path
replacement is outside the threat model. No coin, wallet or payment is needed.
