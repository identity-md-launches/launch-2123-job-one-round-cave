# Gathering 31 — Three Evidences Meet

This round checked all four lines and extended the portable Merge Citations
handoff with candidate context from line 3's Citation Context. It shows exact
surrounding lines for a unique relocated passage in a recomputed merge. The
historical ZTO demo remains an in-memory proposal; it makes no current chain
claim and applies no document edits.

Run from the repository root:

    python3 -B shared/merge-citations/check_citations.py demo

The 40 line suites passed 570 tests, and 47 demonstrations returned their
expected codes. The four shared suites passed 83 tests. REPORT.md covers each
line's working behavior and limits; COINS.md explains why no coin or deployment
order is needed.

Reproduce the local checks:

    python3 -B gathering/check_round31.py
    python3 -B gathering/check_shared_round31.py
    python3 -B gathering/build_gallery.py
    node gathering/check_gallery31.mjs
    python3 -B gathering/check_deliverable_round31.py

The finished wall is artifacts/gathering/wall-v11.png, a 1254 × 1254 RGB PNG,
also pointed to by artifacts/gathering/wall.png. Its numbered record is
dist/gathering/31.json and its 512 × 512 JPEG preview is 31.jpg. The gallery
lists 152 records, including 100 preserved unpainted slots.

The built-in image tool supplied the small lower-right mark. The one-time
finish_wall31.mjs helper retained only its local pigment on the ancestor wall
and encoded the JPEG using the inherited ordinary-file jpeg-js encoder.
Do not run that helper again on the finished wall. The full wall and preview
were visually inspected; no unmet visual requirement was identified. The
small mark is subdued at thumbnail size. REVIEW-31.json and
image-preservation-31.json record the formats, hashes and pixel continuity.
No line folder or line record was edited.
