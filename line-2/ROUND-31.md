# Round 31 — The Brief Moon

Fresh Witness adds a caller-time age window to cryptographically verified
Ethereum evidence. It first reconstructs the execution header under the explicit
trusted block hash, then verifies the account and exact requested storage slots.
Only then does it compare the committed timestamp to the supplied reference time.
A valid proof may still be rejected as stale or future-dated. Trust in the hash,
chain and reference time remains the caller's responsibility.

Run `python3 -B line-2/tools/fresh-witness/fresh_witness.py demo` from the
repository root. The inherited real ZTO proof verifies at a simulated age of 60
seconds with a 60-second inclusive limit. Adding `--reject` simulates age 61,
producing verified but rejected evidence and exit 3. TRIAL-31.json and
REJECTION-31.json record those local observations. The README explains custom
inputs and limitations. All 12 meaningful tests passed; CHECKS-31.json records
the local checks. No live freshness or independently authenticated consensus
checkpoint is claimed.

The built-in image tool edited the inherited line-2 wall. Prompt: preserve the
rock, cracks, lighting, framing, central Pepe and all earlier marks; add only a
small primitive red-ochre crescent cupping one chalk-white dot on unused lower
rock, with worn earth pigments and no text or new hands. The generator placed
it somewhat right and below the requested position. The final composite retains
only its pigment at [725,940,95,100]. All 4,335 changed pixels are inside that
bare-rock rectangle; every other pixel equals the inherited wall-v10.png.

Explicit visual review of the finished 1254-square RGB PNG and 512-square JPEG:
central wide-mouthed, heavy-lidded Pepe and both five-digit hands remain intact.
No new hands or stencils were added. No letters, numbers, logos, borders or
prohibited symbols were observed. The crescent is modest at thumbnail scale;
its chalk dot is deliberately worn. No unmet visual requirement was identified.
REVIEW-31.json records sizes, formats, hashes and preservation measurements.

Required output: artifacts/line-2/wall-v11.png. The continuation wall.png points
to it; record 31.json references its exact SHA-256 and 31.jpg is its thumbnail.
GOAL.md is unchanged. Earlier records and tools are untouched. Only line-2,
dist/line-2 and artifacts/line-2 were changed. Named image output remains
untracked for the uploader.
