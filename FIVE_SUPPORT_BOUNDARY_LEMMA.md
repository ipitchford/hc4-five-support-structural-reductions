# Five-support normalization and collision boundary

**Date:** 29 August 2026  
**Status:** geometric lemma; applied after exact closure of all seven rows

## 1. Coverage of the seven rows

Let a nonzero binary decic have exactly five distinct projective roots and
root-multiplicity multiset

```text
(a,b,c,d,e),    a+b+c+d+e=10.
```

Label its roots so that these multiplicities occur in the displayed order.
The unique projective transformation carrying the first three labelled roots
to `0`, `infinity`, and `1` writes the form, up to a nonzero scalar, as

```text
s^a t^b (s-t)^c (s-lambda*t)^d (s-mu*t)^e.
```

Thus one fixed ordering for each multiplicity partition loses no geometric
case: relabelling precedes normalization.  The seven partitions of ten into
five positive parts are exactly

```text
(6,1,1,1,1), (5,2,1,1,1), (4,3,1,1,1),
(4,2,2,1,1), (3,3,2,1,1), (3,2,2,2,1),
(2,2,2,2,2).
```

The ordered distinct-root parameter space in this normalization is

```text
M_0,5 = Spec Q[lambda,mu,1/Delta],
Delta=lambda*mu*(lambda-1)*(mu-1)*(lambda-mu).
```

The third normalized point is already infinity, so every other distinct root
has a finite affine coordinate.  No distinct-five-root configuration is lost
at `lambda=infinity` or `mu=infinity`; those limits collide with the normalized
infinity-root.

## 2. The complete collision divisor

Every irreducible affine boundary component has a direct support-lowering
interpretation:

| component | merged roots | new multiplicity |
|---|---|---|
| `lambda=0` | `0` and `lambda` | `a+d` |
| `mu=0` | `0` and `mu` | `a+e` |
| `lambda=1` | `1` and `lambda` | `c+d` |
| `mu=1` | `1` and `mu` | `c+e` |
| `lambda=mu` | `lambda` and `mu` | `d+e` |

Intersections merge still more roots.  In a projective compactification,
`lambda=infinity` and `mu=infinity` merge the corresponding root with the
root of multiplicity `b`.  Hence every component of the complement of
`M_0,5` specializes to a binary decic supported on at most four points.

## 3. Clean residual-line coverage

Write the residual line as

```text
ell=A*x+B*y+C*z.
```

The three Rabinowitsch charts `A!=0`, `B!=0`, and `C!=0` cover `ell!=0`.
Consequently, for a fixed partition, exact unit ideals

```text
(I, u*A*Delta-1)=(1),
(I, u*B*Delta-1)=(1),
(I, u*C*Delta-1)=(1)
```

exclude the complete normalized five-support open, not merely a generic
fiber.  The extracted-line presentation is equivalent: `A`, `B`, and `C`
are respectively the coefficients of `x^5*z^4`, `x^4*y*z^4`, and `x^4*z^5`
in the Hessian determinant.

## 4. Boundary theorem and assurance

At source commit
`3ed4544e8bbd9f2345c43612d1f3cf94fe279dc9`, `HC4NHM15` together with
`HC4NHM18` states that every clean double-conic restriction supported on at
most four points is empty.  Therefore a complete polynomial-open unit matrix
for the seven rows would leave only strata covered by that earlier theorem.

This campaign independently reconstructed the four normal covariant layers,
but it did not independently reconstruct every support-at-most-four standard
basis or the written endpoint proof of `HC4NHM18`.  Any final theorem should
therefore distinguish:

1. the new exact polynomial-open certificates;
2. the elementary collision-boundary lemma above; and
3. reliance on the pinned author-associated support-at-most-four closure.

All seven rows have now been closed by exact endpoint/radical certificates,
which replace the initially contemplated 21-chart polynomial-open matrix.
Thus the lemma applies to the consolidated exactly-five-support theorem.  The
support-at-most-four conclusion remains an explicit dependency on the pinned
author-associated result, not an independently reconstructed claim of this
campaign.
