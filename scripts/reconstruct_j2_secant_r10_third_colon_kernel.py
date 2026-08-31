#!/usr/bin/env sage-python
"""Two-prime reconstruction of the third secant colon-kernel candidate.

The inputs are the first-kernel taps for I2=(F_1,...,F_17,h,h2):M at two
distinct primes.  Matching monic support is reconstructed by CRT.  The result
remains a rational candidate until an identity M*h3 in I2 is proved.
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


EXPECTED_STATUS = "CANDIDATE_MODULAR_SECOND_RESIDUAL_COLON_KERNEL_EXTRACTED"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != (
        "hc4.decimic-j2-secant-r10-second-residual-colon-scout.v1"
    ):
        raise ValueError(f"{path}: unsupported scout schema")
    if payload.get("status") != EXPECTED_STATUS:
        raise ValueError(f"{path}: scout is not a passing candidate event")
    candidates = payload["calculation"]["kernel_polynomials"]
    if len(candidates) != 1:
        raise ValueError(f"{path}: expected exactly one kernel polynomial")
    candidate = candidates[0]
    if (
        candidate["reconstructed_total_degree"] != 4
        or candidate["reported_degree"] != 4
        or candidate["character_weight_mod_12"] != 2
        or candidate["term_count"] != 248
    ):
        raise ValueError(f"{path}: unexpected third-candidate profile")
    terms = {
        tuple(map(int, term["exponents"])): int(term["coefficient"])
        for term in candidate["terms"]
    }
    if len(terms) != 248:
        raise ValueError(f"{path}: duplicate exponent vectors")
    leading_exponents = tuple(map(int, candidate["terms"][0]["exponents"]))
    characteristic = int(payload["characteristic"])
    if terms[leading_exponents] % characteristic != 1:
        raise ValueError(f"{path}: candidate is not monic in the tapped normalization")
    return payload, characteristic, candidate, terms, leading_exponents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts", nargs=2, type=Path)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-secant-r10-third-colon-kernel-qq-reconstruction.json"),
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
    if supports[0] != supports[1]:
        raise ValueError("candidate supports differ")
    leading_exponents = [item[4] for item in loaded]
    if leading_exponents[0] != leading_exponents[1]:
        raise ValueError("tapped leading monomials differ")

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
            observed = int(
                field(coefficient.numerator()) / field(coefficient.denominator())
            )
            if observed != terms[exponents] % prime:
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
    primitive_content = abs(gcd(list(primitive_coefficients.values())))
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
            modular_terms, equations, variables, prime, candidate_character=2
        )
        audit.update(
            {
                "characteristic": prime,
                "tested_ideal": "I2=(17 cubics,h,h2) in degree four and character two",
                "additional_quartic_rows": 0,
                "reason": (
                    "h and h2 have characters four and three, so their constant "
                    "degree-four rows do not enter the character-two block"
                ),
            }
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
    passed = (
        not residue_mismatches
        and maximum_numerator <= uniqueness_bound
        and maximum_denominator <= uniqueness_bound
        and all(test["nontrivial_quotient_class"] for test in membership_tests)
    )
    artifact = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-kernel-qq-candidate.v1",
        "status": (
            "RATIONAL_THIRD_COLON_CANDIDATE_RECONSTRUCTED"
            if passed
            else "INCOMPLETE_THIRD_COLON_CANDIDATE_RECONSTRUCTION"
        ),
        "assurance": "exact two-prime CRT reconstruction; colon identity not replayed",
        "variable_names": list(map(str, variables)),
        "total_degree": 4,
        "character_weight_mod_12": 2,
        "term_count": len(terms),
        "monic_leading_exponents": list(leading_exponents[0]),
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
            "kernel taps and finite-field degree-four nonmembership tests. It does "
            "not prove M*h3 is in I2, lift a colon identity, compute a colon or "
            "saturated ideal, close the secant chart, or establish HC4."
        ),
    }
    artifact_path = arguments.artifact
    if not artifact_path.is_absolute():
        artifact_path = campaign / artifact_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-kernel-reconstruction.v1",
        "status": (
            "PASS_TWO_PRIME_THIRD_COLON_CANDIDATE_RECONSTRUCTION"
            if passed
            else "FAIL_THIRD_COLON_CANDIDATE_RECONSTRUCTION"
        ),
        "assurance": "exact two-prime reconstruction and finite-field nonmembership tests",
        "source_receipts": [
            {"path": str(path), "sha256": sha256(path)} for path in paths
        ],
        "discovery_primes": primes,
        "support_matches": supports[0] == supports[1],
        "support_term_count": len(supports[0]),
        "degree_matches": [item[2]["reconstructed_total_degree"] for item in loaded],
        "character_matches": [item[2]["character_weight_mod_12"] for item in loaded],
        "monic_leading_exponents": [list(item) for item in leading_exponents],
        "monic_leading_coefficients": [item[3][item[4]] for item in loaded],
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
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
