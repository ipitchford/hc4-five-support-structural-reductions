# Research metrics

**Frozen:** 30 August 2026  
**Policy:** report measured stages separately; do not infer theorem-completion
time from a single Gröbner run.

## Current replay telemetry

| Stage | Measured result | Interpretation |
|---|---:|---|
| full consolidated replay and audit | `385.50 s` | all producers rerun serially, then source/hash/coverage audit |
| independent normal-layer reconstruction | `84.03 s` | four layers, three training samples, two held-out symbolic samples |
| seven row receipts, serial-equivalent sum | `297.13 s` | sum of producer-reported replay walls; not historical elapsed research time |
| fastest row | `4.30 s` | `(6,1,1,1,1)` |
| slowest row | `212.82 s` | `(2,2,2,2,2)` |
| Cassini second derivation | `0.13 s` | exact all-index symbolic audit |
| final-row equation construction | `21.12 s` | common 52-equation build |
| final-row exact certificate | `191.70 s` | all cells and line directions |
| final compact `R!=0` line bases | `0.29–15.47 s` | exact modular characteristic-zero reconstruction |

## Route comparison in the final row

The unsplit central `W!=0` line-`x` calculation reached its `600 s` timeout,
used about `591.16` child CPU seconds and approximately `2.02 GB` native RSS,
and produced no basis result.  It was route evidence only.

After the exact `R=0/R!=0` split, the full replay's `R=0` line tests took
about `13.95–15.72 s`; the four-equation `R!=0` tests took `0.29–15.47 s`.
This is the relevant calibrated comparison: a structural factor split changed
the same assurance target from a timeout to a compact exact certificate.

## Forecast use

For subsequent research, estimates should report at least:

1. time to construct or reduce the equations;
2. time to the next decisive falsifier or exact certificate;
3. CPU, peak RSS, variable count, equation count, maximum degree, and branch
   count where available;
4. the closest comparable completed and timed-out routes;
5. an update trigger that changes the route or forecast.

Unknown proof difficulty remains unknown.  These metrics constrain route cost;
they do not turn compute time into a probability of mathematical closure.

## Fixed-181 Dixon Phase-I terminal

The registered eight-digit pilot never reached digit one.  Its successive
pre-execution and Phase-I terminals are measured separately:

| Version | Preprocessor | Factorizer | Peak factorizer RSS | Swaps | Terminal |
|---|---:|---:|---:|---:|---|
| v1 | not run | not run | not observed | not observed | immutable manifest/interface mismatch |
| v2 | `22.12 s` | `577.31 s`, exit 124 | `3,236,954,112 B` | `0` | wall stop; no factor artifact |
| v3 packed encoder | `27.86 s` | `571.33 s`, exit 124 | `3,962,667,008 B` | `0` | wall and RSS stop before `ELIMINATION_COMPLETE` |

The v2/v3 factorizer operates on an `85,651 x 35,881` coefficient restriction
with `1,354,540` nonzeros.  In v3, `INPUT_LOADED` occurred after `1.7523 s` at
`212,156,416 B` native RSS; no later milestone was reached.  This rejects the
pre-registered hypothesis that canonical payload packing was the controlling
bottleneck.  The final exact terminal is
`STOP_PHASE1_WALL_AND_RSS_V3_IMPLEMENTATION_FAMILY_TERMINAL`.

Fermi implication: another Python dictionary/incidence trace with the same
35,881 prescribed pivots has no calibrated path through the existing gates.
A successor should first demonstrate a materially different scaling law on a
frozen prefix or black-box operation.  Candidates are compiled sparse
finite-field factorization, a block/Wiedemann solve that avoids storing the
full affected-row trace, or an algebraic reduction of the 114-dimensional
Koszul quotient.  Increasing the timeout or optimizing output bytes is not a
new route.

The first synthetic-only LinBox scout is positive but not yet an HC4-matrix
benchmark.  Over `GF(181)`, Sage 10.9/LinBox 1.7.1 returned the independently
known full rank on matrices with target-like row ratio and about 16.4 nonzeros
per row:

| Columns | Rows | Nonzeros | LinBox rank wall |
|---:|---:|---:|---:|
| 512 | 1,224 | 20,080 | `0.0092 s` |
| 1,024 | 2,448 | 40,176 | `0.0313 s` |
| 2,048 | 4,895 | 80,352 | `0.1079 s` |
| 4,096 | 9,790 | 160,720 | `0.4153 s` |

Peak process RSS after the largest case was `256,622,592 B`.  A quadratic
extrapolation from the largest case to 35,881 columns is roughly 32 seconds,
but the embedded identity and synthetic support can make this optimistic.  It
is a route-selection signal only.  The receipt is
`receipts/hsop-j2-secant-r10-third-colon-linbox-synthetic-capability-scout.json`.

## Actual target-blind p181 LinBox coefficient benchmark

V1 failed before rank on a row-domain hash mismatch: it enumerated 89,964
ambient character-block monomials rather than the 85,651 sorted nonempty
coefficient-support rows.  Its 19.71-second, 381,665,280-byte, zero-swap
terminal is retained as `FAIL_PRE_RANK_ROW_DOMAIN_INTEGRITY_V1`.  A frozen
amendment licensed only the row-support correction.

V2 rebuilt the actual coefficient map without importing or constructing the
third candidate or RHS.  All exact sparse LinBox ranks were full:

| Columns | Rows | Nonzeros | 16 matvecs | Exact LinBox rank wall | Rank |
|---:|---:|---:|---:|---:|---:|
| 4,096 | 85,651 | 146,642 | `2.00 s` | `1.05 s` | 4,096 |
| 8,192 | 85,651 | 301,450 | `4.20 s` | `9.76 s` | 8,192 |
| 16,384 | 85,651 | 546,088 | `4.84 s` | `9.24 s` | 16,384 |
| 35,881 | 85,651 | 1,354,540 | `10.84 s` | `35.66 s` | 35,881 |

The full supervised run took `95.38 s`, maximum RSS was `624,082,944 B`, and
process swaps were zero.  The 7,457,948-byte promoted CSR has SHA-256
`2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef`.
An independent byte-level audit replays all four deterministic matvec hashes
and confirms that Sage 10.9 dispatches rank to exact sparse modular Gaussian
elimination.  It does not independently recompute the ranks.

This converts the compiled route from a synthetic signal to an actual-matrix
capability result.  It does not test the target column, produce a solution,
or establish membership.  The next calibrated experiment is one separately
frozen deterministic solve with an explicit vector and exact all-row replay;
only a passing solve can license p-adic or rational reconstruction.

## HSOP/nullcone pilot baseline

The first unreduced `j2` tests used the 55 direct normal equations plus one
inverse equation in 21 variables.  Equation construction took about `3.6 s`
in each orbit.  Both characteristic-32003 Gröbner calculations reached their
`300 s` caps without a basis result:

| Residual orbit | Gröbner wall | Child CPU | Peak native RSS | Disposition |
|---|---:|---:|---:|---|
| tangent | `300.04 s` | `293.22 s` | `1.569 GB` | timeout retained |
| secant | `300.04 s` | `293.30 s` | `1.566 GB` | timeout retained |

These measurements reject the unreduced presentation as the next tractable
route; they do not bear on the truth of radical containment.  The replacement
case budget and update triggers are in `NEXT_GOAL_HSOP_NULLCONE.md`.

The first tangent normalized pair chart also timed out at `180.03 s` under
Singular `std` (`1.25 GB` RSS).  The same chart timed out at `180.12 s` under
four-thread `msolve` (`2.88 GB` RSS), rejecting solver substitution without a
structural reduction.  After the exact `j2=1` gauge and first-nonzero-jet split,
the deepest `r=5` stratum has 16 variables.  Finite-field `msolve` runs at
primes `101`, `32003`, and `65521` each returned a one-element unit basis in
about `0.46–0.48 s` of solver wall time and roughly `71–73 MB` RSS.  The first
characteristic-zero full-generator `modStd` lift reached `180.03 s` without a
basis result, so generator minimization is the active route.  Characteristic-
zero `msolve` runs use probabilistic modular reconstruction in the installed
version and are retained only as route signals, not exact certificates.

## Tangent `j2` exact closure telemetry

The first-jet reduction closed all six tangent strata exactly:

| Stratum | Exact route | Solver wall | Peak RSS |
|---|---|---:|---:|
| `r=5` | `g0` compatibility split, Singular `qstd` | `17.11 s` + `5.10 s` | `64.1 MB` max |
| `r=6` | coefficient slice, Singular `slimgb` | `0.165 s` | `13.2 MB` |
| `r=7` | coefficient slice, Singular `slimgb` | `0.255 s` | `22.4 MB` |
| `r=8` | coefficient slice, Singular `slimgb` | `35.36 s` | `753.5 MB` |
| `r=9` | coefficient slice, Singular `slimgb` | `20.25 s` | `482.8 MB` |
| `r=10`, degree 6 | pseudo-remainder branch, `slimgb` | `1.69 s` | `38.6 MB` |
| `r=10`, degree 5 | pseudo-remainder branch, `modStd` | `22.88 s` | `58.0 MB` |
| `r=10`, degree 4 | pseudo-remainder branch, `slimgb` | `7.36 s` | `22.1 MB` |
| `r=10`, degree 3 | pseudo-remainder branch, `slimgb` | `0.021 s` | `5.2 MB` |
| `r=10`, `A=0` | coefficient-vanishing branch, `slimgb` | `0.021 s` | `5.0 MB` |

The decisive route comparisons were unusually sharp.  The full 20-variable
`r=10` coefficient slice timed out at `180.05 s` and about `2.01 GB`.  A
22-equation tail reduced modular wall time to about five seconds but both
`slimgb` and `modStd` exact runs still timed out at 180 seconds.  The verified
convolution identity then removed `f3,f4` through five leading-degree branches.
Direct rational `qstd` timed out on degrees six and five; branch-specific
`slimgb` closed degree six in `1.69 s`, while branch-specific `modStd` closed
degree five in `22.88 s`.  These measurements are the calibration baseline
for the secant-chart work.

## Secant `j2` sharp-reduction telemetry

The secant first-jet strata `r=5,...,9` closed exactly with solver walls of
`1.165`, `0.163`, `0.157`, `10.113`, and `0.588` seconds respectively.  The
`r=10` branch tree then closed all cases except `f9!=0` with leading
convolution degree six.  Representative exact homogenized walls were
`32.55 s` for the `f9!=0` degree-four branch, `622.38 s` for degree five,
`13.52 s` for `f9=0` degree five, and `54.62 s` for `f9=0` degree six.

The remaining degree-six open has a minimized 19-variable, 19-equation input
of maximum degree three.  A characteristic-101 unit signal took `12.58 s` of
solver wall.  The deterministic characteristic-zero homogenized backend was
terminated at the frozen `3609 s` decision point after reaching at least
`2,072,368 KiB` RSS; no certificate was emitted.  An eager exact unit-linear
reducer was terminated at `611 s` after reaching at least `555,456 KiB` RSS;
no reduced input was emitted.  These are lower bounds from authoritative
polls, not recovered process maxima, and neither timeout changes the claim.

The exact homogeneous audit then completed in `6.20 s`. It verified 17
homogeneous cubics, the open factor
`M=f9*f10*(2*f9^2+5*f10*g0)`, and four successive unit-linear pivots, reducing
the localized presentation to 13 equations in 14 homogeneous variables. A
dedicated F4 saturation attempt at prime `1073741827` was stopped at `180.19
s` after reaching degree nine, approximately `1.85 GB` immediate-scope RSS,
and a displayed queue of about 49,000 pairs. It emitted no saturation
decision. Prime 101 was rejected immediately by this backend as too small.
These measurements favour a bounded graded membership/resultant experiment
over a longer blind saturation retry.

The ensuing `Z/12` character split reduced the degree-eight `M^2` Macaulay
problem over `GF(101)` to a `37,219 x 85,689` sparse row presentation with
`1,276,345` nonzero entries. Matrix construction took under 14 seconds; the
actual Sage sparse echelonization was interrupted without a decision after
`1046.80 s` wall (`697.01 s` user, `223.17 s` system), with
`3,752,902,656` bytes maximum RSS, a `6,151,722,480` byte peak footprint, and
zero swap. This calibrates the generic sparse-elimination route as the wrong
next implementation at this block size; it does not calibrate the truth of
membership.

The grading itself is now exact rather than experimental.  Its `567 x 18`
exponent-difference matrix has integer rank 17 and Smith quotient
`Z direct_sum Z/12`; the frozen Sage audit completed in `10.21 s`.  The much
smaller `N=1` character block (`32 x 384`, 1,323 nonzeros) terminated in
`8.49 s` and proved that no degree-four `M` identity exists over `GF(101)`.

The first-colon pivot has the following measured stages:

| Stage | Measured result | Interpretation |
|---|---:|---|
| modular kernel extraction, prime `1073741827` | `91.98 s` | 189-term quartic candidate |
| modular kernel extraction, prime `1073742851` | `74.03 s` | identical support at a second discovery prime |
| rational reconstruction plus held-out replay | `9.18 s` | unique 189-term `QQ` candidate; all coefficients match at prime `1073741789` |
| degree-four quotient test, prime `101` | `25 x 242`, 885 nonzeros | candidate class is nonzero modulo `I_4` |
| Singular `liftstd/slimgb`, prime `101` | `300.02 s` timeout | no identity or nonidentity decision |
| Singular direct lift, prime `103` | `300.01 s` timeout | no multipliers; no identity or nonidentity decision |
| sparse Macaulay, prime `103` | `18.04 s`, `640.6 MB` RSS | exact modular identity; 34,979 pivots and 1,927 free coordinates |
| fixed prime-103 pivot order, prime `107` | `171.72 s` timeout | coefficient-dependent order did not transfer |
| fixed free-coordinate set, prime `107` | `18.62 s`, `640.7 MB` RSS | exact held-out modular identity with adaptive pivot order |
| four 31-bit reconstruction primes | `16.14--16.75 s` each | exact modular identities; stable 6,301-term support |
| rational reconstruction and exact replay | `10.16 s` | exact `QQ` identity; 6,301 multiplier coefficients |

The reconstructed quartic has denominator lcm 3024, maximum denominator 756,
and maximum absolute numerator 264290.  Its product `M*h` has degree eight and
362 terms.  The successful character block has 36,906 multiplier coordinates,
85,646 monomial equations, and 1,254,205 nonzeros.  The rational multiplier
reconstruction uses five primes with CRT modulus
`2190567584044155746197442675313152470997`; its equal
numerator/denominator uniqueness bound is `33095072020197778580`.  The maximum
absolute numerator is `11398558304840159`, the maximum denominator is
`70058025576000`, and the unused prime 107 check reports `0/6301` coefficient
mismatches.

The exact artifact and receipt hashes are respectively
`a90070b5f81c0664988d4272b9b3893385c9672089b1ea798ed8fc425028abcb`
and `551f4596db46abfb69ed5a2d2e320dece326f6f435b006cb1163e44991eae58c`.
The standard-library-only verifier replays all 17 multiplier products against
the frozen 362-term target and problem digest.  The independent prime-103
audit separately rebuilds the 36,906-coordinate block and checks all
1,254,205 entries; its receipt hash is
`1dc72d34a64b6ffe287ad84d6573dcbcf76eb156de8c4a97e223e6efa7d07e3f`.

Two negative route calibrations should be retained.  First, a fixed pivot
*order* is not portable across characteristics, whereas a fixed
free-coordinate *set* is a valid gauge and permits coefficient-adaptive
pivoting.  Second, substituting the four localized pivots expands the
189-term quartic to an irreducible 3,883-term degree-16 numerator over `u^6`;
this route completed in `7.96 s` but offers no compression or factor split.
The msolve provenance audit likewise shows that retrofitting the original F4
trace would require module ancestry through a 4,970-element basis and a
`355024 x 792344` matrix.  Sparse target-specific Macaulay elimination is the
measured successful implementation.

### Second-colon telemetry

The next colon step is larger but remains a bounded character block.  Its
211-term character-three quartic was reconstructed from two large-prime taps;
the separate identity target `M*h2` has 412 terms.  With generators
`F_1,...,F_17,h`, the degree-eight character-four block has 37,476 multiplier
coordinates, 85,921 monomial equations, and 1,355,292 nonzeros at prime 103.

| Stage | Measured result | Interpretation |
|---|---:|---|
| residual-colon tap, prime `1073741827` | `63.48 s` producer wall | first 211-term character-three quartic |
| residual-colon tap, prime `1073742851` | `63.07 s` producer wall | identical support at a second discovery prime |
| candidate reconstruction | `6.94 s` | unique bounded two-prime rational candidate; denominator at most 648 |
| structural audit, prime `1073741827` | `6.67 s` | irreducible and new modulo cubics, `h`, and 39 first-order transforms |
| prime-103 identity block | `171.02 s`, `2.14 GB` RSS | exact modular identity; 35,423 pivots and 2,053 free coordinates |
| fixed free-coordinate set, prime `107` | `18.62 s`, `798.0 MB` RSS | exact held-out modular identity with adaptive pivot order |
| fifteen approximately 31-bit primes | `22.31--23.77 s` each, `655--848 MB` RSS | exact source identities; stable 15,211-term support |
| five-prime reconstruction attempt | `57.13 s`, `344.9 MB` RSS | fail-closed: modulus insufficient, no QQ decision |
| six-prime reconstruction attempt | `57.58 s`, `359.5 MB` RSS | fail-closed: modulus still insufficient, no QQ decision |
| sixteen-prime reconstruction and rational replay | `72.70 s`, `410.0 MB` RSS | exact QQ identity, zero 412-term remainder |
| standard-library independent replay | `1.78 s`, `65.8 MB` native RSS | zero remainder from frozen artifact and problem digest |

The two discovery primes reconstruct `h2` with CRT modulus
`1152922610560928777`, common denominator 648, maximum denominator 648, and
maximum absolute numerator 124805.  The identity reconstruction uses prime
103 and fifteen approximately 31-bit primes.  Its CRT product has 472 bits;
the maximum absolute numerator is
`4361149698997496204601843075014067511274003`, and the maximum denominator is
`61776803775171319112508656025600000`.  All 15,211 reconstructed nonzero
coordinates lie inside the product uniqueness budget.  The unused prime 107
has `0/15211` coefficient mismatches, and exact rational convolution gives
zero remainder with all 18 multipliers nonzero.

Two implementation corrections are frozen with the successful run.  First,
gauged-run telemetry now guards an incomplete solve whose value vector is
`None`, rather than indexing it while checking gauge coverage.  Second, when
the active-equation count reaches zero, adaptive elimination clears any stale
heap entries and proceeds to back-substitution; before this fix the initial
prime-103 run could report a false timeout even with zero active equations.
The intermediate `retry-v2` receipt is different: it stopped with 555 active
rows and is a genuine timeout.  A duplicate `generator_count` JSON key was
also removed.  These are solver/reporting corrections, not mathematical
assumptions.

The exact certificate artifact SHA-256 is
`32ffb748a88f59c6c7a1ad98d95beb84d5e3c1cdb1422a724677fca1a4ff5d61`;
the reconstruction receipt SHA-256 is
`41ee3ee58a80f8e646dc71d6011e20543a4f06fea38a1b446ffe017ed6809690`;
and the independent standard-library replay receipt SHA-256 is
`dbb894781b206e07988a5a63e7a5c0a676e72624bf37cc2d05f141d45624fa82`.
This measures two successive colon elements only.  It is not a measurement or
certificate of colon equality, saturation, secant closure, or HC4.

### Third-colon candidate and modular-lift telemetry

The third discovery step first produced a bounded rational candidate, then
several exact finite-field membership identities.  These assurance layers are
separate:

| Stage | Measured result | Interpretation |
|---|---:|---|
| second residual-colon tap, prime `1073741827` | `72.36 s`, `2.07 GB` RSS | 248-term degree-four, character-two candidate at basis position 5,859 |
| second residual-colon tap, prime `1073742851` | `79.74 s`, `1.96 GB` RSS | identical support at the second discovery prime |
| third-candidate reconstruction | `7.04 s` internal; `10.29 s`, `320.5 MB` RSS external | exact bounded two-prime reconstruction and two modular nonmembership tests |
| original hybrid identity, prime `173` | `311.59 s`, `2.39 GB` RSS | exact modular identity; 20,245 nonzero multiplier coordinates |
| independent prime-`173` replay | `5.28 s`, `168.1 MB` RSS | zero coefficientwise remainder |
| alternative-gauge identity, prime `181` | `305.13 s`, `2.16 GB` RSS | exact modular identity in a different fixed-free gauge |
| dense-pivot-swap identity, prime `181` | `268.95 s`, `2.54 GB` RSS | exact modular identity after exchanging 581 pivots and free coordinates |
| independent dense-swap replay | `4.35 s`, `182.8 MB` RSS | exact gauge exchange and zero coefficientwise remainder |
| pure-sparse identity, prime `181` | `296.83 s`, `2.60 GB` RSS | exact modular identity; 18,951 nonzero coordinates and no dense handoff |
| pure-sparse transfers, primes `173`, `197`, `2147483647`, `2147483629` | `26.73--34.78 s` each, `1.17--1.27 GB` RSS | four exact modular identities with zero same-process replay mismatches |

The reconstructed `h3` has CRT modulus `1152922610560928777`, equal-height
uniqueness bound 759250489, common and maximum denominator 4284, and maximum
absolute numerator 98020015.  Both source-prime reductions match all 248
coefficients.  At each prime, a `32 x 341` degree-four character block with
1,288 nonzeros proves that the candidate is nonzero modulo `(I,h,h2)` in that
block.  The artifact and receipt hashes are
`b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97`
and
`6064a2d441cc9f54f64d69085a846d09908860b53a1fac830dafc657de203616`.
Thus `M*h3 in (I,h,h2)` is proved at the displayed finite characteristics.
It is not proved over `QQ`: the modular multiplier vectors use distinct gauges
and do not yet assemble into one rational vector with an exact rational
convolution replay.

The complete bounded full-vector censuses quantify that lift obstruction:

| Gauge and bound | No candidate | Unique zero | Unique nonzero | Ambiguous | Interpretation |
|---|---:|---:|---:|---:|---|
| alternative prime-`181`, `M566` | `19,762` | `17,751` | `535` | not used | bounded full-vector reconstruction fails; all 581 dense-handoff pivots have no candidate |
| dense-pivot swap, `M70` | `19,844` | `17,660` | `544` | `0` | pivot exchange preserves modular solvability but not bounded rational reconstruction |
| pure sparse, `M70` | `17,758` | `18,998` | `1,292` | `0` | 2,086 fewer no-candidate labels than dense swap, a descriptive `10.5%` bounded outcome improvement |

The pure-sparse producer and independent audits complete in `1.44 s` and
`1.56 s`, with receipt SHA-256 hashes
`78d0bd0200299c1dc8fb7df7880f479613e93cf0ccca99c4741a97883c501ad7`
and
`9c0f4d0dd1f5d603e66c7e5f6f933a98300e1c25805276a090c3aa6babb38964`.
The final census uses primes `181`, `2147483647`, and `2147483629` as CRT
sources and `173` and `197` as selectors.  The independent standard-library
audit reproduces all candidate, selector-survivor, and outcome streams without
importing or running the producer; it recomputes the bounded census, not the
pure-sparse polynomial identity.  The 10.5-percent change is an improvement
in bounded outcome count only; it is descriptive rather than causal because
the gauges and selector sets differ.  None of the three censuses
reconstructs rational multipliers, proves or disproves a `QQ` identity,
identifies a colon or saturation, closes the secant chart, or establishes HC4.

### Exact Koszul-syzygy scout telemetry

The preregistered structural scout constructs exactly 2,053 primitive integer
Koszul columns for the frozen third-colon Macaulay map, with 154,939 nonzero
entries.  Exact coefficientwise convolution verifies `A*K=0`.  The support
graph has one component containing all 2,053 columns and 28,853 active
multiplier coordinates; its maximum matching has size 2,053.  Sparse rank at
prime 181 is also 2,053, which proves the 2,053 columns are independent over
`QQ`.

| Run | Wall | Native maximum RSS | Result |
|---|---:|---:|---|
| frozen producer | `24.50 s` | `375,603,200` bytes | exact primitive columns, `A*K=0`, connected graph, matching/rank `2,053` |
| independent content audit | `22.87 s` | `187,531,264` bytes | same mathematical content and rank; PASS without producer execution |
| retained metadata-serialization attempt | `21.43 s` | `126,238,720` bytes | fail closed; no mathematical conclusion |
| retained primitive-serialization attempt | `21.49 s` | `126,369,792` bytes | fail closed; no mathematical conclusion |

At characteristic 181, the frozen kernel quotient by the Koszul span has
dimension 114.  Over `QQ`, the only licensed conclusion is the upper bound
114; equality, a quotient basis, and rational target membership are not proved.
The independent audit reconstructs canonically sign-normalized primitive
content but does not reproduce the producer's undocumented byte serialization:
its primitive stream hash is
`bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856`,
not the producer hash
`8a36159e01332cfc8fac9449e95001a069e440e8f7242965e756c09d15dfea76`.
The PASS is for content invariants, exact convolution, support, matching, and
rank, not byte identity.

The frozen producer script/receipt SHA-256 hashes are
`39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988`
and
`6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875`;
the independent script/receipt hashes are
`eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea`
and
`15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102`.
The failed metadata- and primitive-serialization receipt hashes are
`73d11eab68fc8a6e85494f1deab36b93f773740faab856420f90b525564491e2`
and
`acd008f446fc08fee4cecac89f8ea3e6b7aec12bd65ccbdea8b97cf8c1eb680f`.
They remain fail-closed history and license no positive claim.  Fixed-minor
Koszul normalization is a separate route from this content audit.  The scout
proves no `QQ` target membership, colon, saturation, secant closure, nullcone
containment, or HC4.

### Fixed-minor Koszul normalization stop telemetry

The preregistered selected-coordinate-minor route terminated fail closed.  Its
`2053 x 2053` minor has the following exact rank telemetry:

| Characteristic | Rank | Interpretation |
|---:|---:|---|
| `181` | `2,053` | selected minor nonsingular; transient computation only |
| `173` | `2,053` | selected minor nonsingular; transient computation only |
| `197` | `2,052` | nullity one; route-stopping singular minor |

The characteristic-197 minor has 13,915 nonzero entries.  The producer's first
missing pivot column and the independent verifier's first dependent column are
both 1,983.  The independent audit reconstructs the minor without executing
the producer and obtains rank 2,052 by both its local sparse basis algorithm
and Sage sparse rank.  The producer stops in `13.04 s` at `282,640,384` bytes
native maximum RSS; the independent audit passes in `28.82 s` at `392,511,488`
bytes.  The initial `12.11 s` attempt is retained as fail-closed history.

The final producer script/receipt SHA-256 hashes are
`fceb3a0a12ae5473bf48f72d2c37e864c6569897052c6d0f60235b0a4fe6a08f`
and
`0ba428b62f3bf8b7ccca4aded1c12e3c9659a498eac300f65036f393a54622e1`;
the independent verifier script/receipt hashes are
`deaa1d47f73d21bc7609a46d6df0474e92ea2e59c622fd6cd1c92bfb6118619d`
and
`e97001a1c7232e903192e649f440fc8bfe81277229793a9905469288dec8936f`.
The initial failed-receipt hash is
`a013cdda57a74c7084a315f6fc2ab98a4663f068ff3d6d47823aee64a38c24df`.

The fail-closed stop occurs before testing primes `2147483647` and
`2147483629`; no additional primes are used, no normalized artifacts are
written, and no `M70` census is run.  It stops only this selected-coordinate-
minor normalization.  It does not invalidate the source modular identities,
determine full `K` rank modulo 197, prove or disprove `QQ` membership, compute a
colon or saturation, close the secant chart, establish nullcone containment,
or prove HC4.  The exact statuses are `FAIL_CLOSED_FIXED_MINOR_SINGULAR` and
`PASS_INDEPENDENT_P197_FIXED_MINOR_SINGULARITY`.  No next residual route is
designated by this result.

## Residual-114 quotient and rational-lift telemetry

The compiled quotient-section route turns the formerly descriptive
114-dimensional residual into a measured exact interface.  All runs below had
zero swaps.

| Unit | Result | Wall seconds | Maximum RSS bytes |
|---|---|---:|---:|
| exact rational quotient-chart producer | `B*T=C` over `QQ` | `67.29` | `155,107,328` |
| independent quotient-chart audit | all zero/nonzero entries replayed | `36.63` | about `257,300,000` |
| canonical residual-114 modular section | rank `2,053+114=2,167` over `GF(181)` | `218.78` | `751,173,632` |
| independent modular-section audit | source rebuild and direct equations | `41.0787` | `474,775,552` |
| sparse-four two-digit lift v2 | four columns through `181^2` | `82.43` | `319,078,400` |
| independent two-digit audit | exact RHS and `181^2` invariant replay | `12.7071` | `306,020,352` |
| sparse-four four-digit extension | four columns through `181^4` | `124.12` | `150,519,808` |
| exact rational sparse-four replay | all `143,524` coordinates | `1.64` | `85,819,392` |
| independent rational audit | `342,604` exact scalar comparisons | `1.5176` | `88,424,448` |

Each compiled correction solve took approximately 59--63 seconds and returned
708 nonzero digit coordinates for the four-column batch.  Increasing the
number of right-hand sides does not multiply the factorization cost in the
same way that solving columns separately would, so the next cost-calibrated
experiment batches the 18 remaining residual columns of modular support at
most 5,000.  The observed reconstruction height is favorable: four digits
were enough, exact common denominators have only 14--16 bits, and support did
not grow across the p-adic corrections.

The mathematical output is narrower than the engineering success.  Four
exact rational residual syzygies prove a rational quotient lower bound of 4;
the exact quotient chart gives the upper bound 114.  Neither the resource
profile nor the modular dimension decides whether the old target vector lies
in the rational source image.

## Direct nullcone-ideal telemetry

Macaulay2 1.26.06 with `CoincidentRootLoci` reconstructed the exact defining
ideal of `X_(6,1,1,1,1)` from the partition in `77.54 s` wall (`100.38 s`
user CPU), with maximum RSS `885,260,288` bytes.  The exact profile is:

| Quantity | Value |
|---|---:|
| projective dimension | `5` |
| codimension in `P^10` | `5` |
| degree | `30` |
| minimal generators | `31` |
| generator degrees | `1 x 2`, `10 x 3`, `20 x 4` |

This is the first calibrated cost for the direct coincident-root target.  It
does not measure the cost of proving containment of the normal-layer locus.

The first whole-degree `HighestWeights` decomposition was interrupted at
`348.13 s` wall and `4,733,190,144` bytes RSS without output.  Replacing it by
the torus weights of the 31 minimal generators completed in `85.29 s` wall and
`882,966,528` bytes RSS.  It produced the exact family decomposition
`V0` in degree two, `V2+V6` in degree three, and `V0+2V4+V8` in degree four.
This is the relevant calibration: the representation reduction lowers 31
coefficient equations to seven highest-weight families before any normal-
layer containment calculation begins.

## Tangent cubic nullcone closure telemetry

The direct cubic target closed both irreducible families exactly on the
tangent normal layer.  The five lower top-index cells had the following exact
solver walls:

| Family | `r=5` | `r=6` | `r=7` | `r=8` | `r=9` |
|---|---:|---:|---:|---:|---:|
| `V6` | `120.40 s` | `0.568 s` | `0.313 s` | `32.57 s` | `62.47 s` |
| `V2` | `3.004 s` | `0.539 s` | `0.295 s` | `24.22 s` | `64.40 s` |

For `r=10`, the direct convolution-degree cover closed `A=0` and degrees zero
through four in at most `3.08 s` per exact branch.  Degree five took `23.31 s`
for `V6` and `23.68 s` for `V2`.  The `V6` degree-six retained-fibre branch
took `280.89 s` and `2.23 GB` RSS over `Q`.

The unsplit `V2` `r=10` modular chart timed out at `600.09 s` and `3.47 GB`.
Its unnormalized degree-six branch then timed out at `240.04 s` and `2.97 GB`.
Using the weight-zero property of `V2` to normalize the weight-`-16`
coefficient `f10=1` changed that same branch to a modular unit in `72.70 s`
and an exact rational unit in `27.82 s` with `713 MB` RSS.

The stabilizer propagation computations were subsecond once highest-coordinate
containment was available: the `V6` orbit polynomial has degree six and exact
coefficient rank seven; the `V2` orbit polynomial has degree two and rank
three.  This is the principal quartic calibration: test stabilizer cyclicity
before launching every coordinate separately, and use torus weights to seek a
top-coefficient normalization even when the target itself has weight zero.

## Secant `V2` normalized highest-coordinate reduction telemetry

This secant calculation is separate from the completed tangent `V2` family.
The exact torus audit proves that the nonzero `V2` highest coordinate, which has
character one, may be normalized to one.  Equation construction took `3.61 s`.
The direct normalized characteristic-101 calculation then retained a
`120.08 s` solver timeout (`124.54 s` including construction) with
`1,362,771,968` bytes immediate-scope RSS.  The timeout is route-cost evidence
only.

The target is linear in `f10` with primitive pivot

```text
P = 90*f0*f4 - 63*f1*f3 + 28*f2^2.
```

An exact symbolic replay over `QQ`, matched over `GF(101)`, gives in `10.88 s`
the exhaustive branch cover `D(P) union V(P)`.  On `D(P)`, the displayed recovery formula eliminates
`f10`, lowering the variable count from 21 to 20; all denominators are powers
of `P` times units.  On `V(P)`, the boundary is retained as the 55 original
normal equations together with `P` and `B-1`, for 57 generators in 21
variables.  The normalization and reduction receipt SHA-256 hashes are
`23390584d9355b6b5775e6991c54b7bcf3e87e18c6043a59053255709237cc34`
and
`31a1d0d04d58c2ed7bd8c7fc37c44e3d2d143feeb552737c1d0605d49bac6e57`.
Neither branch is proved empty, and the calculation proves neither the other
`V2` coordinates, secant nullcone containment, polynomial-level lifting, nor
HC4.

## Third-colon target closure telemetry

The fixed-main target route now closes the former characteristic-zero
membership gate.  All runs had zero swaps.

| Unit | Result | Wall seconds | Maximum RSS bytes |
|---|---|---:|---:|
| target extension `181^48` to `181^54` | six exact correction digits; zero unresolved coordinates | `311.41` external | `151,617,536` |
| independent p54 replay | rebuild endpoint and full integer invariant | `2.5` including freeze check | below `1.5 GB` gate |
| exact rational system replay | 35,881 coordinates; 85,651 zero equations | `1.96` external | `180,518,912` |
| independent certificate audit | normalization, p54 reduction, and 85,651 zero equations | `1.8` including freeze check | below `1.5 GB` gate |
| independent polynomial audit | rebuild 19 generators, 38,048 descriptors, and 85,651 monomial rows | `10.50` internal | `393,904,128` |

The terminal rational vector has 19,050 nonzero coordinates, a 188-bit global
denominator, and maximum local denominator
`317682618125658972024024232366797141308227584000000`.  The p54 height census
was informative rather than dispositive; exact system replay and the separate
source-level polynomial replay are the proof gates.  The semantic certificate
contains 19,050 multiplier records and verifies
`M*h3=sum(q_i*F_i)+q_18*h+q_19*h2` over `QQ` with zero of 85,651 coefficient
mismatches.

Fermi implication: further digits on this fixed target have zero expected
theorem value because the exact identity is already established.  The next
calibration target is the low-degree colon/unit scan after adjoining `h3`, not
additional quotient directions or target-height optimization.

## Fourth-colon target lift and recovery telemetry

The target after adjoining `h3` has a larger fixed-gauge system than the
closed third target: 85,688 rows, 36,587 selected columns, 1,487,624 nonzeros,
and 2,239 free coordinates.  All reported solver runs had zero swaps.

| Unit | Result | Wall seconds | Maximum RSS bytes |
|---|---|---:|---:|
| exact system and modular interface | frozen integral target system | see construction receipt | see construction receipt |
| `173^8` pilot lift | seven correction digits pass | frozen pilot receipt | frozen pilot receipt |
| `173^8 -> 173^54` extension | 46 correction digits pass | `5,338.31` external | about `450,000,000` |
| independent `173^54` audit | full 54-digit congruence replay | short audit | below `1.5 GB` gate |
| `173^54 -> 173^96` extension | 42 correction digits pass | `4,932.96` external | `459,046,912` |
| independent `173^96` audit | every digit and full congruence replay | `6.58` external | `136,822,784` |
| frozen `p96` exact-recovery hierarchy | no exact rational replay | `16.47` external | `457,932,800` |

Equal-height rational reconstruction left 8,961 coordinates unresolved at
`p54` and 8,579 at `p96`, a gain of only 382 coordinates for 42 additional
digits.  At `p96`, 28,008 coordinates reconstructed and 8,579 did not.  The
601 nonzero coordinates stable between `p84` and `p96` had a 289-bit common
denominator candidate; exact replay failed 42,870 rows.  Fixed unscaled LLL
blocks of dimensions 8, 16, 24, and 32 produced candidate denominators of
roughly 897--969 bits, with every candidate failing the frozen 512-row sample.

Fermi implication: on the observed fixed gauge, additional precision has a
poor theorem-value rate.  The next tractable investment is gauge optimization
or quotient reduction, with an out-of-sample checkpoint, rather than a longer
unchanged lift.  The modular lift is positive infrastructure evidence; the
negative recovery result exhausts only the registered reconstruction family.

The first exact kernel-batch selection census cost `10.88 s` wall and
`346,292,224` bytes maximum RSS.  Among 2,239 free source columns, support
ranges from 13 to 248 and 43 columns attain support 13.  Thus a support-ordered
16-column batch is a real sparse stratum.  This measures input sparsity only;
the fill and height of `-B^(-1)C16` remain unmeasured.

The next-run Fermi bracket is now explicit.  Exact block rebuilding is
observed at `11.51 s`; a fourth-target solve is about `115 s`; and `C16` adds
only 208 raw terms to 1,487,624 existing nonzeros.  Allow 2--8 solve
equivalents (`4--16 min`) for the canonical transfer and first `p2`
correction, with a fail-closed recalibration above eight equivalents or
`1.5 GB` RSS.  Implementation and independent-audit effort are separate from
this solver-runtime bracket.

## Fourth-colon 16-column rational-kernel result

The preregistered support-ordered batch passed every frozen gate.  The source
export rebuilt the 85,688 rational rows, matched all 1,487,624 frozen `B`
entries with zero row mismatch, and retained the original primitive row scale.
Two of the 208 selected source entries are nonintegral under that scale but
have 173-adic-unit denominators.

| Unit | Result | Wall seconds | Maximum RSS bytes |
|---|---|---:|---:|
| source-interface reconstruction | four algebra hashes and every frozen `B` row pass | `11.60` | `592,838,656` |
| canonical section modulo 173 | nullity 16; 351 nonzeros; zero replay mismatches | `109.00` | `422,838,272` |
| first correction to `173^2` | nullity 16; 286 nonzeros; zero replay mismatches | `106.16` | `426,196,992` |
| third digit | nullity 16; 286 nonzeros; zero replay mismatches | `113.82` | within the same resource gate |
| fourth digit | nullity 16; 286 nonzeros; zero replay mismatches | `110.35` | within the same resource gate |
| `p4` reconstruction and exact row replay | all 585,392 coordinates resolve; zero exact mismatches | `6.44` | `474,365,952` |
| independent direct-polynomial audit | sixteen zero expanded polynomials | `7.59` | `345,718,784` |

The transfer plus the first correction used `215.157 s`, below the frozen
four-single-target-solve promotion ceiling of `460 s`.  The full four-solve
LinBox total was `439.334 s`, with zero swaps.  Equal-height reconstruction at
modulus `173^4 = 895745041` and uniqueness bound 21,162 produced exact
rational source syzygies: the first has 37 nonzero coefficients including its
distinguished free unit, and each remaining syzygy has 22.  The independent
audit bypassed the CSR row encoder and expanded all sixteen source combinations
directly over `QQ`; every residual polynomial had zero terms.

This is a positive calibration result for support-ordered gauge discovery and
an exact rational source-kernel theorem candidate.  It does not solve the
separate inhomogeneous `M*h4` target, prove a fourth colon identity or colon
equality, close the secant orbit, establish the full invariant nullcone, or
prove HC4 or JC2.
