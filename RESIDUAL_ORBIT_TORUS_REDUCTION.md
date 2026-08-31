# Residual-orbit torus reduction

**Status:** exact normalization lemma  
**Producer:** `scripts/certify_residual_orbit_torus.py`  
**Receipt:** `receipts/residual-orbit-torus.json`

Let `A=diag(a,b)` act on the binary variables and let `M=Sym^2(A)` act on
`(x,y,z)`.  If `h'(v)=c h(Mv)`, the Hessian determinant acquires the factor

\[
c^3\det(M)^2=c^3(ab)^6,
\]

while `q(Mv)=(ab)^2q(v)`.

## Tangent residual

For residual `x`, take

\[
a=\sigma^3,\qquad b=1,\qquad c=\sigma^{-16}.
\]

Then `c^3(ab)^14a^2=1`, so the normalized equation with residual `x` is
preserved.  The decimic coefficients transform as

\[
f_i\longmapsto\sigma^{14-3i}f_i.
\]

The weights at indices `0,...,5` are `14,11,8,5,2,-1`, all nonzero.  On
each of the six reciprocal-pair charts, the left coefficient can therefore
be normalized to `1` over the algebraic closure without losing a branch.

Every term of `j2` has tangent weight `-2`.  Consequently the whole open
`j2 != 0` can instead be normalized globally to

\[
j_2=1.
\]

This is the preferred tangent reduction: it removes the Rabinowitsch inverse
and does not require six monomial charts.

For the deepest first-jet stratum it is arithmetically better to choose the
equivalent gauge `j2=-5`.  There `j2=-5*f5^2`, hence `f5^2=1`.  The remaining
torus element `sigma=-1` preserves `j2=-5` and flips `f5`, so one may set
`f5=1` over `Q` without an algebraic extension.

The tangent unipotent `(s,t)->(s,t+u*s)` gives

\[
f_9\longmapsto f_9+10u f_{10}.
\]

It can kill `f9` when `f10 != 0`, but it may simultaneously annihilate a
different coefficient selected for torus normalization.  It is therefore
not combined with coefficient normalization.  It does preserve `j2` exactly,
so after the global `j2=1` gauge the tangent problem splits exhaustively into

```text
f10 = 0,
f10 != 0 and f9 = 0.
```

The first branch has 20 remaining coefficient/correction variables.  The
second has 20 such variables plus one inverse for `f10`, hence 21 total.

Iterating the zero branch gives a sharper exhaustive decomposition.  Let `r`
be the largest index with `f_r != 0`.  Since `j2=1`, at least one of
`f5,...,f10` is nonzero, so `5 <= r <= 10`.  On

```text
f_(r+1) = ... = f10 = 0,  f_r != 0,
```

the triangular unipotent identity is

\[
f_{r-1}\longmapsto f_{r-1}+r u f_r.
\]

Thus one may also impose `f_(r-1)=0`.  The resulting six strata have,
respectively for `r=5,...,10`, `16,17,18,19,20,21` variables including the
one inverse for `f_r`.

## Secant residual

For residual `y`, take

\[
a=\tau,\qquad b=1,\qquad c=\tau^{-5}.
\]

Then `c^3(ab)^15=1`, and

\[
f_i\longmapsto\tau^{5-i}f_i.
\]

The left coefficient can be normalized on the first five reciprocal-pair
charts.  The central coefficient `f5` has weight zero, so the `f5^2` chart
must remain unnormalized.

Here every term of `j2` has weight zero.  Thus `j2` cannot be normalized by
the residual-preserving secant torus, and the six-open cover remains necessary.

This is an orbit reduction, not a proof that any normalized chart is empty.
