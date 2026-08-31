# HC4 double-conic five-support campaign

**Opened:** 29 August 2026  
**Status:** exact five-support theorem and all 31 tangent-orbit nullcone
generators assembled and replayed; secant `j2` reduced to one degree-six
saturation chart with an exact `Z/12` grading and an exact three-step
characteristic-zero colon-element chain; the third identity has an independently
replayed 19,050-term rational multiplier certificate and direct coefficientwise
`QQ` polynomial audit; full colon equality and saturation remain open; the
third-colon source kernel also has an independently content-audited
2,053-dimensional rational Koszul subspace, an exact rational 114-dimensional
quotient chart, an independently replayed full `2,053+114` decomposition over
`GF(181)`, and 22 independently replayed rational residual syzygies; the secant `V2`
highest-coordinate chart has an exact normalized two-branch reduction;
quartic/nullcone stretch goal active

This unit targets the first unresolved nonlinear repeated-factor row in the
audited direct-HC4 programme: clean double-conic normal-layer solutions whose
binary-decic restriction has exactly five support points.

The source baseline is Roy van Rijn's repository at commit
`3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9`. Source reconstruction and new
claims are kept separate:

1. `scripts/reconstruct_normal_layers.py` independently derives harmonic
   lifts by a closed projection recurrence and recovers the normal covariants
   in an automatically generated transvectant basis. It does not import the
   published coefficient table.
2. The five-support search will use the exact direct equations
   `det Hess(h5)=q^4*ell` in three nonzero-line charts. This is the geometric
   realization of saturation by the three coefficients of `Phi_2`.
3. Modular scouts are route evidence only. A generic theorem requires a
   characteristic-zero function-field certificate, and generic emptiness does
   not close exceptional parameter divisors.

The seven partitions are

```text
(6,1,1,1,1), (5,2,1,1,1), (4,3,1,1,1),
(4,2,2,1,1), (3,3,2,1,1), (3,2,2,2,1),
(2,2,2,2,2).
```

Roots are normalized to `0`, `infinity`, `1`, `lambda`, and `mu`, localized
away from

```text
lambda*mu*(lambda-1)*(mu-1)*(lambda-mu)=0.
```

No HC4 conclusion is claimed by opening this campaign.

## Current exact row ledger

| Partition | Exact certificate | Boundary outside the unit |
|---|---|---|
| `(6,1,1,1,1)` | `ENDPOINT_RADICAL_CERTIFICATE_61111.md` | none in the affine parameter plane |
| `(5,2,1,1,1)` | `ENDPOINT_RADICAL_CERTIFICATE_52111.md` | none in the affine parameter plane |
| `(4,3,1,1,1)` | `ENDPOINT_COVER_CERTIFICATE_43111.md` | `Delta=0` |
| `(4,2,2,1,1)` | `ENDPOINT_COVER_CERTIFICATE_42211.md` | `Delta=0` |
| `(3,3,2,1,1)` | `ENDPOINT_RADICAL_CERTIFICATE_33211.md` | `Delta=0` |
| `(3,2,2,2,1)` | `ENDPOINT_COVER_CERTIFICATE_32221.md` | `Delta=0` |
| `(2,2,2,2,2)` | `ENDPOINT_COVER_CERTIFICATE_22222.md` | `Delta=0` |

This ledger establishes the seven normalized open-locus rows only after the
individual replay receipts pass.  The collision boundary is not inferred from
generic emptiness: it is a separate dependency on the pinned
support-at-most-four result.  The consolidated theorem and dependency audit
are frozen in `FIVE_SUPPORT_THEOREM.md` and
`receipts/five-support-theorem-audit.json`.  Restrictions with at least six
support points, the full double-conic packet, and the full HC4 theorem remain
open.

The consolidated statement, proof dependency graph, assurance boundary, and
replay command are in `FIVE_SUPPORT_THEOREM.md`; machine-readable claim types
are frozen in `CLAIM_LEDGER.json`, and measured route costs are in
`RESEARCH_METRICS.md`.

The next proof-or-falsification target and its stopping rules are frozen in
`NEXT_GOAL_HSOP_NULLCONE.md`.  It begins with the two orbitwise `j2` radical
containments and generalizes to the remaining HSOP forms only if the structural
reduction succeeds.

The exact six-chart cover of `j2 != 0` is frozen in
`J2_OPEN_COVER_CERTIFICATE.md`.  The tangent-orbit half has now been closed
exactly by the six first-jet-stratum proof in
`TANGENT_J2_RADICAL_CERTIFICATE.md` and
`receipts/hsop-j2-tangent-all-strata.json`.  On the secant orbit, `r=5,...,9`
and every `r=10` branch except `f9!=0` with leading convolution degree six are
exact. The sole open chart, its modular signal, exact timeouts, and claim
boundary are frozen in `SECANT_J2_DEGREE6_OBSTRUCTION.md`. The open branch has
since been recast exactly as a homogeneous saturation and reduced by four
triangular unit-linear eliminations to 13 equations in 14 homogeneous
variables; see `SECANT_J2_HOMOGENEOUS_SATURATION_REDUCTION.md`. The saturation
membership itself remains open.  The universal support-lattice grading is now
certified as `Z direct_sum Z/12`, and a 189-term rational quartic has been
reconstructed from two large-prime kernel extractions and replayed at a held-
out prime.  Its degree-four class is nonzero modulo the original cubic span at
characteristic 101.  The identity

```text
M*h = q_1*F_1 + ... + q_17*F_17
```

is now certified exactly over `QQ` by 17 explicit degree-five multipliers
(16 nonzero, 6,301 terms).  The rational reconstruction uses five modular
certificates, passes a coefficientwise held-out replay at prime 107 with
`0/6301` mismatches, and passes an independent standard-library replay against
a frozen digest of the 17 cubics and the 362-term target.  The frozen artifact
and receipt SHA-256 hashes are respectively
`a90070b5f81c0664988d4272b9b3893385c9672089b1ea798ed8fc425028abcb`
and `551f4596db46abfb69ed5a2d2e320dece326f6f435b006cb1163e44991eae58c`.
This proves one element `h in I:M`.  After adjoining `h`, a second pair of
large-prime saturation taps exposed a 211-term character-three quartic `h2`.
The two-prime rational candidate has common denominator 648 and passed a
finite-field structural audit: it is irreducible at prime 1073741827, is a new
degree-four quotient class modulo the cubics and `h`, and is outside the span
of all 39 character-compatible first-order transforms of `h`.  More
decisively, an exact characteristic-zero certificate now proves

```text
M*h2 = q_1*F_1 + ... + q_17*F_17 + q_18*h.
```

The certificate has 15,211 nonzero rational multiplier coefficients.  It was
reconstructed from prime 103 and fifteen approximately 31-bit primes under a
fixed-free-coordinate gauge, using a 472-bit CRT modulus; the held-out prime
107 comparison has `0/15211` coefficient mismatches.  Exact rational
convolution gives zero remainder, and a separate standard-library verifier
replays the identity.  The artifact and reconstruction-receipt SHA-256 hashes
are respectively
`32ffb748a88f59c6c7a1ad98d95beb84d5e3c1cdb1422a724677fca1a4ff5d61`
and
`41ee3ee58a80f8e646dc71d6011e20543a4f06fea38a1b446ffe017ed6809690`.
These two successive colon elements do not identify either full colon,
establish `I:M^infinity=(1)`, or certify secant containment.

One bounded step beyond the exact chain is now frozen.  After adjoining
`h,h2`, the two discovery primes 1073741827 and 1073742851 returned the same
248-term, degree-four, character-two kernel support at reported basis position
5,859.  Their uniquely bounded rational reconstruction `h3` has common and
maximum denominator 4,284, maximum absolute numerator 98,020,015, and zero
source-prime residue mismatches.  Exact finite-field tests at both primes show
that its class is nonzero in the degree-four, character-two piece modulo
`(I,h,h2)`.  The candidate artifact and reconstruction-receipt SHA-256 hashes
are
`b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97`
and
`6064a2d441cc9f54f64d69085a846d09908860b53a1fac830dafc657de203616`.
The characteristic-zero gate is now closed.  A fixed-main lift through
`181^54` reconstructs all 35,881 selected coordinates; 19,050 are nonzero,
the common denominator has 188 bits, and all 85,651 exact integral equations
vanish.  A separate verifier independently replays the pair encoding, modular
reduction, and exact system.  Most importantly, an independent semantic audit
rebuilds the 19 rational generators, 38,048 multiplier descriptors, and all
85,651 degree-eight monomial rows without reading the integral target system,
and proves coefficientwise over `QQ`

```text
M*h3 = q_1*F_1 + ... + q_17*F_17 + q_18*h + q_19*h2.
```

The sparse semantic certificate has 19,050 multiplier terms and zero exact
coefficient mismatches.  This proves `h3 in (I,h,h2):M`; it does not determine
the full colon, prove `I:M^infinity=(1)`, close the secant chart, or prove HC4.
The principal receipts are
`receipts/hsop-j2-secant-r10-p181-target-exact-rational-independent-audit.json`
and
`receipts/hsop-j2-secant-r10-p181-target-exact-polynomial-identity-audit.json`.

Three independently audited bounded full-vector censuses quantify the current
lift obstruction.  In the alternative characteristic-181 gauge, the complete
`M566` strict-product census of 38,048 coordinates has 19,762 no-candidate,
17,751 unique-zero, and 535 unique-nonzero coordinates; all 581 dense-handoff
pivots fail that bound.  Exchanging those 581 pivots with 581 old free
coordinates gives the exact dense-pivot-swap modular identity, but its complete
`M70` census still has 19,844 no-candidate, 17,660 unique-zero, 544
unique-nonzero, and zero ambiguous coordinates.

At `M70`, the pure-sparse characteristic-181 gauge has a separate complete,
38,048-coordinate bounded census with 17,758 no-candidate, 18,998
unique-zero, 1,292 unique-nonzero, and zero ambiguous coordinates.  The final
census uses characteristics 181, 2147483647, and 2147483629 as CRT sources and
173 and 197 as selectors.  Relative to the dense-swap row it has 2,086 fewer
no-candidate labels, about 10.5 percent of the dense-swap count: this is a
descriptive bounded outcome improvement, not a causal comparison, because the
gauges and selector sets differ.  The census is independently reproduced in
`receipts/hsop-j2-secant-r10-third-colon-extended-sparse-full-vector-m70-independent-audit.json`.
The producer and independent receipt SHA-256 hashes are respectively
`78d0bd0200299c1dc8fb7df7880f479613e93cf0ccca99c4741a97883c501ad7`
and
`9c0f4d0dd1f5d603e66c7e5f6f933a98300e1c25805276a090c3aa6babb38964`.
The independent audit recomputes the bounded CRT/candidate census without
importing or executing the producer; it does not independently replay the
pure-sparse polynomial identity.  This is a bounded gauge improvement and
supplies neither rational reconstruction nor a `QQ` identity, colon equality,
saturation, secant closure, or an HC4 result.

The exact Koszul-syzygy scout isolates structure inside the frozen third-colon
multiplier kernel, not the missing `QQ` target identity.  It constructs 2,053
primitive integer Koszul vectors with 154,939 nonzero entries and verifies
`A*K=0` coefficientwise exactly.  Their bipartite support graph is connected,
with one component containing all 2,053 columns and 28,853 active multiplier
coordinates; the maximum matching has size 2,053.  Rank 2,053 modulo 181 proves
that all 2,053 vectors are linearly independent over `QQ`.  The quotient of the
frozen characteristic-181 kernel by this span has dimension 114, but over
`QQ` the receipt proves only the upper bound 114, not equality or a quotient
basis.

An implementation independent of the scout reconstructs the same canonically
sign-normalized primitive content, verifies the exact syzygies, connected
support profile, matching, and rank, and has status
`PASS_INDEPENDENT_CONTENT_INVARIANT_2053_KOSZUL_SYZYGIES_AND_RANK`.  It does
not reproduce the producer's undocumented primitive byte serialization:
the producer stream hash is
`8a36159e01332cfc8fac9449e95001a069e440e8f7242965e756c09d15dfea76`,
while the independent serialization is
`bf22711579d285ebcafd81b95f20b9b7193c360c360452feb6de67e74e30d856`.
Its PASS is therefore content-invariant, not byte-identical.  The frozen
producer script/receipt SHA-256 hashes are
`39a73daab21470954300b9053c716c9dc300a491a9c81648b89539369eeb9988`
and
`6b7451265043da89ee359b756ae5d8e25dd08e26ed09146d8b6e65603e0f6875`;
the independent script/receipt hashes are
`eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea`
and
`15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102`.
Earlier metadata- and primitive-serialization assertions remain retained as
fail-closed receipts, with hashes
`73d11eab68fc8a6e85494f1deab36b93f773740faab856420f90b525564491e2`
and
`acd008f446fc08fee4cecac89f8ea3e6b7aec12bd65ccbdea8b97cf8c1eb680f`;
they license no positive conclusion.  The scout proves no `QQ` target
membership, multiplier reconstruction, colon, saturation, secant closure,
nullcone containment, or HC4.

The separately preregistered fixed-minor normalization has now terminated
fail closed.  The selected `2053 x 2053` coordinate minor has rank 2,053 at
characteristics 181 and 173.  At characteristic 197 it has 13,915 nonzero
entries but rank 2,052 and nullity one; the first missing producer pivot and
first dependent independently audited column are both column 1,983.  The
independent verifier reconstructs the minor from the frozen generators and
confirms rank 2,052 by both a local sparse basis computation and Sage sparse
rank.  The stop occurred before testing 2147483647 or 2147483629; no additional
primes were used, no normalized artifact was written, and no `M70` census was
performed.  The producer status is `FAIL_CLOSED_FIXED_MINOR_SINGULAR`; the
independent verifier status is
`PASS_INDEPENDENT_P197_FIXED_MINOR_SINGULARITY`.

The final producer script/receipt SHA-256 hashes are
`fceb3a0a12ae5473bf48f72d2c37e864c6569897052c6d0f60235b0a4fe6a08f`
and
`0ba428b62f3bf8b7ccca4aded1c12e3c9659a498eac300f65036f393a54622e1`;
the independent verifier script/receipt hashes are
`deaa1d47f73d21bc7609a46d6df0474e92ea2e59c622fd6cd1c92bfb6118619d`
and
`e97001a1c7232e903192e649f440fc8bfe81277229793a9905469288dec8936f`.
The initial failed characteristic-197 receipt remains as fail-closed history
with hash
`a013cdda57a74c7084a315f6fc2ab98a4663f068ff3d6d47823aee64a38c24df`.
This result stops only this selected-coordinate-minor normalization route.  It
does not invalidate any modular identity, determine the rank of the full
Koszul matrix modulo 197, prove or disprove `QQ` membership, compute a colon or
saturation, close the secant chart, establish nullcone containment, or prove
HC4.  At that stage no next residual route was announced; the later quotient-
section route recorded below supersedes that historical route-selection state.

The subsequent fixed-181, zero-free-gauge Dixon pilot also has a precise
negative terminal.  Its algebra, binary formats, rational-reconstruction rule,
resource gates, and two replay lineages were frozen before preprocessing.  V1
ended before execution because its immutable implementation manifest omitted
two wrapper path keys.  V2 then rebuilt the canonical 85,651 by 38,048 integer
system in 22.12 external seconds, but its coefficient-only factorizer was
killed at 577.31 seconds before emitting a factorization artifact.  It remained
below the 3.5 GB cap at 3,236,954,112 bytes and reported zero swaps.

V3 prospectively tested the concrete hypothesis that boxed trace
serialization was the bottleneck, keeping every algebraic choice and the
600-second/3.5-GB gates unchanged.  Optimized encoders passed byte-identical
oracle tests, but the factorizer again stopped before its
`ELIMINATION_COMPLETE` milestone: 571.33 seconds, 3,962,667,008 bytes maximum
RSS, and zero swaps.  Thus v3 failed both wall and RSS gates before
serialization, and Amendment 04 terminates this Python sparse-factorizer
family.  No canonical Phase-I bundle or factorization index exists; no
arithmetic modulo `181^2` and no Dixon digit were computed.  The terminal
receipt is
`receipts/hsop-j2-secant-r10-third-colon-dixon-p181-phase1-v3-terminal.json`
with SHA-256
`8fc302fece32a36ad22d2fc282280debeb52b987364f4fda551532108fe47541`.
This stops an implementation family only: it gives no rank conclusion and
does not prove or disprove the `QQ` identity, a colon, saturation, secant
closure, nullcone containment, or HC4.

A subsequent read-only/synthetic tool scout found a materially different
installed route: Sage 10.9 exposes compiled sparse prime-field LinBox rank,
with Wiedemann and modular-solve support present in LinBox 1.7.1.  Target-like
synthetic full-rank matrices scaled through 4,096 columns and 160,720 nonzeros;
the largest rank calculation took 0.415 seconds at about 257 MB process RSS.
The fixed HC4 matrix and RHS were not opened, so this is only a positive route
signal.  It moves the next experiment to frozen actual-coefficient
rank/matvec scaling, not directly to a Dixon digit.

That target-blind actual-coefficient experiment has now passed after one
fail-closed interface correction.  V1 stopped before any rank because it
confused the 89,964-monomial ambient character block with the 85,651 nonempty
coefficient-support rows.  A prospectively amended v2 changed only that row
enumeration and retained the same algebra, gauge, prefixes, backend, and
600-second/3.5-GB/zero-swap gates.  Exact Sage/LinBox ranks were full at
4,096, 8,192, 16,384, and all 35,881 selected columns.  The full
85,651 by 35,881 matrix has 1,354,540 nonzeros; its exact rank took 35.66
seconds, while the entire supervised run took 95.38 seconds at 624,082,944
bytes maximum RSS and zero swaps.  An independent byte-level audit replays
all four deterministic matvec hashes and confirms exact sparse modular
Gaussian backend dispatch.  The RHS, third candidate, known solution,
augmented rank, solve, and p-adic digits were not read or computed.  This
licenses a separately frozen explicit solve; it is not target membership or
an HC4 result.  See
`receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal-v2.json` and
`receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json`.

The resulting quotient route has now produced three sharper exact interfaces.
First, a 72-digit lift followed by exact replay proves `B*T=C` for the fixed
rational 114-dimensional Koszul quotient chart; the independent audit checks
all 228,643 zero and 5,399 nonzero transition entries.  Second, a compiled
LinBox solve constructs the complete canonical residual section over
`GF(181)`, and an independent source-level audit rebuilds its 19 generators,
38,048 columns, 85,651 rows, 2,053 Koszul directions, and 114 residual
directions.  Thus the encoded modular kernel has exact dimension 2,167 and the
residual section is complementary to the Koszul block in this characteristic.

Third, the four sparsest residual columns, with full supports
`136,194,194,194`, lift through `181^4` and reconstruct exactly over `QQ`.
Their source syzygies have supports `135,193,193,193`, common denominators
`48384,24192,24192,12096`, and survive an independent 342,604-comparison
rational replay.  Their distinct residual unit coordinates prove that the
rational kernel has dimension at least 2,057 and that its quotient by the
certified Koszul block has dimension between 4 and 114.  This is not the
third-colon target identity: it proves neither that the target lies in the
source image nor that the remaining 110 residual classes lift.  The next
bounded experiment is therefore a support-ordered batch of the next 18
residual columns, not another blind target-digit extension.

The direct target nullcone has also been constructed independently with
Macaulay2's `CoincidentRootLoci` package.  The multiplicity-six locus
`X_(6,1,1,1,1)` has codimension five, degree 30, and a 31-generator defining
ideal concentrated in degrees two, three, and four.  This is an exact target-
ideal profile, not containment of the clean normal-layer locus; see
`receipts/decimic-nullcone-crl-61111-macaulay2-exact.json` and the revised
route in `NEXT_GOAL_HSOP_NULLCONE.md`.

The 31 generators decompose exactly into only seven `SL2` covariant families:
`V0` in degree two, `V2+V6` in degree three, and `V0+2V4+V8` in degree four.
The replay and receipt are
`scripts/profile_decimic_nullcone_minimal_generators_sl2.m2` and
`receipts/decimic-nullcone-crl-61111-sl2-minimal-generators-exact.json`.

On the tangent residual orbit, all 31 quadratic, cubic, and quartic generators
are now certified in the radical of the clean normal-layer ideal.  Highest-
coordinate proofs use exhaustive no-unipotent top-index covers; the tangent
stabilizer then propagates them across all seven irreducible families.  The
aggregate statement, proof graph, replay, measured resource profile, and
assurance boundary are in
`TANGENT_NULLCONE_ALL_GENERATORS_CERTIFICATE.md` and
`receipts/nullcone-tangent-all-31-generators.json`.  The secant orbit remains
separate.

On the secant orbit, the nonzero `V2` highest coordinate admits an exact torus
normalization to one.  Over `QQ`, with a matching replay over `GF(101)`,
`P=90*f0*f4-63*f1*f3+28*f2^2` gives an exact split of the normalized target chart into
`D(P)`, where `f10` is eliminated and the variable count drops from 21 to 20,
and the retained boundary branch `V(P)`.  The direct normalized calculation at
characteristic 101 timed out after 120 seconds, so neither branch is proved
empty.  This reduction does not prove the other `V2` coordinates, secant
nullcone containment, polynomial-level lifting, or HC4; see
`receipts/nullcone-v2-secant-torus-normalization.json` and
`receipts/nullcone-v2-secant-target-normalized-p101.json` and
`receipts/nullcone-v2-secant-target-normalized-f10-reduction.json`.

## Fourth localized-colon target at characteristic 173

After adjoining the three certified successive elements `h`, `h2`, and `h3`,
the next target system for `M*h4` has been constructed exactly.  The frozen
integer system has 85,688 rows, 36,587 selected coordinates, and 1,487,624
nonzero entries.  Its characteristic-173 fixed-gauge solution lifted without
row swaps through `173^96`; the 42-digit extension from `173^54` took
4,932.96 seconds and 459,046,912 bytes maximum RSS.  A separately frozen
source-independent audit replayed every stored correction and the full
integer congruence.  The producer and audit receipt SHA-256 hashes are
`72973069b837145ffaf8bf15569f2d9dd2c9e1ba2253b4b3635005ffe99f4f2d`
and
`4a2234d1b905d2039badccc946e81e40c42a37aadd9dbb73d4d093ea803ea25e`.

Exact rational recovery remains open.  The prospectively frozen `p96`
hierarchy reconstructed 28,008 of 36,587 coordinates by equal-height rational
reconstruction and left 8,579 unresolved.  A 601-coordinate denominator
stable from `p84` to `p96` failed 42,870 exact rows, and the fixed simultaneous
LLL blocks of dimensions 8, 16, 24, and 32 produced no sampled exact replay.
The terminal recovery receipt is
`artifacts/fourth-colon-p173-target-p96-exact-rational-recovery-v1/replay.json`
with SHA-256
`5454be5227dca5ca7c19bbe893f2224f2b5ccb64a5404db8f0b8143f23a9bc13`.
This exhausts only the frozen recovery hierarchy.  It neither disproves
rational membership nor proves a fourth colon identity, colon equality,
saturation, secant closure, nullcone containment, or HC4.
