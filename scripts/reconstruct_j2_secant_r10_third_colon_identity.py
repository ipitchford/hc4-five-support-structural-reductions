#!/usr/bin/env sage-python
"""CRT-reconstruct and exactly replay the third colon identity over QQ.

Every source certificate must use the same fixed-free gauge and prove

    M*h3 = sum(q_i*F_i) + q_18*h + q_19*h2

over a distinct prime field.  Acceptance requires complete rational-candidate
enumeration in the declared height region, singleton selection after the
frozen selector primes, an exact coefficientwise QQ replay, and every held-out
replay.  The height inequality ``2*abs(n)*d < M`` is an enumeration theorem,
not a uniqueness theorem; the exact QQ replay is the proof gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import sympy as sp
from sage.all import ZZ, crt

from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    CERTIFICATE_SCHEMA,
    build_character_block,
    canonical_hash,
)
from reconstruct_j2_secant_r10_colon_identity import (
    canonical_digest,
    file_sha256,
    multiply_add_modular,
    multiply_add_rational,
    polynomial_terms_qq,
    rational_residue,
    reconstruct_residue_vector,
    reduce_qq_terms,
    serialize_sparse_polynomial,
    sparse_stream_sha256,
    subtract_sparse,
)
from scout_decimic_nullcone_hsop import digest


class ReconstructionInsufficient(ValueError):
    """Carry a frozen partial-height profile without claiming nonmembership."""

    def __init__(self, diagnostic: dict[str, object]):
        super().__init__(
            "rational reconstruction failed at coordinate "
            f"{diagnostic['failing_coordinate']}"
        )
        self.diagnostic = diagnostic


def canonical_problem(campaign: Path) -> dict[str, object]:
    """Build the frozen rational problem using a full-support auxiliary prime."""

    block = build_character_block(campaign, 173)
    return {
        "equations": block["normal_equations"],
        "variables": block["variables"],
        "generators": block["generators"],
        "generator_degrees": block["generator_degrees"],
        "multiplier_degrees": block["multiplier_degrees"],
        "generator_weights": block["generator_weights"],
        "target": block["target_expression"],
        "target_weight": block["target_weight"],
        "descriptors": block["descriptors"],
        "monomials": block["monomials"],
    }


def load_certificate(
    path: Path,
    problem: dict[str, object],
    descriptor_hash: str,
    monomial_hash: str,
    generator_hash: str,
    target_hash: str,
) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="ascii"))
    if payload.get("schema") != CERTIFICATE_SCHEMA:
        raise ValueError(f"{path}: unsupported certificate schema")
    characteristic = int(payload["characteristic"])
    if characteristic <= 5 or not sp.isprime(characteristic):
        raise ValueError(f"{path}: inadmissible characteristic")
    if payload.get("variable_names") != [str(v) for v in problem["variables"]]:
        raise ValueError(f"{path}: variable stream changed")
    expected_hashes = {
        "row_descriptor_sha256": descriptor_hash,
        "monomial_stream_sha256": monomial_hash,
        "generator_stream_sha256": generator_hash,
        "target_sha256": target_hash,
    }
    for key, expected in expected_hashes.items():
        if payload.get(key) != expected:
            raise ValueError(f"{path}: {key} changed")
    if payload.get("target_character_weight") != 3:
        raise ValueError(f"{path}: target character changed")
    if payload.get("generator_degrees") != problem["generator_degrees"]:
        raise ValueError(f"{path}: generator degrees changed")
    if payload.get("multiplier_degrees") != problem["multiplier_degrees"]:
        raise ValueError(f"{path}: multiplier degrees changed")

    descriptors = problem["descriptors"]
    pivots = list(map(int, payload.get("pivot_unknown_indices", [])))
    free = list(map(int, payload.get("free_unknown_indices", [])))
    universe = set(range(len(descriptors)))
    if (
        len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != universe
        or payload.get("pivot_unknown_indices_sha256") != canonical_hash(pivots)
        or payload.get("free_unknown_indices_sha256") != canonical_hash(free)
    ):
        raise ValueError(f"{path}: invalid pivot/free profile")
    vector = list(map(int, payload.get("coordinate_vector", [])))
    if (
        len(vector) != len(descriptors)
        or payload.get("coordinate_vector_sha256") != canonical_hash(vector)
        or any(vector[index] % characteristic for index in free)
    ):
        raise ValueError(f"{path}: invalid coordinate vector")
    residues = {
        index: value % characteristic
        for index, value in enumerate(vector)
        if value % characteristic
    }
    observed_support = {}
    for record in payload.get("solution_support", []):
        index = int(record["unknown_index"])
        if index in observed_support or not 0 <= index < len(descriptors):
            raise ValueError(f"{path}: malformed sparse support")
        generator_index, exponents = descriptors[index]
        if (
            int(record["generator_position"]) != generator_index
            or tuple(map(int, record["multiplier_exponents"])) != exponents
        ):
            raise ValueError(f"{path}: support descriptor mismatch")
        coefficient = int(record["coefficient"]) % characteristic
        if not coefficient:
            raise ValueError(f"{path}: zero support coefficient")
        observed_support[index] = coefficient
    if observed_support != residues:
        raise ValueError(f"{path}: sparse support and vector disagree")

    multipliers = [{} for _ in problem["generators"]]
    for index, coefficient in residues.items():
        generator_index, exponents = descriptors[index]
        multipliers[generator_index][exponents] = coefficient
    source = payload.get("gauge_source")
    if source is not None:
        source_path = Path(source["path"])
        if not source_path.is_file() or file_sha256(source_path) != source["sha256"]:
            raise ValueError(f"{path}: gauge-source file/hash mismatch")
    return {
        "path": path,
        "sha256": file_sha256(path),
        "characteristic": characteristic,
        "pivots": pivots,
        "free": free,
        "coordinate_residues": residues,
        "multipliers": multipliers,
        "monomial_stream_sha256": payload["monomial_stream_sha256"],
    }


def replay_modular(certificate, generator_terms, target_terms):
    prime = int(certificate["characteristic"])
    generators = [reduce_qq_terms(item, prime) for item in generator_terms]
    target = reduce_qq_terms(target_terms, prime)
    observed = {}
    for generator, multiplier in zip(
        generators, certificate["multipliers"], strict=True
    ):
        multiply_add_modular(observed, generator, multiplier, prime)
    remainder = subtract_sparse(target, observed)
    return {
        "characteristic": prime,
        "identity_zero": not remainder,
        "remainder_term_count": len(remainder),
        "multiplier_support_count": sum(map(len, certificate["multipliers"])),
        "multiplier_stream_sha256": sparse_stream_sha256(certificate["multipliers"]),
    }


def reconstruct_multipliers(
    certificates, descriptors, generator_count, heldout_certificates=()
):
    primes = [int(item["characteristic"]) for item in certificates]
    if len(set(primes)) != len(primes):
        raise ValueError("reconstruction primes are not distinct")
    pivot_set = set(certificates[0]["pivots"])
    free = certificates[0]["free"]
    if any(set(item["pivots"]) != pivot_set for item in certificates[1:]):
        raise ValueError("pivot sets differ across source primes")
    if any(item["free"] != free for item in certificates[1:]):
        raise ValueError("free-coordinate lists differ across source primes")
    residue_vectors = [item["coordinate_residues"] for item in certificates]
    modulus = math.prod(primes)
    support = sorted(set().union(*(set(vector) for vector in residue_vectors)))
    coordinates = {}
    numerator_maximum = 0
    denominator_maximum = 0
    product_maximum = 0
    for prefix_index, coordinate in enumerate(support):
        residues = [vector.get(coordinate, 0) for vector in residue_vectors]
        combined = ZZ(crt(residues, primes))
        try:
            recovered = combined.rational_reconstruction(ZZ(modulus))
        except (ArithmeticError, ValueError) as error:
            raise ReconstructionInsufficient(
                {
                    "crt_modulus": str(modulus),
                    "crt_modulus_bit_length": int(modulus.bit_length()),
                    "equal_numerator_denominator_uniqueness_bound": str(
                        math.isqrt(modulus // 2)
                    ),
                    "failing_coordinate": int(coordinate),
                    "failing_coordinate_prefix_position": prefix_index,
                    "recovered_prefix_coordinate_count": prefix_index,
                    "recovered_prefix_nonzero_count": len(coordinates),
                    "recovered_prefix_maximum_absolute_numerator": str(
                        numerator_maximum
                    ),
                    "recovered_prefix_maximum_denominator": str(
                        denominator_maximum
                    ),
                    "recovered_prefix_maximum_twice_numerator_times_denominator": str(
                        product_maximum
                    ),
                    "union_support_count": len(support),
                    "characteristics": primes,
                    "failure_kind": "SOURCE_MODULUS_RATIONAL_RECONSTRUCTION_FAILED",
                    "reason": str(error),
                }
            ) from error
        value = sp.Rational(
            int(recovered.numerator()), int(recovered.denominator())
        )
        for prime, residue_value in zip(primes, residues, strict=True):
            if rational_residue(value, prime) != residue_value:
                raise AssertionError("CRT reconstruction failed source-prime replay")
        for heldout in heldout_certificates:
            heldout_prime = int(heldout["characteristic"])
            observed = heldout["coordinate_residues"].get(coordinate, 0)
            expected = rational_residue(value, heldout_prime)
            if expected != observed:
                raise ReconstructionInsufficient(
                    {
                        "crt_modulus": str(modulus),
                        "crt_modulus_bit_length": int(modulus.bit_length()),
                        "equal_numerator_denominator_uniqueness_bound": str(
                            math.isqrt(modulus // 2)
                        ),
                        "failing_coordinate": int(coordinate),
                        "failing_coordinate_prefix_position": prefix_index,
                        "recovered_prefix_coordinate_count": prefix_index,
                        "recovered_prefix_nonzero_count": len(coordinates),
                        "recovered_prefix_maximum_absolute_numerator": str(
                            numerator_maximum
                        ),
                        "recovered_prefix_maximum_denominator": str(
                            denominator_maximum
                        ),
                        "recovered_prefix_maximum_twice_numerator_times_denominator": str(
                            product_maximum
                        ),
                        "union_support_count": len(support),
                        "characteristics": primes,
                        "failure_kind": "HELDOUT_PREFIX_COEFFICIENT_MISMATCH",
                        "candidate_numerator": str(value.p),
                        "candidate_denominator": str(value.q),
                        "heldout_characteristic": heldout_prime,
                        "heldout_expected_residue_from_candidate": expected,
                        "heldout_observed_residue": observed,
                        "reason": (
                            "a source-modulus rational candidate failed immediate "
                            "held-out coefficient replay"
                        ),
                    }
                )
        if value:
            coordinates[coordinate] = value
        numerator_maximum = max(numerator_maximum, abs(int(value.p)))
        denominator_maximum = max(denominator_maximum, int(value.q))
        product_maximum = max(
            product_maximum, 2 * abs(int(value.p)) * int(value.q)
        )
    metadata = {
        "crt_modulus": modulus,
        "crt_modulus_bit_length": int(modulus.bit_length()),
        "equal_numerator_denominator_uniqueness_bound": math.isqrt(modulus // 2),
        "maximum_absolute_numerator": numerator_maximum,
        "maximum_denominator": denominator_maximum,
        "maximum_twice_numerator_times_denominator": product_maximum,
        "all_coefficients_inside_complete_enumeration_region": product_maximum < modulus,
        "standard_symmetric_reconstruction_is_unique": True,
        "union_support_count": len(support),
        "reconstructed_nonzero_count": len(coordinates),
    }
    multipliers = [{} for _ in range(generator_count)]
    for coordinate, coefficient in coordinates.items():
        generator_index, exponents = descriptors[int(coordinate)]
        multipliers[generator_index][exponents] = coefficient
    return multipliers, {
        **metadata,
        "characteristics": primes,
        "gauge": "one common pivot/free coordinate partition; all free coordinates zero",
        "pivot_count": len(pivot_set),
        "free_unknown_count": len(free),
        "pivot_unknown_set_sha256": canonical_hash(sorted(pivot_set)),
        "free_unknown_indices_sha256": canonical_hash(free),
        "multiplier_stream_sha256": sparse_stream_sha256(multipliers),
    }


def asymmetric_eea_candidates(residue_value: int, modulus: int):
    """Enumerate every primitive EEA candidate inside 2*|n|*d < modulus."""

    residue_value %= modulus
    if residue_value == 0:
        return [(0, 1)], 0
    old_remainder, remainder = modulus, residue_value
    old_denominator, denominator = 0, 1
    candidates = set()
    step_count = 0
    while remainder:
        step_count += 1
        numerator = remainder
        candidate_denominator = denominator
        if candidate_denominator < 0:
            numerator = -numerator
            candidate_denominator = -candidate_denominator
        common = math.gcd(abs(numerator), candidate_denominator)
        numerator //= common
        candidate_denominator //= common
        if (
            candidate_denominator > 0
            and math.gcd(candidate_denominator, modulus) == 1
            and 2 * abs(numerator) * candidate_denominator < modulus
            and (numerator - residue_value * candidate_denominator) % modulus == 0
        ):
            candidates.add((numerator, candidate_denominator))
        quotient = old_remainder // remainder
        old_remainder, remainder = (
            remainder,
            old_remainder - quotient * remainder,
        )
        old_denominator, denominator = (
            denominator,
            old_denominator - quotient * denominator,
        )
    return sorted(candidates), step_count


def reconstruct_multipliers_asymmetric(
    certificates,
    descriptors,
    generator_count,
    selection_heldouts,
):
    """Recover one strict-product EEA candidate per coordinate."""

    primes = [int(item["characteristic"]) for item in certificates]
    if len(set(primes)) != len(primes):
        raise ValueError("reconstruction primes are not distinct")
    pivot_set = set(certificates[0]["pivots"])
    free = certificates[0]["free"]
    if any(set(item["pivots"]) != pivot_set for item in certificates[1:]):
        raise ValueError("pivot sets differ across source primes")
    if any(item["free"] != free for item in certificates[1:]):
        raise ValueError("free-coordinate lists differ across source primes")
    if not selection_heldouts:
        raise ValueError("asymmetric reconstruction requires selection heldouts")

    residue_vectors = [item["coordinate_residues"] for item in certificates]
    modulus = math.prod(primes)
    support = sorted(set().union(*(set(vector) for vector in residue_vectors)))
    coordinates = {}
    numerator_maximum = 0
    denominator_maximum = 0
    product_maximum = 0
    maximum_eea_steps = 0
    before_histogram = {}
    after_histogram = {}
    for prefix_index, coordinate in enumerate(support):
        residues = [vector.get(coordinate, 0) for vector in residue_vectors]
        combined = int(crt(residues, primes))
        candidates, steps = asymmetric_eea_candidates(combined, modulus)
        maximum_eea_steps = max(maximum_eea_steps, steps)
        before_histogram[len(candidates)] = before_histogram.get(len(candidates), 0) + 1
        filtered = []
        for numerator, denominator in candidates:
            matches = True
            for heldout in selection_heldouts:
                prime = int(heldout["characteristic"])
                observed = heldout["coordinate_residues"].get(coordinate, 0)
                if denominator % prime == 0:
                    matches = False
                    break
                expected = numerator % prime * pow(denominator % prime, -1, prime) % prime
                if expected != observed:
                    matches = False
                    break
            if matches:
                filtered.append((numerator, denominator))
        after_histogram[len(filtered)] = after_histogram.get(len(filtered), 0) + 1
        if len(filtered) != 1:
            kind = (
                "ASYMMETRIC_EEA_NO_CANDIDATE"
                if not filtered
                else "ASYMMETRIC_EEA_AMBIGUOUS_CANDIDATES"
            )
            reason = (
                "no strict-product EEA candidate survived every selection holdout"
                if not filtered
                else "more than one strict-product EEA candidate survived every selection holdout"
            )
            raise ReconstructionInsufficient(
                {
                    "crt_modulus": str(modulus),
                    "crt_modulus_bit_length": int(modulus.bit_length()),
                    "failing_coordinate": int(coordinate),
                    "failing_coordinate_prefix_position": prefix_index,
                    "recovered_prefix_coordinate_count": prefix_index,
                    "recovered_prefix_nonzero_count": len(coordinates),
                    "recovered_prefix_maximum_absolute_numerator": str(numerator_maximum),
                    "recovered_prefix_maximum_denominator": str(denominator_maximum),
                    "recovered_prefix_maximum_twice_numerator_times_denominator": str(product_maximum),
                    "union_support_count": len(support),
                    "characteristics": primes,
                    "failure_kind": kind,
                    "candidate_count_before_selection_heldouts": len(candidates),
                    "candidate_count_after_selection_heldouts": len(filtered),
                    "selection_heldout_characteristics": [
                        int(item["characteristic"]) for item in selection_heldouts
                    ],
                    "candidate_height_profiles": [
                        {
                            "numerator_bit_length": abs(numerator).bit_length(),
                            "denominator_bit_length": denominator.bit_length(),
                            "twice_product_bit_length": (
                                2 * abs(numerator) * denominator
                            ).bit_length(),
                        }
                        for numerator, denominator in filtered[:8]
                    ],
                    "reason": reason,
                }
            )
        numerator, denominator = filtered[0]
        value = sp.Rational(numerator, denominator)
        for prime, source_residue in zip(primes, residues, strict=True):
            if rational_residue(value, prime) != source_residue:
                raise AssertionError("asymmetric candidate failed source replay")
        if value:
            coordinates[coordinate] = value
        numerator_maximum = max(numerator_maximum, abs(int(value.p)))
        denominator_maximum = max(denominator_maximum, int(value.q))
        product_maximum = max(
            product_maximum, 2 * abs(int(value.p)) * int(value.q)
        )

    multipliers = [{} for _ in range(generator_count)]
    for coordinate, coefficient in coordinates.items():
        generator_index, exponents = descriptors[int(coordinate)]
        multipliers[generator_index][exponents] = coefficient
    return multipliers, {
        "method": (
            "complete strict-product EEA candidate enumeration plus frozen-prime "
            "singleton selection; exact QQ convolution is the proof gate"
        ),
        "crt_modulus": modulus,
        "crt_modulus_bit_length": int(modulus.bit_length()),
        "maximum_absolute_numerator": numerator_maximum,
        "maximum_denominator": denominator_maximum,
        "maximum_twice_numerator_times_denominator": product_maximum,
        "all_coefficients_inside_complete_enumeration_region": product_maximum < modulus,
        "strict_product_region_is_not_a_uniqueness_claim": True,
        "all_coordinates_unique_after_selection_heldouts": True,
        "selection_heldout_characteristics": [
            int(item["characteristic"]) for item in selection_heldouts
        ],
        "candidate_count_before_selection_histogram": before_histogram,
        "candidate_count_after_selection_histogram": after_histogram,
        "maximum_eea_step_count": maximum_eea_steps,
        "union_support_count": len(support),
        "reconstructed_nonzero_count": len(coordinates),
        "characteristics": primes,
        "gauge": "one common pivot/free coordinate partition; all free coordinates zero",
        "pivot_count": len(pivot_set),
        "free_unknown_count": len(free),
        "pivot_unknown_set_sha256": canonical_hash(sorted(pivot_set)),
        "free_unknown_indices_sha256": canonical_hash(free),
        "multiplier_stream_sha256": sparse_stream_sha256(multipliers),
    }


def replay_rational(multipliers, generator_terms, target_terms):
    observed = {}
    for generator, multiplier in zip(generator_terms, multipliers, strict=True):
        multiply_add_rational(observed, generator, multiplier)
    remainder = subtract_sparse(target_terms, observed)
    nonzero = [item for item in multipliers if item]
    return {
        "identity_zero": not remainder,
        "remainder_term_count": len(remainder),
        "observed_term_count": len(observed),
        "target_term_count": len(target_terms),
        "multiplier_count": len(multipliers),
        "nonzero_multiplier_count": len(nonzero),
        "multiplier_support_count": sum(map(len, multipliers)),
        "maximum_multiplier_total_degree": max(
            (sum(exponents) for item in nonzero for exponents in item),
            default=None,
        ),
        "multiplier_stream_sha256": sparse_stream_sha256(multipliers),
    }


def heldout_replay(certificate, multipliers):
    prime = int(certificate["characteristic"])
    mismatches = 0
    union_count = 0
    for rational, observed in zip(multipliers, certificate["multipliers"], strict=True):
        support = set(rational) | set(observed)
        union_count += len(support)
        for exponents in support:
            expected = rational_residue(rational.get(exponents, 0), prime)
            if expected != observed.get(exponents, 0):
                mismatches += 1
    return {
        "path": str(certificate["path"]),
        "sha256": certificate["sha256"],
        "characteristic": prime,
        "coefficient_union_count": union_count,
        "coefficient_mismatch_count": mismatches,
        "passed": mismatches == 0,
    }


def serialize_multipliers(multipliers):
    return [
        {
            "generator_position": index,
            "term_count": len(multiplier),
            "terms": [
                {
                    "exponents": list(exponents),
                    "numerator": str(sp.Rational(coefficient).p),
                    "denominator": str(sp.Rational(coefficient).q),
                }
                for exponents, coefficient in sorted(multiplier.items())
            ],
        }
        for index, multiplier in enumerate(multipliers)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("certificates", type=Path, nargs="+")
    parser.add_argument(
        "--asymmetric-eea",
        action="store_true",
        help="enumerate all strict-product EEA candidates and filter with selection heldouts",
    )
    parser.add_argument(
        "--selection-heldout", type=Path, action="append", default=[]
    )
    parser.add_argument("--heldout", type=Path, action="append", default=[])
    parser.add_argument("--artifact-output", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if len(arguments.certificates) < 2:
        parser.error("at least two source certificates are required")
    if arguments.asymmetric_eea and (
        len(arguments.selection_heldout) < 2 or not arguments.heldout
    ):
        parser.error(
            "--asymmetric-eea requires at least two selection heldouts and one independent heldout"
        )

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    problem = canonical_problem(campaign)
    descriptors = problem["descriptors"]
    descriptor_hash = canonical_hash(descriptors)
    monomial_hash = canonical_hash(problem["monomials"])
    generator_hash = digest(tuple(problem["generators"]))
    target_hash = digest((problem["target"],))
    generator_terms = [
        polynomial_terms_qq(generator, problem["variables"])
        for generator in problem["generators"]
    ]
    target_terms = polynomial_terms_qq(problem["target"], problem["variables"])
    frozen_problem = {
        "variable_names": [str(variable) for variable in problem["variables"]],
        "generators": [serialize_sparse_polynomial(item) for item in generator_terms],
        "target_M_times_h3": serialize_sparse_polynomial(target_terms),
    }
    frozen_problem["sha256"] = canonical_digest(frozen_problem)

    paths = [path.resolve() for path in arguments.certificates]
    selection_paths = [path.resolve() for path in arguments.selection_heldout]
    heldout_paths = [path.resolve() for path in arguments.heldout]
    if (
        set(paths) & set(heldout_paths)
        or set(paths) & set(selection_paths)
        or set(selection_paths) & set(heldout_paths)
        or len(set(selection_paths)) != len(selection_paths)
    ):
        parser.error("source, selection-heldout, and independent-heldout sets must be disjoint")
    load_args = (
        problem, descriptor_hash, monomial_hash, generator_hash, target_hash
    )
    certificates = [load_certificate(path, *load_args) for path in paths]
    selection_heldout = [
        load_certificate(path, *load_args) for path in selection_paths
    ]
    heldout = [load_certificate(path, *load_args) for path in heldout_paths]
    modular_replays = [
        replay_modular(item, generator_terms, target_terms)
        for item in certificates + selection_heldout + heldout
    ]
    if not all(item["identity_zero"] for item in modular_replays):
        raise ValueError("an input certificate failed modular replay")

    try:
        if arguments.asymmetric_eea:
            multipliers, reconstruction = reconstruct_multipliers_asymmetric(
                certificates,
                descriptors,
                len(problem["generators"]),
                selection_heldout,
            )
        else:
            multipliers, reconstruction = reconstruct_multipliers(
                certificates,
                descriptors,
                len(problem["generators"]),
                heldout,
            )
    except ReconstructionInsufficient as error:
        output = arguments.output or Path(
            "receipts/hsop-j2-secant-r10-third-colon-identity-qq-reconstruction.json"
        )
        if not output.is_absolute():
            output = campaign / output
        failure_kind = error.diagnostic.get("failure_kind")
        diagnostic_status = {
            "HELDOUT_PREFIX_COEFFICIENT_MISMATCH": (
                "INCOMPLETE_RATIONAL_RECONSTRUCTION_HELDOUT_PREFIX_MISMATCH"
            ),
            "ASYMMETRIC_EEA_NO_CANDIDATE": (
                "INCOMPLETE_ASYMMETRIC_EEA_NO_CANDIDATE"
            ),
            "ASYMMETRIC_EEA_AMBIGUOUS_CANDIDATES": (
                "INCOMPLETE_ASYMMETRIC_EEA_AMBIGUOUS_CANDIDATES"
            ),
        }.get(
            failure_kind,
            "INCOMPLETE_RATIONAL_RECONSTRUCTION_MODULUS_INSUFFICIENT",
        )
        diagnostic_result = {
            "schema": "hc4.decimic-j2-secant-r10-third-colon-identity-qq-reconstruction-attempt.v1",
            "status": diagnostic_status,
            "assurance": "fail-closed CRT and held-out diagnostic only",
            "input_certificates": [
                {
                    "path": str(item["path"]),
                    "sha256": item["sha256"],
                    "characteristic": item["characteristic"],
                }
                for item in certificates
            ],
            "heldout_certificates": [
                {
                    "path": str(item["path"]),
                    "sha256": item["sha256"],
                    "characteristic": item["characteristic"],
                }
                for item in heldout
            ],
            "selection_heldout_certificates": [
                {
                    "path": str(item["path"]),
                    "sha256": item["sha256"],
                    "characteristic": item["characteristic"],
                }
                for item in selection_heldout
            ],
            "selection_holdout_role": (
                "Candidate selection and falsification only. These congruence "
                "checks do not prove a rational coefficient or polynomial "
                "identity; a PASS additionally requires exact QQ convolution."
            ),
            "independent_holdout_role": (
                "Out-of-selection modular validation only. This check is not a "
                "substitute for exact QQ convolution."
            ),
            "modular_replays": modular_replays,
            "reconstruction_diagnostic": error.diagnostic,
            "certificate": None,
            "artifact_emitted": False,
            "wall_seconds": time.perf_counter() - started,
            "source_sha256": {
                str(script_path.relative_to(campaign)): file_sha256(script_path)
            },
            "claim_boundary": (
                "This attempt makes no characteristic-zero membership decision. "
                "It records only that the displayed source set was insufficient: "
                "standard reconstruction failed, a source-only candidate failed "
                "immediate held-out replay, or strict-product EEA filtering was "
                "nonunique or empty. It is not evidence "
                "against the identity, a colon or saturation certificate, a secant "
                "closure, or HC4."
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(diagnostic_result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": diagnostic_result["status"],
            "output": str(output),
            "artifact_emitted": False,
            "reconstruction_diagnostic": error.diagnostic,
            "wall_seconds": diagnostic_result["wall_seconds"],
        }, indent=2, sort_keys=True))
        return 1
    exact_replay = replay_rational(multipliers, generator_terms, target_terms)
    heldout_replays = [heldout_replay(item, multipliers) for item in heldout]
    selection_heldout_replays = [
        heldout_replay(item, multipliers) for item in selection_heldout
    ]
    passed = (
        exact_replay["identity_zero"]
        and reconstruction["all_coefficients_inside_complete_enumeration_region"]
        and all(item["passed"] for item in selection_heldout_replays)
        and all(item["passed"] for item in heldout_replays)
    )

    artifact_path = arguments.artifact_output or Path(
        "artifacts/j2-secant-r10-third-colon-identity-qq.json"
    )
    if not artifact_path.is_absolute():
        artifact_path = campaign / artifact_path
    artifact_record = None
    if passed:
        artifact = {
            "schema": "hc4.decimic-j2-secant-r10-third-colon-identity-qq-certificate.v1",
            "status": "PASS_EXACT_QQ_THIRD_COLON_IDENTITY",
            "variable_names": frozen_problem["variable_names"],
            "generator_count": len(problem["generators"]),
            "normal_cubic_generator_count": len(problem["equations"]),
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "row_descriptor_sha256": descriptor_hash,
            "problem": frozen_problem,
            "reconstruction": reconstruction,
            "exact_rational_replay": exact_replay,
            "multipliers": serialize_multipliers(multipliers),
            "claim_boundary": (
                "This proves only M*h3 in (F_1,...,F_17,h,h2) over QQ. It does "
                "not determine a colon or saturated ideal, close the secant chart, "
                "or establish HC4."
            ),
        }
        artifact["certificate_sha256"] = canonical_digest(artifact)
        text = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(text, encoding="ascii")
        artifact_record = {
            "path": str(artifact_path),
            "sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
            "byte_count": len(text.encode("ascii")),
        }

    status = (
        "PASS_EXACT_QQ_THIRD_COLON_IDENTITY"
        if passed
        else "INCOMPLETE_QQ_THIRD_COLON_IDENTITY_RECONSTRUCTION"
    )
    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-identity-qq-reconstruction.v1",
        "status": status,
        "assurance": "exact characteristic-zero polynomial identity" if passed else "modular reconstruction attempt",
        "claim": "M*h3 lies in the ideal generated by the 17 cubics, h, and h2",
        "input_certificates": [
            {"path": str(item["path"]), "sha256": item["sha256"], "characteristic": item["characteristic"]}
            for item in certificates
        ],
            "heldout_certificates": [
            {"path": str(item["path"]), "sha256": item["sha256"], "characteristic": item["characteristic"]}
            for item in heldout
        ],
        "selection_heldout_certificates": [
            {"path": str(item["path"]), "sha256": item["sha256"], "characteristic": item["characteristic"]}
            for item in selection_heldout
        ],
        "selection_holdout_role": (
            "Candidate selection and falsification only. These congruence "
            "checks do not prove a rational coefficient or polynomial identity; "
            "a PASS additionally requires exact QQ convolution."
        ),
        "independent_holdout_role": (
            "Out-of-selection modular validation only. This check is not a "
            "substitute for exact QQ convolution."
        ),
        "hashes": {
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
        },
        "modular_replays": modular_replays,
        "reconstruction": reconstruction,
        "exact_rational_replay": exact_replay,
        "heldout_replays": heldout_replays,
        "selection_heldout_replays": selection_heldout_replays,
        "certificate": artifact_record,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {str(script_path.relative_to(campaign)): file_sha256(script_path)},
        "claim_boundary": (
            "A PASS proves only the displayed third colon identity over QQ; not a "
            "colon, saturation, secant closure, or HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/hsop-j2-secant-r10-third-colon-identity-qq-reconstruction.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": status,
        "output": str(output),
        "certificate": artifact_record,
        "crt_modulus": reconstruction["crt_modulus"],
        "reconstructed_nonzero_count": reconstruction["reconstructed_nonzero_count"],
        "exact_identity_zero": exact_replay["identity_zero"],
        "heldout_replays": heldout_replays,
        "wall_seconds": result["wall_seconds"],
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
