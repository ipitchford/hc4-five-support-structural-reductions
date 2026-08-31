#!/usr/bin/env python3
"""Build the exact five-branch convolution cover for secant ``r=10``.

Rows 37--44 of the first normal layer are linear in ``f3,f4`` and are the
coefficient equations of ``C(t) + (f3 + f4*t) A(t)``.  On a branch where
``deg(A)=d``, existence of ``f3,f4`` forces the high coefficients of ``C``
and the pseudo-remainder of ``C`` by ``A`` to vanish.  When ``A=0``, every
coefficient of ``C`` must vanish.
"""

from __future__ import annotations

import sympy as sp

from certify_j2_secant_coefficient_slice import coefficient_slice
from certify_j2_tangent_r10_degree_branches import convolution_data
from scout_decimic_nullcone_hsop import f_coefficients
from scout_five_support import g_coefficients


BASE_INDICES = (36,) + tuple(range(45, 55))
CONVOLUTION_INDICES = tuple(range(37, 45))
branch_inverse = sp.Symbol("leadinv")
t = sp.Symbol("t")


def clear_denominators(expression: sp.Expr) -> sp.Expr:
    """Return the integral scalar multiple of a rational polynomial."""
    denominator, polynomial = sp.Poly(sp.expand(expression)).clear_denoms()
    if denominator == 0:
        raise AssertionError("zero denominator while clearing a branch equation")
    return sp.expand(polynomial.as_expr())


def secant_branch_systems():
    normal_equations, localization, full_variables, substitutions, j2 = (
        coefficient_slice(10)
    )
    _, A, C = convolution_data(normal_equations)
    A_polynomial = sp.Poly(A, t)
    if A_polynomial.degree() != 6 or sp.Poly(C, t).degree() != 7:
        raise AssertionError("the secant convolution degrees changed")

    f9 = f_coefficients[9]
    g0, g1, g2, g3 = g_coefficients[:4]
    specifications = (
        ("degree_6", {}, 2 * f9**2 + 5 * g0, 6),
        ("degree_5", {g0: -sp.Rational(2, 5) * f9**2}, 2 * f9**3 + 25 * g1, 5),
        (
            "degree_4",
            {
                g0: -sp.Rational(2, 5) * f9**2,
                g1: -sp.Rational(2, 25) * f9**3,
            },
            f9**4 + 125 * g2,
            4,
        ),
        (
            "degree_3",
            {
                g0: -sp.Rational(2, 5) * f9**2,
                g1: -sp.Rational(2, 25) * f9**3,
                g2: -sp.Rational(1, 125) * f9**4,
            },
            f9**5 + 3125 * g3,
            3,
        ),
        (
            "A_zero",
            {
                g0: -sp.Rational(2, 5) * f9**2,
                g1: -sp.Rational(2, 25) * f9**3,
                g2: -sp.Rational(1, 125) * f9**4,
                g3: -sp.Rational(1, 3125) * f9**5,
            },
            None,
            None,
        ),
    )

    branches = {}
    for name, zero_substitutions, leading_form, expected_degree in specifications:
        A_specialized = sp.Poly(sp.expand(A.subs(zero_substitutions)), t)
        C_specialized = sp.Poly(sp.expand(C.subs(zero_substitutions)), t)
        base = [
            sp.expand(normal_equations[index].subs(zero_substitutions))
            for index in BASE_INDICES
        ]
        localizer = [
            sp.expand(equation.subs(zero_substitutions)) for equation in localization
        ]
        compatibility: list[sp.Expr] = []
        auxiliary: list[sp.Expr] = []
        if leading_form is None:
            if A_specialized.as_expr() != 0:
                raise AssertionError("A does not vanish on the terminal branch")
            compatibility = [
                sp.expand(C_specialized.coeff_monomial(t**degree))
                for degree in range(8)
            ]
        else:
            if A_specialized.degree() != expected_degree:
                raise AssertionError(f"unexpected A degree on {name}")
            actual_leading = sp.factor(A_specialized.LC())
            ratio = sp.cancel(actual_leading / leading_form)
            if ratio.free_symbols or ratio == 0:
                raise AssertionError(f"the leading form on {name} changed")
            compatibility.extend(
                sp.expand(C_specialized.coeff_monomial(t**degree))
                for degree in range(expected_degree + 2, 8)
            )
            pseudo_remainder = sp.Poly(sp.prem(C_specialized, A_specialized), t)
            compatibility.extend(
                sp.expand(pseudo_remainder.coeff_monomial(t**degree))
                for degree in range(expected_degree)
            )
            auxiliary = [sp.expand(branch_inverse * leading_form - 1)]

        equations = [
            clear_denominators(equation)
            for equation in base + compatibility + localizer + auxiliary
            if equation != 0
        ]
        # The j2 localizer still contains f3 and f4.  Leaving them free makes
        # this a deliberately weaker necessary system, so unit ideal remains
        # a valid emptiness certificate.  A non-unit result would only call
        # for adding the two quotient-reconstruction equations.
        excluded = {*zero_substitutions.keys()}
        variables = tuple(
            variable
            for variable in full_variables
            if variable not in excluded
            and any(equation.has(variable) for equation in equations)
        )
        if any(equation.has(branch_inverse) for equation in equations):
            variables += (branch_inverse,)
        if any(equation.free_symbols - set(variables) for equation in equations):
            missing = set().union(*(equation.free_symbols for equation in equations)) - set(variables)
            raise AssertionError(f"unlisted variables on {name}: {sorted(map(str, missing))}")
        branches[name] = {
            "zero_substitutions": zero_substitutions,
            "leading_form": leading_form,
            "expected_degree": expected_degree,
            "A": A_specialized.as_expr(),
            "C": C_specialized.as_expr(),
            "base": [equation for equation in base if equation != 0],
            "compatibility": [equation for equation in compatibility if equation != 0],
            "localizer": [equation for equation in localizer if equation != 0],
            "auxiliary": auxiliary,
            "equations": equations,
            "variables": variables,
        }
    return A, C, substitutions, j2, branches


if __name__ == "__main__":
    A, C, substitutions, j2, branches = secant_branch_systems()
    print("A =", sp.factor(A))
    print("C degree =", sp.Poly(C, t).degree())
    for name, branch in branches.items():
        print(name, len(branch["equations"]), len(branch["variables"]))
