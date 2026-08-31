# Exact six-open cover for `j2 != 0`

**Status:** exact characteristic-zero algebraic reduction  
**Producer:** `scripts/certify_j2_open_cover.py`  
**Receipt:** `receipts/j2-open-cover.json`

The independently reconstructed quadratic HSOP invariant has transvectant
content `10450944000`.  After removing that content, its primitive form is

\[
j_2=2520f_0f_{10}-252f_1f_9+56f_2f_8-21f_3f_7
    +12f_4f_6-5f_5^2.
\]

Let the six displayed monomials without coefficients be

\[
m_0=f_0f_{10},\ m_1=f_1f_9,\ m_2=f_2f_8,\
m_3=f_3f_7,\ m_4=f_4f_6,\ m_5=f_5^2.
\]

If every `m_i` vanishes at a characteristic-zero point, then the displayed
identity gives `j2=0` at that point.  Equivalently,

\[
D(j_2)\subseteq\bigcup_{i=0}^{5}D(m_i).
\]

Thus the `j2 != 0` locus on each residual-quadratic orbit is covered by six
coefficient-pair charts.  Every chart calculation must retain the localization
by `j2`; localization by `m_i` alone includes irrelevant points at which the
six terms cancel.

The same cover is valid in characteristics outside `{2,3,5,7}`.  Those four
primes are exactly the prime divisors occurring among the six primitive
coefficients; the planned scouts use much larger primes.

This certificate proves the cover only.  It does not prove any chart empty,
does not establish `j2` radical membership, and does not establish HSOP
nullcone containment.
