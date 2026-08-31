#!/usr/bin/env python3
"""Character-block Macaulay certificate for the last secant ``j2`` chart."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp
from sage.all import GF, QQ, matrix, vector

from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


CHARACTER_MODULUS = 12
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)


def exact_exponent_tuples(variable_count: int, degree: int):
    def recurse(position: int, remaining: int, prefix: tuple[int, ...]):
        if position + 1 == variable_count:
            yield prefix + (remaining,)
            return
        for exponent in range(remaining + 1):
            yield from recurse(position + 1, remaining - exponent, prefix + (exponent,))

    yield from recurse(0, degree, ())


def character_weight(exponents: tuple[int, ...]) -> int:
    return sum(
        exponent * weight for exponent, weight in zip(exponents, CHARACTER_WEIGHTS, strict=True)
    ) % CHARACTER_MODULUS


def coefficient_record(coefficient, exact: bool) -> dict[str, str] | int:
    if exact:
        return {
            "numerator": str(coefficient.numerator()),
            "denominator": str(coefficient.denominator()),
        }
    return int(coefficient)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--saturation-power", type=int, default=2)
    parser.add_argument("--export-sms-prefix", type=Path)
    parser.add_argument("--skip-sage-solve", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be nonnegative")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")
    if arguments.saturation_power < 1:
        parser.error("saturation power must be positive")

    started = time.perf_counter()
    equations, variables, _, open_factor = homogeneous_saturation_system()
    if len(variables) != len(CHARACTER_WEIGHTS):
        raise AssertionError("the frozen character vector has the wrong length")

    polynomial_terms: list[list[tuple[tuple[int, ...], sp.Rational]]] = []
    generator_weights: list[int] = []
    generator_degrees: list[int] = []
    for index, equation in enumerate(equations):
        polynomial = sp.Poly(equation, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), coefficient)
            for exponents, coefficient in polynomial.terms()
        ]
        weights = {character_weight(exponents) for exponents, _ in terms}
        if len(weights) != 1:
            raise AssertionError(f"normal generator {index} is not character-homogeneous")
        degrees = {sum(exponents) for exponents, _ in terms}
        if degrees != {3}:
            raise AssertionError(f"normal generator {index} is not homogeneous cubic")
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
        generator_degrees.append(3)

    target_expression = sp.expand(open_factor ** arguments.saturation_power)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    target_terms = [
        (tuple(map(int, exponents)), coefficient)
        for exponents, coefficient in target_polynomial.terms()
    ]
    target_weights = {character_weight(exponents) for exponents, _ in target_terms}
    if len(target_weights) != 1:
        raise AssertionError("the saturation target is not character-homogeneous")
    target_weight = next(iter(target_weights))
    target_degree = target_polynomial.total_degree()
    if target_degree != 4 * arguments.saturation_power:
        raise AssertionError("unexpected homogeneous saturation-target degree")
    build_polynomials_seconds = time.perf_counter() - started

    rows: list[tuple[int, tuple[int, ...]]] = []
    row_terms: list[list[tuple[tuple[int, ...], sp.Rational]]] = []
    monomial_set: set[tuple[int, ...]] = set()
    for generator_index, (terms, generator_weight) in enumerate(
        zip(polynomial_terms, generator_weights, strict=True)
    ):
        multiplier_degree = target_degree - 3
        multiplier_weight = (target_weight - generator_weight) % CHARACTER_MODULUS
        for multiplier in exact_exponent_tuples(len(variables), multiplier_degree):
            if character_weight(multiplier) != multiplier_weight:
                continue
            products = []
            for exponents, coefficient in terms:
                product_exponents = tuple(
                    left + right for left, right in zip(exponents, multiplier, strict=True)
                )
                if sum(product_exponents) != target_degree:
                    raise AssertionError("a product left the target total degree")
                if character_weight(product_exponents) != target_weight:
                    raise AssertionError("a product left the target character block")
                monomial_set.add(product_exponents)
                products.append((product_exponents, coefficient))
            rows.append((generator_index, multiplier))
            row_terms.append(products)
    monomial_set.update(exponents for exponents, _ in target_terms)
    monomials = sorted(monomial_set)
    monomial_index = {monomial: index for index, monomial in enumerate(monomials)}
    enumerate_seconds = time.perf_counter() - started - build_polynomials_seconds

    exact = arguments.characteristic == 0
    field = QQ if exact else GF(arguments.characteristic)
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

    export_record = None
    if arguments.export_sms_prefix is not None:
        if exact:
            parser.error("SMS export currently requires a positive characteristic")
        prefix = arguments.export_sms_prefix
        if not prefix.is_absolute():
            prefix = Path(__file__).resolve().parent.parent / prefix
        prefix.parent.mkdir(parents=True, exist_ok=True)
        matrix_path = Path(str(prefix) + ".sms")
        target_path = Path(str(prefix) + ".rhs")
        descriptor_path = Path(str(prefix) + ".rows.json")
        matrix_lines = [f"{len(monomials)} {len(rows)} M"]
        for (row_index, column_index), coefficient in sorted(entries.items()):
            matrix_lines.append(f"{column_index + 1} {row_index + 1} {int(coefficient)}")
        matrix_lines.append("0 0 0")
        matrix_path.write_text("\n".join(matrix_lines) + "\n", encoding="ascii")
        target_path.write_text(
            "\n".join(str(int(target[index])) for index in range(len(target))) + "\n",
            encoding="ascii",
        )
        descriptor_path.write_text(
            json.dumps(
                [
                    {
                        "normal_generator_position": generator_index,
                        "multiplier_exponents": list(multiplier),
                    }
                    for generator_index, multiplier in rows
                ],
                separators=(",", ":"),
            )
            + "\n",
            encoding="ascii",
        )
        export_record = {
            "matrix_path": str(matrix_path),
            "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
            "target_path": str(target_path),
            "target_sha256": hashlib.sha256(target_path.read_bytes()).hexdigest(),
            "row_descriptor_path": str(descriptor_path),
            "row_descriptor_file_sha256": hashlib.sha256(
                descriptor_path.read_bytes()
            ).hexdigest(),
            "orientation": "transpose of the Macaulay row matrix: C^T*x=target",
            "format": "LinBox SMS matrix plus dense RHS",
        }

    solve_started = time.perf_counter()
    try:
        solution = None if arguments.skip_sage_solve else macaulay.solve_left(target)
        solved = False if solution is None else solution * macaulay == target
    except ValueError:
        solution = None
        solved = False
    solve_seconds = time.perf_counter() - solve_started

    support = []
    if solved and solution is not None:
        for row_index, coefficient in solution.dict().items():
            generator_index, multiplier = rows[int(row_index)]
            support.append(
                {
                    "row_index": int(row_index),
                    "normal_generator_position": generator_index,
                    "multiplier_exponents": list(multiplier),
                    "coefficient": coefficient_record(coefficient, exact),
                }
            )
        support.sort(key=lambda item: item["row_index"])

    status = (
        "EXPORTED_Z12_LINBOX_SYSTEM"
        if arguments.skip_sage_solve and export_record is not None
        else
        "PASS_EXACT_Z12_SATURATION_IDENTITY"
        if solved and exact
        else "PASS_MODULAR_Z12_SATURATION_IDENTITY"
        if solved
        else "NO_Z12_IDENTITY_AT_BOUND"
    )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4.decimic-j2-secant-r10-z12-macaulay.v1",
        "status": status,
        "assurance": "exact characteristic zero" if exact else "exact finite-field linear algebra only",
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "characteristic": arguments.characteristic,
        "saturation_power": arguments.saturation_power,
        "target_degree": target_degree,
        "target_character_weight": target_weight,
        "character_modulus": CHARACTER_MODULUS,
        "variable_names": [str(variable) for variable in variables],
        "character_weights": list(CHARACTER_WEIGHTS),
        "generator_character_weights": generator_weights,
        "generator_count": len(equations),
        "all_generators_character_homogeneous": True,
        "macaulay_row_count": len(rows),
        "macaulay_column_count": len(monomials),
        "macaulay_nonzero_count": len(entries),
        "identity_verified_in_solver_field": bool(solved),
        "solution_support_count": len(support),
        "solution_support": support,
        "linbox_export": export_record,
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
            "scripts/certify_j2_secant_r10_z12_macaulay.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_j2_secant_r10_homogeneous_saturation.py": hashlib.sha256(
                (script_path.parent / "scout_j2_secant_r10_homogeneous_saturation.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "A characteristic-zero passing receipt proves the sole secant degree-six "
            "chart empty. A finite-field pass is a certificate at that prime only and "
            "requires rational reconstruction plus exact replay."
        ),
    }
    field_name = "exact" if exact else f"p{arguments.characteristic}"
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-degree6-z12-saturation-N"
        f"{arguments.saturation_power}-{field_name}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "solution_support"},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if solved or (arguments.skip_sage_solve and export_record is not None) else 1


if __name__ == "__main__":
    raise SystemExit(main())
