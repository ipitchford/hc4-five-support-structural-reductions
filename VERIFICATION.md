# Verification guide

## Tier 1: release integrity

Run:

```sh
python3 verify_package.py
```

This validates the claim ledger, terminal C16 receipt, reconstruction counts,
frozen selection, zero-mismatch conditions, candidate support, key SHA-256
bindings, PDF signature, and `MANIFEST.sha256` when present.

## Tier 2: semantic C16 replay

With SageMath 10.9 and SymPy available:

```sh
python3 verify_package.py --semantic-c16
```

The verifier invokes
`scripts/audit_p173_fourth_colon_c16_rational_syzygies.py` in a temporary
directory. It rebuilds each source combination from the polynomial generators
over `QQ`, bypassing the exported sparse row encoding, and requires sixteen
zero residual polynomials.

Expected terminal status:

```text
PASS_RELEASE_VERIFICATION
PASS_INDEPENDENT_DIRECT_POLYNOMIAL_C16_RATIONAL_SYZYGIES
```

The historical receipt retains the word `INDEPENDENT` in its machine status.
For assurance purposes this means implementation-diverse internal replay, not
unaffiliated reproduction.

## Tier 3: full four-level section solve

The release includes the frozen integer matrix, C16 right-hand sides, LinBox
driver source and recorded four digit vectors. Recompilation command:

```sh
clang++ -std=c++17 -O3 scripts/linbox_p173_canonical_c16_section_driver.cpp \
  -o artifacts/bin/linbox_p173_canonical_c16_section_driver \
  $(pkg-config --cflags --libs linbox)
```

The exact invocations and hashes are preserved in the terminal receipt and the
per-level stdout/stderr files. The four recorded solve times sum to 439.334 s
on the preparation machine. A verifier need not trust those timings: the
theorem claim rests on the exact rational and direct-polynomial replays.

## Claim boundary

Passing any replay tier establishes only the claims mapped in `CLAIMS.json`.
In particular, a source syzygy is not a solution of the inhomogeneous fourth
target, and none of these commands proves HC4 or JC2.

