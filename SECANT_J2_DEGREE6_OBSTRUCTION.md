# Secant `j2`: exact reduction to one degree-six chart

**Frozen:** 30 August 2026  
**Status:** sharp exact reduction; one characteristic-zero branch open  
**Claim ceiling:** this is not the full secant `j2` theorem and not HC4

## Statement of the reduction

On the nonzero secant residual-quadratic orbit, the attempted counterlocus

\[
V(I_{\mathrm{secant}})\cap D(j_2)
\]

is empty on every frozen first-jet stratum except possibly the following
single chart:

```text
r = 10, f9 != 0, f10 != 0, leading convolution degree = 6.
```

The chart is represented exactly by

```text
receipts/hsop-j2-secant-r10-f9-laurent-degree_6-minsubset-groebner-input.json
```

after generator minimization.  It has 19 variables, 19 equations, and maximum
total degree three.  Its equation-stream SHA-256 is
`69d755bd0c4846b15a49915e8e68dacf911b58ede4683a12e714ee46a7183079`.

## Exhaustive cover already closed

The first-nonzero-jet split gives strata `r=5,...,10`.  The five strata
`r=5,...,9` are exact characteristic-zero unit calculations:

| Stratum | Variables | Exact solver wall | Receipt |
|---|---:|---:|---|
| `r=5` | 17 | `1.165 s` | `hsop-j2-secant-r5-coefficient-slice-exact.json` |
| `r=6` | 17 | `0.163 s` | `hsop-j2-secant-r6-coefficient-slice-exact.json` |
| `r=7` | 18 | `0.157 s` | `hsop-j2-secant-r7-coefficient-slice-exact.json` |
| `r=8` | 19 | `10.113 s` | `hsop-j2-secant-r8-coefficient-slice-exact.json` |
| `r=9` | 20 | `0.588 s` | `hsop-j2-secant-r9-coefficient-slice-exact.json` |

For `r=10`, the convolution identity gives the branches of leading degree
six, five, four, three, and the terminal `A=0` case.  The `f9=0` degree-five
and degree-six branches are exact units; the unrestricted lower-degree and
terminal branches are exact units; and on `f9!=0`, degrees four and five are
exact deterministic homogenized characteristic-zero unit bases.  Their core
receipts include:

```text
receipts/hsop-j2-secant-r10-f10-f9zero-degree_5-homogenized-groebner-exact.json
receipts/hsop-j2-secant-r10-f10-f9zero-degree_6-homogenized-groebner-exact.json
receipts/hsop-j2-secant-r10-f9-laurent-degree_4-minsubset-classic-homogenized-groebner-exact.json
receipts/hsop-j2-secant-r10-f9-laurent-degree_5-homogenized-groebner-exact.json
receipts/hsop-j2-secant-r10-degree_3-tail-modstd-exact-x35.json
receipts/hsop-j2-secant-r10-A_zero-tail-modstd-exact.json
```

Thus only `f9!=0`, leading degree six remains.

## Evidence on the open chart

At characteristic 101, the unreduced 23-variable chart produced a unit basis
in `12.58 s` solver wall time.  This is a modular no-solution signal only:

```text
receipts/hsop-j2-secant-r10-f9-laurent-degree_6-msolve-p101.json
```

The 19-generator exact input then received two bounded characteristic-zero
attempts:

1. deterministic certified homogenized Gröbner computation, terminated after
   `3609 s`, with observed RSS at least `2,072,368 KiB` and no output receipt;
2. eager exact quotient-by-known-units reduction, terminated after `611 s`,
   with observed RSS at least `555,456 KiB` and no reduced input emitted.

The corresponding frozen receipts are

```text
receipts/hsop-j2-secant-r10-f9-laurent-degree_6-minsubset-classic-homogenized-groebner-timeout.json
receipts/hsop-j2-secant-r10-f9-laurent-degree_6-minsubset-unit-reduction-timeout.json
```

Neither timeout is evidence of a surviving characteristic-zero point.  The
modular unit is not evidence of a characteristic-zero certificate.

## Structural information retained

The exact profile

```text
receipts/hsop-j2-secant-r10-f9-laurent-degree_6-minsubset-structural-profile.json
```

shows no safe constant-linear elimination.  It does show that many equations
are linear with coefficient `5*f10*g0+2`, which is already a unit on this
branch through the retained inverse relation

\[
\operatorname{leadinv}(5f_{10}g_0+2)-1=0.
\]

The mathematical quotient reduction is therefore still valid.  Only the
eager SymPy expansion strategy is rejected.

That quotient reduction has now been proved structurally without eager
expansion. Homogenizing the 17 retained normal cubics introduces `f9` and
turns the chart into the exact saturation question

\[
I:M^\infty=(1),\qquad
M=f_9f_{10}(2f_9^2+5f_{10}g_0).
\]

On `D(M)`, the four equations of normal indices `10,9,8,7` eliminate
`g4,g5,g7,g8` successively with coefficients `-16u,-16u,16u,16u`, where
`u=2*f9^2+5*f10*g0`. This leaves 13 equations in 14 homogeneous variables.
The replay and precise claim boundary are in
`SECANT_J2_HOMOGENEOUS_SATURATION_REDUCTION.md` and
`receipts/hsop-j2-secant-r10-degree6-homogeneous-reduction.json`.

## Next decision

Do not repeat the one-hour Gröbner run.  The preferred route is now one of:

1. close the resulting 13-in-14 projective system by graded Macaulay
   membership, a multihomogeneous resultant, or a Chow-form certificate;
2. bypass it by proving the lower-order Brouwer--Popoviciu/Weyman covariant
   nullcone conditions; or
3. show directly that the clean normal-layer ideal contains the low-degree
   defining ideal of the multiplicity-six coincident-root locus.

Only an exact characteristic-zero saturation certificate or an exact survivor
closes the secant statement.
