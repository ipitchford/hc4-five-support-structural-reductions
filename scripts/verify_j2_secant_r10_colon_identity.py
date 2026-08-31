#!/usr/bin/env python3
"""Minimal independent replay of the rational secant colon identity.

This checker intentionally uses only Python's standard library.  It does not
import Sage, SymPy, Singular, msolve, or the modular reconstruction script.
The expected problem digest pins the 17 original cubics and the degree-eight
target, preventing a substituted polynomial system from certifying itself.
"""

from __future__ import annotations

import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CERTIFICATE = (
    ROOT / "artifacts" / "j2-secant-r10-colon-identity-qq.json"
)

# Populated from the canonical generator/target stream derived by
# reconstruct_j2_secant_r10_colon_identity.py.  Keeping the value here makes
# this checker reject a self-consistent certificate for a substituted system.
EXPECTED_PROBLEM_SHA256 = (
    "d92609380277ba958acd70884e5bb36b49e047921630b15916b968c1d66c2950"
)


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def coefficient(value: object) -> Fraction:
    if isinstance(value, list):
        if len(value) != 2:
            raise ValueError("a rational coefficient must have two entries")
        return Fraction(int(value[0]), int(value[1]))
    return Fraction(int(value))


def polynomial(data: list[list[object]]) -> dict[tuple[int, ...], Fraction]:
    output = {}
    for exponents, encoded in data:
        monomial = tuple(int(exponent) for exponent in exponents)
        value = coefficient(encoded)
        if not value:
            raise ValueError("zero coefficients are not canonical")
        if monomial in output:
            raise ValueError("duplicate monomial")
        output[monomial] = value
    return output


def add_product(
    accumulator: dict[tuple[int, ...], Fraction],
    left: dict[tuple[int, ...], Fraction],
    right: dict[tuple[int, ...], Fraction],
) -> None:
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            monomial = tuple(
                left_exponent + right_exponent
                for left_exponent, right_exponent in zip(
                    left_monomial, right_monomial, strict=True
                )
            )
            updated = (
                accumulator.get(monomial, Fraction(0))
                + left_coefficient * right_coefficient
            )
            if updated:
                accumulator[monomial] = updated
            else:
                accumulator.pop(monomial, None)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CERTIFICATE
    data = json.loads(path.read_text(encoding="ascii"))
    if data.get("schema") != (
        "hc4.decimic-j2-secant-r10-colon-identity-qq-certificate.v1"
    ):
        raise ValueError("unexpected certificate schema")
    if data.get("status") != "PASS_EXACT_QQ_COLON_IDENTITY":
        raise ValueError("certificate does not claim an exact rational PASS")
    claimed_certificate_digest = data.pop("certificate_sha256")
    if digest(data) != claimed_certificate_digest:
        raise ValueError("certificate digest mismatch")
    problem = data["problem"]
    claimed_problem_digest = problem.pop("sha256")
    if digest(problem) != claimed_problem_digest:
        raise ValueError("problem digest mismatch")
    if claimed_problem_digest != EXPECTED_PROBLEM_SHA256:
        raise ValueError("certificate describes a substituted polynomial system")
    variables = problem["variable_names"]
    if variables != [
        "f3",
        "f4",
        "f5",
        "f6",
        "f7",
        "f8",
        "f10",
        "g0",
        "g1",
        "g2",
        "g3",
        "g4",
        "g5",
        "g6",
        "g7",
        "g8",
        "g9",
        "f9",
    ]:
        raise ValueError("variable stream changed")
    generators = [
        polynomial(serialized) for serialized in problem["normal_generators"]
    ]
    target = polynomial(problem["target_M_times_h"])
    if len(generators) != 17:
        raise ValueError("expected 17 normal generators")
    if any(
        sum(monomial) != 3
        for generator in generators
        for monomial in generator
    ):
        raise ValueError("a normal generator is not homogeneous cubic")
    if any(sum(monomial) != 8 for monomial in target):
        raise ValueError("the target is not homogeneous of degree eight")

    encoded_multipliers = data["multipliers"]
    if len(encoded_multipliers) != len(generators):
        raise ValueError("multiplier count changed")
    multipliers = []
    for index, entry in enumerate(encoded_multipliers):
        if int(entry["normal_generator_position"]) != index:
            raise ValueError("multiplier ordering changed")
        multiplier = polynomial(
            [
                [
                    term["exponents"],
                    (
                        int(term["numerator"])
                        if int(term["denominator"]) == 1
                        else [int(term["numerator"]), int(term["denominator"])]
                    ),
                ]
                for term in entry["terms"]
            ]
        )
        if len(multiplier) != int(entry["term_count"]):
            raise ValueError("multiplier term count changed")
        if any(sum(monomial) != 5 for monomial in multiplier):
            raise ValueError("a nonzero multiplier term is not degree five")
        multipliers.append(multiplier)

    observed: dict[tuple[int, ...], Fraction] = {}
    for generator, multiplier in zip(generators, multipliers, strict=True):
        add_product(observed, generator, multiplier)
    if observed != target:
        support = set(observed) | set(target)
        mismatch_count = sum(
            observed.get(monomial, Fraction(0))
            != target.get(monomial, Fraction(0))
            for monomial in support
        )
        raise ValueError(
            f"exact rational identity has {mismatch_count} mismatched coefficients"
        )
    print("PASS: exact QQ identity M*h=sum(q_i*F_i)")
    print("PASS: 17-cubic system and degree-eight target match the frozen digest")
    print("SCOPE: one colon identity only; saturation, secant closure, and HC4 remain separate")


if __name__ == "__main__":
    main()
