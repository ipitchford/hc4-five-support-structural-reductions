#!/usr/bin/env python3
"""Extract a modular degree-bounded Nullstellensatz identity with Sage."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp
from sage.all import GF, matrix, vector

from certify_j2_secant_r10_f9_laurent_branch import BRANCH_NAMES, laurent_branches
from scout_decimic_nullcone_hsop import digest


def exponent_tuples(variable_count: int, maximum_degree: int):
    """Yield exponent tuples of total degree at most ``maximum_degree``."""

    def exact(position: int, remaining: int, prefix: tuple[int, ...]):
        if position + 1 == variable_count:
            yield prefix + (remaining,)
            return
        for exponent in range(remaining + 1):
            yield from exact(position + 1, remaining - exponent, prefix + (exponent,))

    for degree in range(maximum_degree + 1):
        yield from exact(0, degree, ())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, default="degree_4")
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--degree-bound", type=int, default=6)
    parser.add_argument("--generator-index", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than 5")
    if arguments.degree_bound < 0:
        parser.error("degree bound must be nonnegative")

    started = time.perf_counter()
    _, _, _, _, branches = laurent_branches()
    branch = branches[arguments.branch]
    original_equations = list(branch["equations"])
    if arguments.generator_index:
        generator_indices = tuple(dict.fromkeys(arguments.generator_index))
        if any(index < 0 or index >= len(original_equations) for index in generator_indices):
            parser.error(
                f"every generator index must lie in 0..{len(original_equations) - 1}"
            )
        equations = [original_equations[index] for index in generator_indices]
    else:
        generator_indices = tuple(range(len(original_equations)))
        equations = original_equations
    variables = tuple(
        variable
        for variable in branch["variables"]
        if any(equation.has(variable) for equation in equations)
    )
    missing = set().union(*(equation.free_symbols for equation in equations)) - set(variables)
    if missing:
        raise AssertionError(f"unlisted variables: {sorted(map(str, missing))}")
    polynomials = []
    for equation in equations:
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        if any(coefficient.q != 1 for _, coefficient in polynomial.terms()):
            raise AssertionError("the Macaulay extractor requires integral generators")
        polynomials.append(
            [
                (tuple(map(int, exponents)), int(coefficient))
                for exponents, coefficient in polynomial.terms()
            ]
        )
    build_polynomials_seconds = time.perf_counter() - started

    rows: list[tuple[int, tuple[int, ...]]] = []
    monomial_set: set[tuple[int, ...]] = set()
    row_terms: list[list[tuple[tuple[int, ...], int]]] = []
    for generator_index, (equation, terms) in enumerate(zip(equations, polynomials)):
        generator_degree = sp.Poly(equation, *variables).total_degree()
        multiplier_degree = arguments.degree_bound - generator_degree
        if multiplier_degree < 0:
            continue
        for multiplier in exponent_tuples(len(variables), multiplier_degree):
            product_terms = []
            for exponents, coefficient in terms:
                product_exponents = tuple(
                    left + right for left, right in zip(exponents, multiplier)
                )
                monomial_set.add(product_exponents)
                product_terms.append((product_exponents, coefficient))
            rows.append((generator_index, multiplier))
            row_terms.append(product_terms)
    zero_exponent = (0,) * len(variables)
    monomial_set.add(zero_exponent)
    monomials = sorted(monomial_set, key=lambda item: (sum(item), item))
    monomial_index = {monomial: index for index, monomial in enumerate(monomials)}
    enumerate_seconds = time.perf_counter() - started - build_polynomials_seconds

    field = GF(arguments.characteristic)
    entries = {}
    for row_index, terms in enumerate(row_terms):
        for exponents, coefficient in terms:
            column_index = monomial_index[exponents]
            residue = field(coefficient)
            if residue:
                key = (row_index, column_index)
                entries[key] = entries.get(key, field.zero()) + residue
                if not entries[key]:
                    del entries[key]
    macaulay = matrix(
        field, len(rows), len(monomials), entries, sparse=True
    )
    target = vector(
        field,
        len(monomials),
        {monomial_index[zero_exponent]: field.one()},
        sparse=True,
    )
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
        for row_index, residue in solution.dict().items():
            generator_index, multiplier = rows[int(row_index)]
            support.append(
                {
                    "row_index": int(row_index),
                    "generator_index": generator_index,
                    "multiplier_exponents": list(multiplier),
                    "residue": int(residue),
                }
            )
        support.sort(key=lambda item: item["row_index"])

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-f9-modular-macaulay-identity-v2",
        "status": "PASS_MODULAR_MACAULAY_IDENTITY" if solved else "NO_MODULAR_IDENTITY_AT_BOUND",
        "assurance": "modular exact linear algebra only",
        "orbit": "secant",
        "chart": "f9=1 with f10!=0 and j2!=0",
        "branch": arguments.branch,
        "characteristic": arguments.characteristic,
        "degree_bound": arguments.degree_bound,
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "generator_count": len(equations),
        "original_generator_count": len(original_equations),
        "retained_generator_indices": list(generator_indices),
        "generator_degree_distribution": {
            str(degree): sum(
                sp.Poly(equation, *variables).total_degree() == degree
                for equation in equations
            )
            for degree in sorted({sp.Poly(equation, *variables).total_degree() for equation in equations})
        },
        "macaulay_row_count": len(rows),
        "macaulay_column_count": len(monomials),
        "macaulay_nonzero_count": len(entries),
        "solution_support_count": len(support),
        "solution_support": support,
        "modular_identity_verified": bool(solved),
        "equation_stream_sha256": digest(tuple(equations)),
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
            "scripts/extract_j2_secant_r10_f9_degree6_modular_identity.py": hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this receipt proves a degree-bounded identity only in the displayed "
            "finite characteristic; rational reconstruction and exact verification "
            "are required for a characteristic-zero certificate"
        ),
    }
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-{arguments.branch}-degree{arguments.degree_bound}-"
            f"macaulay-p{arguments.characteristic}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "solution_support"}, indent=2, sort_keys=True))
    return 0 if solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
