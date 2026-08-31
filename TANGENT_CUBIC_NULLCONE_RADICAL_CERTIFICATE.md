# Tangent-orbit quadratic and cubic nullcone certificate

**Status:** exact computer-assisted theorem candidate  
**Scope:** tangent residual orbit only  
**Aggregate receipts:**
`receipts/hsop-j2-tangent-all-strata.json`,
`receipts/nullcone-v6-tangent-stabilizer-span.json`, and
`receipts/nullcone-v2-tangent-stabilizer-span.json`

## Statement

Let (I_{\mathrm{tangent}}) be the characteristic-zero clean normal-layer
ideal after the nonzero residual quadratic is placed in the tangent orbit.
Let (J_{\le3}) be the part in degrees two and three of the defining ideal of
the binary-decimic multiplicity-six coincident-root locus
(X_{(6,1,1,1,1)}). Then

\[
J_{\le3}\subseteq\sqrt{I_{\mathrm{tangent}}}.
\]

Equivalently, the quadratic family (V_0[-2]) and both cubic families
((V_2\oplus V_6)[-3]) vanish on every algebraic-closure point of the tangent
normal-layer system.

This is not the quartic containment, the secant statement, full binary-
decimic nullcone containment, or HC4.

## Exact target identification

Macaulay2's `CoincidentRootLoci` package constructs the multiplicity-six
target ideal with minimal-generator profile

```text
degree 2: V0
degree 3: V2 + V6
degree 4: V0 + 2 V4 + V8.
```

The exact cubic dictionary identifies canonical highest-weight lifts for the
two cubic summands and matches them to classical transvectant channels. The
replay is
`scripts/identify_decimic_nullcone_cubic_covariants.py`; the passing receipt
is
`receipts/decimic-nullcone-cubic-covariant-identification-corrected-lifts-exact.json`.

The quadratic (V_0) statement is the previously certified tangent `j2`
radical theorem in `TANGENT_J2_RADICAL_CERTIFICATE.md`.

## The (V_6) highest coordinate

The primitive (V_6) highest coordinate has tangent-torus weight (6), so
its nonzero locus can be normalized to (V_6=1). Its support forces a largest
nonzero coefficient (f_r) with (5\le r\le10). No tangent unipotent
normalization is used.

The five cells (r=5,\ldots,9) are exact characteristic-zero unit ideals. On
(r=10), equations 37 through 44 have the verified form

\[
C(t)+(f_3+f_4t)A(t)=0,
\qquad \deg A\le6,\quad\deg C\le7.
\]

The exhaustive cover (A=0) or (deg A=d), (0\le d\le6), consists of
eight exact unit ideals. Direct use of the eight convolution equations closes
degrees three through five; retaining the fibre variables closes degree six.
The aggregate replay
`scripts/audit_nullcone_v6_tangent_highest.py` verifies the top-index cover,
the (A)-degree cover, equation hashes, exact unit bases, torus weight, and
absence of unipotent slicing.

Hence the (V_6) highest coordinate lies in
(sqrt{I_{\mathrm{tangent}}}).

## Stabilizer propagation for (V_6)

The tangent stabilizer contains

\[
(s,t)\longmapsto(s,t+us),
\]

induced on ternary coordinates by

\[
(x,y,z)\longmapsto(x,y+ux,z+2uy+u^2x).
\]

The latter map has determinant one and fixes (q=xz-y^2) and (q^4x).
After transforming a generic quintic, its difference from the canonical lift
of the transformed binary restriction is exactly (q) times a cubic, so the
free cubic correction absorbs the coordinate change. Generic Hessian-matrix
covariance verifies preservation of the normal-layer solution set.

If (P_6) is the certified highest coordinate, then

\[
P_6(f^u)=\sum_{j=0}^6u^jC_j(f).
\]

The seven (C_j) have exact rational rank seven, hence span the identified
(V_6) summand. Since (P_6) vanishes at every transformed solution, all
seven coefficients vanish. This is frozen by
`scripts/certify_nullcone_v6_tangent_stabilizer_span.py` and
`receipts/nullcone-v6-tangent-stabilizer-span.json`.

## The (V_2) family

The (V_2) highest coordinate has tangent-torus weight zero. Its nonzero
locus is therefore retained by an explicit inverse rather than normalized.
Its support gives the same exhaustive top-index cover (r=5,\ldots,10).

The cells (r=5,\ldots,9) are exact unit ideals. The (r=10) chart uses the
same eight convolution-degree branches. Seven branches close directly. In
the remaining (deg A=6) branch, (f_{10}\ne0) and has torus weight (-16),
while (V_2) has weight zero; the torus therefore normalizes (f_{10}=1)
without changing the target open. The normalized branch is an exact unit
ideal over (mathbb Q).

The aggregate audit
`scripts/audit_nullcone_v2_tangent_highest.py` replays all cells and the mixed
normalization. Under the already verified tangent stabilizer,

\[
P_2(f^u)=C_0(f)+uC_1(f)+u^2C_2(f)
\]

has exact coefficient rank three. Thus the full (V_2) family vanishes. The
span receipt is `receipts/nullcone-v2-tangent-stabilizer-span.json`.

## Replay

From the campaign root:

```bash
python3 scripts/audit_nullcone_v6_tangent_highest.py
python3 scripts/certify_nullcone_v6_tangent_stabilizer_span.py
python3 scripts/audit_nullcone_v2_tangent_highest.py
python3 scripts/certify_nullcone_v2_tangent_stabilizer_span.py
```

Each aggregate audit reconstructs the symbolic equation streams and checks
their hashes against clean characteristic-zero one-element unit bases.

## Assurance boundary and residue

The result is exact and replayable but computer-assisted. It has not received
unaffiliated reconstruction, formal proof-assistant checking, specialist peer
review, or journal peer review.

The tangent quartic module

\[
V_0\oplus2V_4\oplus V_8
\]

remains open, as do the secant cubic and quartic modules, polynomial-level
lifting from the normal layer, the full double-conic packet, and HC4.
