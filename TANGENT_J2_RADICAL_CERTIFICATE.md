# Tangent-orbit `j2` radical certificate

**Status:** exact computer-assisted theorem candidate  
**Aggregate audit:** `receipts/hsop-j2-tangent-all-strata.json`  
**Scope:** tangent residual orbit only

## Statement

Let `I_tangent` be the characteristic-zero clean normal-layer ideal after the
nonzero residual quadratic is placed in the tangent orbit. Then

\[
j_2\in\sqrt{I_{\mathrm{tangent}}}.
\]

Equivalently, an algebraic-closure point of the tangent normal-layer system
cannot have `j2 != 0`.

This is not the secant statement and is not the full binary-decimic
HSOP/nullcone containment.

## Exhaustive first-jet cover

The exact torus and unipotent identities are frozen in
`RESIDUAL_ORBIT_TORUS_REDUCTION.md` and
`receipts/residual-orbit-torus.json`.  Under `j2 != 0`, at least one of
`f5,...,f10` is nonzero.  If `r` is the largest nonzero index, then

```text
5 <= r <= 10,
f_(r+1) = ... = f10 = 0,
f_r != 0,
f_(r-1) = 0.
```

The last equality is obtained from the triangular tangent unipotent action.
The residual-preserving torus has nonzero weight `14-3r` on `f_r`, so for
`r=6,...,10` the coefficient can be normalized to `f_r=1` over the algebraic
closure.  For `r=5`, the rational gauge `j2=-5` gives `f5^2=1`, and the
remaining sign action gives `f5=1`.

These six strata are disjoint and exhaustive on `j2 != 0`.

## The `r=5` compatibility proof

On the rational slice

```text
f4=0, f5=1, f6=...=f10=0,
```

ten selected equations involve only `g0,...,g9`.  Three further equations,
with source indices `33,37,38`, are affine-linear in `f2,f3`.  If their
augmented coefficient matrix is `M`, the producer verifies the cofactor
identity

\[
\det M\in(E_{33},E_{37},E_{38})
\]

and the exact factorization

\[
\det M=-55296\,g_0^2Q(g).
\]

The two exhaustive branches `g0 != 0` and `g0 = 0` are exact unit ideals over
`Q`.  Singular reports the reduced basis `[1]` in both branches.  Localization
and the closed fibre glue: the open calculation puts a power of `g0` in the
slice ideal, while the closed-fibre calculation makes `g0` invertible modulo
that ideal.  Hence the slice ideal itself is the unit ideal.

The producer and receipt are:

```text
scripts/certify_j2_tangent_r5_compatibility.py
receipts/hsop-j2-tangent-r5-compatibility-exact.json
```

## The `r=6,7,8,9` coefficient slices

For each of these four strata, the 55 reconstructed normal equations together
with the exact `j2` localizer form a unit ideal over `Q` after `f_r=1` and
`f_(r-1)=0`.  Each calculation uses deterministic exact Singular `slimgb`,
reduces `1` to zero, and prints a one-element reduced basis whose element is
`1`.

```text
receipts/hsop-j2-tangent-r6-coefficient-slice-exact.json
receipts/hsop-j2-tangent-r7-coefficient-slice-exact.json
receipts/hsop-j2-tangent-r8-coefficient-slice-exact.json
receipts/hsop-j2-tangent-r9-coefficient-slice-exact.json
```

## The `r=10` convolution proof

After `f10=1` and `f9=0`, equations `36,45,...,54` involve only
`f5,...,f8,g0,...,g9`.  Equations `37,...,44` are linear in `f3,f4` and the
producer verifies that they are the coefficient equations of

\[
C(t)+(f_3+f_4t)A(t)=0,
\]

where `deg(A) <= 6` and `deg(C) <= 7`.  Existence of `f3,f4` therefore forces
the appropriate pseudo-remainder and high-coefficient equations.  The leading
coefficients of `A` give the exhaustive cover

```text
g0 != 0,
g0 = 0 and g1 != 0,
g0 = g1 = 0 and g2 != 0,
g0 = g1 = g2 = 0 and g3 != 0,
g0 = g1 = g2 = g3 = 0 (hence A=0).
```

On the first four branches the producer localizes at the displayed leading
coefficient, adds the high coefficients of `C` required for a quotient of
degree at most one, and adds all coefficients of the pseudo-remainder of `C`
by `A`.  On the terminal branch it adds all eight coefficients of `C`.

All five necessary-condition ideals are exact characteristic-zero unit ideals.
Four receipts use Singular `slimgb`; the degree-five receipt uses Singular
`modStd`.  Each prints the reduced basis element `1`:

```text
receipts/hsop-j2-tangent-r10-degree_6-slimgb-exact.json
receipts/hsop-j2-tangent-r10-degree_5-modstd-exact.json
receipts/hsop-j2-tangent-r10-degree_4-slimgb-exact.json
receipts/hsop-j2-tangent-r10-degree_3-slimgb-exact.json
receipts/hsop-j2-tangent-r10-A_zero-slimgb-exact.json
```

The construction is in
`scripts/certify_j2_tangent_r10_degree_branches.py`; the independent
per-branch exact runner is
`scripts/certify_j2_tangent_r10_degree_branch.py`.

## Conclusion and assurance boundary

Every point with `j2 != 0` belongs to one of the six first-jet strata, and
every stratum is empty.  Hilbert's Nullstellensatz therefore gives the stated
radical containment over characteristic zero.

The result is an exact, replayable, computer-assisted theorem candidate.  It
has not received unaffiliated reconstruction, formal proof-assistant checking,
specialist peer review, or journal peer review.  The secant residual orbit,
the remaining seven HSOP invariants, full nullcone containment, the full
double-conic packet, and HC4 remain open.
