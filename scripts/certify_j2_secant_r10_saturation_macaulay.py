#!/usr/bin/env python3
"""Certify saturation membership for one secant ``r=10`` Laurent branch.

The inverse variables are eliminated exactly.  If the resulting identity is

    (f10 * leading_form)^N = sum_i multiplier_i * generator_i,

then the branch is empty on the open set where both factors are nonzero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp
from sage.all import GF, QQ, matrix, vector

from certify_j2_secant_r10_f9_chart import f10_inverse
from certify_j2_secant_r10_f9_laurent_branch import BRANCH_NAMES, laurent_branches
from extract_j2_secant_r10_f9_degree6_modular_identity import exponent_tuples
from scout_decimic_nullcone_hsop import digest, f_coefficients


def coefficient_record(coefficient) -> dict[str, str] | int:
    if coefficient.parent() is QQ:
        return {
            "numerator": str(coefficient.numerator()),
            "denominator": str(coefficient.denominator()),
        }
    return int(coefficient)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--saturation-power", type=int, default=1)
    parser.add_argument("--degree-bound", type=int, required=True)
    parser.add_argument("--generator-index", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be nonnegative")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")
    if arguments.saturation_power < 1:
        parser.error("saturation power must be positive")
    if arguments.degree_bound < 0:
        parser.error("degree bound must be nonnegative")

    started = time.perf_counter()
    _, _, _, _, branches = laurent_branches()
    branch = branches[arguments.branch]
    original_equations = list(branch["equations"])
    if branch["leading_form"] is None:
        parser.error("the terminal A_zero branch has no leading-form open condition")
    if arguments.generator_index:
        generator_indices = tuple(dict.fromkeys(arguments.generator_index))
    else:
        generator_indices = tuple(range(len(original_equations) - 2))
    if any(index < 0 or index >= len(original_equations) - 2 for index in generator_indices):
        parser.error(
            "generator indices must select normal equations, not the two inverse localizers"
        )

    f10 = f_coefficients[10]
    equations: list[sp.Expr] = []
    cleared_denominators: list[str] = []
    for index in generator_indices:
        rational_expression = sp.cancel(original_equations[index].subs(f10_inverse, 1 / f10))
        numerator, denominator = sp.fraction(rational_expression)
        equations.append(sp.expand(numerator))
        cleared_denominators.append(str(denominator))
    leading_form = sp.expand(branch["leading_form"])
    saturation_element = sp.expand(f10 * leading_form)
    target_expression = sp.expand(saturation_element ** arguments.saturation_power)
    variables = tuple(
        variable
        for variable in branch["variables"]
        if variable not in {f10_inverse, sp.Symbol("leadinv")}
        and (
            target_expression.has(variable)
            or any(equation.has(variable) for equation in equations)
        )
    )
    missing = (
        set().union(target_expression.free_symbols, *(equation.free_symbols for equation in equations))
        - set(variables)
    )
    if missing:
        raise AssertionError(f"unlisted variables: {sorted(map(str, missing))}")

    polynomial_terms: list[list[tuple[tuple[int, ...], sp.Rational]]] = []
    generator_degrees = []
    for equation in equations:
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        generator_degrees.append(polynomial.total_degree())
        polynomial_terms.append(
            [(tuple(map(int, exponents)), coefficient) for exponents, coefficient in polynomial.terms()]
        )
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    if target_polynomial.total_degree() > arguments.degree_bound:
        parser.error("the degree bound is smaller than the saturation target degree")
    build_polynomials_seconds = time.perf_counter() - started

    rows: list[tuple[int, tuple[int, ...]]] = []
    row_terms: list[list[tuple[tuple[int, ...], sp.Rational]]] = []
    monomial_set: set[tuple[int, ...]] = set()
    for generator_index, (degree, terms) in enumerate(zip(generator_degrees, polynomial_terms)):
        multiplier_degree = arguments.degree_bound - degree
        if multiplier_degree < 0:
            continue
        for multiplier in exponent_tuples(len(variables), multiplier_degree):
            products = []
            for exponents, coefficient in terms:
                product_exponents = tuple(
                    left + right for left, right in zip(exponents, multiplier)
                )
                monomial_set.add(product_exponents)
                products.append((product_exponents, coefficient))
            rows.append((generator_index, multiplier))
            row_terms.append(products)
    target_terms = [
        (tuple(map(int, exponents)), coefficient)
        for exponents, coefficient in target_polynomial.terms()
    ]
    monomial_set.update(exponents for exponents, _ in target_terms)
    monomials = sorted(monomial_set, key=lambda item: (sum(item), item))
    monomial_index = {monomial: index for index, monomial in enumerate(monomials)}
    enumerate_seconds = time.perf_counter() - started - build_polynomials_seconds

    field = QQ if arguments.characteristic == 0 else GF(arguments.characteristic)
    entries = {}
    for row_index, terms in enumerate(row_terms):
        for exponents, coefficient in terms:
            column_index = monomial_index[exponents]
            residue = field(int(coefficient.p)) / field(int(coefficient.q))
            if residue:
                key = (row_index, column_index)
                entries[key] = entries.get(key, field.zero()) + residue
                if not entries[key]:
                    del entries[key]
    macaulay = matrix(field, len(rows), len(monomials), entries, sparse=True)
    target_entries = {}
    for exponents, coefficient in target_terms:
        target_entries[monomial_index[exponents]] = (
            field(int(coefficient.p)) / field(int(coefficient.q))
        )
    target = vector(field, len(monomials), target_entries, sparse=True)
    matrix_seconds = time.perf_counter() - started - build_polynomials_seconds - enumerate_seconds
    solve_started = time.perf_counter()
    try:
        solution = macaulay.solve_left(target)
        solved = solution * macaulay == target
    except ValueError:
        solution = None
        solved = False
    solve_seconds = time.perf_counter() - solve_started

    support = []
    if solved and solution is not None:
        for row_index, coefficient in solution.dict().items():
            generator_position, multiplier = rows[int(row_index)]
            support.append(
                {
                    "row_index": int(row_index),
                    "generator_position": generator_position,
                    "original_generator_index": generator_indices[generator_position],
                    "multiplier_exponents": list(multiplier),
                    "coefficient": coefficient_record(coefficient),
                }
            )
        support.sort(key=lambda item: item["row_index"])

    exact = arguments.characteristic == 0
    if solved:
        status = "PASS_EXACT_SATURATION_IDENTITY" if exact else "PASS_MODULAR_SATURATION_IDENTITY"
    else:
        status = "NO_IDENTITY_AT_BOUND"
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-saturation-macaulay-v1",
        "status": status,
        "assurance": "exact characteristic zero" if exact else "modular exact linear algebra only",
        "orbit": "secant",
        "chart": "f9=1 with f10*leading_form!=0",
        "branch": arguments.branch,
        "characteristic": arguments.characteristic,
        "saturation_power": arguments.saturation_power,
        "degree_bound": arguments.degree_bound,
        "saturation_element": str(saturation_element),
        "target_expression": str(target_expression),
        "target_total_degree": target_polynomial.total_degree(),
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "original_generator_count": len(original_equations),
        "retained_generator_indices": list(generator_indices),
        "retained_generator_count": len(equations),
        "cleared_f10_denominators": cleared_denominators,
        "generator_degree_distribution": {
            str(degree): generator_degrees.count(degree)
            for degree in sorted(set(generator_degrees))
        },
        "macaulay_row_count": len(rows),
        "macaulay_column_count": len(monomials),
        "macaulay_nonzero_count": len(entries),
        "solution_support_count": len(support),
        "solution_support": support,
        "identity_verified_in_solver_field": bool(solved),
        "equation_stream_sha256": digest(tuple(equations)),
        "target_sha256": digest((target_expression,)),
        "row_descriptor_sha256": hashlib.sha256(
            json.dumps(rows, separators=(",", ":")).encode("ascii")
        ).hexdigest(),
        "monomial_stream_sha256": hashlib.sha256(
            json.dumps(monomials, separators=(",", ":")).encode("ascii")
        ).hexdigest(),
        "timings": {
            "polynomial_build_seconds": build_polynomials_seconds,
            "row_enumeration_seconds": enumerate_seconds,
            "matrix_build_seconds": matrix_seconds,
            "solve_seconds": solve_seconds,
            "wall_seconds": time.perf_counter() - started,
        },
        "source_sha256": {
            "scripts/certify_j2_secant_r10_saturation_macaulay.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "An exact characteristic-zero passing receipt proves emptiness only for this "
            "single branch on D(f10*leading_form).  A modular pass is route evidence only."
        ),
    }
    if arguments.output is None:
        field_name = "exact" if exact else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-{arguments.branch}-saturation-N"
            f"{arguments.saturation_power}-degree{arguments.degree_bound}-{field_name}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "solution_support"},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
