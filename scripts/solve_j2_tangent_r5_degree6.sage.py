#!/usr/bin/env sage-python
"""Solve the tangent r=5 degree-six membership problem using SageMath."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from sage.all import GF, QQ, matrix, vector


def compositions(total: int, length: int):
    """Yield exponent tuples of fixed total in a stable lexicographic order."""
    if length == 1:
        yield (total,)
        return
    for first in range(total, -1, -1):
        for tail in compositions(total - first, length - 1):
            yield (first,) + tail


def monomials_up_to(maximum_degree: int, length: int):
    for degree in range(maximum_degree + 1):
        yield from compositions(degree, length)


def polynomial_dict(terms, coefficient_ring):
    return {
        tuple(term["exponents"]): coefficient_ring(term["coefficient"])
        for term in terms
    }


def multiply(left, right, coefficient_ring):
    product = {}
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = tuple(a + b for a, b in zip(left_exponents, right_exponents))
            product[exponents] = product.get(exponents, coefficient_ring.zero()) + (
                left_coefficient * right_coefficient
            )
    return {exponents: coefficient for exponents, coefficient in product.items() if coefficient}


def encode_coefficient(coefficient, rational: bool):
    if rational:
        return {"numerator": int(coefficient.numerator()), "denominator": int(coefficient.denominator())}
    return int(coefficient)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--modulus",
        type=int,
        default=0,
        help="debug over GF(p); zero requests the exact rational certificate",
    )
    parser.add_argument(
        "--multiplier-degree",
        type=int,
        default=3,
        help="maximum total degree of the twelve residual multipliers",
    )
    arguments = parser.parse_args()
    if arguments.multiplier_degree < 0:
        parser.error("multiplier degree must be nonnegative")
    started = time.perf_counter()

    system_bytes = arguments.system.read_bytes()
    system = json.loads(system_bytes)
    number_of_variables = len(system["variables"])
    maximum_identity_degree = max(6, arguments.multiplier_degree + 3)
    multiplier_monomials = list(
        monomials_up_to(arguments.multiplier_degree, number_of_variables)
    )
    target_monomials = list(monomials_up_to(maximum_identity_degree, number_of_variables))
    target_monomial_index = {
        monomial: index for index, monomial in enumerate(target_monomials)
    }
    coefficient_ring = GF(arguments.modulus) if arguments.modulus else QQ

    equations = [
        polynomial_dict(entry["terms"], coefficient_ring)
        for entry in system["residual_equations"]
    ]
    P = polynomial_dict(system["P_terms"], coefficient_ring)
    target = multiply(P, P, coefficient_ring)

    row_count = len(equations) * len(multiplier_monomials)
    entries = {}
    for equation_index, equation in enumerate(equations):
        for multiplier_index, multiplier in enumerate(multiplier_monomials):
            row = equation_index * len(multiplier_monomials) + multiplier_index
            for exponents, coefficient in equation.items():
                column_exponents = tuple(a + b for a, b in zip(multiplier, exponents))
                column = target_monomial_index[column_exponents]
                entries[(row, column)] = coefficient
    macaulay = matrix(
        coefficient_ring,
        row_count,
        len(target_monomials),
        entries,
        sparse=True,
    )
    target_vector = vector(
        coefficient_ring,
        len(target_monomials),
        {target_monomial_index[exponents]: coefficient for exponents, coefficient in target.items()},
        sparse=True,
    )
    build_seconds = time.perf_counter() - started
    solve_started = time.perf_counter()
    try:
        solution = macaulay.solve_left(target_vector)
    except ValueError as error:
        solve_seconds = time.perf_counter() - solve_started
        if "no solutions" not in str(error):
            raise
        script_path = Path(__file__).resolve()
        result = {
            "schema": "hc4-decimic-j2-tangent-r5-degree-bounded-membership-v1",
            "status": "NO_SOLUTION_AT_DEGREE_BOUND",
            "coefficient_ring": "QQ" if not arguments.modulus else f"GF({arguments.modulus})",
            "multiplier_maximum_degree": arguments.multiplier_degree,
            "identity_maximum_degree": maximum_identity_degree,
            "system_sha256": system["system_sha256"],
            "system_file_sha256": hashlib.sha256(system_bytes).hexdigest(),
            "row_count": row_count,
            "column_count": len(target_monomials),
            "matrix_nonzero_count": macaulay.dict().__len__(),
            "build_seconds": build_seconds,
            "solve_seconds": solve_seconds,
            "wall_seconds": time.perf_counter() - started,
            "source_sha256": {
                "scripts/solve_j2_tangent_r5_degree6.sage.py": hashlib.sha256(
                    script_path.read_bytes()
                ).hexdigest()
            },
            "claim_boundary": (
                "the target has no certificate within this multiplier-degree "
                "ansatz over the stated coefficient field; this does not rule "
                "out a higher-degree certificate"
            ),
        }
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1
    solve_seconds = time.perf_counter() - solve_started
    if solution * macaulay != target_vector:
        raise AssertionError("Sage returned a vector that does not solve the Macaulay system")

    multipliers = []
    nonzero_count = 0
    for equation_index, equation_entry in enumerate(system["residual_equations"]):
        terms = []
        offset = equation_index * len(multiplier_monomials)
        for multiplier_index, exponents in enumerate(multiplier_monomials):
            coefficient = solution[offset + multiplier_index]
            if coefficient:
                nonzero_count += 1
                terms.append(
                    {
                        "exponents": list(exponents),
                        "coefficient": encode_coefficient(coefficient, not arguments.modulus),
                    }
                )
        multipliers.append(
            {
                "normal_equation_index": equation_entry["normal_equation_index"],
                "terms": terms,
            }
        )

    status = "PASS_EXACT_RATIONAL_CERTIFICATE" if not arguments.modulus else "PASS_MODULAR_MEMBERSHIP_SIGNAL"
    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4-decimic-j2-tangent-r5-degree6-certificate-v1",
        "status": status,
        "coefficient_ring": "QQ" if not arguments.modulus else f"GF({arguments.modulus})",
        "multiplier_maximum_degree": arguments.multiplier_degree,
        "identity_maximum_degree": maximum_identity_degree,
        "system_sha256": system["system_sha256"],
        "system_file_sha256": hashlib.sha256(system_bytes).hexdigest(),
        "row_count": row_count,
        "column_count": len(target_monomials),
        "matrix_nonzero_count": macaulay.dict().__len__(),
        "solution_nonzero_count": nonzero_count,
        "build_seconds": build_seconds,
        "solve_seconds": solve_seconds,
        "wall_seconds": time.perf_counter() - started,
        "multipliers": multipliers,
        "source_sha256": {
            "scripts/solve_j2_tangent_r5_degree6.sage.py": hashlib.sha256(script_path.read_bytes()).hexdigest()
        },
        "claim_boundary": (
            "PASS_EXACT_RATIONAL_CERTIFICATE proves P^2 lies in the twelve-cubic "
            "ideal on the rational tangent r=5 slice; the independent verifier "
            "must still reconstruct the displayed unit identity"
        ),
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "multipliers"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
