#!/usr/bin/env python3
"""Standard-library replay of the exact rational second-colon identity.

This verifier imports neither the producer nor Sage, SymPy, Singular, or
msolve.  A hard-coded problem digest pins the 17 cubics, the first quartic h,
and the target M*h2 before the serialized rational multipliers are replayed
coefficientwise with ``fractions.Fraction``.
"""

from __future__ import annotations

import hashlib
import json
import resource
import sys
import time
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CERTIFICATE = ROOT / "artifacts/j2-secant-r10-second-colon-identity-qq.json"
EXPECTED_PROBLEM_SHA256 = (
    "2a23b5db35b3ed12e72c6925467f15659c62e80d5644b586d18ab18766f364c7"
)
VARIABLES = [
    "f3", "f4", "f5", "f6", "f7", "f8", "f10",
    "g0", "g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "f9",
]


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
        monomial = tuple(map(int, exponents))
        value = coefficient(encoded)
        if len(monomial) != len(VARIABLES) or not value or monomial in output:
            raise ValueError("noncanonical serialized polynomial")
        output[monomial] = value
    return output


def add_product(accumulator: dict, left: dict, right: dict) -> None:
    for left_monomial, left_coefficient in left.items():
        for right_monomial, right_coefficient in right.items():
            monomial = tuple(
                a + b for a, b in zip(left_monomial, right_monomial, strict=True)
            )
            updated = (
                accumulator.get(monomial, Fraction(0))
                + left_coefficient * right_coefficient
            )
            if updated:
                accumulator[monomial] = updated
            else:
                accumulator.pop(monomial, None)


def main() -> int:
    started = time.perf_counter()
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CERTIFICATE
    artifact_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    data = json.loads(path.read_text(encoding="ascii"))
    if data.get("schema") != (
        "hc4.decimic-j2-secant-r10-second-colon-identity-qq-certificate.v1"
    ):
        raise ValueError("unexpected certificate schema")
    if data.get("status") != "PASS_EXACT_QQ_SECOND_COLON_IDENTITY":
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
    if problem.get("variable_names") != VARIABLES or data.get("variable_names") != VARIABLES:
        raise ValueError("variable stream changed")

    generators = [polynomial(serialized) for serialized in problem["generators"]]
    target = polynomial(problem["target_M_times_h2"])
    if len(generators) != 18 or int(data.get("generator_count", -1)) != 18:
        raise ValueError("expected 18 generators")
    if int(data.get("normal_cubic_generator_count", -1)) != 17:
        raise ValueError("expected 17 original cubics")
    if any(sum(monomial) != 3 for generator in generators[:17] for monomial in generator):
        raise ValueError("an original generator is not cubic")
    if any(sum(monomial) != 4 for monomial in generators[17]):
        raise ValueError("the adjoined first-colon generator is not quartic")
    if any(sum(monomial) != 8 for monomial in target):
        raise ValueError("the target is not degree eight")

    encoded_multipliers = data["multipliers"]
    if len(encoded_multipliers) != len(generators):
        raise ValueError("multiplier count changed")
    multipliers = []
    for index, entry in enumerate(encoded_multipliers):
        if int(entry["generator_position"]) != index:
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
        expected_degree = 5 if index < 17 else 4
        if any(sum(monomial) != expected_degree for monomial in multiplier):
            raise ValueError("a multiplier has the wrong total degree")
        multipliers.append(multiplier)

    observed: dict[tuple[int, ...], Fraction] = {}
    for generator, multiplier in zip(generators, multipliers, strict=True):
        add_product(observed, generator, multiplier)
    support = set(observed) | set(target)
    mismatches = [
        monomial
        for monomial in support
        if observed.get(monomial, Fraction(0)) != target.get(monomial, Fraction(0))
    ]
    if mismatches:
        raise ValueError(
            f"exact rational identity has {len(mismatches)} mismatched coefficients"
        )

    uniqueness = data["reconstruction"]
    if not uniqueness.get("all_coefficients_inside_product_uniqueness_budget"):
        raise ValueError("certificate does not record strict reconstruction uniqueness")
    if not (
        2
        * int(uniqueness["maximum_absolute_numerator"])
        * int(uniqueness["maximum_denominator"])
        < int(uniqueness["crt_modulus"])
    ):
        raise ValueError("reconstruction height exceeds the frozen CRT modulus")
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "status": "PASS_STANDARD_LIBRARY_EXACT_QQ_SECOND_COLON_IDENTITY_REPLAY",
        "artifact": str(path),
        "artifact_sha256": artifact_sha256,
        "problem_sha256": claimed_problem_digest,
        "certificate_sha256": claimed_certificate_digest,
        "generator_count": len(generators),
        "multiplier_term_count": sum(map(len, multipliers)),
        "target_term_count": len(target),
        "mismatch_count": 0,
        "strict_crt_uniqueness_verified": True,
        "wall_seconds": time.perf_counter() - started,
        "maximum_rss_native": usage.ru_maxrss,
        "claim_boundary": (
            "This independently proves only M*h2 in (F_1,...,F_17,h) over QQ. "
            "It does not determine a colon or saturated ideal, close the secant "
            "chart, or establish HC4."
        ),
    }
    output = ROOT / "receipts/hsop-j2-secant-r10-second-colon-identity-qq-independent-replay.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
