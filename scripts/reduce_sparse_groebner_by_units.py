#!/usr/bin/env python3
"""Eliminate variables linearly using units already certified in a system.

Inverse relations are detected in the form ``U*u + c = 0``, where ``u``
occurs in no other equation and ``c`` is a nonzero rational constant.  Both
``U`` and ``u`` are then known units.  An equation linear in ``x`` whose
coefficient is a rational multiple of either known unit can be solved for
``x`` without adding a chart or changing the quotient ring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(expression: sp.Expr) -> str:
    return str(sp.factor(expression)).replace("**", "^")


def decode_equation(
    encoded: list[dict[str, object]], variables: tuple[sp.Symbol, ...]
) -> sp.Expr:
    expression = sp.Integer(0)
    for term in encoded:
        coefficient = sp.Rational(
            int(str(term["numerator"])), int(str(term["denominator"]))
        )
        exponents = tuple(int(value) for value in term["exponents"])
        if len(exponents) != len(variables):
            raise AssertionError("term exponent vector has the wrong length")
        expression += coefficient * sp.prod(
            variable**exponent
            for variable, exponent in zip(variables, exponents)
        )
    return sp.expand(expression)


def primitive_polynomial(
    expression: sp.Expr, variables: tuple[sp.Symbol, ...]
) -> sp.Poly:
    _, rational_polynomial = sp.Poly(
        sp.expand(expression), *variables, domain=sp.QQ
    ).clear_denoms()
    _, primitive = sp.Poly(
        rational_polynomial.as_expr(), *variables, domain=sp.ZZ
    ).primitive()
    if primitive.LC() < 0:
        primitive = -primitive
    return primitive


def encode_polynomial(polynomial: sp.Poly) -> list[dict[str, object]]:
    return [
        {
            "numerator": str(int(coefficient)),
            "denominator": "1",
            "exponents": list(exponents),
        }
        for exponents, coefficient in polynomial.terms()
    ]


def term_count(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> int:
    if expression == 0:
        return 0
    return len(sp.Poly(expression, *variables, domain=sp.QQ).terms())


def total_degree(expression: sp.Expr, variables: tuple[sp.Symbol, ...]) -> int:
    if expression == 0:
        return -1
    return int(sp.Poly(expression, *variables, domain=sp.QQ).total_degree())


def detect_unit_relations(
    equations: list[sp.Expr], variables: tuple[sp.Symbol, ...]
) -> tuple[list[dict[str, object]], set[sp.Symbol], set[int]]:
    occurrences = {
        variable: [index for index, equation in enumerate(equations) if equation.has(variable)]
        for variable in variables
    }
    relations: list[dict[str, object]] = []
    protected: set[sp.Symbol] = set()
    relation_indices: set[int] = set()
    for inverse_variable, indices in occurrences.items():
        if len(indices) != 1:
            continue
        equation_index = indices[0]
        polynomial = sp.Poly(equations[equation_index], inverse_variable)
        if polynomial.degree() != 1:
            continue
        unit = sp.expand(polynomial.coeff_monomial(inverse_variable))
        constant = sp.expand(polynomial.coeff_monomial(1))
        if inverse_variable in unit.free_symbols:
            continue
        if constant.free_symbols or constant == 0:
            continue
        constant = sp.Rational(constant)
        unit_reciprocal = sp.expand(-inverse_variable / constant)
        inverse_reciprocal = sp.expand(-unit / constant)
        relations.append(
            {
                "equation_index": equation_index,
                "inverse_variable": inverse_variable,
                "unit": unit,
                "constant": constant,
                "factors": (
                    (
                        unit,
                        unit_reciprocal,
                        "base_unit",
                        equations[equation_index],
                        constant,
                    ),
                    (
                        inverse_variable,
                        inverse_reciprocal,
                        "inverse_variable",
                        equations[equation_index],
                        constant,
                    ),
                ),
            }
        )
        protected.add(inverse_variable)
        protected.update(unit.free_symbols)
        relation_indices.add(equation_index)
    if not relations:
        raise AssertionError("no isolated inverse relations were detected")
    return relations, protected, relation_indices


def rational_quotient(numerator: sp.Expr, denominator: sp.Expr) -> sp.Rational | None:
    quotient = sp.cancel(numerator / denominator)
    if quotient.free_symbols:
        return None
    try:
        value = sp.Rational(quotient)
    except (TypeError, ValueError):
        return None
    return value if value != 0 else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    arguments = parser.parse_args()

    input_path = arguments.input.resolve()
    source = json.loads(input_path.read_text(encoding="utf-8"))
    variable_names = tuple(str(name) for name in source["variable_names"])
    variables = tuple(sp.symbols(" ".join(variable_names), seq=True))
    equations = [decode_equation(row, variables) for row in source["equations"]]
    labels = list(range(len(equations)))
    relations, protected, relation_indices = detect_unit_relations(equations, variables)
    active_variables = list(variables)
    eliminations: list[dict[str, object]] = []

    unit_factors = [factor for relation in relations for factor in relation["factors"]]
    while True:
        candidates = []
        active_tuple = tuple(active_variables)
        for position, (label, equation) in enumerate(zip(labels, equations)):
            if label in relation_indices:
                continue
            for variable in active_variables:
                if variable in protected:
                    continue
                polynomial = sp.Poly(equation, variable)
                if polynomial.degree() != 1:
                    continue
                coefficient = sp.expand(polynomial.coeff_monomial(variable))
                remainder = sp.expand(polynomial.coeff_monomial(1))
                for unit, reciprocal, unit_kind, unit_relation, relation_constant in unit_factors:
                    quotient = rational_quotient(coefficient, unit)
                    if quotient is None:
                        continue
                    replacement = sp.expand(-remainder * reciprocal / quotient)
                    candidates.append(
                        (
                            term_count(replacement, active_tuple),
                            total_degree(replacement, active_tuple),
                            position,
                            str(variable),
                            variable,
                            coefficient,
                            remainder,
                            replacement,
                            unit,
                            reciprocal,
                            quotient,
                            unit_kind,
                            unit_relation,
                            relation_constant,
                            label,
                        )
                    )
        if not candidates:
            break
        (
            _,
            _,
            position,
            _,
            variable,
            coefficient,
            remainder,
            replacement,
            unit,
            reciprocal,
            quotient,
            unit_kind,
            unit_relation,
            relation_constant,
            label,
        ) = min(candidates)
        substituted_source = sp.expand(coefficient * replacement + remainder)
        expected_residual = sp.expand(remainder * unit_relation / relation_constant)
        if sp.expand(substituted_source - expected_residual) != 0:
            raise AssertionError(
                "the proposed substitution is not exact modulo the unit relation"
            )
        eliminations.append(
            {
                "step": len(eliminations) + 1,
                "source_equation_original_index": label,
                "variable": str(variable),
                "coefficient": render(coefficient),
                "known_unit_factor": render(unit),
                "known_unit_reciprocal": render(reciprocal),
                "rational_multiple": str(quotient),
                "unit_kind": unit_kind,
                "replacement": render(replacement),
                "substituted_source_residual": render(substituted_source),
                "source_residual_as_unit_relation_multiple": render(
                    remainder / relation_constant
                ),
                "replacement_total_degree_before_substitution": total_degree(
                    replacement, tuple(active_variables)
                ),
                "replacement_term_count_before_substitution": term_count(
                    replacement, tuple(active_variables)
                ),
            }
        )
        substituted = [sp.expand(equation.subs(variable, replacement)) for equation in equations]
        if sp.expand(substituted[position] - expected_residual) != 0:
            raise AssertionError("the source equation congruence changed after substitution")
        retained = [
            (existing_label, equation)
            for existing_position, (existing_label, equation) in enumerate(
                zip(labels, substituted)
            )
            if existing_position != position and equation != 0
        ]
        labels = [existing_label for existing_label, _ in retained]
        equations = [equation for _, equation in retained]
        active_variables.remove(variable)

    active_tuple = tuple(active_variables)
    polynomials = [primitive_polynomial(equation, active_tuple) for equation in equations]
    encoded_equations = [encode_polynomial(polynomial) for polynomial in polynomials]
    canonical_stream = json.dumps(
        encoded_equations, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    script_path = Path(__file__).resolve()
    output_path = arguments.output.resolve()
    receipt_path = arguments.receipt.resolve()

    unit_rows = [
        {
            "equation_original_index": relation["equation_index"],
            "unit": render(relation["unit"]),
            "inverse_variable": str(relation["inverse_variable"]),
            "relation_constant": str(relation["constant"]),
            "unit_reciprocal": render(-relation["inverse_variable"] / relation["constant"]),
        }
        for relation in relations
    ]
    reduction = {
        "schema": "known-unit-linear-reduction-v1",
        "status": "PASS_EXACT_QUOTIENT_RING_REDUCTION",
        "input_sha256": sha256(input_path),
        "detected_unit_relations": unit_rows,
        "protected_variables": sorted(str(variable) for variable in protected),
        "eliminations": eliminations,
        "elimination_count": len(eliminations),
        "original_variable_count": len(variables),
        "reduced_variable_count": len(active_tuple),
        "reduced_variables": [str(variable) for variable in active_tuple],
        "original_equation_count": len(source["equations"]),
        "reduced_equation_count": len(polynomials),
        "retained_original_equation_labels": labels,
        "reduced_maximum_total_degree": max(
            (int(polynomial.total_degree()) for polynomial in polynomials), default=-1
        ),
        "reduced_equation_term_counts": [len(polynomial.terms()) for polynomial in polynomials],
        "checks": {
            "inverse_relations_detected_from_isolated_variables": True,
            "every_eliminated_coefficient_is_a_rational_multiple_of_a_known_unit": True,
            "every_source_equation_became_an_explicit_multiple_of_a_retained_unit_relation": True,
            "no_new_localization_added": True,
            "quotient_ring_isomorphism_preserves_unit_ideal": True,
        },
        "claim_boundary": (
            "this proves an exact presentation equivalence over Q; emptiness is "
            "proved only if an exact unit-basis certificate passes on the reduced system"
        ),
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(reduction, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    reduced_input = {
        **source,
        "schema": "hc4-decimic-j2-secant-r10-unit-reduced-rational-input-v1",
        "equation_count": len(polynomials),
        "variable_count": len(active_tuple),
        "variable_names": [str(variable) for variable in active_tuple],
        "equations": encoded_equations,
        "equation_stream_sha256": hashlib.sha256(canonical_stream).hexdigest(),
        "maximum_total_degree": max(
            (int(polynomial.total_degree()) for polynomial in polynomials), default=-1
        ),
        "metadata": {
            **source.get("metadata", {}),
            "known_unit_linear_reduction_receipt": str(receipt_path),
            "known_unit_linear_reduction_receipt_sha256": sha256(receipt_path),
            "source_input_sha256": sha256(input_path),
        },
        "source_sha256": {
            **source.get("source_sha256", {}),
            str(script_path): sha256(script_path),
            str(input_path): sha256(input_path),
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(reduced_input, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(reduction, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
