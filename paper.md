---
title: "Structural reductions toward the quartic Hessian conjecture in dimension four"
subtitle: "Five-support exclusion, tangent nullcone containment, and exact secant colon certificates"
author: "Anonymous"
date: "31 August 2026"
license: "CC0-1.0"
---

# Abstract

We give a computer-assisted package of exact structural reductions for a
quartic Hessian problem in dimension four.  The package does **not** prove the
quartic Hessian conjecture or the two-dimensional Jacobian conjecture.  Its
purpose is to isolate, certify and sharply reduce one repeated-factor boundary
that had remained opaque in a direct normal-form programme.

There are four principal results.  First, for a clean double-conic normal
layer, a non-zero binary-decimic restriction with exactly five distinct
projective roots cannot occur; the seven multiplicity partitions of ten into
five positive parts are treated by exact characteristic-zero certificates.
Second, on the tangent residual-quadratic orbit, the full 31-generator ideal of
the binary-decimic multiplicity-six locus lies in the radical of the clean
normal-layer ideal.  Third, on the remaining secant chart, a 
$\mathbb Z/12$-graded homogeneous reduction yields three successive exact
localized-colon identities

$$
Mh\in I,\qquad Mh_2\in (I,h),\qquad Mh_3\in (I,h,h_2),
$$

over $\mathbb Q$.  These are colon elements, not a computation of the full
colon or saturation.  Fourth, a prospectively selected batch of sixteen
minimum-source-support free columns in the next Macaulay block lifts through
$173^4$, reconstructs uniquely, and gives sixteen exact rational
source-module syzygies.  A separate audit expands all sixteen combinations to
the zero polynomial over $\mathbb Q$.

The release includes frozen claim and metrics ledgers, exact receipts,
reconstruction scripts, a 26 MB integer matrix interface, and fail-closed
negative results.  In particular, a fixed-gauge fourth target lifts through
$173^{96}$, but a preregistered exact-recovery hierarchy does not produce a
rational target identity.  The remaining secant-orbit containment, fourth
target membership, colon equality, saturation and global lifting gates are
stated explicitly.

# 1. Introduction

The Hessian-nilpotent reformulation of the Jacobian conjecture turns a global
invertibility question into a collection of algebraic constraints on a
homogeneous potential and its Hessian.  Zhao showed that the Jacobian
conjecture is equivalent to a vanishing conjecture for homogeneous quartic
Hessian-nilpotent polynomials [@zhao2004]; van den Essen and Zhao developed
further vanishing criteria [@vandenessen-zhao2007].  Dimension three is known
for gradient maps and constant Hessian determinant problems
[@debondt2012].  The dimension-four quartic boundary remains a natural first
place where repeated factors, non-trivial Hessian kernels and invariant theory
interact.

This paper reports a structural-reductions campaign inside one such
dimension-four programme.  The starting point is a pinned normal-layer
construction in Roy van Rijn's public repository
(<https://github.com/royvanrijn/jacobian-research>) at commit
`3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9`.  The present package separately
reconstructs the relevant covariant normal layers, then subjects the resulting
systems to exact algebraic tests.  Source reconstruction and new claims are
kept separate throughout.

The central geometric object is a ternary quintic $h_5$ restricted to the
Veronese conic

$$
q=xz-y^2=0,\qquad (x,y,z)=(s^2,st,t^2).
$$

The restriction is a binary decimic $f_{10}$.  A clean residual-line target
has

$$
\det\operatorname{Hess}(h_5)=q^4\ell
\tag{1.1}
$$

for a non-zero linear form $\ell$.  The repeated-factor boundary is therefore
controlled by the root support of $f_{10}$ and, on the stable locus, by the
invariant theory of binary decimics.

The results should be read at three distinct levels:

1. ordinary mathematical implications, such as the seven-partition
   exhaustion and the exact rational identities;
2. finite certificates and deterministic replay, which establish the stated
   algebraic equalities for the frozen encodings;
3. assurance claims, which remain internal and producer-coordinated unless an
   unaffiliated reconstruction is explicitly recorded.

These levels are not interchangeable.  A finite-field unit is not a
characteristic-zero theorem; a long p-adic lift is not rational
reconstruction; an exact source syzygy is not membership of an inhomogeneous
target; and internal review is not peer review.

## 1.1 Main results

The first result eliminates the exactly-five-support stratum.

**Theorem A (five-support exclusion, computer-assisted).**  Let $K$ be a
field of characteristic zero.  Let $h_5\in K[x,y,z]$, and let its non-zero
restriction $f_{10}(s,t)=h_5(s^2,st,t^2)$ have exactly five distinct roots in
$\mathbb P^1(\overline K)$.  Then there is no non-zero linear form $\ell$
for which (1.1) holds.

The next result closes the tangent half of the stable nullcone target.

**Theorem B (tangent normal-layer containment, computer-assisted).**  Let
$I_{\mathrm{tan}}$ be the characteristic-zero clean normal-layer ideal after
the tangent residual-quadratic substitution.  Let $N_6$ be the defining
ideal of the binary-decimic coincident-root locus

$$
X_{(6,1,1,1,1)}=\{L^6Q_4\}\subset
\mathbb P(\operatorname{Sym}^{10}K^2).
$$

Then

$$
N_6\subseteq \sqrt{I_{\mathrm{tan}}}.
\tag{1.2}
$$

Equivalently, every algebraic-closure point of the tangent normal-layer system
has a binary-decimic restriction with a root of multiplicity at least six.

On the secant orbit, the package proves a smaller exact chain rather than
closure.

**Theorem C (three localized-colon elements).**  For the frozen remaining
secant chart, let $I=(F_1,\ldots,F_{17})$ be the homogeneous cubic ideal and
let

$$
M=f_9f_{10}(2f_9^2+5f_{10}g_0).
$$

There are explicit rational quartics $h,h_2,h_3$ and explicit rational
multipliers satisfying

$$
\begin{aligned}
Mh   &=\sum_{i=1}^{17}q_iF_i,\\
Mh_2 &=\sum_{i=1}^{17}r_iF_i+r_{18}h,\\
Mh_3 &=\sum_{i=1}^{17}s_iF_i+s_{18}h+s_{19}h_2.
\end{aligned}
\tag{1.3}
$$

The three identities are verified coefficientwise over $\mathbb Q$.  They
show

$$
h\in I:M,\quad h_2\in(I,h):M,\quad h_3\in(I,h,h_2):M.
$$

They do not show that any displayed colon is generated by the exhibited
element, and they do not prove $I:M^\infty=(1)$.

The fourth result is new to the closing experiment of this release.

**Theorem D (sixteen rational fourth-block source syzygies,
computer-assisted).**  In the frozen degree-eight, character-two fourth
Macaulay source block, partition the 38,826 columns as $[B\mid C]$, where
$B$ consists of 36,587 characteristic-173 pivot columns.  For the
prospectively selected free coordinates

$$
46,47,57,66,68,102,155,547,763,965,966,1261,1269,1499,1699,1711,
\tag{1.4}
$$

let $C_{16}$ be the corresponding source columns under the frozen primitive
row scale.  There exists an explicit matrix
$T\in\operatorname{Mat}_{36587\times16}(\mathbb Q)$ such that

$$
BT+C_{16}=0.
\tag{1.5}
$$

The first column of $T$ has 36 non-zero entries and each remaining column has
21.  After adjoining the distinguished unit in $C_{16}$, the sixteen
source-module syzygies have supports 37 and $22^{\times15}$, respectively.

Theorem D is a source-kernel theorem.  It does not assert that the fourth
inhomogeneous target lies in the image of $B$, nor that the rational kernel
directions suffice to change the failed fixed gauge into a target solution.

## 1.2 What remains open

The following implications are *not* claimed:

- Theorem B does not transfer from the tangent residual orbit to the secant
  residual orbit.
- Theorem C does not determine the full colon or saturation.
- Theorem D does not imply rational membership of the fourth target
  $Mh_4$.
- The five-support and tangent results do not close restrictions with six or
  more distinct support points.
- The clean normal-layer results do not by themselves prove polynomial-level
  orbit closure or the global quartic Hessian conjecture.

# 2. Binary decimics and the nullcone target

Write $V_{10}=\operatorname{Sym}^{10}(K^2)$.  The nullcone of the natural
$SL_2$-action consists of binary decimics with a root of multiplicity at
least six.  Brouwer and Popoviciu give a homogeneous system of parameters of
degrees

$$
2,4,6,6,8,9,10,14
$$

for the invariant ring [@brouwer-popoviciu2010].  Their nullcone
characterisation is classical input here, not a new result.

The same target is the coincident-root locus $X_{(6,1,1,1,1)}$.  Equations
and local presentations for multiple-root loci were developed by Chipalkatti
[@chipalkatti2003] and corrected and refined by Kurmann [@kurmann2011]; Gordan
ideals provide another classical description [@weyman1993].  The conormal and
duality geometry of multiple-root loci gives a further perspective
[@lee-sturmfels2016].

An exact Macaulay2 construction in the present package gives the following
profile.

**Proposition 2.1 (target-ideal profile).**  The projective variety
$X_{(6,1,1,1,1)}$ has dimension five, codimension five and degree 30.  Its
defining ideal has 31 minimal generators, decomposing under $SL_2$ as

$$
\begin{array}{c|c|c}
\text{degree}&\text{modules}&\text{dimension}\\ \hline
2&V_0&1\\
3&V_2\oplus V_6&3+7\\
4&V_0\oplus V_4\oplus V_4\oplus V_8&1+5+5+9.
\end{array}
\tag{2.1}
$$

Thus an equivariant containment proof needs seven highest-weight families,
not 31 unrelated coordinate calculations.

# 3. Exactly five support points

Assume $f_{10}$ has exactly five distinct projective roots.  After a
projective change of binary variables, three roots may be placed at
$0,\infty,1$, while the other two have coordinates $\lambda,\mu$.  The
distinct-root condition is

$$
\Delta=\lambda\mu(\lambda-1)(\mu-1)(\lambda-\mu)\ne0.
\tag{3.1}
$$

The multiplicities form a partition of ten into five positive parts.  Up to
ordering there are seven:

$$
\begin{gathered}
(6,1,1,1,1),\ (5,2,1,1,1),\ (4,3,1,1,1),\
(4,2,2,1,1),\\
(3,3,2,1,1),\ (3,2,2,2,1),\ (2,2,2,2,2).
\end{gathered}
\tag{3.2}
$$

Every normal form is represented by

$$
s^at^b(s-t)^c(s-\lambda t)^d(s-\mu t)^e.
$$

The induced $\operatorname{Sym}^2$-action preserves the conic up to a unit,
so existence of (1.1) is invariant under the normalization.  An arbitrary
ternary quintic with the given restriction is the canonical harmonic lift
plus $qG_3$ for an arbitrary ternary cubic $G_3$.

For each partition the producer expands

$$
D=\det\operatorname{Hess}(h_5)
$$

over $\mathbb Q$, extracts the residual coordinates

$$
A=[x^5z^4]D,\qquad B=[x^4yz^4]D,\qquad C=[x^4z^5]D,
$$

and generates the 52 non-zero coefficients of

$$
D-q^4(Ax+By+Cz).
\tag{3.3}
$$

Each row certificate proves

$$
(A,B,C)\subseteq
\sqrt{I\,K[\lambda,\mu,g_0,\ldots,g_9,1/\Delta]}.
\tag{3.4}
$$

The proofs use branch-complete radical chains, endpoint staircases and
fixed-content identities.  Whenever a pivot factor is inverted, its zero fibre
is treated as a separate branch.  No exceptional component is removed without
a receipt.  Since (3.2) is exhaustive, (3.4) proves Theorem A over
$\mathbb Q$; the displayed rational identities and radical containments then
persist after base change to any characteristic-zero field.

The divisor $\Delta=0$ merges roots and therefore belongs to support at most
four.  The package records this geometric boundary separately.  A further
support-at-most-four corollary depends on the pinned source commit and is not
promoted to a separately reconstructed result here.

# 4. Tangent-orbit nullcone containment

The residual quadratic has two non-zero $SL_2$-orbits, tangent and secant.
On the tangent orbit, a torus action normalises the quadratic invariant
$j_2$ to one.  A first-jet stratification indexed by the largest non-zero
endpoint coefficient $r=5,\ldots,10$ reduces the original presentation to
six exact cases.

The $r=5$ case is closed by a two-branch compatibility determinant;
$r=6,\ldots,9$ use coefficient-normalised exact standard bases; and
$r=10$ uses a convolution identity followed by five leading-degree
branches.  All branches are over characteristic zero.

For each of the seven irreducible families in (2.1), one highest-weight
coordinate is shown to lie in $\sqrt{I_{\mathrm{tan}}}$ by an exact unit-ideal
cover.  The tangent stabiliser preserves the normal-layer ideal.  Exact
orbit-rank calculations therefore span every coordinate of each family.  The
module dimensions add to $1+10+20=31$, proving (1.2).

This is an exact computer-assisted radical-containment theorem on one residual
orbit.  It is not a numerical sample and not a transfer from one highest
weight without a stabiliser argument.  It remains internal: no unaffiliated
team has rebuilt the complete proof.

# 5. The secant obstruction and colon chain

The analogous secant $j_2$-problem closes on first-jet strata
$r=5,\ldots,9$ and on all but one $r=10$ branch.  The remaining chart has
$f_9\ne0$ and leading convolution degree six.  Four triangular unit-linear
relations eliminate $g_4,g_5,g_7,g_8$, leaving 13 equations in 14
homogeneous variables.  In the unreduced coordinates, the frozen homogeneous
form is

$$
I=(F_1,\ldots,F_{17})\subset
\mathbb Q[f_3,\ldots,f_{10},g_0,g_1,g_2,g_3,g_6,g_9]
$$

with open factor $M=f_9f_{10}(2f_9^2+5f_{10}g_0)$.  The unresolved
geometric statement is

$$
I:M^\infty=(1).
\tag{5.1}
$$

An exact Smith-form audit of within-generator exponent differences gives the
universal grading quotient

$$
\mathbb Z\oplus\mathbb Z/12.
\tag{5.2}
$$

The free factor is total degree, the auxiliary inverse has character zero,
and $M$ has character one.  This grading isolates small degree-eight
Macaulay blocks.

The three identities (1.3) were found by finite-field kernel extraction and
rational reconstruction but certified by exact characteristic-zero replay.
The first identity has 6,301 non-zero multiplier coefficients, the second
15,211 and the third 19,050.  For the third identity, a separate semantic
audit rebuilds 19 generators, 38,048 multiplier descriptors and all 85,651
degree-eight monomial rows, obtaining zero coefficient mismatches.

Successive colon elements are evidence of structure: multiplication by $M$
repeatedly returns new quartic quotient classes to the preceding ideal.  They
are not, however, a finite-generation theorem for the entire saturation.  In
particular, (5.1) does not follow from three examples.

# 6. Source kernels, quotient charts and failed routes

The third-colon source matrix contains an exact 2,053-dimensional rational
Koszul subspace.  A matching computation proves rank 2,053 over $\mathbb Q$,
and a separate 72-digit lift gives an exact rational 114-dimensional quotient
chart.  Over $\mathbb F_{181}$, the Koszul block and a canonical residual
section give a full $2,053+114$ kernel decomposition.  Several sparse
residual directions lift to exact rational syzygies.

Two negative routes are preserved because they delimit what the positive
results do not show.  A selected 2,053-square coordinate minor is singular in
characteristic 197, so that fixed-minor normalisation stops fail-closed.  A
Python Dixon factorisation family exceeds its frozen wall/RSS gates before a
factorisation artifact is produced.  Neither failure is evidence against the
underlying membership statement; each rejects only its registered
architecture.

Compiled sparse LinBox elimination changes the computational scale.  The
actual 85,651 by 35,881 third-block coefficient matrix has full selected-column
rank modulo 181, with the full rank computation taking 35.66 seconds.  This
calibrated capability motivates the multi-right-hand-side experiment in the
next section.

# 7. The fourth target and the 16-column experiment

After adjoining $h,h_2,h_3$, the next inhomogeneous target system has 85,688
rows, 36,587 selected pivot coordinates, 2,239 free coordinates and 1,487,624
selected non-zero entries.  A fixed-gauge solution lifts through $173^{96}$,
and a separate audit replays every correction and the terminal congruence.

That long lift does not reconstruct in the frozen hierarchy.  At height 96,
equal-height reconstruction resolves 28,008 coordinates and leaves 8,579
unresolved.  A stable-denominator candidate fails 42,870 exact rows, and
fixed simultaneous-LLL blocks of dimensions 8, 16, 24 and 32 fail their
sampled exact replays.  This is a negative result about one gauge and one
reconstruction family—not a proof of non-membership.

## 7.1 Prospective selection

Before computing a transfer, the 2,239 free source columns were ordered by

$$
(\text{source support},\text{global coordinate}).
$$

Supports range from 13 to 248, and 43 columns have minimum support 13.  The
first sixteen in that fixed ordering are (1.4), all in the same generator
family.  No target vector was used to choose them.

Write the global source matrix as $[B\mid C]$.  The experiment reuses the
primitive scale of each existing $B$-row.  The new $C_{16}$ coefficients
do not participate in a second row-content normalisation.  Two of the 208
scaled source entries are rational, with denominators that are units at 173.

The exporter reconstructs the complete rational row stream and verifies the
frozen generator, target, descriptor and monomial hashes.  It then compares
every primitive $B$-row against the 1,487,624-entry integer matrix.  The
observed mismatch count is zero.

## 7.2 Canonical section and p-adic lift

Over $\mathbb F_{173}$, the nullspace of $[B\mid C_{16}]$ has dimension
16.  The lower 16 by 16 block is invertible, so right-normalisation produces

$$
T_0=-B^{-1}C_{16}\pmod {173}.
$$

All 85,688 rows replay exactly.  Three Hensel correction steps reuse the same
$B$.  At height $k$, the accumulated vector is checked modulo $173^k$,
the residual is divided by $173^k$, and a shared 16-right-hand-side solve
produces the next digit.  Every augmented nullity is 16 and every replay
mismatch count is zero.

The four LinBox solves take 108.999, 106.158, 113.824 and 110.353 seconds,
respectively, for a total of 439.334 seconds.  The first two use 215.157
seconds, below the prospectively frozen 460-second promotion ceiling.  Peak
observed solver RSS is about 426 MB, with zero swaps.

## 7.3 Rational reconstruction and implementation-diverse audit

At modulus

$$
173^4=895745041,
$$

the equal numerator/denominator uniqueness bound is 21,162.  All 585,392
coordinates resolve.  Exact rational replay of $BT+C_{16}$ has zero
mismatches, proving (1.5).

The separate internal audit does not read the CSR rows.  It maps each non-zero
coordinate back to its generator and multiplier monomial, adjoins the selected
free coefficient one, and expands the resulting source combination directly
over $\mathbb Q$.  Each of the sixteen residual polynomials has zero terms.
This proves Theorem D without relying on the p-adic row encoding, subject to the
shared frozen generator definitions.

# 8. Claim architecture and remaining gates

The contribution of each result to the quartic Hessian programme is summarised
below.

| unit | exact contribution | next missing implication |
|---|---|---|
| five-support theorem | excludes every clean exactly-five-root restriction | six-or-more support and full double-conic packet |
| tangent nullcone theorem | all 31 multiplicity-six generators vanish on the tangent normal layer | secant nullcone containment |
| secant colon chain | three exact new localized-colon elements | full colon or saturation |
| fourth target lift | certified congruence through $173^{96}$ | rational target identity |
| C16 theorem | sixteen exact rational source syzygies | prove they can move the target to an exactly reconstructible gauge |
| global programme | sharper clean normal-layer frontier | polynomial-level lifting and HC4 |

The most tractable successor is now a **gauge-action test**, not another blind
precision extension: apply the exact 16-dimensional rational kernel family to
the fourth target, derive the height objective explicitly, and test whether a
rationally simple target representative exists.  That successor requires its
own preregistration because Theorem D proves kernel freedom but does not select
or certify an optimal gauge.

# 9. Reproducibility and assurance

The repository contains:

- the manuscript in Markdown and LaTeX;
- `CLAIM_LEDGER.json`, with theorem, bounded-certificate and open-gate labels;
- `RESEARCH_METRICS.md`, separating construction, solve, audit and failed-route
  timings;
- all campaign receipts and scripts needed by the included replay paths;
- the frozen integer and characteristic-173 $B$-matrix interfaces;
- the C16 p-adic digits, rational candidates and terminal receipt;
- the direct-polynomial implementation-diverse audit receipt;
- the pinned-source boundary and novelty-gate report.

The public research repository is
<https://github.com/ipitchford/hc4-five-support-structural-reductions>, and
the version DOI is <https://doi.org/10.5281/zenodo.22216400>.

The principal closing receipts are:

```text
651b952e7a228014b91d3ef28eb3954b7ba2265c2d0de302390b27e77c25eb25  p4-reconstruction.json
0f66ed6bd7182ffda4f7e4f34deca1eb80e785488b88fa66182aacd00bafd8cd  rational-candidates.json
ace9072d6e00b305350d617901e6a134fe52b8905d5447c4a6db5a14171ca5d7  direct-polynomial audit
```

The result is an anonymous, AI-assisted, unrefereed candidate.  The internal
audit uses a separate direct-polynomial implementation, but it is still
producer-coordinated and does not count as unaffiliated reproduction.
Independent rerun, independent reimplementation, formal verification,
authenticated specialist review, editorial peer review and priority
assessment remain absent or partial as stated in the machine record.

# 10. Conclusion

The repeated-factor HC4 boundary is more structured than the original large
systems suggested.  Exactly five support points are excluded; the tangent
residual orbit lies in the multiplicity-six nullcone; the remaining secant
chart carries an exact three-step colon chain; and the fourth source block has
a sparse rational 16-dimensional kernel slice found by a prospectively frozen
p-adic experiment.

The decisive missing statement is still not cosmetic.  Neither the secant
saturation nor rational fourth-target membership has been proved.  The value
of the present package is therefore a changed frontier: a diffuse family of
large symbolic systems has been replaced by exact orbitwise statements,
explicit identities, reusable rational syzygies and sharply stated next
gates.

# References

::: {#refs}
:::
