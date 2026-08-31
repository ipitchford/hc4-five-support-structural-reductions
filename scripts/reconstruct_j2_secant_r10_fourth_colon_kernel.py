#!/usr/bin/env -S sage -python
"""Two-prime reconstruction of the conditional fourth colon-kernel candidate.

The inputs are first-kernel taps for I3=(F_1,...,F_17,h,h2,h3):M at two
distinct primes.  Matching monic support is reconstructed by CRT.  Since the
h3 colon identity is not an input theorem here, the result is conditional on
the future proof that M*h3 belongs to I2 over QQ.
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


EXPECTED_SCHEMA = "hc4.decimic-j2-secant-r10-third-residual-colon-scout.v1"
EXPECTED_STATUS = (
    "CANDIDATE_MODULAR_THIRD_RESIDUAL_COLON_KERNEL_EXTRACTED_CONDITIONALLY"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != EXPECTED_SCHEMA:
        raise ValueError(f"{path}: unsupported scout schema")
    if payload.get("status") != EXPECTED_STATUS:
        raise ValueError(f"{path}: scout is not a passing conditional candidate event")
    candidates = payload["calculation"]["kernel_polynomials"]
    if len(candidates) != 1:
        raise ValueError(f"{path}: expected exactly one kernel polynomial")
    candidate = candidates[0]
    expected_profile = {
        "basis_index": 6312,
        "reported_degree": 4,
        "reconstructed_total_degree": 4,
        "character_weight_mod_12": 1,
        "term_count": 250,
    }
    observed_profile = {key: candidate[key] for key in expected_profile}
    if observed_profile != expected_profile:
        raise ValueError(f"{path}: unexpected fourth-candidate profile {observed_profile}")
    terms = {
        tuple(map(int, term["exponents"])): int(term["coefficient"])
        for term in candidate["terms"]
    }
    if len(terms) != 250:
        raise ValueError(f"{path}: duplicate exponent vectors")
    leading_exponents = tuple(map(int, candidate["terms"][0]["exponents"]))
    characteristic = int(payload["characteristic"])
    if terms[leading_exponents] % characteristic != 1:
        raise ValueError(f"{path}: candidate is not monic in the tapped normalization")
    if payload["conditional_predecessor_gate"]["proved_by_this_scout"] is not False:
        raise ValueError(f"{path}: conditional predecessor gate was misstated")
    return payload, characteristic, candidate, terms, leading_exponents


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipts", nargs=2, type=Path)
    parser.add_argument(
        "--artifact",
        type=Path,
        default=Path("artifacts/j2-secant-r10-fourth-colon-kernel-qq-candidate.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-fourth-colon-kernel-qq-reconstruction.json"
        ),
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
    reconstruction_failures = []
    for exponents in sorted(supports[0]):
        residue = CRT(
            Integer(loaded[0][3][exponents]),
            Integer(loaded[1][3][exponents]),
            Integer(primes[0]),
            Integer(primes[1]),
        )
        try:
            coefficient = residue.rational_reconstruction(modulus)
        except ArithmeticError:
            reconstruction_failures.append(list(exponents))
            continue
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

    complete = len(reconstructed) == len(supports[0])
    maximum_numerator = (
        max(abs(value.numerator()) for value in reconstructed.values())
        if reconstructed
        else None
    )
    maximum_denominator = (
        max(value.denominator() for value in reconstructed.values())
        if reconstructed
        else None
    )
    common_denominator = (
        lcm(value.denominator() for value in reconstructed.values())
        if complete
        else None
    )
    primitive_content = None
    primitive_maximum = None
    primitive_coefficients = {}
    if complete:
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
    if complete:
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
                modular_terms, equations, variables, prime, candidate_character=1
            )
            audit.update(
                {
                    "characteristic": prime,
                    "tested_ideal": "I3=(17 cubics,h,h2,h3) in degree four and character one",
                    "additional_quartic_rows": 0,
                    "reason": (
                        "h, h2, and h3 have characters four, three, and two, so "
                        "their constant degree-four rows do not enter character one"
                    ),
                }
            )
            membership_tests.append(audit)

    within_bound = (
        complete
        and maximum_numerator <= uniqueness_bound
        and maximum_denominator <= uniqueness_bound
    )
    passed = (
        within_bound
        and not residue_mismatches
        and all(test["nontrivial_quotient_class"] for test in membership_tests)
        and len(membership_tests) == 2
    )
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
    claim_boundary = (
        "This result is conditional on the separately unproved identity M*h3 in I2. "
        "It is a uniquely bounded rational reconstruction of matching modular taps "
        "and finite-field degree-four nonmembership tests. It does not prove M*h4 "
        "is in I3, lift a colon identity, compute a colon or saturated ideal, close "
        "the secant chart, or establish HC4."
    )
    artifact = {
        "schema": "hc4.decimic-j2-secant-r10-fourth-colon-kernel-qq-candidate.v1",
        "status": (
            "RATIONAL_FOURTH_COLON_CANDIDATE_RECONSTRUCTED_CONDITIONALLY"
            if passed
            else "INCOMPLETE_FOURTH_COLON_CANDIDATE_RECONSTRUCTION"
        ),
        "assurance": "exact two-prime CRT reconstruction conditional on the h3 identity",
        "conditional_predecessor_statement": "M*h3 belongs to I2 over QQ",
        "variable_names": list(map(str, variables)),
        "total_degree": 4,
        "character_weight_mod_12": 1,
        "term_count": len(terms),
        "monic_leading_exponents": list(leading_exponents[0]),
        "discovery_primes": primes,
        "crt_modulus": str(modulus),
        "equal_numerator_denominator_uniqueness_bound": str(uniqueness_bound),
        "maximum_absolute_numerator": (
            None if maximum_numerator is None else str(maximum_numerator)
        ),
        "maximum_denominator": (
            None if maximum_denominator is None else str(maximum_denominator)
        ),
        "common_denominator": (
            None if common_denominator is None else str(common_denominator)
        ),
        "primitive_integer_content_before_normalization": (
            None if primitive_content is None else str(primitive_content)
        ),
        "primitive_integer_maximum_absolute_coefficient": (
            None if primitive_maximum is None else str(primitive_maximum)
        ),
        "terms": terms,
        "primitive_integer_terms": primitive_terms,
        "claim_boundary": claim_boundary,
    }
    artifact_path = arguments.artifact
    if not artifact_path.is_absolute():
        artifact_path = campaign / artifact_path
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    result = {
        "schema": "hc4.decimic-j2-secant-r10-fourth-colon-kernel-reconstruction.v1",
        "status": (
            "PASS_TWO_PRIME_FOURTH_COLON_CANDIDATE_RECONSTRUCTION_CONDITIONAL"
            if passed
            else "FAIL_FOURTH_COLON_CANDIDATE_RECONSTRUCTION"
        ),
        "assurance": "exact two-prime reconstruction and finite-field nonmembership tests",
        "conditional_predecessor_statement": "M*h3 belongs to I2 over QQ",
        "source_receipts": [
            {"path": str(path), "sha256": sha256(path)} for path in paths
        ],
        "discovery_primes": primes,
        "support_matches": supports[0] == supports[1],
        "support_term_count": len(supports[0]),
        "basis_indices": [item[2]["basis_index"] for item in loaded],
        "degree_matches": [item[2]["reconstructed_total_degree"] for item in loaded],
        "character_matches": [item[2]["character_weight_mod_12"] for item in loaded],
        "monic_leading_exponents": [list(item) for item in leading_exponents],
        "monic_leading_coefficients": [item[3][item[4]] for item in loaded],
        "crt_modulus": str(modulus),
        "equal_numerator_denominator_uniqueness_bound": str(uniqueness_bound),
        "maximum_absolute_numerator": (
            None if maximum_numerator is None else str(maximum_numerator)
        ),
        "maximum_denominator": (
            None if maximum_denominator is None else str(maximum_denominator)
        ),
        "all_terms_rationally_reconstructed": complete,
        "rational_reconstruction_failure_count": len(reconstruction_failures),
        "rational_reconstruction_failures": reconstruction_failures,
        "both_heights_within_uniqueness_bound": within_bound,
        "common_denominator": (
            None if common_denominator is None else str(common_denominator)
        ),
        "primitive_integer_content_before_normalization": (
            None if primitive_content is None else str(primitive_content)
        ),
        "primitive_integer_maximum_absolute_coefficient": (
            None if primitive_maximum is None else str(primitive_maximum)
        ),
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
        "claim_boundary": claim_boundary,
    }
    output_path = arguments.output
    if not output_path.is_absolute():
        output_path = campaign / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
