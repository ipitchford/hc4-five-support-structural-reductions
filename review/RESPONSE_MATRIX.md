# Editorial response matrix

## Frozen target

Substantive review target: commit
`2779d701b2e115c141df4eab22b3843af19c593c`, identified in
`REVIEW_TARGET.sha256`.

| finding | response | scientific effect |
|---|---|---|
| Add plain-language release status | Added `STATUS.md` | none; distribution and assurance clarity |
| Claim map narrower than manuscript | Added C5–C7 for the third-block kernel, 96-digit fail-closed result, and open-conjecture boundary | machine map now matches manuscript |
| C2 cited a profile rather than containment receipt | Replaced it with `nullcone-tangent-all-31-generators.json` | correct evidence binding |
| Fast verifier omitted C1–C3 and intermediate statuses | Added exact status checks for eight aggregate receipts | stronger replay gate |
| Pinned upstream commit not machine-readable outside Git | Added `UPSTREAM_SOURCE.json` and verifier checks | stronger provenance binding |
| Upstream URL absent from manuscript | Added the repository URL | citation clarity |
| Characteristic-zero base change implicit | Added an explicit rational-identity/base-change sentence after Theorem A's certificate argument | logical clarification, no new claim |
| C16 selection could look post-selected | Retained the frozen design, complete support census, ordering rule, and terminal receipt | no change; adversarial evidence preserved |
| Machine status uses `INDEPENDENT` | Human-facing assurance consistently labels the audit implementation-diverse and producer-coordinated | no change to historical receipt |

## Confirmation evidence

- `python3 verify_package.py --semantic-c16`: pass.
- PDF raw-TeX preflight: pass, zero findings.
- All sixteen direct-polynomial residuals: zero.
- C16 selection and terminal receipt: unchanged.
- The fixed-gauge fourth target remains explicitly unresolved over the
  rationals.

Later DOI, repository-release, manifest and Evidence Press fields are a
distribution-layer delta and do not modify the reviewed scientific claims.

