# Editor-in-chief report

**Target:** commit `2779d701b2e115c141df4eab22b3843af19c593c`  
**Assurance class:** internal producer-coordinated role review  
**Decision:** revise before candidate publication

## Strengths

The manuscript leads with a precise negative claim boundary, separates four
bounded results from HC4 and JC2, gives a readable geometric narrative, and
preserves failed routes. The title uses “toward,” the abstract explicitly says
the conjectures remain open, and the closing experiment is presented as a
source-kernel theorem rather than target membership.

## Required repairs

1. Add a concise `STATUS.md` that states version, review level, and public-state
   fields without requiring readers to infer them from `CITATION.cff`.
2. Expand `CLAIMS.json` to cover the substantial intermediate assertions in
   Section 6 and the 96-digit/failure assertions in Section 7; otherwise the
   machine claim map is narrower than the paper.
3. Add a direct URL for the pinned upstream repository in the manuscript, not
   only its owner and commit.

## Recommendation

Publish as an unrefereed candidate after these repairs and confirmation. Do not
market the package as a proof of HC4, a proof of JC2, or independent review.

