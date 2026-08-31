#!/usr/bin/env python3
"""Construct corrected highest lifts for the four quartic target families."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

import sympy as sp

import identify_decimic_nullcone_cubic_covariants as cubic
from reconstruct_normal_layers import s, t
from scout_decimic_nullcone_hsop import digest, f_coefficients, generic_decimic


a = cubic.a
WEIGHT_KEYS = {
    8: "V8_QUARTIC",
    4: "V4_WEIGHT_4_CANDIDATES",
    0: "V0_WEIGHT_0_CANDIDATES",
}
EXPECTED_MULTIPLICITIES = {8: 1, 4: 2, 0: 1}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_m2(text: str) -> sp.Expr:
    local = {f"t_{index}": a[index] for index in range(11)}
    return sp.Poly(
        sp.sympify(text.replace("^", "**"), locals=local), *a, domain=sp.QQ
    ).as_expr()


def raising(expression: sp.Expr) -> sp.Expr:
    return cubic.raise_weight(expression)


def lowering(expression: sp.Expr, steps: int = 1) -> sp.Expr:
    result = expression
    for _ in range(steps):
        result = cubic.lower(result)
    return sp.expand(result)


def primitive_expression(expression: sp.Expr, variables: Sequence[sp.Symbol]) -> sp.Expr:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    coefficients = [sp.Rational(value) for value in polynomial.coeffs()]
    denominator = sp.ilcm(*(value.q for value in coefficients))
    integers = [int(value * denominator) for value in coefficients]
    content = sp.igcd(*(abs(value) for value in integers if value))
    multiplier = sp.Rational(denominator, content or 1)
    result = sp.expand(expression * multiplier)
    first = sp.Poly(result, *variables).terms()[0][1]
    if first < 0:
        result = -result
    return sp.expand(result)


def expression_matrix(expressions: Sequence[sp.Expr]) -> sp.Matrix:
    dictionaries = [sp.Poly(item, *a, domain=sp.QQ).as_dict() for item in expressions]
    monomials = sorted(set().union(*dictionaries))
    return sp.Matrix(
        [[dictionary.get(monomial, 0) for dictionary in dictionaries] for monomial in monomials]
    )


def cubic_chains(j2: sp.Expr) -> dict[str, list[tuple[int, sp.Expr]]]:
    v6 = sp.expand(cubic.parse_polynomial(cubic.V6_TEXT) - j2 * a[2])
    weight2 = [cubic.parse_polynomial(text) for text in cubic.WEIGHT2_TEXTS]
    v2 = sp.expand(6 * weight2[0] + weight2[1] - j2 * a[4])

    def chain(highest: sp.Expr, highest_weight: int) -> list[tuple[int, sp.Expr]]:
        result = []
        current = highest
        for weight in range(highest_weight, -highest_weight - 1, -2):
            result.append((weight, sp.expand(current)))
            current = lowering(current)
        return result

    return {"V6": chain(v6, 6), "V2": chain(v2, 2)}


def lower_ideal_basis(
    weight: int, j2: sp.Expr, chains: dict[str, list[tuple[int, sp.Expr]]]
) -> tuple[list[sp.Expr], list[str]]:
    values: list[sp.Expr] = []
    labels: list[str] = []
    for left in range(11):
        for right in range(left, 11):
            if (10 - 2 * left) + (10 - 2 * right) == weight:
                values.append(sp.expand(j2 * a[left] * a[right]))
                labels.append(f"J2*a_{left}*a_{right}")
    for family, chain in chains.items():
        for cubic_weight, coordinate in chain:
            for index in range(11):
                if cubic_weight + (10 - 2 * index) == weight:
                    values.append(sp.expand(coordinate * a[index]))
                    labels.append(f"{family}[{cubic_weight}]*a_{index}")
    return values, labels


def corrected_highest(
    candidates: list[sp.Expr], lower_basis: list[sp.Expr], expected: int
) -> tuple[list[sp.Expr], dict[str, object]]:
    combined = candidates + lower_basis
    raising_matrix = expression_matrix([raising(item) for item in combined])
    kernel = raising_matrix.nullspace()
    candidate_count = len(candidates)
    projected = (
        sp.Matrix.hstack(*(sp.Matrix(vector[:candidate_count, :]) for vector in kernel))
        if kernel
        else sp.zeros(candidate_count, 0)
    )
    projected_rank = projected.rank()
    if projected_rank != expected:
        raise AssertionError(
            f"expected projected kernel rank {expected}, received {projected_rank}"
        )
    selected: list[sp.Matrix] = []
    selected_projection = sp.zeros(candidate_count, 0)
    current_rank = 0
    for vector in kernel:
        trial = selected_projection.row_join(sp.Matrix(vector[:candidate_count, :]))
        trial_rank = trial.rank()
        if trial_rank > current_rank:
            selected.append(vector)
            selected_projection = trial
            current_rank = trial_rank
    highest = [
        primitive_expression(
            sp.expand(sum(vector[index] * combined[index] for index in range(len(combined)))),
            a,
        )
        for vector in selected
    ]
    if len(highest) != expected or not all(raising(item) == 0 for item in highest):
        raise AssertionError("corrected highest-weight construction failed")
    return highest, {
        "candidate_count": candidate_count,
        "lower_ideal_basis_count": len(lower_basis),
        "raising_matrix_rows": raising_matrix.rows,
        "raising_matrix_columns": raising_matrix.cols,
        "kernel_dimension": len(kernel),
        "projected_kernel_rank": projected_rank,
    }


def coordinates_mod_lower(
    target: sp.Expr, candidates: list[sp.Expr], lower_basis: list[sp.Expr]
) -> list[sp.Rational]:
    combined = candidates + lower_basis
    dictionaries = [
        sp.Poly(item, *a, domain=sp.QQ).as_dict() for item in [target, *combined]
    ]
    monomials = sorted(set().union(*dictionaries))
    matrix = sp.Matrix(
        [[dictionary.get(monomial, 0) for dictionary in dictionaries[1:]] for monomial in monomials]
    )
    vector = sp.Matrix([dictionaries[0].get(monomial, 0) for monomial in monomials])
    solution, parameters = matrix.gauss_jordan_solve(vector)
    if parameters.rows:
        solution = solution.subs({symbol: 0 for symbol in parameters})
    residual = sp.expand(target - sum(solution[index] * combined[index] for index in range(len(combined))))
    if residual != 0:
        raise AssertionError("quotient coordinate solve did not replay")
    # Minimal generators are independent modulo the lower ideal.  Therefore
    # every relation among the combined columns has zero candidate prefix.
    for relation in matrix.nullspace():
        if any(relation[index] != 0 for index in range(len(candidates))):
            raise AssertionError("candidate coordinates are not unique modulo the lower ideal")
    return [sp.Rational(solution[index]) for index in range(len(candidates))]


def raw_primitive(expression: sp.Expr) -> sp.Expr:
    substitutions = {
        a[index]: f_coefficients[index] / sp.binomial(10, index)
        for index in range(11)
    }
    return primitive_expression(sp.expand(expression.subs(substitutions)), f_coefficients)


def torus_weight(expression: sp.Expr) -> int:
    weights = {f_coefficients[index]: 14 - 3 * index for index in range(11)}
    values = {
        sum(
            term.as_powers_dict().get(symbol, 0) * weights[symbol]
            for symbol in f_coefficients
        )
        for term in sp.Add.make_args(sp.expand(expression))
    }
    if len(values) != 1:
        raise AssertionError(f"raw quartic is not tangent-torus homogeneous: {values}")
    return int(next(iter(values)))


def orbit_profile(expression: sp.Expr) -> dict[str, object]:
    u = sp.Symbol("u")
    binary = generic_decimic()
    transformed = sp.expand(binary.subs({t: t + u * s}))
    images = tuple(
        sp.Poly(transformed, s, t).coeff_monomial(s ** (10 - index) * t**index)
        for index in range(11)
    )
    orbit = sp.Poly(
        sp.expand(
            expression.subs(
                dict(zip(f_coefficients, images, strict=True)), simultaneous=True
            )
        ),
        u,
    )
    coefficients = [
        sp.expand(orbit.coeff_monomial(u**index)) for index in range(orbit.degree() + 1)
    ]
    dictionaries = [sp.Poly(item, *f_coefficients).as_dict() for item in coefficients]
    monomials = sorted(set().union(*dictionaries))
    matrix = sp.Matrix(
        [[dictionary.get(monomial, 0) for dictionary in dictionaries] for monomial in monomials]
    )
    return {
        "parameter_degree": orbit.degree(),
        "coefficient_count": len(coefficients),
        "exact_rank": matrix.rank(),
        "coefficient_sha256": [digest((item,)) for item in coefficients],
    }


def build_quartic_data(receipt_path: Path) -> dict[str, object]:
    extracted = json.loads(receipt_path.read_text(encoding="utf-8"))
    if extracted.get("status") != "PASS_EXACT_WEIGHT_SPACE_EXTRACTION":
        raise AssertionError("the exact weight-space extraction is unavailable")
    polynomials = extracted["polynomials"]
    j2 = parse_m2(polynomials["V0_QUADRATIC"][0])
    if raising(j2) != 0 or lowering(j2) != 0:
        raise AssertionError("the extracted quadratic is not invariant")
    chains = cubic_chains(j2)

    candidates: dict[int, list[sp.Expr]] = {
        weight: [parse_m2(text) for text in polynomials[key]]
        for weight, key in WEIGHT_KEYS.items()
    }
    lower_bases: dict[int, list[sp.Expr]] = {}
    highest_by_weight: dict[int, list[sp.Expr]] = {}
    kernel_profiles = {}
    for weight in (8, 4, 0):
        lower_bases[weight], _ = lower_ideal_basis(weight, j2, chains)
        highest_by_weight[weight], kernel_profiles[str(weight)] = corrected_highest(
            candidates[weight], lower_bases[weight], EXPECTED_MULTIPLICITIES[weight]
        )

    v8 = highest_by_weight[8][0]
    v4a, v4b = highest_by_weight[4]
    v0 = highest_by_weight[0][0]
    weight4_coordinates = [
        coordinates_mod_lower(item, candidates[4], lower_bases[4])
        for item in (lowering(v8, 2), v4a, v4b)
    ]
    weight0_coordinates = [
        coordinates_mod_lower(item, candidates[0], lower_bases[0])
        for item in (lowering(v8, 4), lowering(v4a, 2), lowering(v4b, 2), v0)
    ]
    if sp.Matrix.hstack(*(sp.Matrix(item) for item in weight4_coordinates)).rank() != 3:
        raise AssertionError("the quartic weight-four quotient rank is not three")
    if sp.Matrix.hstack(*(sp.Matrix(item) for item in weight0_coordinates)).rank() != 4:
        raise AssertionError("the quartic weight-zero quotient rank is not four")

    divided = {"V8": v8, "V4_1": v4a, "V4_2": v4b, "V0": v0}
    raw = {name: raw_primitive(expression) for name, expression in divided.items()}
    orders = {"V8": 8, "V4_1": 4, "V4_2": 4, "V0": 0}
    family_profiles = {}
    for name, expression in raw.items():
        polynomial = sp.Poly(expression, *f_coefficients)
        top_indices = sorted(
            {
                max(index for index, exponent in enumerate(monomial) if exponent)
                for monomial, _ in polynomial.terms()
            }
        )
        orbit = orbit_profile(expression)
        if orbit["exact_rank"] != orders[name] + 1:
            raise AssertionError(f"{name}: the tangent unipotent orbit is not cyclic")
        family_profiles[name] = {
            "order": orders[name],
            "divided_power_term_count": len(sp.Poly(divided[name], *a).terms()),
            "raw_term_count": len(polynomial.terms()),
            "tangent_torus_weight": torus_weight(expression),
            "top_support_indices": top_indices,
            "minimum_top_index": min(top_indices),
            "raw_sha256": digest((expression,)),
            "raw_polynomial": str(expression),
            "orbit": orbit,
        }
    return {
        "j2": j2,
        "divided": divided,
        "raw": raw,
        "kernel_profiles": kernel_profiles,
        "weight4_quotient_coordinates": weight4_coordinates,
        "weight0_quotient_coordinates": weight0_coordinates,
        "family_profiles": family_profiles,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("receipts/decimic-nullcone-weight-generators-exact.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/decimic-nullcone-quartic-covariants-exact.json"),
    )
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    input_path = arguments.input if arguments.input.is_absolute() else campaign / arguments.input
    data = build_quartic_data(input_path)

    result = {
        "schema": "hc4.decimic-nullcone-quartic-covariants.v1",
        "status": "PASS_EXACT_QUARTIC_COVARIANT_IDENTIFICATION",
        "field": "QQ",
        "coefficient_conventions": {
            "divided_power": "F=sum(binomial(10,i)*a_i*x^(10-i)*y^i)",
            "campaign_raw": "F=sum(f_i*s^(10-i)*t^i)",
        },
        "lower_ideal_correction": "R2*I2 + R1*I3",
        "projected_raising_kernel_profiles": data["kernel_profiles"],
        "weight4_quotient_coordinates": [
            [str(value) for value in vector] for vector in data["weight4_quotient_coordinates"]
        ],
        "weight0_quotient_coordinates": [
            [str(value) for value in vector] for vector in data["weight0_quotient_coordinates"]
        ],
        "weight4_quotient_rank": 3,
        "weight0_quotient_rank": 4,
        "families": data["family_profiles"],
        "input": str(input_path.relative_to(campaign)),
        "input_sha256": sha256(input_path),
        "source_sha256": {
            "scripts/identify_decimic_nullcone_quartic_covariants.py": sha256(script_path),
            "scripts/identify_decimic_nullcone_cubic_covariants.py": sha256(
                campaign / "scripts/identify_decimic_nullcone_cubic_covariants.py"
            ),
        },
        "claim_boundary": (
            "this exactly identifies corrected highest lifts and cyclic tangent-"
            "stabilizer spans for the four quartic target families; it does not prove "
            "any quartic vanishes on the normal-layer locus"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
