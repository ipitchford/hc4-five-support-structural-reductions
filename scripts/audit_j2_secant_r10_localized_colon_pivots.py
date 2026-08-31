#!/usr/bin/env sage-python
"""Audit the first secant colon quartic after the four ``D(M)`` pivots.

This is a reduction audit, not a proof that the reconstructed quartic belongs
to ``I:M`` over characteristic zero.  It independently reconstructs the
quartic coefficients, replays the held-out coefficient stream, and then works
exactly over ``QQ`` in the localized triangular quotient.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path

import sympy as sp
from sage.all import PolynomialRing, QQ

from audit_j2_secant_r10_degree6_homogeneous_reduction import PIVOT_DATA
from replay_j2_secant_r10_colon_kernel import (
    expression_from_rationals,
    reconstruct_coefficients,
)
from scout_j2_secant_r10_homogeneous_saturation import (
    RETAINED_NORMAL_INDICES,
    homogeneous_saturation_system,
)


RECONSTRUCTION_PRIMES = (1073741827, 1073742851)
HELD_OUT_PRIME = 1073741789


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_polynomial_hash(polynomial) -> str:
    rows = []
    for exponents, coefficient in sorted(polynomial.dict().items()):
        rows.append(
            [
                list(map(int, exponents)),
                str(coefficient.numerator()),
                str(coefficient.denominator()),
            ]
        )
    payload = json.dumps(rows, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    candidate_paths = [
        campaign
        / "research"
        / f"j2_secant_r10_colon_kernel_candidate_p{prime}.json"
        for prime in RECONSTRUCTION_PRIMES
    ]
    reconstruction_receipt = (
        campaign
        / "receipts"
        / "hsop-j2-secant-r10-degree6-first-colon-kernel-qq-reconstruction.json"
    )

    equations, sympy_variables, sympy_u, _ = homogeneous_saturation_system()
    primes, modulus, rational_terms = reconstruct_coefficients(candidate_paths)
    if tuple(primes) != RECONSTRUCTION_PRIMES:
        raise AssertionError("unexpected reconstruction primes")
    h_sympy = expression_from_rationals(rational_terms, sympy_variables)

    frozen_reconstruction = json.loads(
        reconstruction_receipt.read_text(encoding="utf-8")
    )
    held_out = frozen_reconstruction["held_out_validation"]
    if int(held_out["characteristic"]) != HELD_OUT_PRIME:
        raise AssertionError("unexpected held-out characteristic")
    held_out_terms = {
        tuple(map(int, row["exponents"])): int(row["coefficient"])
        for row in held_out["terms"]
    }
    if held_out_terms.keys() != rational_terms.keys():
        raise AssertionError("held-out support differs from reconstructed support")
    held_out_mismatches = []
    for exponents, coefficient in rational_terms.items():
        reduced = (
            int(coefficient.numerator())
            * pow(int(coefficient.denominator()), -1, HELD_OUT_PRIME)
        ) % HELD_OUT_PRIME
        if reduced != held_out_terms[exponents] % HELD_OUT_PRIME:
            held_out_mismatches.append(exponents)
    if held_out_mismatches:
        raise AssertionError("held-out coefficient replay failed")

    ring = PolynomialRing(QQ, [str(variable) for variable in sympy_variables])
    variables = ring.gens()
    positions = {str(variable): index for index, variable in enumerate(variables)}

    def convert(expression: sp.Expr):
        polynomial = sp.Poly(expression, *sympy_variables, domain=sp.QQ)
        return ring(
            {
                tuple(map(int, exponents)): QQ(int(coefficient.p))
                / QQ(int(coefficient.q))
                for exponents, coefficient in polynomial.terms()
            }
        )

    u = convert(sympy_u)
    h = convert(h_sympy)
    indexed_equations = {
        index: convert(equation)
        for index, equation in zip(RETAINED_NORMAL_INDICES, equations, strict=True)
    }

    def substitute_with_u_denominators(polynomial, solutions):
        """Return ``(N,P)`` for a substitution equal to ``N/u^P``."""

        data = [
            (positions[str(variable)], numerator, power)
            for variable, (numerator, power) in solutions.items()
        ]
        if not data:
            return polynomial, 0
        terms = polynomial.dict()
        common_power = max(
            sum(power * exponents[position] for position, _, power in data)
            for exponents in terms
        )
        power_cache = {
            (position, exponent): numerator**exponent
            for position, numerator, _ in data
            for exponent in range(
                1, max(term[position] for term in terms) + 1
            )
        }
        numerator = ring.zero()
        for exponents, coefficient in terms.items():
            denominator_power = sum(
                power * exponents[position] for position, _, power in data
            )
            residual_exponents = list(exponents)
            summand = ring(coefficient) * u ** (common_power - denominator_power)
            for position, _, _ in data:
                exponent = residual_exponents[position]
                residual_exponents[position] = 0
                if exponent:
                    summand *= power_cache[(position, exponent)]
            numerator += summand * ring.monomial(*residual_exponents)
        return numerator, common_power

    solutions = {}
    pivot_audits = []
    for normal_index, sympy_pivot, scalar in PIVOT_DATA:
        pivot = variables[positions[str(sympy_pivot)]]
        equation_numerator, previous_power = substitute_with_u_denominators(
            indexed_equations[normal_index], solutions
        )
        pivot_coefficient = equation_numerator.polynomial(pivot)[1]
        expected_coefficient = QQ(scalar) * u ** (previous_power + 1)
        if pivot_coefficient != expected_coefficient:
            raise AssertionError(f"pivot coefficient mismatch at {normal_index}")
        remainder = equation_numerator.subs({pivot: 0})
        solution_numerator = -remainder / QQ(scalar)
        solution_power = previous_power + 1
        removed_u_powers = 0
        while solution_power and solution_numerator.mod(u) == 0:
            solution_numerator //= u
            solution_power -= 1
            removed_u_powers += 1
        if (
            QQ(scalar)
            * u ** (previous_power + 1 - solution_power)
            * solution_numerator
            + remainder
            != 0
        ):
            raise AssertionError(f"pivot identity failed at {normal_index}")
        solutions[pivot] = (solution_numerator, solution_power)
        pivot_audits.append(
            {
                "normal_index": normal_index,
                "pivot": str(pivot),
                "formula": f"{pivot}=A_{pivot}/u^{solution_power}",
                "scalar_before_normalization": scalar,
                "denominator_u_power": solution_power,
                "removed_common_u_powers": removed_u_powers,
                "numerator_term_count": len(solution_numerator.dict()),
                "numerator_total_degree": int(solution_numerator.total_degree()),
                "numerator_sha256": canonical_polynomial_hash(solution_numerator),
                "exact_pivot_identity_verified": True,
            }
        )

    residual_numerator, residual_power = substitute_with_u_denominators(h, solutions)
    removed_residual_u_powers = 0
    while residual_power and residual_numerator.mod(u) == 0:
        residual_numerator //= u
        residual_power -= 1
        removed_residual_u_powers += 1

    denominator_lcm = math.lcm(
        *(int(coefficient.denominator()) for coefficient in residual_numerator.dict().values())
    )
    integer_scaled = residual_numerator * denominator_lcm
    integer_content = math.gcd(
        *(abs(int(coefficient)) for coefficient in integer_scaled.dict().values())
    )
    primitive = integer_scaled / integer_content
    primitive_scalar = QQ(integer_content) / QQ(denominator_lcm)
    if primitive.leading_coefficient() < 0:
        primitive = -primitive
        primitive_scalar = -primitive_scalar
    if residual_numerator != primitive_scalar * primitive:
        raise AssertionError("primitive residual normalization failed")

    factorization = primitive.factor()
    irreducible = (
        factorization.unit() == 1
        and len(factorization) == 1
        and factorization[0][0] == primitive
        and factorization[0][1] == 1
    )
    if not irreducible:
        raise AssertionError("residual numerator unexpectedly factors")

    minimum_exponents = [
        min(exponents[index] for exponents in primitive.dict())
        for index in range(ring.ngens())
    ]
    monomial_content = {
        str(variable): exponent
        for variable, exponent in zip(variables, minimum_exponents, strict=True)
        if exponent
    }
    localized_divisibility = {
        "f9": residual_numerator.mod(variables[positions["f9"]]) == 0,
        "f10": residual_numerator.mod(variables[positions["f10"]]) == 0,
        "u": residual_numerator.mod(u) == 0,
    }
    if any(localized_divisibility.values()) or monomial_content:
        raise AssertionError("an unremoved localized or monomial factor remains")

    eliminated = {str(row[1]) for row in PIVOT_DATA}
    remaining_variables = [
        str(variable) for variable in variables if str(variable) not in eliminated
    ]
    source_paths = candidate_paths + [reconstruction_receipt, script_path]
    result = {
        "schema": "hc4.decimic-j2-secant-r10-localized-colon-pivots.v1",
        "status": "PASS_EXACT_LOCALIZED_COLON_PIVOT_REDUCTION_NO_SPLIT",
        "assurance": "exact coefficient replay and symbolic identities over QQ",
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*u nonzero",
        "u": str(u),
        "reconstruction": {
            "primes": list(primes),
            "crt_modulus": str(modulus),
            "quartic_term_count": len(h.dict()),
            "quartic_total_degree": int(h.total_degree()),
            "quartic_sha256": canonical_polynomial_hash(h),
        },
        "held_out_validation": {
            "characteristic": HELD_OUT_PRIME,
            "role": "excluded from coefficient reconstruction",
            "support_matches": True,
            "term_count": len(held_out_terms),
            "coefficient_mismatch_count": len(held_out_mismatches),
            "all_coefficients_replay": not held_out_mismatches,
            "source_stream_sha256": held_out["sha256"],
        },
        "pivot_order": [str(row[1]) for row in PIVOT_DATA],
        "pivot_audits": pivot_audits,
        "localized_identity": f"h_after_pivots=N/u^{residual_power}",
        "residual": {
            "denominator_u_power": residual_power,
            "removed_common_u_powers": removed_residual_u_powers,
            "remaining_variable_count": len(remaining_variables),
            "remaining_variables": remaining_variables,
            "numerator_term_count": len(residual_numerator.dict()),
            "numerator_total_degree": int(residual_numerator.total_degree()),
            "numerator_sha256": canonical_polynomial_hash(residual_numerator),
            "primitive_integer_scalar": str(primitive_scalar),
            "primitive_integer_term_count": len(primitive.dict()),
            "primitive_integer_total_degree": int(primitive.total_degree()),
            "primitive_integer_sha256": canonical_polynomial_hash(primitive),
            "monomial_content": monomial_content,
            "localized_factor_divisibility": localized_divisibility,
            "factorization_over_QQ": "irreducible",
            "irreducible_factor_count": 1,
            "factorization_exactly_verified": irreducible,
        },
        "route_decision": {
            "materially_smaller_localized_generator": False,
            "useful_factor_branch_split": False,
            "reason": (
                "The 189-term quartic becomes an irreducible 3883-term degree-16 "
                "numerator after clearing the minimal u^6 denominator, and no "
                "f9, f10, u, or monomial factor can be removed on D(M)."
            ),
            "recommended_use": (
                "Retain h before triangular pivot substitution as a candidate "
                "colon generator; do not use its expanded localized numerator as "
                "the next saturation representation."
            ),
        },
        "source_sha256": {
            str(path.relative_to(campaign)): sha256(path) for path in source_paths
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "This receipt proves coefficient reconstruction/held-out replay and "
            "the displayed QQ pivot-substitution identity and irreducibility. It "
            "does not prove M*h lies in I over QQ, describe I:M, decide the "
            "saturation, close the secant chart, or prove HC4."
        ),
    }
    output = (
        campaign
        / "receipts"
        / "hsop-j2-secant-r10-localized-colon-pivot-reduction.json"
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "pivot_profiles": [
                    [
                        row["pivot"],
                        row["denominator_u_power"],
                        row["numerator_term_count"],
                    ]
                    for row in pivot_audits
                ],
                "residual": result["residual"],
                "route_decision": result["route_decision"],
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
