# Clean double-conic normal layers with exactly five support points

**Date:** 30 August 2026  
**Status:** exact computer-assisted theorem candidate; independently
reconstructed equations, replayable characteristic-zero certificates, no
formal proof-assistant or specialist peer review

## 1. Statement

Let (K) be a characteristic-zero field, put

\[
q=xz-y^2,
\]

and let (h_5\in K[x,y,z]) be a ternary quintic.  Restrict (h_5) to the
Veronese conic by

\[
(x,y,z)=(s^2,st,t^2),
\]

obtaining a binary decic (f_{10}).

> **Five-support theorem candidate.** If the nonzero binary decic (f_{10})
> has exactly five distinct projective roots, then there is no nonzero linear
> form (ell) such that
> \[
> \det\operatorname{Hess}(h_5)=q^4\ell.
> \]

Equivalently, the clean residual-line locus of the double-conic normal-layer
system is empty over the exactly-five-support stratum.

## 2. Why seven normal forms are exhaustive

The multiplicities of five distinct roots are a partition of ten into five
positive parts.  There are exactly seven:

```text
(6,1,1,1,1), (5,2,1,1,1), (4,3,1,1,1),
(4,2,2,1,1), (3,3,2,1,1), (3,2,2,2,1),
(2,2,2,2,2).
```

After labelling three roots, a projective change of binary variables sends
them to `0`, `infinity`, and `1`.  The remaining roots have finite coordinates
`lambda` and `mu`, and distinctness is exactly

```text
Delta=lambda*mu*(lambda-1)*(mu-1)*(lambda-mu) != 0.
```

The induced `Sym^2` action on `(x,y,z)` preserves the conic up to a nonzero
scalar, so existence of the Hessian identity is invariant under this
normalization.  A nonzero scalar multiplying the binary decic is harmless:
dividing the entire quintic by that scalar divides its arbitrary cubic
correction by the same scalar and rescales the Hessian determinant by the
cube.  Thus every case is represented by

\[
s^a t^b(s-t)^c(s-\lambda t)^d(s-\mu t)^e.
\]

An arbitrary ternary quintic with this restriction is the canonical harmonic
lift plus (qG_3) for an arbitrary ternary cubic (G_3); the (q^2)-linear
harmonic summand is included because (G_3) itself is unrestricted.

## 3. Exact equation and residual-line presentation

For each partition, the producer reconstructs

\[
D=\det\operatorname{Hess}(h_5)
\]

over the exact rationals.  The prospective residual-line coordinates

\[
A=[x^5z^4]D,\qquad B=[x^4yz^4]D,\qquad C=[x^4z^5]D
\]

are extracted, and the 52 nonzero coefficients of

\[
D-q^4(Ax+By+Cz)
\]

generate the normal ideal (I).  The clean target is a common zero of those
52 equations with ((A,B,C)\ne(0,0,0)).

Each row certificate proves

\[
(A,B,C)\subseteq\sqrt{I\,K[\lambda,\mu,g_0,\ldots,g_9,1/\Delta]}.
\]

Some rows prove a stronger global-affine statement.  For every factor used
as an internal pivot, its zero fibre is treated as a separate branch; no
unrecorded exceptional component is saturated away.

## 4. Seven exact rows

| partition | certificate mechanism | exterior divisor |
|---|---|---|
| `(6,1,1,1,1)` | endpoint radical chain and fixed-content identity | none |
| `(5,2,1,1,1)` | endpoint radical chain and fixed-content identity | none |
| `(4,3,1,1,1)` | two head branches and endpoint chain | collision divisor |
| `(4,2,2,1,1)` | head/tail cover plus explicit interior-divisor contradiction | collision divisor |
| `(3,3,2,1,1)` | two endpoint staircases and a fixed-content (H^5) identity | collision divisor |
| `(3,2,2,2,1)` | head staircase and a proved (W=0/W\ne0) tail cover | collision divisor |
| `(2,2,2,2,2)` | four endpoint cells and proved (W,R) nested covers | collision divisor |

The accompanying files give the identities, localizations, generated-source
hashes, and exact standard-basis remainders.  Every row receipt has status
`PASS` and covers all three residual-line directions.

This proves the statement because the seven multiplicity partitions exhaust
the normalized exactly-five-support locus.

## 5. Collision boundary and source-dependent corollary

Every component of `Delta=0`, including projective `lambda=infinity` and
`mu=infinity`, merges at least two of the five roots and therefore specializes
to a nonzero binary decic supported on at most four projective points.  This is
an elementary geometric statement recorded in `FIVE_SUPPORT_BOUNDARY_LEMMA.md`.

At the pinned source commit
`3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9`, the author-associated theorems
`HC4NHM15` and `HC4NHM18` state that every such support-at-most-four clean
double-conic restriction is empty.  Hence:

> **Pinned-source corollary.** Combining that source result with the new
> exactly-five-support theorem excludes every clean double-conic target whose
> nonzero binary-decic restriction is supported on at most five points.

The support-at-most-four half has not been independently reconstructed in
this campaign and remains labelled as a pinned-source dependency.

## 6. Assurance and remaining frontier

The four covariant normal layers were independently reconstructed from a
harmonic-projection recurrence and an automatically generated transvectant
basis, with three exact training samples and two disjoint symbolic holdouts.
The row proofs then work directly with the Hessian determinant equations, so
the exactly-five-support theorem is not merely a replay of the source
coefficient table.

The result has exact symbolic and characteristic-zero computer-algebra
evidence.  It has not received unaffiliated reconstruction, formal
proof-assistant verification, specialist peer review, journal review, or a
priority determination.

It does **not** prove the full double-conic packet or HC4.  Restrictions with
at least six distinct support points remain open.  The invariant-nullcone
HSOP calculation is a stretch route toward that larger stable locus, not a
premise of the theorem proved here.

## 7. Replay

Audit the frozen receipts, source pin, hashes, partition coverage, and claim
ledger:

```sh
/opt/homebrew/bin/python3 scripts/audit_five_support_theorem.py
```

Regenerate the independent normal-layer receipt, all seven row receipts, and
the Cassini second-derivation receipt before auditing:

```sh
/opt/homebrew/bin/python3 scripts/audit_five_support_theorem.py --full-replay
```
