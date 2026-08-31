# Exact second-colon identity on the (j_2,r=10) secant chart

## Result

Let (I=(F_1,\ldots,F_{17})) be the frozen homogeneous cubic ideal, let
(h) be the certified first quartic, let (h_2) be the independently tapped
second quartic candidate, and let

\[
M=f_9f_{10}(2f_9^2+5f_{10}g_0).
\]

The frozen certificate proves the single characteristic-zero identity

\[
M h_2=\sum_{i=1}^{17}q_iF_i+q_{18}h,
\]

with the first seventeen multipliers homogeneous of degree five and the last
multiplier homogeneous of degree four.  Thus (M h_2\in(I,h)) over
\(\mathbb Q\).

This does **not** determine ((I,h):M^\infty), prove saturation, close the
secant chart, or establish HC4.

## Exact block and modular discovery

- Target degree/character: degree (8), character (4\pmod {12}).
- Multiplier coordinates: 37,476.
- Monomial equations: 85,921.
- Matrix incidences: 1,355,292 at (p=103).
- Discovery solve: 35,423 pivots, 2,053 free coordinates, 15,043 nonzero
  coordinates, exact remainder zero.
- Independent (p=103) reconstruction: exact remainder zero without importing
  the producer or elimination code.
- The fixed-free gauge reduced subsequent solve time from 157.6 seconds to
  approximately 6--11 seconds after block construction.

The (p=103) certificate is
`artifacts/j2-secant-r10-second-colon-identity-sparse-macaulay-retry-v3-p103.json`
with SHA-256
`3adf88c17f6308d0ae5f1bc96e20cd9332146c7259404b1e0d1bfc1da1e41cb2`.

## Rational reconstruction and exact replay

The fixed-free representative was reconstructed from (p=103) and fifteen
31-bit primes.  The CRT modulus has 472 bits and the symmetric uniqueness
radius has 236 bits.  The recovered coefficient heights are:

- maximum numerator: 142 bits,
  (4361149698997496204601843075014067511274003);
- maximum denominator: 116 bits,
  (61776803775171319112508656025600000);
- strict product uniqueness:
  (2\max|a|\max b < M_{\mathrm{CRT}}).

The exact rational replay has 15,211 multiplier terms across all 18 nonzero
multipliers and reproduces the 412-term target with zero remainder.  The
excluded prime (p=107) supplies a held-out test: 15,211 coefficient
comparisons, zero mismatches.

The characteristic-zero artifact is
`artifacts/j2-secant-r10-second-colon-identity-qq.json`, SHA-256
`32ffb748a88f59c6c7a1ad98d95beb84d5e3c1cdb1422a724677fca1a4ff5d61`.
The reconstruction receipt is
`receipts/hsop-j2-secant-r10-second-colon-identity-qq-reconstruction.json`,
SHA-256
`41ee3ee58a80f8e646dc71d6011e20543a4f06fea38a1b446ffe017ed6809690`.

A standard-library verifier, importing neither the producer nor any computer
algebra system, pins the 18-generator problem digest and replays every rational
coefficient.  It passed in 1.78 seconds with zero mismatches.  Its receipt is
`receipts/hsop-j2-secant-r10-second-colon-identity-qq-independent-replay.json`,
SHA-256
`dbb894781b206e07988a5a63e7a5c0a676e72624bf37cc2d05f141d45624fa82`.

## Calibrated negative telemetry

Five-prime and six-prime CRT attempts were insufficient for rational
reconstruction; they failed closed at coordinates 16 and 21.  At a 224-bit
modulus (112-bit symmetric radius), reconstruction advanced to coordinate 220,
with already recovered heights of 106 numerator bits and 86 denominator bits.
These no-decision events are retained in separate receipts and explain why the
final reconstruction used fifteen large primes.

## Assurance boundary

The result is an exact, independently replayed rational identity for one
displayed generator.  It is stronger than a modular sample or rational
candidate, but weaker than a computation of the residual colon, the saturated
ideal, the secant-chart closure, or HC4.
