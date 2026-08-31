# Novelty-gate report: HC4 decimic normal-layer nullcone containment

**Search date:** 30 August 2026  
**Researcher/agent:** Codex  
**Corpus boundary:** arXiv and primary journal records; public GitHub results indexed by web search; pinned campaign source  
**Intended contribution unit:** restricted radical-containment theorem and proof bridge

## 1. Frozen claim

### Exact statement

For the clean double-conic normal-layer ideal on the binary-decimic
restriction, prove that every clean solution lies in the binary-decimic
nullcone. Equivalently, prove the positive-degree invariant ideal is contained
in the radical of the clean normal-layer ideal after residual-line saturation.

### Exclusions

The result is not established by one HSOP invariant, a finite-field unit, a
generic calculation, or an incidence parameterization of the nullcone. It is
not a proof of full HC4.

### Permitted claim language before the gate

"Campaign-specific nullcone containment is open; several classical
descriptions of the target nullcone supply alternative proof architectures."

## 2. Normalisation and translation table

| Campaign object | Classical object | Transformation checked |
|---|---|---|
| binary decimic `f0,...,f10` | `V_10=Sym^10(K^2)` | coefficient order frozen in the HSOP reconstruction receipt |
| all positive invariants vanish | `f` is an `SL_2` nullform | Hilbert-Mumford criterion cited by Brouwer-Popoviciu |
| nullform | `f=L^6 Q_4` for some linear form `L` | degree ten and multiplicity strictly greater than five |
| eight campaign HSOP forms | Brouwer-Popoviciu Theorem 3.1 | formulas independently reconstructed in the campaign |
| residual `x` / `y` | tangent / secant binary-quadratic orbit | exact orbit and torus receipt |

## 3. Fingerprints

### Invariants and covariants

The eight-form fingerprint is
`j2, j4, A6, C6, j8, j9, j10, j14+A14`. The lower-order covariant fingerprint
used in the source proof is `k=(f,f)_8`, `m=(f,k)_4`, `q=(f,f)_6`, together
with nullform tests on `V_4`, `V_6`, and `V_8`.

### Geometric fingerprint

The target is the multiplicity-six padded-form variety
`{L^6 Q_4}` inside `P(Sym^10 K^2)`, also described as a coincident-root locus,
a Hilbert-Mumford unstable stratum, and a Gordan/multiplicity ideal.

### Current computational fingerprint

The clean normal system has 55 coefficient equations. Tangent `j2` radical
containment is exact. Secant first-jet strata `r=5,...,9` are exact; the only
unresolved `j2` chart is `r=10`, `f9!=0`, leading degree six.

## 4. Alias map

| Invariant theory | Projective geometry | Commutative algebra | Computational route |
|---|---|---|---|
| binary-decimic nullcone | multiplicity-six coincident-root locus | Gordan or multiplicity ideal | transvectant radical membership |
| unstable binary form | padded form `L^6 Q_4` | Fitting ideal of the incidence normalization | Eagon-Northcott complex |
| common high-multiplicity root | root-incidence bundle | local generators with a Jacobian unit block | regular-chain or chart elimination |

## 5. Search log

| Date | Corpus/database | Query family | Results inspected | Consequence |
|---|---|---|---|---|
| 2026-08-30 | arXiv | binary decimic nullcone HSOP covariants | Brouwer-Popoviciu, arXiv:1002.1008 | collision for the HSOP and nullcone criterion; new route via Lemmas 3.4-3.6 |
| 2026-08-30 | arXiv/journal | coincident-root ideal binary forms | Chipalkatti, arXiv:math/0110224 | Eagon-Northcott/Fitting and covariant-complex route |
| 2026-08-30 | arXiv | local generators coincident-root normalization | Kurmann, arXiv:1108.4532 | corrected scheme-theoretic construction and local Jacobian unit block |
| 2026-08-30 | DOI/journal | Gordan ideals binary forms Weyman | DOI 10.1006/jabr.1993.1225 | self-transvectant-to-high-root lemma used by the decimic proof |
| 2026-08-30 | journal metadata | invariant equations decisive graphs | DOI 10.1007/s00013-004-1191-z | combinatorial covariant generators for prescribed root multiplicities |
| 2026-08-30 | GitHub web index | binary decimic, nullcone, coincident root, transvectant | Sage invariant-theory sources and the pinned `jacobian-research` repository | no ready campaign-specific containment implementation located |
| 2026-08-30 | Macaulay2 docs and exact local replay | `CoincidentRootLoci`, degree-ten partition `(6,1,1,1,1)` | package docs and Macaulay2 1.26.06 | exact target ideal computed: codimension 5, degree 30, 31 generators in degrees 2, 3, 4 |
| 2026-08-30 | arXiv | multi-polynomial subresultants, parametric root multiplicity | Hong--Yang (2021), Wang--Yang (2023) | unmined determinant route for eliminating the common root of the first six Hasse derivatives |
| 2026-08-30 | arXiv/journal | duality and tangent geometry of multiple-root loci | Katz (2002), Lee--Sturmfels (2015) | possible conormal/tangent bypass for orbitwise containment; lower priority than the direct ideal |
| 2026-08-30 | Macaulay2 docs | `HighestWeights`, equivariant resolutions | current package documentation | concrete route to compress 31 coefficient generators to irreducible `SL2` summands |

## 6. Verified collisions or bridges

1. **Collision: nullcone and HSOP statement.** Brouwer-Popoviciu already prove
   that the eight displayed invariants define the binary-decimic nullcone and
   recall that this nullcone consists exactly of forms with a root of
   multiplicity at least six.
2. **Bridge candidate: normal layers to covariant nullforms.** Their proof
   reduces through nullform conditions on the quartic `k`, sextic `m`, and
   octavic `q`, using three normal forms for `k`. No source inspected here
   states that the clean normal-layer ideal forces those hypotheses.
3. **Bridge candidate: normal layers to the coincident-root Fitting ideal.**
   Chipalkatti and Kurmann provide structured equations for the target
   root-incidence locus. No inspected source identifies those equations with
   consequences of the clean normal-layer ideal.
4. **New exact software bridge: direct target ideal.** The current
   `CoincidentRootLoci` package constructs the defining ideal of
   `X_(6,1,1,1,1)` exactly.  A clean replay found one quadratic, ten cubic,
   and twenty quartic minimal generators in `77.54 s`.  This does not prove
   containment, but it replaces an abstract target by a low-degree exact
   presentation.
   The minimal generators further decompose as `V0` in degree two,
   `V2+V6` in degree three, and `V0+2V4+V8` in degree four.  Hence only seven
   highest-weight families need be tested if the normal-layer formulation is
   used equivariantly.
5. **New determinant bridge: Hasse derivatives.** A multiplicity-six root is
   a common root of the first six Hasse derivatives. Modern multi-polynomial
   subresultants give coefficient formulas for parametric multiplicity and
   may yield a compact determinantal certificate on the normal-layer slice.
   This route has not yet been tested and must be checked for extraneous
   distributed-multiplicity components.

## 7. Negative evidence and missingness audit

The Weyman full text and the 2004 decisive-graph paper were identified through
primary bibliographic records but not fully inspected in this pass. GitHub code
search coverage is limited to publicly indexed results. No author enquiry was
made. Therefore absence of a campaign-specific theorem is bounded search
evidence, not a priority claim.

## 8. Outcome by contribution unit

| Unit | Outcome | Confidence | Allowed wording | Forbidden wording |
|---|---|---:|---|---|
| Nullcone/HSOP statement | COLLISION | 0.99 | classical theorem of Brouwer-Popoviciu/Hilbert | new characterization |
| Normal-layer containment statement | BOUNDED UNCERTAINTY | 0.75 | not found in this bounded search | new or first theorem |
| Covariant-nullform proof bridge | BRIDGE candidate | 0.80 | promising unmined transfer mechanism | established implication |
| Fitting/Eagon-Northcott bridge | BRIDGE candidate | 0.70 | structured alternative worth a bounded test | known solution |
| Replayable campaign certificates | CLEAR within corpus | 0.85 | independently generated computation artefacts | historically first computation |

## 9. Decision

**BOUNDED UNCERTAINTY**, now with three concrete routes. First decompose and
test the low-degree direct nullcone ideal, because exact construction is
already tractable. Next test the Brouwer-Popoviciu/Weyman low-covariant
implications. Test multi-polynomial subresultants or the Fitting-complex route
only if those two fail their bounded membership falsifiers.

## 10. Rerun triggers

- a low-degree covariant is found in the radical of both residual-orbit ideals;
- a Gordan-ideal generator reduces identically modulo the normal equations;
- the multiplicity-six Fitting minors acquire a sparse determinantal form on
  the normal-layer slice;
- the remaining secant `j2` branch closes and exposes a simpler quotient;
- a published computation of the degree-ten multiplicity-six ideal is found.
- the direct ideal's degree-three and degree-four generators decompose into
  only a few highest-weight summands;
- a multi-polynomial subresultant specializes to a sparse determinant on the
  normal-layer slice.

## Primary sources

- Brouwer, A. E., & Popoviciu, M. (2010). *The invariants of the binary
  decimic*. https://arxiv.org/abs/1002.1008
- Chipalkatti, J. V. (2003). *On equations defining coincident root loci*.
  https://arxiv.org/abs/math/0110224
- Kurmann, S. (2011). *Some remarks about equations defining coincident root
  loci*. https://arxiv.org/abs/1108.4532
- Weyman, J. (1993). *Gordan ideals in the theory of binary forms*.
  https://doi.org/10.1006/jabr.1993.1225
- Chipalkatti, J. V. (2004). *Invariant equations defining coincident root
  loci*. https://doi.org/10.1007/s00013-004-1191-z
- Hong, H., & Yang, J. (2021). *Subresultant of several univariate
  polynomials*. https://arxiv.org/abs/2112.15370
- Wang, W., & Yang, J. (2023). *Two variants of Bezout subresultants for
  several univariate polynomials*. https://arxiv.org/abs/2304.00262
- Katz, G. (2002). *How tangents solve algebraic equations, or a remarkable
  geometry of discriminant varieties*. https://arxiv.org/abs/math/0211281
- Lee, H., & Sturmfels, B. (2015). *Duality of multiple root loci*.
  https://arxiv.org/abs/1508.00202
