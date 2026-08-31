# Next goal: binary-decimic nullcone containment

**Set:** 30 August 2026  
**Parent goal:** HC4 clean double-conic normal-layer campaign  
**Status:** active, proof-or-falsification; all 31 tangent target generators
exact, secant `j2` reduced to one degree-six saturation chart with a certified
characteristic-zero three-step colon-element chain, including an independently
replayed exact `QQ` polynomial identity for `M*h3`; the secant
third-colon source kernel has an independently content-audited 2,053-dimensional
rational Koszul subspace, an exact rational 114-dimensional quotient chart, a
full independently replayed `2,053+114` kernel decomposition over `GF(181)`,
and 22 independently replayed rational residual syzygies; full colon equality
and saturation remain open; the secant
`V2` highest-coordinate chart has an exact normalized two-branch reduction  
**Claim ceiling:** this is not a proof of HC4

## Objective

Decide, or sharply reduce, the invariant-theoretic stretch gate left after the
exact five-support theorem:

\[
R_+\subseteq \sqrt{(I_{\mathrm{nor}}:\mathfrak m_2^\infty)
                    \cap \mathbf Q[f_0,\ldots,f_{10}]}.
\]

Here `I_nor` is the clean double-conic normal-layer ideal, `m2` is the ideal
of the three residual-quadratic coefficients, and `R_+` is the positive-degree
invariant ideal of binary decimics.  Work with the reconstructed eight-element
homogeneous system of parameters

```text
j2, j4, A6, C6, j8, j9, j10, j14_plus_A14
```

and the two nonzero residual-quadratic orbits, tangent and secant.

## First tractable target

Prove or falsify the two orbitwise statements

\[
j_2\in\sqrt{I_{\mathrm{tangent}}},\qquad
j_2\in\sqrt{I_{\mathrm{secant}}}.
\]

The unreduced presentations have 55 equations in 21 unknowns after adding
the inverse variable.  Both characteristic-32003 pilots reached the 300 s
limit at about 1.57 GB RSS, so increasing that timeout is not the next route.

Instead, write

\[
j_2=c_0f_0f_{10}+c_1f_1f_9+\cdots+c_4f_4f_6+c_5f_5^2,
\]

with the exact nonzero rational coefficients produced by the reconstruction.
The locus `j2 != 0` is covered by the six opens on which the displayed
monomial terms are nonzero.  On each open, retain the localization by `j2`
itself and use the nonzero coefficient pair to expose endpoint pivots and the
residual-orbit stabilizer.  This gives twelve first-stage cases: six opens for
each of the two residual orbits.

The monomial localization is an auxiliary cover, not a replacement for
`inv*j2-1`: a nonzero term can occur at a point where the six terms cancel.

## Ordered work programme

1. **Freeze the cover.** Export the exact six terms of `j2`, prove that they
   cover `j2 != 0`, and hash the normal-equation and invariant streams.
2. **Reduce before eliminating.** In every orbit/open case, use sparse endpoint
   equations and the tangent or secant stabilizer to eliminate or normalize as
   many of the ten cubic-correction coefficients as the equations justify.
   Record every division as an explicit open condition and branch on its zero
   locus rather than discarding it.
3. **Run bounded falsifiers.** Test the reduced cases at characteristic 32003
   and at held-out primes.  A modular unit is route evidence only.  A nonunit
   must be converted into an exact point/component or recorded as undecided.
4. **Lift only successful routes.** For every modular unit, compute a
   characteristic-zero certificate over `Q` (or a denominator-audited modular
   reconstruction) and replay it from a clean process.
5. **Generalize conditionally.** Only if the `j2` reduction is reusable, apply
   it to `j4`, `A6`, `C6`, `j8`, `j9`, `j10`, and `j14_plus_A14`.  Do not begin
   sixteen unreduced long-running jobs.
6. **Assemble the invariant conclusion.** All eight invariants must have exact
   certificates on both residual orbits before claiming HSOP nullcone
   containment.  Then audit that the chosen eight forms generate a homogeneous
   system of parameters and state precisely what the containment contributes
   to the clean double-conic problem.

## Decisive outcomes

- **Proof signal:** all twelve `j2` cover cases are exact characteristic-zero
  units, establishing the two displayed radical containments.
- **Falsification signal:** an exact normal-layer point or positive-dimensional
  component on which `j2` is nonzero.
- **Sharp reduction:** a replayable elimination that lowers the correction
  variable count and leaves explicit residual ideals, even if a final unit or
  survivor is not yet decided.
- **Route stop:** the localized presentations reach their resource caps without
  a variable-count reduction.  Preserve the receipts and change method; do not
  infer either containment or failure.

## Full success condition

The next goal is complete only when one of the following is frozen and replayed:

1. exact characteristic-zero radical certificates for all eight HSOP forms on
   both residual orbits, together with the HSOP/nullcone audit; or
2. an exact counterexample component to the claimed containment; or
3. a formally stated smaller residual theorem whose remaining ideal and branch
   conditions are explicit enough to constitute a genuine sharp reduction.

Finite-field scans, generic samples, and timeouts do not satisfy this condition.

## Calibrated resource gate

The measured baseline is two 300 s timeouts at approximately 1.57 GB RSS, with
equation construction taking only about 3.6 s.  Therefore the first route is
budgeted by cases rather than by an invented proof-completion time:

- at most 12 first-stage `j2` opens;
- a 180 s initial finite-field cap per reduced case;
- an immediate route review if two structurally equivalent cases time out
  without reducing the 21-variable presentation;
- characteristic-zero work only after a modular unit or a demonstrably smaller
  exact ideal;
- record wall time, child CPU, peak RSS, variables, equations, maximum degree,
  branches, and basis size for every completed or timed-out case.

The next decisive computational signal is bounded by this case budget.  The
time to a uniform proof is deliberately not forecast from Gröbner runtime.

## Frozen first-stage evidence

`J2_OPEN_COVER_CERTIFICATE.md` and `receipts/j2-open-cover.json` give the exact
primitive six-term identity, the cover proof, exceptional characteristics, and
producer hashes.  At that stage, the unresolved step was the endpoint-pivot
reduction of the twelve orbit/open cases; the later exact reductions below
supersede that work-programme snapshot.

`RESIDUAL_ORBIT_TORUS_REDUCTION.md` and
`receipts/residual-orbit-torus.json` certify one branch-safe coefficient
normalization in every tangent chart and in the five noncentral secant charts.
The central secant chart remains unnormalized.  A tangent unipotent identity is
recorded but not used without its required zero/nonzero branch.

The same certificate gives the stronger tangent reduction `j2=1` on the whole
`j2 != 0` locus, because `j2` has tangent torus weight `-2`.  The next tangent
scout uses this 21-variable global gauge; only the secant orbit retains the
six-chart plan.

The tangent unipotent then gives an exhaustive endpoint split: `f10=0`, or
`f10!=0` with `f9=0`.  These are the current 20- and 21-variable tangent
targets.  The unsplit gauge and one coefficient-normalized chart have both
timed out and are retained only as route telemetry.

Refining by the largest nonzero endpoint coefficient gives six exact tangent
first-jet strata indexed by `r=5,...,10`; after setting `f_(r-1)=0` they have
16 through 21 variables.  The computational order is deepest-first, so a
positive signal is obtained before attempting the two largest strata.

All six tangent strata are now exact characteristic-zero unit calculations.
The `r=5` proof uses a two-branch compatibility determinant; `r=6,...,9` use
coefficient-normalized exact `slimgb` bases; and `r=10` uses the convolution
identity `C+(f3+f4*t)A=0` followed by five leading-degree branches.  The
aggregate audit is `receipts/hsop-j2-tangent-all-strata.json`, and the theorem
note is `TANGENT_J2_RADICAL_CERTIFICATE.md`.

The secant statement has now been reduced exactly to one interface:

\[
j_2\in\sqrt{I_{\mathrm{secant}}}.
\]

The strata `r=5,...,9` and every `r=10` branch except `f9!=0`, leading
convolution degree six, have exact characteristic-zero unit receipts.  The
remaining 19-variable, 19-equation cubic presentation, modular unit signal,
and two bounded exact timeouts are frozen in
`SECANT_J2_DEGREE6_OBSTRUCTION.md`.  The tangent conclusion must not be
transferred to this chart without a new exact certificate.

The remaining chart now has a sharper exact form. Seventeen homogeneous
cubics in 18 variables define an ideal `I`, and the open condition is
`M=f9*f10*(2*f9^2+5*f10*g0)`. Four triangular equations eliminate
`g4,g5,g7,g8` on `D(M)`, leaving 13 equations in 14 homogeneous variables.
The sole remaining statement is `I:M^infinity=(1)`. See
`SECANT_J2_HOMOGENEOUS_SATURATION_REDUCTION.md` and its exact audit receipt.

The character decomposition used by the bounded membership experiments is no
longer heuristic.  An exact integer Smith-form audit of all 567 within-
generator exponent differences gives the universal abelian grading quotient
`Z direct_sum Z/12`; the free factor is total degree, `u` has character zero,
and `M` has character one.  At characteristic 101 the degree-four `M` identity
does not exist, while the degree-eight `M^2` block remains undecided after the
recorded sparse-echelon timeout.

The instrumented colon extraction exposed a much smaller interface.  Two
large-prime runs returned the same 189-term quartic support, componentwise CRT
reconstruction produced a unique rational `h`, and an unused third prime
replayed all coefficients exactly.  The class of `h` is nonzero in the
degree-four quotient at characteristic 101.  The original-generator identity

\[
Mh=\sum_{i=1}^{17} q_i F_i
\]

is now exact over `QQ`: the 17 degree-five multipliers have 6,301 nonzero
coefficients and replay coefficientwise to the 362-term target.  Five modular
input certificates give CRT modulus
`2190567584044155746197442675313152470997`; the equal numerator/denominator
uniqueness bound is `33095072020197778580`, while the observed maximum
absolute numerator and denominator are `11398558304840159` and
`70058025576000`.  Prime 107 was held out and gives `0/6301` coefficient
mismatches.  A standard-library-only verifier independently recomputes the
identity against a hard-coded problem digest.

After adjoining `h`, two further large-prime taps exposed a matching 211-term
character-three quartic `h2`.  Two-prime reconstruction alone made `h2` only a
rational candidate, although the prime-1073741827 structure audit proved it is
irreducible and new modulo the degree-four cubic span, `h`, and all 39
character-compatible first-order transforms of `h`.  The membership gate is
now closed independently: an exact rational identity proves

\[
Mh_2=\sum_{i=1}^{17} r_iF_i+r_{18}h.
\]

The degree-eight character-four Macaulay block has 85,921 monomial equations,
37,476 multiplier coordinates, and 1,355,292 nonzeros at prime 103.  Prime 103
and fifteen approximately 31-bit source primes reconstruct all 15,211 nonzero
rational multiplier coefficients under a 472-bit CRT modulus.  Prime 107 was
held out and gives `0/15211` mismatches; exact rational convolution and an
independent standard-library replay both give zero remainder.

After adjoining `h2`, that next graded discovery step has also terminated at
two large primes.  Both return a 248-term, degree-four, character-two kernel
at reported basis position 5,859.  The uniquely bounded two-prime rational
reconstruction `h3` has common denominator 4,284 and is nonzero modulo the
degree-four, character-two part of `(I,h,h2)` at both primes.

The characteristic-zero membership block is now solved.  A fixed-main
characteristic-181 lift through 54 digits reconstructs all 35,881 coordinates
with a 188-bit common denominator and 19,050 nonzero entries.  Exact replay
gives zero residuals on all 85,651 equations, an independent certificate audit
repeats that result, and an independent source-level construction proves

\[
Mh_3=\sum_{i=1}^{17}q_iF_i+q_{18}h+q_{19}h_2
\]

coefficientwise over `QQ`.  Thus `h3` is a third certified characteristic-zero
colon element.  This still does not determine the full colon or saturation.

Complete bounded censuses make the gauge obstruction explicit.  The
alternative characteristic-181 `M566` gauge has 19,762 no-candidate, 17,751
unique-zero, and 535 unique-nonzero coordinates.  The dense-pivot-swap `M70`
gauge has 19,844 no-candidate, 17,660 unique-zero, 544 unique-nonzero, and zero
ambiguous coordinates.  The pure-sparse `M70` gauge improves this to 17,758
no-candidate, 18,998 unique-zero, 1,292 unique-nonzero, and zero ambiguous
coordinates.  That is 2,086 fewer no-candidate coordinates, about a 10.5
percent bounded outcome improvement relative to the dense-swap count.  The
comparison is descriptive, not causal, because the gauges and selector sets
differ.  The final census uses characteristics 181,
2147483647, and 2147483629 as CRT sources and 173 and 197 as selectors.  Its
producer and independent receipt SHA-256 hashes are
`78d0bd0200299c1dc8fb7df7880f479613e93cf0ccca99c4741a97883c501ad7`
and
`9c0f4d0dd1f5d603e66c7e5f6f933a98300e1c25805276a090c3aa6babb38964`.
The independent standard-library audit recomputes the bounded CRT/candidate
census, not the pure-sparse polynomial identity.  None of these bounded
censuses reconstructs rational multipliers or proves or disproves a `QQ`
identity.

The exact Koszul scout now exposes 2,053 primitive integer kernel directions
with 154,939 nonzero entries.  Exact coefficientwise convolution gives
`A*K=0`; the support graph is connected on all 2,053 columns and 28,853 active
coordinates; maximum matching and rank modulo 181 are both 2,053.  The modular
rank proves independence over `QQ`.  After quotienting the frozen
characteristic-181 kernel by this span, the dimension is 114.  Over `QQ`, 114
is only an upper bound: no equality, rational quotient basis, or target
membership follows.

The independent content audit has PASS status and reproduces the primitive
mathematical content, exact syzygies, graph, matching, and rank without using
the producer as code.  It does not reproduce the producer byte-serialization
hash: the producer primitive stream is
`8a36159e01332cfc8fac9449e95001a069e440e8f7242965e756c09d15dfea76`,
whereas the independent serialization is
`bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856`.
The producer script/receipt hashes are
`39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988`
and
`6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875`;
the independent script/receipt hashes are
`eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea`
and
`15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102`.
The two earlier serialization attempts remain fail closed in their retained
receipts, with hashes
`73d11eab68fc8a6e85494f1deab36b93f773740faab856420f90b525564491e2`
and
`acd008f446fc08fee4cecac89f8ea3e6b7aec12bd65ccbdea8b97cf8c1eb680f`;
they license no conclusion.

The preregistered fixed-minor Koszul normalization route has now stopped fail
closed.  Its selected `2053 x 2053` coordinate minor has rank 2,053 at
characteristics 181 and 173, but at characteristic 197 it has 13,915 nonzero
entries, rank 2,052, and nullity one.  The first missing producer pivot and
first dependent independently audited column are both 1,983.  The independent
verifier reconstructs the minor and confirms rank 2,052 with both a local
sparse computation and Sage sparse rank.

The producer script/receipt hashes are
`fceb3a0a12ae5473bf48f72d2c37e864c6569897052c6d0f60235b0a4fe6a08f`
and
`0ba428b62f3bf8b7ccca4aded1c12e3c9659a498eac300f65036f393a54622e1`;
the independent verifier script/receipt hashes are
`deaa1d47f73d21bc7609a46d6df0474e92ea2e59c622fd6cd1c92bfb6118619d`
and
`e97001a1c7232e903192e649f440fc8bfe81277229793a9905469288dec8936f`.
The initial failed receipt remains fail-closed history with hash
`a013cdda57a74c7084a315f6fc2ab98a4663f068ff3d6d47823aee64a38c24df`.
The stop precedes the two large primes 2147483647 and 2147483629; no additional
prime, normalized artifact, or `M70` census is produced.  The final statuses
are `FAIL_CLOSED_FIXED_MINOR_SINGULAR` and
`PASS_INDEPENDENT_P197_FIXED_MINOR_SINGULARITY`.

This result closes only this selected-coordinate-minor normalization route.  It
does not invalidate a modular identity, determine full `K` rank modulo 197,
prove or disprove `QQ` membership, compute a colon or saturation, close the
secant chart, establish nullcone containment, or prove HC4.  At that point no
next residual route was announced; the later frozen quotient-section route
below supersedes that historical route-selection state.

The immediate theorem gate is now the next colon/saturation step after
adjoining `h3`.  The target-specific `QQ` replay is complete, so more p181
digits, residual quotient columns, or gauge censuses are not progress on that
gate.  The next bounded experiment should test whether `(I,h,h2,h3):M`
introduces another low-degree generator or becomes the unit ideal after
localization.  Three certified characteristic-zero colon elements still do
not determine the full colon, the saturation, secant `j2` containment,
polynomial-open closure, or HC4.

The later fixed-181 Dixon attempt does not alter that theorem gate.  Its v1
implementation freeze failed before execution; v2 stopped on wall time; and
the byte-identical packed-encoder v3 stopped on both wall and RSS before the
coefficient elimination completed.  Neither run emitted a factorization
artifact, opened `181^2`, or computed digit one.  Amendment 04 terminates the
Python dictionary/incidence factorizer family.  A successor is admissible only
if it changes the factorization method itself.  The next bounded selection
order is:

1. a read-only tool/API scout for compiled sparse prime-field or black-box
   rank/solve support, followed by a frozen prefix-scaling experiment that
   never reads `b_Z`;
2. if no compiled route has a credible memory law, an exact reduction of the
   114-dimensional Koszul quotient to a smaller target-membership interface;
3. only after one of those passes, a newly registered lift or direct `QQ`
   replay.

No further modular census, Python sparse-trace retry, relaxed Phase-I cap, or
reuse of quarantined v2/v3 integer systems counts as progress.

The read-only first item has now passed at tool and synthetic levels.  Sage
10.9 exposes sparse prime-field `rank(algorithm='linbox')`; LinBox 1.7.1 and
FFLAS-FFPACK 2.5.0 are installed with sparse elimination, Wiedemann, Block
Wiedemann, and modular solve headers.  Deterministic synthetic matrices with
the target row ratio and approximately 16.4 nonzeros per row reached 4,096
columns at 0.415 seconds and about 257 MB process RSS, with the returned rank
certified by an embedded identity block.  This does not benchmark the HC4
matrix or prove that a reusable solve is available.

That target-blind actual-coefficient benchmark has now passed after one
pre-rank row-domain correction.  The corrected v2 reconstructs the sorted
nonempty coefficient support without importing the third candidate or RHS.
Exact sparse LinBox rank is full at 4,096, 8,192, 16,384, and 35,881 columns;
the full 85,651 by 35,881 matrix has 1,354,540 nonzeros and rank 35,881 in
35.66 seconds.  The whole supervised run took 95.38 seconds at 624,082,944
bytes maximum RSS and zero swaps.  Independent byte-level CSR/matvec replay
and exact-backend inspection pass.  Rank timing alone still licenses no digit
and proves no target membership.

The next preregistered target is therefore a deterministic explicit solve at
characteristic 181.  It must freeze the target construction separately,
return all 35,881 selected coordinates, verify every one of the 85,651 rows
directly from the promoted target-free CSR and a separately rebuilt RHS, and
be independently replayed before any arithmetic modulo `181^2`.  A black-box
consistency decision without a vector is insufficient.  Failure to produce
and replay the vector inside a newly calibrated resource gate moves effort to
the 114-dimensional Koszul quotient; success licenses a separately frozen
p-adic or direct-`QQ` reconstruction design.

That sequence has now reached an exact, smaller residual interface.  A
72-digit characteristic-181 lift and exact rational replay proves `B*T=C` for
the fixed 114-dimensional quotient chart.  A separate compiled solve then
constructs the complete canonical residual section over `GF(181)`.  Its
independent source-level audit rebuilds the coefficient system and verifies
the exact direct-sum data: Koszul rank 2,053, residual rank 114, combined rank
2,167, direct raw kernel equations, zero Koszul-pivot block, and identity
residual-pivot block.

The four sparsest residual section columns, at quotient indices
`43,35,46,48`, have now been lifted through `181^4`, reconstructed over `QQ`,
and independently replayed against the integer source equations.  Their full
modular supports are `136,194,194,194`; the exact rational supports are
`135,193,193,193`; the common denominators have only 14--16 bits.  Hence the
rational source kernel has dimension at least 2,057 and its quotient by the
certified Koszul block has dimension between 4 and 114.  This is an exact
source-syzygy result, not rational target membership or a third-colon proof.

The immediate bounded target is now support-stratified expansion: lift the
next 18 residual columns whose modular supports are at most 5,000, first
through `181^2` and, only if every correction remains solvable, through
`181^4` and exact replay.  Together with the four completed columns this tests
22 of 114 residual directions at essentially the measured cost of two compiled
correction solves per digit batch.  A successful exact batch raises the
rational quotient lower bound from 4 to 22 and supplies a materially larger
space for target-height optimization; any failed correction is a decisive
local obstruction.  Blindly adding further digits to the old target vector is
not the selected route.

## Method pivot after the `j2` reduction

The original instruction to test the other seven HSOP forms one by one is no
longer the preferred next route.  Brouwer and Popoviciu's proof of the decimic
HSOP theorem supplies a smaller transfer target.  With

\[
k=(f,f)_8\in V_4,\qquad m=(f,k)_4\in V_6,\qquad q=(f,f)_6\in V_8,
\]

their Lemma 3.5 reduces high root multiplicity, after `j2=0`, to two
lower-order nullcone tests:

1. on `k!=0`, prove that `(k,m)` is in the joint nullcone of `V4+V6`;
2. on `k=0`, prove that `q` is an octavic nullform (with `q=0` handled by
   Weyman's stronger self-transvectant criterion).

This can replace seven unrelated high-degree radical calculations with two
structured lower-order gates.

There is also a direct low-degree target.  Macaulay2 1.26.06 constructs the
multiplicity-six coincident-root locus `X_(6,1,1,1,1)` exactly in about 78
seconds.  It has projective dimension five, codimension five, degree 30, and a
minimal defining ideal with generator profile

```text
degree 2: 1, degree 3: 10, degree 4: 20.
```

The replay is `scripts/probe_decimic_nullcone_crl.m2`; the receipt is
`receipts/decimic-nullcone-crl-61111-macaulay2-exact.json`.  This does not
prove normal-layer containment.  It supplies a new bounded experiment:
decompose the cubic and quartic generators into `SL2` summands and test one
highest-weight consequence per summand whenever equivariance is available.

That decomposition experiment is now exact.  The minimal-generator module is

\[
V_0[-2]\oplus(V_2\oplus V_6)[-3]
\oplus(V_0\oplus2V_4\oplus V_8)[-4].
\]

Thus the 31 coefficient generators form only seven irreducible covariant
families.  A whole-component `HighestWeights` attempt was stopped after
`348.13 s` and `4.73 GB` RSS, but direct decomposition of the 31 torus-weight
lists completed exactly in `85.29 s` and under `0.89 GB`.  The next direct-
ideal task at that stage was to extract the seven highest-weight polynomials
and test them on the normal-layer quotient, orbit by orbit; the tangent part is
closed below.

### Historical priority before cubic closure

1. Attempt the quotient-native reduction of the sole secant degree-six chart,
   with a short bounded cap and no repetition of the frozen one-hour route.
2. Extract and test the seven exact highest-weight nullcone generators on the
   normal ideal, beginning with the two cubic families after the already-known
   quadratic `j2` family.
3. If the direct ideal does not compress, run the Brouwer--Popoviciu/Weyman
   joint-nullcone falsifiers for `(k,m)` and `q`.
4. Use the Chipalkatti--Kurmann Fitting/Eagon--Northcott presentation only if
   both low-degree routes fail to produce a smaller exact interface.

The direct cubic experiment has now closed exactly on the tangent orbit.  Both
highest coordinates admit exhaustive no-unipotent top-index covers, and the
tangent unipotent stabilizer spans the full `V6` and `V2` modules.  Together
with tangent `j2`, this proves the entire degree-two and degree-three target
ideal lies in the tangent normal-layer radical.  The aggregate statement is
`TANGENT_CUBIC_NULLCONE_RADICAL_CERTIFICATE.md`.

### Historical priority after cubic closure

1. Lift `M*h3 in (I,h,h2)` over `QQ` by a target-specific character-three
   degree-eight Macaulay block.  Finite-field membership is now exact in
   several gauges but is not the characteristic-zero lift.  Preserve both
   exact earlier identities and the two-prime candidate reconstruction as
   distinct assurance layers.
2. Extract exact highest polynomials and a transvectant dictionary for the
   four quartic summands `V0+2V4+V8`.
3. Run support/torus/stabilizer analysis before Gröbner work.  Begin with the
   scalar quartic `V0`, then whichever of `V4` or `V8` has the smallest
   no-unipotent top-index cover.  Reuse stabilizer propagation only after an
   exact orbit-rank check.
4. Preserve the sole secant `j2` degree-six obstruction as a parallel open
   interface; do not transfer tangent certificates to it or infer saturation
   from two colon elements.
5. Use Brouwer--Popoviciu/Weyman or Fitting/subresultant routes if the quartic
   direct ideal does not compress.

The full success condition remains unchanged: exact full containment, an
exact counterexample, or a genuinely smaller replayable residual theorem.

### Revised priority after tangent closure

The direct tangent experiment has now closed exactly in degrees two, three,
and four.  All 31 minimal generators of `X_(6,1,1,1,1)` lie in the radical of
the tangent normal-layer ideal; see
`TANGENT_NULLCONE_ALL_GENERATORS_CERTIFICATE.md`.  This does not transfer to
the secant orbit.

The secant `V2` highest-coordinate nonvanishing locus now also has an exact
reduction over `QQ`, with matching replay over `GF(101)`.  Its torus character
permits normalization to `V2_highest=1`.  With

```text
P = 90*f0*f4 - 63*f1*f3 + 28*f2^2,
```

the normalized chart is the exhaustive union `D(P) union V(P)`.  On `D(P)`,
`f10` is eliminated and the variable count falls from 21 to 20.  On `V(P)`,
the 55 original normal equations, `P`, and `B-1` are retained.  The direct
characteristic-101 normalized calculation timed out after 120 seconds; neither
branch is proved empty, and no survivor conclusion follows from the timeout.
This proves no other `V2` coordinate and no secant nullcone containment.

1. Treat the `QQ` identity `M*h3 in (I,h,h2)` as closed and preserve its
   independent semantic certificate.  Test the next localized colon after
   adjoining `h3`, beginning with a bounded modular low-degree kernel/unit
   scan and promoting only a replayable characteristic-zero result.
2. Solve or sharply reduce both exact secant `V2` branches `D(P)` and `V(P)`;
   do not discard the boundary branch or transfer tangent certificates.
3. Compare the sparse modular certificates and their gauge failures with the
   hook coincident-root/padded-form complexes before attempting another large
   direct Gröbner cover.
4. Attempt a tangent-to-secant degeneration only with a properness or
   saturation argument that prevents counterpoints escaping through the zero
   residual line.
5. Preserve full colon equality, saturation, secant closure, polynomial-level
   orbit closure, and full HC4 as later, separate gates.

### Priority after the certified `p173^96` fourth-target lift

The fourth target now has a certified modular lift but not an exact rational
certificate.  Extending the same fixed-gauge vector by more digits is not the
default next experiment: 42 additional digits reduced the equal-height
unresolved census only from 8,961 to 8,579, and both the stable-denominator and
fixed simultaneous-LLL recoveries failed well away from exact replay.

1. Search for a lower-height gauge over `GF(173)` inside the 2,239-dimensional
   free-coordinate space, using a prospectively fixed objective measured by
   early-digit rational-reconstruction yield.  Promote only a gauge whose
   out-of-sample digit checkpoints improve materially over the current
   fixed-main census.
2. In parallel, reduce the fourth target in the exact 114-dimensional
   residual quotient and test whether the 22 already certified rational
   residual directions, together with the Koszul block, expose a rational
   target combination.  This attacks the source of height rather than merely
   purchasing more modulus.
3. Keep the two exact secant `V2` branches `D(P)` and `V(P)` as an independent
   geometric route.  A fourth colon element would still not replace the
   missing colon-equality/saturation and orbit-closure arguments.
4. Pre-register a new precision extension only if a selected new gauge or
   quotient model yields a calibrated recovery threshold.  The measured
   current-gauge rate does not justify `p96 -> pN` by itself.
