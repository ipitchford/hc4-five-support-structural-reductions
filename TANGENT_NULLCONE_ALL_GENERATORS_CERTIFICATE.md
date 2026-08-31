# Tangent normal-layer containment in the multiplicity-six nullcone

## Statement

Let `I_tangent` be the characteristic-zero clean normal-layer ideal after the
tangent residual-orbit substitution.  Let `N_6` be the defining ideal of the
binary-decimic coincident-root locus

\[
X_{(6,1,1,1,1)}=\{L^6Q_4\}\subset \mathbf P(\operatorname{Sym}^{10}).
\]

The exact computer-assisted calculation proves

\[
N_6\subseteq \sqrt{I_{\mathrm{tangent}}}.
\]

Equivalently, every algebraic-closure point of the tangent normal-layer
system has a binary-decimic restriction with a root of multiplicity at least
six.

## Proof graph

Macaulay2's `CoincidentRootLoci` construction gives a defining ideal with 31
minimal generators.  Exact `SL2` profiling decomposes them as

\[
\begin{array}{c|c|c}
\text{degree}&\text{modules}&\text{dimension}\\ \hline
2&V_0&1\\
3&V_2\oplus V_6&3+7\\
4&V_0\oplus V_4\oplus V_4\oplus V_8&1+5+5+9.
\end{array}
\]

For each of the seven modules, an exact characteristic-zero unit-ideal cover
proves that one highest-weight coordinate lies in
`sqrt(I_tangent)`.  The tangent stabilizer preserves the normal-layer ideal;
an exact orbit-rank calculation then spans every coordinate of the module.
The dimensions add to `1 + 10 + 20 = 31`.

The aggregate receipt verifies the exact status and characteristic of every
family receipt, checks the dimension profile, and records the SHA-256 of each
input.  Replay it with

```bash
python3 scripts/audit_nullcone_tangent_all_generators.py
```

The resulting status is

```text
PASS_EXACT_TANGENT_ALL_31_GENERATORS_RADICAL_CONTAINMENT
```

## Cover and resource profile

The non-top cells use the exhaustive top-index cover `r=5,...,9`.  The top
cell `r=10` is split by the convolution polynomial into `A=0` and degrees
zero through six.  Degree six uses the top-coefficient torus gauge; the other
branches use target localization.

For the final `V0` and `V8` families, exact non-top solver times ranged from
about `0.30 s` to `63.42 s`, with maximum immediate-scope RSS from about
`20.7 MB` to `419.2 MB`.  On the top cell, the exact degree-six branches took
`26.71 s` and `26.02 s`, each at about `719.9 MB`.  Their modular screens took
about `72 s` and reached roughly `1.02--1.06 GB`.  These are measured replay
figures, not forecasts; process-level counters can omit delegated descendants
as stated in the individual receipts.

## Primary evidence

- `receipts/nullcone-tangent-all-31-generators.json`
- `receipts/hsop-j2-tangent-all-strata.json`
- `receipts/nullcone-v2-tangent-stabilizer-span.json`
- `receipts/nullcone-v6-tangent-stabilizer-span.json`
- `receipts/nullcone-v0-tangent-stabilizer-span.json`
- `receipts/nullcone-v4-1-tangent-stabilizer-span.json`
- `receipts/nullcone-v4-2-tangent-stabilizer-span.json`
- `receipts/nullcone-v8-tangent-stabilizer-span.json`

The quadratic proof is detailed in `TANGENT_J2_RADICAL_CERTIFICATE.md`; the
cubic proof is detailed in `TANGENT_CUBIC_NULLCONE_RADICAL_CERTIFICATE.md`.

## Assurance boundary

This is an exact characteristic-zero, computer-assisted result with
replayable hashed receipts.  It has not yet received an unaffiliated
reconstruction, formal proof, or peer review.  It proves only the tangent
residual orbit on the clean normal layer.  The secant residual orbit,
polynomial-level lifting, full-family closure, HC4, and the quartic Hessian
conjecture remain open.
