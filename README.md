# Structural reductions toward HC4 in dimension four

This is an anonymous, unrefereed, computer-assisted candidate release. It
collects exact structural reductions for a quartic Hessian problem in dimension
four and closes with a prospectively selected 16-column source-kernel test.

The package proves four bounded results:

1. exclusion of the exactly-five-support binary-decimic stratum;
2. containment of all 31 generators of the multiplicity-six target ideal in
   the radical of the tangent normal-layer ideal;
3. three explicit rational localized-colon elements on the remaining secant
   chart; and
4. sixteen exact rational source-module syzygies in the frozen fourth Macaulay
   block.

It does **not** prove fourth-target membership, a full colon or saturation
identity, secant-orbit closure, the quartic Hessian conjecture in dimension
four, or the two-dimensional Jacobian conjecture.

## Verification

The fast, non-destructive release check requires Python 3.11 or later:

```sh
python3 verify_package.py
```

The theorem-critical direct-polynomial replay of the closing result additionally
requires SageMath 10.9 and SymPy:

```sh
python3 verify_package.py --semantic-c16
```

The semantic check reconstructs all sixteen source combinations without using
the sparse row encoding and requires every residual polynomial to be zero
over `QQ`. It normally takes seconds after Sage starts. Re-running the four
LinBox section solves is optional and is documented in `VERIFICATION.md`.

## Reading order

1. `paper.pdf` or `paper.md` — the mathematical statement and argument.
2. `CLAIMS.json` — claim-to-evidence map and explicit scope limits.
3. `ASSURANCE.md` — what was established internally and what remains external.
4. `VERIFICATION.md` — replay tiers and expected outcomes.
5. `receipts/hsop-j2-secant-r10-fourth-colon-c16-kernel-batch-terminal.json`
   — compact terminal receipt for the closing experiment.
6. `CAMPAIGN_README.md` and `RESEARCH_METRICS.md` — research history and
   calibrated resource measurements.

## Closing 16-column result

The frozen source matrix has 85,688 rows and 36,587 pivot columns. The sixteen
selected free columns lift through `173^4`; all 585,392 rational coordinates
reconstruct uniquely; the exact row replay has zero mismatches; and a separate
direct-polynomial implementation obtains sixteen zero residuals. The resulting
syzygy supports are 37 for the first column and 22 for each of the other
fifteen, including the distinguished free coefficient.

## Source and provenance

The normal-layer starting point is Roy van Rijn's public
`jacobian-research` repository at commit
`3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9`. The precise reconstruction
boundary is described in `SOURCE_BRIDGE.md`. The release's new scripts,
receipts, claim ledger, and manuscript are producer-coordinated work and are
not described as unaffiliated reproduction.

## Licence

Original prose and data are dedicated to the public domain under CC0-1.0.
Original code is offered under the MIT licence. Preserved upstream material,
if any, retains its existing terms and is not relicensed by this package.
