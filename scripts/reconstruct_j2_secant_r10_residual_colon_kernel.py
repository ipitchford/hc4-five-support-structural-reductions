#!/usr/bin/env python3
"""Two-prime reconstruction of the second modular secant colon-kernel form.

The result is a rational *candidate*.  Reconstruction and finite-field
nonmembership are checked here; the residual colon identity is not.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from sage.all import CRT, GF, Integer, gcd, lcm

from certify_j2_secant_r10_colon_kernel import degree_four_membership_test
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


EXPECTED_STATUS = "CANDIDATE_MODULAR_RESIDUAL_COLON_KERNEL_EXTRACTED"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["status"] != EXPECTED_STATUS:
        raise ValueError(f"{path} is not a passing modular residual-colon scout")
    candidates = data["calculation"]["kernel_polynomials"]
    if len(candidates) != 1:
        raise ValueError(f"{path} does not contain exactly one candidate")
    candidate = candidates[0]
    if candidate["reconstructed_total_degree"] != 4:
        raise ValueError("candidate is not quartic")
    terms = {
        tuple(map(int, term["exponents"])): int(term["coefficient"])
        for term in candidate["terms"]
    }
    return data, int(data["characteristic"]), candidate, terms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts", nargs=2, type=Path)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-secant-r10-second-colon-kernel-qq-reconstruction.json"),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    paths = [path if path.is_absolute() else campaign / path for path in arguments.receipts]
    loaded = [load_candidate(path) for path in paths]
    primes = [item[1] for item in loaded]
    if primes[0] == primes[1] or gcd(primes[0], primes[1]) != 1:
        raise ValueError("discovery moduli must be distinct and coprime")
    supports = [set(item[3]) for item in loaded]
    support_matches = supports[0] == supports[1]
    if not support_matches:
        raise ValueError("candidate supports differ")
    characters = [item[2]["character_weight_mod_12"] for item in loaded]
    if characters != [3, 3]:
        raise ValueError("candidate characters differ from the expected character 3")

    modulus = Integer(primes[0]) * Integer(primes[1])
    uniqueness_bound = Integer(math.isqrt(int(modulus // 2)))
    reconstructed = {}
    residue_mismatches = []
    for exponents in sorted(supports[0]):
        residue = CRT(
            Integer(loaded[0][3][exponents]),
            Integer(loaded[1][3][exponents]),
            Integer(primes[0]),
            Integer(primes[1]),
        )
        coefficient = residue.rational_reconstruction(modulus)
        reconstructed[exponents] = coefficient
        for prime, terms in zip(primes, [loaded[0][3], loaded[1][3]], strict=True):
            field = GF(prime)
            reduced = field(coefficient.numerator()) / field(coefficient.denominator())
            if int(reduced) != terms[exponents] % prime:
                residue_mismatches.append(
                    {"prime": prime, "exponents": list(exponents)}
                )

    maximum_numerator = max(abs(value.numerator()) for value in reconstructed.values())
    maximum_denominator = max(value.denominator() for value in reconstructed.values())
    common_denominator = lcm(value.denominator() for value in reconstructed.values())
    primitive_coefficients = {
        exponents: Integer(value * common_denominator)
        for exponents, value in reconstructed.items()
    }
    primitive_content = gcd(list(primitive_coefficients.values()))
    if primitive_content < 0:
        primitive_content = -primitive_content
    primitive_coefficients = {
        exponents: value // primitive_content
        for exponents, value in primitive_coefficients.items()
    }
    primitive_maximum = max(abs(value) for value in primitive_coefficients.values())

    equations, variables, _, _ = homogeneous_saturation_system()
    membership_tests = []
    for prime in primes:
        field = GF(prime)
        modular_terms = [
            (
                exponents,
                int(field(value.numerator()) / field(value.denominator())),
            )
            for exponents, value in reconstructed.items()
        ]
        audit = degree_four_membership_test(
            modular_terms, equations, variables, prime, candidate_character=3
        )
        audit["characteristic"] = prime
        audit["note"] = (
            "h has character 4, so adjoining h does not enlarge the character-3 "
            "degree-four subspace tested here"
        )
        membership_tests.append(audit)

    terms = [
        {
            "exponents": list(exponents),
            "numerator": str(value.numerator()),
            "denominator": str(value.denominator()),
        }
        for exponents, value in sorted(reconstructed.items())
    ]
    primitive_terms = [
        {"exponents": list(exponents), "coefficient": str(value)}
        for exponents, value in sorted(primitive_coefficients.items())
    ]
    artifact = {
        "schema": "hc4.decimic-j2-secant-r10-second-colon-kernel-qq-candidate.v1",
        "status": "RATIONAL_CANDIDATE_RECONSTRUCTED_FROM_TWO_MODULAR_TAPS",
        "assurance": "exact two-prime CRT and rational reconstruction; colon identity not replayed",
        "variable_names": list(map(str, variables)),
        "total_degree": 4,
        "character_weight_mod_12": 3,
        "term_count": len(terms),
        "discovery_primes": primes,
        "crt_modulus": str(modulus),
        "equal_numerator_denominator_uniqueness_bound": str(uniqueness_bound),
        "maximum_absolute_numerator": str(maximum_numerator),
        "maximum_denominator": str(maximum_denominator),
        "common_denominator": str(common_denominator),
        "primitive_integer_content_before_normalization": str(primitive_content),
        "primitive_integer_maximum_absolute_coefficient": str(primitive_maximum),
        "terms": terms,
        "primitive_integer_terms": primitive_terms,
        "claim_boundary": (
            "This is a uniquely bounded rational reconstruction of matching modular "
            "tap outputs. It does not prove M*h2 is in (I,h), establish h2 over QQ "
            "as a colon element, compute a colon ideal, or prove saturation."
        ),
    }
    artifact_path = arguments.artifact
    if not artifact_path.is_absolute():
        artifact_path = campaign / artifact_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = {
        "schema": "hc4.decimic-j2-secant-r10-second-colon-kernel-reconstruction.v1",
        "status": (
            "PASS_TWO_PRIME_RATIONAL_CANDIDATE_RECONSTRUCTION"
            if not residue_mismatches
            and all(test["nontrivial_quotient_class"] for test in membership_tests)
            else "FAIL_RECONSTRUCTION_OR_DEGREE_FOUR_NONMEMBERSHIP"
        ),
        "assurance": "exact two-prime reconstruction and bounded finite-field nonmembership tests",
        "source_receipts": [
            {"path": str(path), "sha256": sha256(path)} for path in paths
        ],
        "discovery_primes": primes,
        "support_matches": support_matches,
        "support_term_count": len(supports[0]),
        "degree_matches": [item[2]["reconstructed_total_degree"] for item in loaded],
        "character_matches": characters,
        "monic_leading_coefficients": [
            item[3][next(iter(item[3]))] for item in loaded
        ],
        "crt_modulus": str(modulus),
        "equal_numerator_denominator_uniqueness_bound": str(uniqueness_bound),
        "maximum_absolute_numerator": str(maximum_numerator),
        "maximum_denominator": str(maximum_denominator),
        "both_heights_within_uniqueness_bound": (
            maximum_numerator <= uniqueness_bound
            and maximum_denominator <= uniqueness_bound
        ),
        "common_denominator": str(common_denominator),
        "primitive_integer_content_before_normalization": str(primitive_content),
        "primitive_integer_maximum_absolute_coefficient": str(primitive_maximum),
        "coefficient_residue_mismatch_count": len(residue_mismatches),
        "coefficient_residue_mismatches": residue_mismatches,
        "degree_four_nonmembership_tests": membership_tests,
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "artifact": {
            "path": str(artifact_path),
            "sha256": sha256(artifact_path),
            "byte_count": artifact_path.stat().st_size,
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": artifact["claim_boundary"],
    }
    output_path = arguments.output
    if not output_path.is_absolute():
        output_path = campaign / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
