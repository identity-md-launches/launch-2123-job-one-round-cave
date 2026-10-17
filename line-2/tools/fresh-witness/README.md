# Fresh Witness

Verify an Ethereum account/storage proof against a caller-authenticated block hash,
then accept it only when its authenticated header timestamp is within an explicit
age window. This helps a worker refuse old evidence even when its proof is valid.
Python 3.9+ and the standard library; no installation or network required.

From the repository root:

```sh
python3 -B line-2/tools/fresh-witness/fresh_witness.py demo
```

## What happened when tried

The offline demo verified the inherited real ZTO account and slots 0 and 1 at
mainnet block 26,212,390. With a **simulated** reference time of header timestamp
plus 60 seconds and a 60-second inclusive limit, it returned `verified: true`,
`accepted: true`, `ageSeconds: 60`. `demo --reject` advances the simulated time
one more second: the same valid proof returns `accepted: false`, `stale-header`,
and exit 3. Neither demo claims the historical evidence is fresh today.

All 12 tests passed: real ZTO evidence, inclusive and zero-width boundaries,
stale and future headers, timestamp tampering, wrong hash, missing slots,
corrupt proof even when stale, metadata isolation, time input bounds, CLI demo
statuses, and input immutability. Run:

```sh
python3 -B -m unittest discover -s line-2/tools/fresh-witness -p 'test_*.py' -v
```

## Your own evidence

```sh
python3 -B line-2/tools/fresh-witness/fresh_witness.py check \
  path/to/header.json path/to/witness.json \
  --block-hash YOUR_INDEPENDENTLY_AUTHENTICATED_BLOCK_HASH \
  --address YOUR_EXPECTED_ACCOUNT_ADDRESS \
  --slot 0x0 --at YOUR_TRUSTED_UNIX_SECONDS --max-age 300
```

Replace the uppercase arguments with real trusted inputs. Repeat `--slot` for
exactly the requested slots, or omit it for an account-only proof. Header files
use Header Anchor's strict header-only RPC schema; witnesses use
`state-witness/1`. All input files must resolve inside the current working
directory; symlink escapes fail. Header input is at most 64 KiB, witness input
at most 1 MB, and proofs request at most 64 slots. Keep the sibling
`header-anchor/` and `state-witness/` folders alongside this tool.

`--at` and `--max-age` are canonical unsigned decimal uint64 seconds. No clock is
read implicitly. Acceptance requires `0 <= at - header.timestamp <= max_age`.
Future timestamps always reject. Invalid proofs never produce a successful age
report, even if they would also be stale. Witness block labels cannot supply the
reference timestamp. The JSON output includes the verified header and proven
state so the result remains bound to the exact account, slots and block.

Exit 0 means verified and within the window; 3 means verified but stale or
future-dated; 1 means malformed input or verification failure (error JSON on
stderr, no success output); 2 means CLI syntax error. The imported verifier
supplies strict JSON, Keccak, RLP and MPT checks. No cryptography was reimplemented.

## Trust and limits

Authenticate **both the block hash and reference time** independently. The demo
hash is an inherited historical RPC observation, not a consensus checkpoint.
This tests age of the committed **header timestamp**, not when the proof was
captured, whether a more recent block exists, or whether state has changed.
It does not establish consensus, canonicality, finality, execution validity,
storage semantics, a token balance, a price, or present freshness. A bad caller
clock or permissive age limit can accept evidence the caller should reject.
Verification is a point-in-time check, not a lasting authorization.

The tool reads only explicit bounded workspace files and sibling code, and prints
JSON. It does not discover configuration, read environment variables, access keys
or wallets, sign, send transactions, pay, post or deploy.
