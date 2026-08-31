#!/usr/bin/env python3
"""Independently reconstruct the double-conic Hessian normal layers.

The derivation does not import Roy van Rijn's transvectant table.  Harmonic
lifts are obtained from the closed projection recurrence for

    Box = d_x d_z - (1/4) d_y^2,  q = x*z-y^2,

and each cubic covariant block is fitted exactly in an automatically
enumerated iterated-transvectant spanning family.  Disjoint symbolic samples
are reserved for holdout verification.
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path

import sympy as sp


x, y, z, s, t = sp.symbols("x y z s t")
scale_f, scale_g, scale_k = sp.symbols("scale_f scale_g scale_k")
q = x * z - y**2

FORM_DEGREES = {"f": 10, "g": 6, "k": 2}
TERNARY_DEGREES = {"f": 5, "g": 3, "k": 1}
OUTPUT_DEGREES = (18, 14, 10, 6)
MULTIDEGREES = tuple(
    (a, b, 3 - a - b)
    for a in range(4)
    for b in range(4 - a)
)


@dataclass(frozen=True, order=True)
class Term:
    first: str
    second: str
    first_order: int
    third: str
    second_order: int

    def render(self) -> str:
        return (
            f"[[{self.first},{self.second}]_{self.first_order},"
            f"{self.third}]_{self.second_order}"
        )


def box(polynomial: sp.Expr) -> sp.Expr:
    return sp.expand(
        sp.diff(polynomial, x, z) - sp.diff(polynomial, y, 2) / 4
    )


def conic_restriction(polynomial: sp.Expr) -> sp.Expr:
    return sp.expand(polynomial.subs({x: s**2, y: s * t, z: t**2}))


def canonical_lift(binary: sp.Expr, ternary_degree: int) -> sp.Expr:
    """Return a monomial lift whose conic restriction is ``binary``."""

    polynomial = sp.Poly(sp.expand(binary), s, t)
    result = sp.Integer(0)
    for index in range(2 * ternary_degree + 1):
        coefficient = polynomial.coeff_monomial(
            s ** (2 * ternary_degree - index) * t**index
        )
        half = index // 2
        if index % 2 == 0:
            monomial = x ** (ternary_degree - half) * z**half
        else:
            monomial = (
                x ** (ternary_degree - half - 1) * y * z**half
            )
        result += coefficient * monomial
    return sp.expand(result)


def harmonic_lift(binary: sp.Expr, ternary_degree: int) -> sp.Expr:
    """Project a lift to ``ker(Box)`` by a closed recurrence.

    For homogeneous ``F`` of degree ``r``, direct differentiation gives

        Box(q^j F) = q^j Box(F) + j(r+j+1/2) q^(j-1) F.

    Applying this to successive ``Box`` powers yields the coefficient
    recurrence used below.
    """

    current = canonical_lift(binary, ternary_degree)
    coefficient = sp.Integer(1)
    result = sp.Integer(0)
    for index in range(ternary_degree // 2 + 1):
        result += coefficient * q**index * current
        current = box(current)
        denominator = (index + 1) * (
            sp.Rational(2 * (ternary_degree - index) - 1, 2)
        )
        coefficient = -coefficient / denominator
    result = sp.expand(result)
    assert box(result) == 0
    assert sp.expand(conic_restriction(result) - binary) == 0
    return result


def divide_by_q(polynomial: sp.Expr) -> sp.Expr:
    quotient, remainder = sp.div(
        sp.Poly(sp.expand(polynomial), z), sp.Poly(q, z)
    )
    assert remainder.as_expr() == 0
    return sp.expand(quotient.as_expr())


def decompose_hessian_layers(forms: dict[str, sp.Expr]) -> dict[int, sp.Expr]:
    h5 = (
        scale_f * harmonic_lift(forms["f"], 5)
        + scale_g * q * harmonic_lift(forms["g"], 3)
        + scale_k * q**2 * harmonic_lift(forms["k"], 1)
    )
    current = sp.expand(sp.hessian(h5, (x, y, z)).det())
    result: dict[int, sp.Expr] = {}
    for ternary_degree in (9, 7, 5, 3, 1):
        binary = conic_restriction(current)
        result[2 * ternary_degree] = binary
        if ternary_degree > 1:
            current = divide_by_q(
                current - harmonic_lift(binary, ternary_degree)
            )
    return result


def transvectant(first: sp.Expr, second: sp.Expr, order: int) -> sp.Expr:
    return sp.expand(
        sum(
            (-1) ** index
            * sp.binomial(order, index)
            * sp.diff(first, s, order - index, t, index)
            * sp.diff(second, s, index, t, order - index)
            for index in range(order + 1)
        )
    )


def evaluate_term(term: Term, forms: dict[str, sp.Expr]) -> sp.Expr:
    first = transvectant(
        forms[term.first], forms[term.second], term.first_order
    )
    return transvectant(first, forms[term.third], term.second_order)


def candidate_terms(
    output_degree: int, multidegree: tuple[int, int, int]
) -> tuple[Term, ...]:
    labels = (
        ["f"] * multidegree[0]
        + ["g"] * multidegree[1]
        + ["k"] * multidegree[2]
    )
    terms: set[Term] = set()
    for first, second, third in set(itertools.permutations(labels, 3)):
        for first_order in range(
            min(FORM_DEGREES[first], FORM_DEGREES[second]) + 1
        ):
            intermediate = (
                FORM_DEGREES[first]
                + FORM_DEGREES[second]
                - 2 * first_order
            )
            numerator = intermediate + FORM_DEGREES[third] - output_degree
            if numerator < 0 or numerator % 2:
                continue
            second_order = numerator // 2
            if second_order <= min(intermediate, FORM_DEGREES[third]):
                terms.add(
                    Term(first, second, first_order, third, second_order)
                )
    return tuple(sorted(terms))


def binary_coefficients(polynomial: sp.Expr, degree: int) -> list[sp.Expr]:
    poly = sp.Poly(sp.expand(polynomial), s, t)
    return [
        poly.coeff_monomial(s ** (degree - index) * t**index)
        for index in range(degree + 1)
    ]


def random_forms(generator: random.Random) -> dict[str, sp.Expr]:
    result: dict[str, sp.Expr] = {}
    for label, degree in FORM_DEGREES.items():
        coefficients = [sp.Integer(generator.randint(-2, 2)) for _ in range(degree + 1)]
        if not any(coefficients):
            coefficients[0] = sp.Integer(1)
        result[label] = sum(
            coefficients[index] * s ** (degree - index) * t**index
            for index in range(degree + 1)
        )
    return result


def component(
    layer: sp.Expr, multidegree: tuple[int, int, int]
) -> sp.Expr:
    return sp.Poly(layer, scale_f, scale_g, scale_k).coeff_monomial(
        scale_f ** multidegree[0]
        * scale_g ** multidegree[1]
        * scale_k ** multidegree[2]
    )


def sample_data(seed: int, count: int) -> list[tuple[dict[str, sp.Expr], dict[int, sp.Expr]]]:
    generator = random.Random(seed)
    samples = []
    for index in range(count):
        started = time.perf_counter()
        forms = random_forms(generator)
        layers = decompose_hessian_layers(forms)
        samples.append((forms, layers))
        print(
            f"sample {index + 1}/{count}: exact layers derived in "
            f"{time.perf_counter() - started:.3f}s",
            flush=True,
        )
    return samples


def fit_block(
    output_degree: int,
    multidegree: tuple[int, int, int],
    training,
    holdout,
) -> dict[str, object]:
    terms = candidate_terms(output_degree, multidegree)
    rows: list[list[sp.Expr]] = []
    targets: list[sp.Expr] = []
    for forms, layers in training:
        actual = component(layers[output_degree], multidegree)
        candidates = [evaluate_term(term, forms) for term in terms]
        candidate_coefficients = [
            binary_coefficients(candidate, output_degree)
            for candidate in candidates
        ]
        actual_coefficients = binary_coefficients(actual, output_degree)
        for index, target in enumerate(actual_coefficients):
            rows.append([column[index] for column in candidate_coefficients])
            targets.append(target)

    if not terms:
        assert not any(targets)
        return {
            "multidegree": list(multidegree),
            "candidate_count": 0,
            "rank": 0,
            "basis": [],
            "holdout_pass": True,
        }

    matrix = sp.Matrix(rows)
    target_vector = sp.Matrix(targets)
    nonzero_columns = [
        index for index in range(matrix.cols) if any(matrix[:, index])
    ]
    reduced = matrix[:, nonzero_columns]
    _, pivot_indices = reduced.rref()
    basis_columns = [nonzero_columns[index] for index in pivot_indices]
    basis_matrix = matrix[:, basis_columns]
    rank = len(basis_columns)
    if rank == 0:
        assert not any(target_vector)
        coefficients = sp.zeros(0, 1)
    else:
        solution, parameters = basis_matrix.gauss_jordan_solve(target_vector)
        assert parameters.rows == 0
        coefficients = solution

    for forms, layers in holdout:
        predicted = sp.Integer(0)
        for coefficient_value, column in zip(coefficients, basis_columns):
            predicted += coefficient_value * evaluate_term(terms[column], forms)
        actual = component(layers[output_degree], multidegree)
        assert sp.expand(predicted - actual) == 0

    return {
        "multidegree": list(multidegree),
        "candidate_count": len(terms),
        "nonzero_candidate_count": len(nonzero_columns),
        "rank": rank,
        "basis": [
            {
                "term": terms[column].render(),
                "coefficient": str(coefficient_value),
            }
            for coefficient_value, column in zip(coefficients, basis_columns)
            if coefficient_value != 0
        ],
        "holdout_pass": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-samples", type=int, default=3)
    parser.add_argument("--holdout-samples", type=int, default=1)
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.training_samples < 1 or args.holdout_samples < 1:
        raise SystemExit("training and holdout sample counts must be positive")

    started = time.perf_counter()
    samples = sample_data(
        args.seed, args.training_samples + args.holdout_samples
    )
    training = samples[: args.training_samples]
    holdout = samples[args.training_samples :]
    layers: dict[str, list[dict[str, object]]] = {}
    for output_degree in OUTPUT_DEGREES:
        records = []
        for multidegree in MULTIDEGREES:
            record = fit_block(
                output_degree, multidegree, training, holdout
            )
            records.append(record)
        layers[str(output_degree)] = records
        print(
            f"PASS: Phi_{output_degree} independently reconstructed and "
            "verified on held-out symbolic samples",
            flush=True,
        )

    result = {
        "schema": "hc4-double-conic-independent-normal-layers-v1",
        "status": "PASS",
        "method": {
            "harmonic_projection": (
                "closed Box(q^j F) recurrence; no matrix-inverse lift"
            ),
            "covariant_basis": (
                "all admissible ordered iterated transvectants; exact "
                "pivot basis selected from training samples"
            ),
            "reference_coefficient_table_imported": False,
        },
        "seed": args.seed,
        "training_samples": args.training_samples,
        "holdout_samples": args.holdout_samples,
        "layers": layers,
        "wall_seconds": time.perf_counter() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
