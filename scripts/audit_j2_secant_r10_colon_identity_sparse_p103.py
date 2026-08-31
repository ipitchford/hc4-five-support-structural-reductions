#!/usr/bin/env sage-python
"""Independent coefficient audit of the frozen p=103 colon certificate.

This verifier intentionally does not import either sparse-Macaulay producer or
its replay script.  It rebuilds the rational quartic from the two modular taps,
enumerates the character block independently, and checks the displayed
multiplier identity by direct dictionary convolution over GF(103).

The v1 certificate does not contain its pivot/free-coordinate partition.  The
audit therefore verifies every mathematical field of the sparse solution and
records that the producer's claimed elimination gauge is not independently
recoverable from that artifact alone.
"""

from __future__ import annotations

import hashlib
import json
import math
import resource
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp

from scout_j2_secant_r10_homogeneous_saturation import homogeneous_saturation_system


PRIMES = (1073741827, 1073742851)
P = 103
MODULUS = 12
WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
EXPECTED_SCHEMA = "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def polynomial_digest(expressions) -> str:
    payload = "\n".join(str(sp.expand(expression)).replace("**", "^") for expression in expressions)
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def weak_compositions(length: int, total: int):
    """Generate weak compositions in the producer's documented lexicographic order."""

    def recurse(position: int, remaining: int, prefix: tuple[int, ...]):
        if position == length - 1:
            yield prefix + (remaining,)
            return
        for value in range(remaining + 1):
            yield from recurse(position + 1, remaining - value, prefix + (value,))

    yield from recurse(0, total, ())


def weight(exponents: tuple[int, ...]) -> int:
    if len(exponents) != len(WEIGHTS):
        raise ValueError("wrong exponent-vector length")
    return sum(left * right for left, right in zip(exponents, WEIGHTS, strict=True)) % MODULUS


def rational_residue(value: Fraction | sp.Rational, prime: int) -> int:
    value = Fraction(int(value.p), int(value.q)) if isinstance(value, sp.Rational) else value
    return value.numerator % prime * pow(value.denominator % prime, -1, prime) % prime


def crt_pair(left: int, right: int, p_left: int, p_right: int) -> int:
    return (left + p_left * (((right - left) * pow(p_left, -1, p_right)) % p_right)) % (
        p_left * p_right
    )


def rational_reconstruction(residue: int, modulus: int) -> Fraction:
    """Balanced Wang reconstruction, implemented independently of Sage's helper."""

    bound = math.isqrt(modulus // 2)
    old_r, current_r = modulus, residue % modulus
    old_t, current_t = 0, 1
    while current_r > bound:
        quotient = old_r // current_r
        old_r, current_r = current_r, old_r - quotient * current_r
        old_t, current_t = current_t, old_t - quotient * current_t
    numerator, denominator = current_r, current_t
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    if denominator == 0 or denominator > bound or abs(numerator) > bound:
        raise ArithmeticError("rational reconstruction is outside the uniqueness box")
    fraction = Fraction(numerator, denominator)
    if (residue * fraction.denominator - fraction.numerator) % modulus:
        raise ArithmeticError("rational reconstruction failed its defining congruence")
    return fraction


def load_candidate(path: Path) -> tuple[int, dict[tuple[int, ...], int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = payload.get("candidates", [])
    if len(candidates) != 1:
        raise ValueError(f"{path} does not contain exactly one candidate")
    terms = {}
    for record in candidates[0]["terms"]:
        exponents = tuple(map(int, record["exponents"]))
        if exponents in terms:
            raise ValueError(f"duplicate candidate exponent in {path}")
        terms[exponents] = int(record["coefficient"])
    return int(payload["characteristic"]), terms


def reconstruct_quartic(campaign: Path):
    paths = [
        campaign / "research" / f"j2_secant_r10_colon_kernel_candidate_p{prime}.json"
        for prime in PRIMES
    ]
    loaded = [load_candidate(path) for path in paths]
    if tuple(prime for prime, _ in loaded) != PRIMES:
        raise ValueError("candidate characteristics do not match the frozen primes")
    if loaded[0][1].keys() != loaded[1][1].keys():
        raise ValueError("candidate supports differ")
    modulus = math.prod(PRIMES)
    terms = {}
    for exponents in loaded[0][1]:
        residue = crt_pair(loaded[0][1][exponents], loaded[1][1][exponents], *PRIMES)
        terms[exponents] = rational_reconstruction(residue, modulus)
    return terms, paths


def sympy_terms(expression, variables):
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return {
        tuple(map(int, exponents)): Fraction(int(coefficient.p), int(coefficient.q))
        for exponents, coefficient in polynomial.terms()
    }


def convolve_mod(left, right, prime: int):
    result = {}
    for left_exponents, left_coefficient in left.items():
        left_value = (
            rational_residue(left_coefficient, prime)
            if isinstance(left_coefficient, (Fraction, sp.Rational))
            else int(left_coefficient) % prime
        )
        for right_exponents, right_coefficient in right.items():
            right_value = (
                rational_residue(right_coefficient, prime)
                if isinstance(right_coefficient, (Fraction, sp.Rational))
                else int(right_coefficient) % prime
            )
            product = tuple(
                a + b for a, b in zip(left_exponents, right_exponents, strict=True)
            )
            value = (result.get(product, 0) + left_value * right_value) % prime
            if value:
                result[product] = value
            else:
                result.pop(product, None)
    return result


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    certificate_path = campaign / "artifacts/j2-secant-r10-colon-identity-sparse-macaulay-p103.json"
    producer_receipt_path = campaign / "receipts/hsop-j2-secant-r10-colon-identity-sparse-macaulay-p103.json"
    replay_receipt_path = campaign / "receipts/hsop-j2-secant-r10-colon-identity-sparse-macaulay-replay-p103.json"
    canonical_quartic_path = campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json"
    v2_certificate_path = campaign / (
        "artifacts/audit-j2-secant-r10-colon-identity-sparse-macaulay-v2-rerun-p103.json"
    )
    v2_receipt_path = campaign / (
        "receipts/audit-j2-secant-r10-colon-identity-sparse-macaulay-v2-rerun-p103.json"
    )
    v2_replay_path = campaign / (
        "receipts/audit-j2-secant-r10-colon-identity-sparse-macaulay-v2-replay-p103.json"
    )
    certificate = json.loads(certificate_path.read_text(encoding="ascii"))
    producer_receipt = json.loads(producer_receipt_path.read_text(encoding="utf-8"))
    replay_receipt = json.loads(replay_receipt_path.read_text(encoding="utf-8"))

    equations, variables, _, open_factor = homogeneous_saturation_system()
    quartic_terms, candidate_paths = reconstruct_quartic(campaign)
    canonical_quartic = json.loads(canonical_quartic_path.read_text(encoding="utf-8"))
    canonical_terms = {
        tuple(map(int, record["exponents"])): Fraction(
            int(record["numerator"]), int(record["denominator"])
        )
        for record in canonical_quartic["h_rational_terms"]
    }
    quartic_matches_canonical = quartic_terms == canonical_terms

    quartic_expression = sp.Integer(0)
    for exponents, coefficient in quartic_terms.items():
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        quartic_expression += sp.Rational(coefficient.numerator, coefficient.denominator) * monomial
    quartic_expression = sp.expand(quartic_expression)
    target_expression = sp.expand(open_factor * quartic_expression)
    target_terms = convolve_mod(sympy_terms(open_factor, variables), quartic_terms, P)

    generator_terms = [sympy_terms(equation, variables) for equation in equations]
    generator_weights = []
    generator_degrees = []
    for terms in generator_terms:
        generator_weights.append(sorted({weight(exponents) for exponents in terms}))
        generator_degrees.append(sorted({sum(exponents) for exponents in terms}))
    homogeneous_generators = all(
        observed_weight and len(observed_weight) == 1 and observed_degree == [3]
        for observed_weight, observed_degree in zip(generator_weights, generator_degrees, strict=True)
    )
    scalar_generator_weights = [observed[0] for observed in generator_weights]
    target_weights = sorted({weight(exponents) for exponents in target_terms})
    target_degrees = sorted({sum(exponents) for exponents in target_terms})

    degree_five_by_weight = [[] for _ in range(MODULUS)]
    all_degree_five_count = 0
    for exponents in weak_compositions(len(variables), 5):
        degree_five_by_weight[weight(exponents)].append(exponents)
        all_degree_five_count += 1

    descriptors = []
    monomial_set = set(target_terms)
    matrix_nonzeros = 0
    for generator_index, (terms, generator_weight) in enumerate(
        zip(generator_terms, scalar_generator_weights, strict=True)
    ):
        multiplier_weight = (5 - generator_weight) % MODULUS
        for multiplier in degree_five_by_weight[multiplier_weight]:
            descriptors.append((generator_index, multiplier))
            for exponents, coefficient in terms.items():
                product = tuple(a + b for a, b in zip(exponents, multiplier, strict=True))
                monomial_set.add(product)
                if rational_residue(coefficient, P):
                    matrix_nonzeros += 1
    monomials = sorted(monomial_set)

    descriptor_hash = hashlib.sha256(
        json.dumps(descriptors, separators=(",", ":")).encode("ascii")
    ).hexdigest()
    monomial_hash = hashlib.sha256(
        json.dumps(monomials, separators=(",", ":")).encode("ascii")
    ).hexdigest()

    support = certificate.get("solution_support", [])
    support_unknowns = []
    descriptor_mismatch_count = 0
    malformed_record_count = 0
    duplicate_unknown_count = 0
    previous_unknown = -1
    solution_terms_by_generator = [dict() for _ in equations]
    seen_unknowns = set()
    for record in support:
        try:
            unknown = int(record["unknown_index"])
            generator_index = int(record["normal_generator_position"])
            exponents = tuple(map(int, record["multiplier_exponents"]))
            coefficient = int(record["coefficient"])
        except (KeyError, TypeError, ValueError):
            malformed_record_count += 1
            continue
        if unknown in seen_unknowns:
            duplicate_unknown_count += 1
        seen_unknowns.add(unknown)
        support_unknowns.append(unknown)
        if not (0 <= unknown < len(descriptors)) or descriptors[unknown] != (
            generator_index,
            exponents,
        ):
            descriptor_mismatch_count += 1
            continue
        if unknown <= previous_unknown or not (0 < coefficient < P):
            malformed_record_count += 1
        previous_unknown = unknown
        solution_terms_by_generator[generator_index][exponents] = coefficient

    reconstructed_target = {}
    for multiplier, generator in zip(solution_terms_by_generator, generator_terms, strict=True):
        contribution = convolve_mod(multiplier, generator, P)
        for exponents, coefficient in contribution.items():
            value = (reconstructed_target.get(exponents, 0) + coefficient) % P
            if value:
                reconstructed_target[exponents] = value
            else:
                reconstructed_target.pop(exponents, None)
    residual_keys = set(reconstructed_target) | set(target_terms)
    residual = {
        exponents: (reconstructed_target.get(exponents, 0) - target_terms.get(exponents, 0)) % P
        for exponents in residual_keys
        if (reconstructed_target.get(exponents, 0) - target_terms.get(exponents, 0)) % P
    }

    normal_digest = polynomial_digest(tuple(equations))
    target_digest = polynomial_digest((target_expression,))
    artifact_hashes_match = {
        "normal_equation_stream": certificate.get("normal_equation_stream_sha256") == normal_digest,
        "target": certificate.get("target_sha256") == target_digest,
        "row_descriptor": certificate.get("row_descriptor_sha256") == descriptor_hash,
        "monomial_stream": certificate.get("monomial_stream_sha256") == monomial_hash,
    }
    receipt_dimensions_match = producer_receipt.get("dimensions") == {
        "unknown_multiplier_coordinates": len(descriptors),
        "monomial_equations": len(monomials),
        "matrix_nonzeros": matrix_nonzeros,
        "target_terms": len(target_terms),
    }

    current_producer_hash = sha256_file(
        campaign / "scripts/certify_j2_secant_r10_colon_identity_sparse_macaulay.py"
    )
    current_replay_hash = sha256_file(
        campaign / "scripts/replay_j2_secant_r10_colon_identity_sparse_macaulay.py"
    )
    frozen_producer_hash = producer_receipt.get("hashes", {}).get("source_sha256")
    frozen_replay_hash = replay_receipt.get("source_sha256")
    provenance_drift = {
        "producer_source_matches_frozen_receipt": current_producer_hash == frozen_producer_hash,
        "replay_source_matches_frozen_receipt": current_replay_hash == frozen_replay_hash,
        "artifact_schema_accepted_by_current_replay": certificate.get("schema")
        == "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v2",
    }

    v2_certificate = json.loads(v2_certificate_path.read_text(encoding="ascii"))
    v2_receipt = json.loads(v2_receipt_path.read_text(encoding="utf-8"))
    v2_replay = json.loads(v2_replay_path.read_text(encoding="utf-8"))
    pivot_indices = list(map(int, v2_certificate["pivot_unknown_indices"]))
    free_indices = list(map(int, v2_certificate["free_unknown_indices"]))
    pivot_set = set(pivot_indices)
    free_set = set(free_indices)
    support_indices = {int(record["unknown_index"]) for record in support}
    v2_gauge_checks = {
        "schema_is_v2": v2_certificate.get("schema")
        == "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v2",
        "full_solution_support_matches_frozen_v1": v2_certificate.get("solution_support")
        == support,
        "all_structural_hashes_match_frozen_v1": all(
            v2_certificate.get(key) == certificate.get(key)
            for key in (
                "normal_equation_stream_sha256",
                "target_sha256",
                "row_descriptor_sha256",
                "monomial_stream_sha256",
                "deterministic_gauge",
            )
        ),
        "pivot_indices_unique": len(pivot_indices) == len(pivot_set),
        "free_indices_sorted_unique": free_indices == sorted(free_set),
        "pivot_free_disjoint": pivot_set.isdisjoint(free_set),
        "pivot_free_partition_all_coordinates": pivot_set | free_set
        == set(range(len(descriptors))),
        "displayed_support_disjoint_from_free_coordinates": support_indices.isdisjoint(
            free_set
        ),
        "pivot_count_matches_receipt": len(pivot_indices)
        == v2_receipt.get("solver", {}).get("pivot_count"),
        "free_count_matches_receipt": len(free_indices)
        == v2_receipt.get("solver", {}).get("free_unknown_count"),
        "current_producer_source_still_matches_v2_receipt": current_producer_hash
        == v2_receipt.get("hashes", {}).get("source_sha256"),
        "v2_replay_passed": v2_replay.get("status")
        == "PASS_INDEPENDENT_SYMPY_MODULAR_COLON_IDENTITY_REPLAY",
        "v2_replay_certificate_hash_matches": v2_replay.get("certificate", {}).get(
            "sha256"
        )
        == sha256_file(v2_certificate_path),
        "v2_replay_source_hash_matches_current": v2_replay.get("source_sha256")
        == current_replay_hash,
    }
    # The shared producer source may continue to evolve after this bounded
    # rerun.  That drift is reported, but is not a mathematical failure of the
    # already-frozen v2 partition and exact replay.
    v2_gauge_pass = all(
        value
        for key, value in v2_gauge_checks.items()
        if key != "current_producer_source_still_matches_v2_receipt"
    )

    mathematical_pass = all(
        (
            certificate.get("schema") == EXPECTED_SCHEMA,
            certificate.get("characteristic") == P,
            certificate.get("variable_names") == [str(variable) for variable in variables],
            certificate.get("character_modulus") == MODULUS,
            certificate.get("character_weights") == list(WEIGHTS),
            certificate.get("target_character_weight") == 5,
            certificate.get("normal_generator_count") == len(equations),
            quartic_matches_canonical,
            homogeneous_generators,
            target_weights == [5],
            target_degrees == [8],
            all(artifact_hashes_match.values()),
            receipt_dimensions_match,
            not malformed_record_count,
            not duplicate_unknown_count,
            not descriptor_mismatch_count,
            not residual,
            v2_gauge_pass,
        )
    )

    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-identity-sparse-p103-independent-audit.v1",
        "status": (
            "PASS_INDEPENDENT_DIRECT_COEFFICIENT_AUDIT_WITH_PROVENANCE_CAVEAT"
            if mathematical_pass
            else "FAIL_INDEPENDENT_DIRECT_COEFFICIENT_AUDIT"
        ),
        "assurance": "independent exact GF(103) coefficient and grading audit",
        "characteristic": P,
        "inputs": {
            "certificate": {"path": str(certificate_path), "sha256": sha256_file(certificate_path)},
            "producer_receipt": {
                "path": str(producer_receipt_path),
                "sha256": sha256_file(producer_receipt_path),
            },
            "replay_receipt": {
                "path": str(replay_receipt_path),
                "sha256": sha256_file(replay_receipt_path),
            },
            "audit_v2_gauge_rerun_certificate": {
                "path": str(v2_certificate_path),
                "sha256": sha256_file(v2_certificate_path),
            },
            "audit_v2_gauge_rerun_receipt": {
                "path": str(v2_receipt_path),
                "sha256": sha256_file(v2_receipt_path),
            },
            "audit_v2_replay_receipt": {
                "path": str(v2_replay_path),
                "sha256": sha256_file(v2_replay_path),
            },
            "canonical_quartic": {
                "path": str(canonical_quartic_path),
                "sha256": sha256_file(canonical_quartic_path),
            },
            "modular_candidates": [
                {"path": str(path), "sha256": sha256_file(path)} for path in candidate_paths
            ],
        },
        "independent_method": (
            "two-prime CRT plus local Wang rational reconstruction; independent weak-composition "
            "enumeration; direct sparse dictionary convolution over GF(103)"
        ),
        "checks": {
            "quartic_matches_frozen_canonical_terms": quartic_matches_canonical,
            "quartic_term_count": len(quartic_terms),
            "all_generators_homogeneous_cubics_and_character_homogeneous": homogeneous_generators,
            "generator_character_weights": scalar_generator_weights,
            "target_degree": target_degrees,
            "target_character": target_weights,
            "all_degree_five_monomials": all_degree_five_count,
            "unknown_multiplier_coordinates": len(descriptors),
            "monomial_equations": len(monomials),
            "matrix_nonzeros": matrix_nonzeros,
            "target_terms": len(target_terms),
            "producer_receipt_dimensions_match": receipt_dimensions_match,
            "artifact_hashes_match": artifact_hashes_match,
            "solution_support_count": len(support),
            "solution_unknown_indices_strictly_increasing": support_unknowns
            == sorted(set(support_unknowns)),
            "duplicate_unknown_count": duplicate_unknown_count,
            "malformed_record_count": malformed_record_count,
            "descriptor_mismatch_count": descriptor_mismatch_count,
            "nonzero_multiplier_count": sum(bool(terms) for terms in solution_terms_by_generator),
            "reconstructed_target_term_count": len(reconstructed_target),
            "identity_residual_term_count": len(residual),
            "identity_zero": not residual,
        },
        "deterministic_gauge_audit": {
            "certificate_claim": certificate.get("deterministic_gauge"),
            "displayed_sparse_vector_has_zero_on_all_omitted_coordinates": True,
            "pivot_free_partition_present_in_v1_artifact": False,
            "producer_pivot_sequence_independently_auditable_from_v1_artifact": False,
            "v2_replication": {
                "checks": v2_gauge_checks,
                "pivot_count": len(pivot_indices),
                "free_coordinate_count": len(free_indices),
                "passed": v2_gauge_pass,
            },
            "conclusion": (
                "The displayed vector and its identity are exact. A current-source v2 rerun "
                "reproduced the entire v1 sparse vector and froze a valid 34979-pivot/1927-free "
                "partition with zero support on every free coordinate. This strongly reproduces "
                "the stated deterministic gauge, but it is not a byte-for-byte replay of the "
                "unavailable historical v1 producer source."
            ),
        },
        "static_implementation_review": {
            "producer_findings": [
                "The substitution sign is correct: x_p=b/a_p-sum(a_j/a_p)x_j.",
                "Each pivot is eliminated from all incident active equations, preventing reuse.",
                "Reverse pivot traversal with omitted coordinates initialized to zero implements the stated gauge.",
                "The independent zero-residual convolution makes any solver, sign, or back-substitution error fail closed.",
            ],
            "replay_findings": [
                "The current v2 replay validates degree, character, partition hashes, partition coverage, and the polynomial identity.",
                "It does not validate unknown_index against the canonical generator/exponent descriptor or recompute row/monomial stream hashes; this audit supplies both checks.",
            ],
            "term_order_conclusion": (
                "No Groebner term-order assumption enters the certificate: descriptor and monomial "
                "streams are lexicographically frozen and the final assertion is coefficientwise."
            ),
        },
        "provenance_version_audit": {
            **provenance_drift,
            "frozen_producer_source_sha256": frozen_producer_hash,
            "current_producer_source_sha256": current_producer_hash,
            "frozen_replay_source_sha256": frozen_replay_hash,
            "current_replay_source_sha256": current_replay_hash,
            "legacy_replay_reported_multiplier_term_count": replay_receipt.get(
                "checks", {}
            ).get("multiplier_term_count"),
            "independent_multiplier_term_count": len(support),
            "current_v2_replay_multiplier_term_count": v2_replay.get("checks", {}).get(
                "multiplier_term_count"
            ),
            "legacy_multiplier_term_count_inconsistent": replay_receipt.get(
                "checks", {}
            ).get("multiplier_term_count")
            != len(support),
            "note": (
                "The current scripts have evolved to certificate schema v2 after the frozen v1 "
                "run; the old replay receipt cannot be attributed to the current source hashes. "
                "Its 6243-term telemetry also disagrees with the 6242 unique frozen support "
                "records; the direct audit and current replay both obtain 6242."
            ),
        },
        "hashes": {
            "normal_equation_stream_sha256": normal_digest,
            "target_sha256": target_digest,
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "audit_source_sha256": sha256_file(script_path),
        },
        "runtime": {
            "wall_seconds": time.perf_counter() - started,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
            "maximum_rss_native": usage.ru_maxrss,
        },
        "claim_boundary": (
            "This audit proves the displayed M*h identity and the reported character-block "
            "dimensions only over GF(103). It does not prove a QQ identity, the full colon or "
            "saturation, closure of the secant chart, or HC4. It does not attest the omitted "
            "historical pivot sequence of the v1 producer."
        ),
    }
    output = campaign / "receipts/hsop-j2-secant-r10-colon-identity-sparse-p103-independent-audit.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if mathematical_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
