# Fourth-colon character-two kernel-batch scout design

**Designed:** 31 August 2026  
**State:** exact experiment design, not implementation freeze or result

## Purpose

The certified fixed-gauge target lift through `173^96` did not reconstruct to
an exact rational vector in the frozen hierarchy.  The next bounded question
is whether low-support kernel directions of the same character-two Macaulay
block lift at low height and can therefore change the gauge economically.

This is narrower than optimizing over all 2,239 free coordinates.  It first
constructs a canonical, support-ordered batch of 16 kernel directions and
tests them through `173^2`; only a favorable checkpoint licenses `173^4` and
exact rational reconstruction.

## Exact interface

Let the 85,688-row global source matrix be partitioned as

```text
[ B | C ]
```

using the already frozen 36,587 pivot indices and 2,239 free indices.  The
integer row normalization must be exactly the normalization used in
`A_Z_b_Z_fixed_gauge_p173.i64csr`; free-column coefficients are scaled by that
same row multiplier and must not cause a new row-content normalization.

1. Rebuild the global rational row stream and verify the frozen generator,
   target, descriptor, monomial, pivot, and free-index hashes.
2. Compute every free column's nonzero support count after the frozen row
   normalization.  Order by `(support_count, global_coordinate)`.
3. Select exactly the first 16 free columns.  Export their integer and
   characteristic-173 matrices `C16_Z` and `C16_mod173` and bind their hashes.
4. Compute a nullspace basis of `[B | C16]` over `GF(173)`.  The expected
   nullity is 16.  If the lower 16 by 16 block is nonsingular, right-normalize
   it to the identity, obtaining the canonical transfer
   `T = -B^(-1) C16`.
5. Replay all 85,688 equations `B*T + C16 = 0` independently, including zero
   rows and the frozen row normalization.

No target vector is used to choose the batch.  No support ordering or batch
size may change after the transfer is observed.

The `p2` gate is algebraically necessary.  Full column rank of `B` modulo 173
implies full column rank of `B` over `QQ`, but the rank of the *global* matrix
may rise in characteristic zero.  Hence some or all of the 2,239 modular free
directions could be characteristic-173 kernel accidents.  Failure of a
canonical direction to lift is a genuine obstruction to using that direction
as rational gauge freedom; it is not repaired by choosing more target digits.

## Two-digit falsifier

Lift all 16 canonical directions simultaneously through `173^2`, reusing one
factorization.  Stop the route if any of the following occurs:

- nullity is not 16 or the free block is singular;
- the modular source replay has a nonzero residual;
- any correction equation is insoluble;
- the two-digit support or memory gate is exceeded;
- an independent replay disagrees with any stored digit.

Record columnwise support, union support, digit support, and equal-height
rational-reconstruction census.  A pass is only a certified two-digit kernel
batch, not an exact rational syzygy or target identity.

## Promotion rule

Promote the unchanged 16 directions through exactly `173^4` only if all 16
pass the two-digit falsifier and the measured batch cost remains below four
single target-digit solves.  At `p4`, attempt equal-height rational
reconstruction columnwise and replay each candidate against the full integer
source matrix.  Exact passes become rational kernel syzygies available for a
separately preregistered target-gauge optimization.  Partial or failed
reconstruction does not license extra digits without a new measured threshold.

## Calibration and claim boundary

The earlier four-column residual batch required about 59--63 seconds per
shared correction solve, and the current fourth-target solve requires about
115 seconds per digit.  Therefore the first useful checkpoint should cost
minutes, not hours, once the full-column export and multi-right-hand-side
driver exist.  Construction and compilation costs must be reported separately
from solve time.

Even 16 exact rational kernel directions would prove only source syzygies in
the fourth character block.  They would not prove rational membership of
`M*h4`, a fourth colon identity, colon equality, saturation, secant closure,
nullcone containment, or HC4.

## Exact support-census result

The descriptor-level census subsequently passed in 10.88 seconds with the
frozen descriptor hash
`478302e341969ae2d8edec433bfd7fc12374598502b7f4e661884b31c4bd5f67`.
The 2,239 free columns have genuinely stratified source supports ranging from
13 to 248; 43 directions attain support 13.  The prospectively selected first
16 all belong to generator `g00` and have global coordinates

```text
46, 47, 57, 66, 68, 102, 155, 547,
763, 965, 966, 1261, 1269, 1499, 1699, 1711.
```

This passes the selection-premise test.  It says nothing yet about fill in
`T=-B^(-1)C16`, liftability through `173^2`, or rational height.

## Measured Fermi bracket for the next run

The exact source-system rebuild already costs 11.51 seconds and about 460 MB.
The selected `C16` contributes only 208 raw source terms to the existing
1,487,624-nonzero `B` matrix.  Existing fourth-target correction solves cost
about 115 seconds each, while multi-right-hand-side work shares the same
coefficient matrix and factorization.

Accordingly, budget the canonical modular transfer plus one `p2` correction
at 2--8 single-solve equivalents: approximately 4--16 minutes of solver wall,
plus implementation, compilation, and independent-audit time reported as
separate quantities.  Stop and recalibrate if the modular transfer alone
exceeds eight solve equivalents or 1.5 GB RSS.  This bracket is based on
observed matrix construction and solve receipts; it is not a prediction that
the mathematical route will succeed.

The normalization algorithm need not be invented.  The existing
`scripts/linbox_p181_canonical_residual_114_section_driver.cpp` already forms
an augmented nullspace for 114 right-hand sides, inverts the lower block,
normalizes it to the identity, writes the row-major transfer, and replays every
row.  Its canonical-section run completed in 218.78 seconds.  The `p173`,
16-column driver should be a format/constant port of that audited pattern with
a toy known-section oracle, not a separate solver design.
