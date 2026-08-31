#!/usr/bin/env sage-python
"""CRT-reconstruct and exactly replay the second colon identity over QQ.

Inputs must be aligned fixed-free sparse Macaulay certificates proving

    M*h2 = sum_{i=1}^{17} q_i*F_i + q_18*h

over distinct prime fields.  This script validates every modular certificate,
requires one common pivot/free coordinate decomposition, reconstructs the full
multiplier vector by CRT and rational reconstruction, and finally checks the
identity coefficientwise over QQ.  The rational replay—not the modular sample
or reconstruction heuristic—is the decisive acceptance gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

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
from replay_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    canonical_hash,
    canonical_problem,
)


CERTIFICATE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-second-colon-identity-"
    "sparse-macaulay-certificate.v1"
)


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
    variables = problem["variables"]
    descriptors = problem["descriptors"]
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError(f"{path}: variable stream changed")
    if payload.get("row_descriptor_sha256") != descriptor_hash:
        raise ValueError(f"{path}: multiplier-coordinate stream changed")
    if payload.get("monomial_stream_sha256") != monomial_hash:
        raise ValueError(f"{path}: monomial-equation stream changed")
    if payload.get("generator_stream_sha256") != generator_hash:
        raise ValueError(f"{path}: generator stream changed")
    if payload.get("target_sha256") != target_hash:
        raise ValueError(f"{path}: target changed")
    if payload.get("target_character_weight") != 4:
        raise ValueError(f"{path}: target character changed")
    if payload.get("generator_degrees") != problem["generator_degrees"]:
        raise ValueError(f"{path}: generator degrees changed")
    if payload.get("multiplier_degrees") != problem["multiplier_degrees"]:
        raise ValueError(f"{path}: multiplier degrees changed")

    pivots = list(map(int, payload.get("pivot_unknown_indices", [])))
    free = list(map(int, payload.get("free_unknown_indices", [])))
    unknowns = set(range(len(descriptors)))
    if (
        len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != unknowns
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
        raise ValueError(f"{path}: invalid complete coordinate vector")
    coordinate_residues = {
        index: value % characteristic
        for index, value in enumerate(vector)
        if value % characteristic
    }
    support = payload.get("solution_support", [])
    observed_support = {}
    for record in support:
        index = int(record["unknown_index"])
        if index in observed_support or not 0 <= index < len(descriptors):
            raise ValueError(f"{path}: malformed support coordinate")
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
    if observed_support != coordinate_residues:
        raise ValueError(f"{path}: sparse support does not match complete vector")

    multipliers = [{} for _ in problem["generators"]]
    for index, coefficient in coordinate_residues.items():
        generator_index, exponents = descriptors[index]
        multipliers[generator_index][exponents] = coefficient
    source = payload.get("gauge_source")
    source_valid = True
    if source is not None:
        source_path = Path(source["path"])
        source_valid = source_path.is_file() and file_sha256(source_path) == source["sha256"]
    if not source_valid:
        raise ValueError(f"{path}: gauge-source file/hash mismatch")
    return {
        "path": path,
        "sha256": file_sha256(path),
        "characteristic": characteristic,
        "pivots": pivots,
        "free": free,
        "coordinate_residues": coordinate_residues,
        "multipliers": multipliers,
        "monomial_stream_sha256": payload["monomial_stream_sha256"],
    }


def replay_modular(
    certificate: dict[str, object],
    generator_terms: list[dict],
    target_terms: dict,
) -> dict[str, object]:
    characteristic = int(certificate["characteristic"])
    generators_mod = [
        reduce_qq_terms(generator, characteristic) for generator in generator_terms
    ]
    target_mod = reduce_qq_terms(target_terms, characteristic)
    observed = {}
    for generator, multiplier in zip(
        generators_mod, certificate["multipliers"], strict=True
    ):
        multiply_add_modular(observed, generator, multiplier, characteristic)
    remainder = subtract_sparse(target_mod, observed)
    return {
        "characteristic": characteristic,
        "identity_zero": not remainder,
        "remainder_term_count": len(remainder),
        "multiplier_support_count": sum(
            len(multiplier) for multiplier in certificate["multipliers"]
        ),
        "multiplier_stream_sha256": sparse_stream_sha256(certificate["multipliers"]),
    }


def reconstruct_multipliers(
    certificates: list[dict[str, object]], descriptors: list[tuple], generator_count: int
) -> tuple[list[dict], dict[str, object]]:
    characteristics = [int(item["characteristic"]) for item in certificates]
    if len(set(characteristics)) != len(characteristics):
        raise ValueError("reconstruction characteristics are not distinct")
    reference_pivots = set(certificates[0]["pivots"])
    reference_free = certificates[0]["free"]
    if any(set(item["pivots"]) != reference_pivots for item in certificates[1:]):
        raise ValueError("pivot-coordinate sets differ across primes")
    if any(item["free"] != reference_free for item in certificates[1:]):
        raise ValueError("free-coordinate lists differ across primes")
    if len({item["monomial_stream_sha256"] for item in certificates}) != 1:
        raise ValueError("monomial streams differ across primes")

    coordinates, metadata = reconstruct_residue_vector(
        [item["coordinate_residues"] for item in certificates], characteristics
    )
    multipliers = [{} for _ in range(generator_count)]
    for coordinate, coefficient in coordinates.items():
        generator_index, exponents = descriptors[int(coordinate)]
        multipliers[generator_index][exponents] = coefficient
    return multipliers, {
        **metadata,
        "characteristics": characteristics,
        "gauge": (
            "identical pivot/free coordinate sets; every common free coordinate "
            "is zero; adaptive pivot order may differ"
        ),
        "pivot_count": len(reference_pivots),
        "free_unknown_count": len(reference_free),
        "pivot_unknown_set_sha256": canonical_hash(sorted(reference_pivots)),
        "free_unknown_indices_sha256": canonical_hash(reference_free),
        "multiplier_stream_sha256": sparse_stream_sha256(multipliers),
    }


def replay_rational(
    multipliers: list[dict], generator_terms: list[dict], target_terms: dict
) -> dict[str, object]:
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


def heldout_replay(certificate: dict, multipliers: list[dict]) -> dict[str, object]:
    characteristic = int(certificate["characteristic"])
    mismatch_count = 0
    union_count = 0
    for rational, observed in zip(multipliers, certificate["multipliers"], strict=True):
        support = set(rational) | set(observed)
        union_count += len(support)
        for exponents in support:
            expected = rational_residue(rational.get(exponents, 0), characteristic)
            if expected != observed.get(exponents, 0):
                mismatch_count += 1
    return {
        "path": str(certificate["path"]),
        "sha256": certificate["sha256"],
        "characteristic": characteristic,
        "coefficient_union_count": union_count,
        "coefficient_mismatch_count": mismatch_count,
        "passed": mismatch_count == 0,
    }


def serialize_multipliers(multipliers: list[dict]) -> list[dict[str, object]]:
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
    parser.add_argument("--heldout", type=Path, action="append", default=[])
    parser.add_argument("--artifact-output", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if len(arguments.certificates) < 2:
        parser.error("at least two reconstruction certificates are required")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    problem = canonical_problem(campaign)
    descriptors = problem["descriptors"]
    descriptor_hash = canonical_hash(descriptors)
    monomial_hash = canonical_hash(problem["monomials"])
    from scout_decimic_nullcone_hsop import digest

    generator_hash = digest(tuple(problem["generators"]))
    target_hash = digest((problem["target"],))
    generator_terms = [
        polynomial_terms_qq(generator, problem["variables"])
        for generator in problem["generators"]
    ]
    target_terms = polynomial_terms_qq(problem["target"], problem["variables"])
    frozen_problem = {
        "variable_names": [str(variable) for variable in problem["variables"]],
        "generators": [
            serialize_sparse_polynomial(generator) for generator in generator_terms
        ],
        "target_M_times_h2": serialize_sparse_polynomial(target_terms),
    }
    frozen_problem["sha256"] = canonical_digest(frozen_problem)

    paths = [path.resolve() for path in arguments.certificates]
    heldout_paths = [path.resolve() for path in arguments.heldout]
    if set(paths) & set(heldout_paths):
        parser.error("a reconstruction certificate cannot also be held out")
    load_arguments = (
        problem,
        descriptor_hash,
        monomial_hash,
        generator_hash,
        target_hash,
    )
    certificates = [load_certificate(path, *load_arguments) for path in paths]
    heldout = [load_certificate(path, *load_arguments) for path in heldout_paths]
    modular_replays = [
        replay_modular(item, generator_terms, target_terms)
        for item in certificates + heldout
    ]
    if not all(item["identity_zero"] for item in modular_replays):
        raise ValueError("an input certificate failed independent modular replay")

    multipliers, reconstruction = reconstruct_multipliers(
        certificates, descriptors, len(problem["generators"])
    )
    rational_replay = replay_rational(multipliers, generator_terms, target_terms)
    heldout_replays = [heldout_replay(item, multipliers) for item in heldout]
    passed = (
        rational_replay["identity_zero"]
        and reconstruction["all_coefficients_inside_product_uniqueness_budget"]
        and all(item["passed"] for item in heldout_replays)
    )

    artifact_output = arguments.artifact_output or Path(
        "artifacts/j2-secant-r10-second-colon-identity-qq.json"
    )
    if not artifact_output.is_absolute():
        artifact_output = campaign / artifact_output
    artifact_record = None
    if passed:
        artifact = {
            "schema": "hc4.decimic-j2-secant-r10-second-colon-identity-qq-certificate.v1",
            "status": "PASS_EXACT_QQ_SECOND_COLON_IDENTITY",
            "variable_names": frozen_problem["variable_names"],
            "generator_count": len(problem["generators"]),
            "normal_cubic_generator_count": len(problem["equations"]),
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "row_descriptor_sha256": descriptor_hash,
            "problem": frozen_problem,
            "reconstruction": reconstruction,
            "exact_rational_replay": rational_replay,
            "multipliers": serialize_multipliers(multipliers),
            "claim_boundary": (
                "This artifact proves only M*h2 in (F_1,...,F_17,h) over QQ. "
                "It does not determine a colon or saturated ideal, close the "
                "secant chart, or establish HC4."
            ),
        }
        artifact["certificate_sha256"] = canonical_digest(artifact)
        text = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
        artifact_output.parent.mkdir(parents=True, exist_ok=True)
        artifact_output.write_text(text, encoding="ascii")
        artifact_record = {
            "path": str(artifact_output),
            "sha256": hashlib.sha256(text.encode("ascii")).hexdigest(),
            "byte_count": len(text.encode("ascii")),
        }

    status = (
        "PASS_EXACT_QQ_SECOND_COLON_IDENTITY"
        if passed
        else "INCOMPLETE_QQ_SECOND_COLON_IDENTITY_RECONSTRUCTION"
    )
    dependency_paths = [
        campaign / "scripts/reconstruct_j2_secant_r10_colon_identity.py",
        campaign
        / "scripts/replay_j2_secant_r10_second_colon_identity_sparse_macaulay.py",
    ]
    result = {
        "schema": "hc4.decimic-j2-secant-r10-second-colon-identity-qq-reconstruction.v1",
        "status": status,
        "assurance": "exact characteristic-zero polynomial identity" if passed else "modular reconstruction attempt only",
        "claim": "M*h2 lies in the ideal generated by the 17 cubics and h",
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
        "hashes": {
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
            "row_descriptor_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
        },
        "modular_replays": modular_replays,
        "reconstruction": reconstruction,
        "exact_rational_replay": rational_replay,
        "heldout_replays": heldout_replays,
        "certificate": artifact_record,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            str(script_path.relative_to(campaign)): file_sha256(script_path),
            **{
                str(path.relative_to(campaign)): file_sha256(path)
                for path in dependency_paths
            },
        },
        "claim_boundary": (
            "A PASS proves only the displayed second colon identity over QQ. It "
            "does not determine a colon or saturated ideal, close the secant "
            "chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/hsop-j2-secant-r10-second-colon-identity-qq-reconstruction.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "output": str(output),
                "certificate": artifact_record,
                "crt_modulus": reconstruction["crt_modulus"],
                "reconstructed_nonzero_count": reconstruction["reconstructed_nonzero_count"],
                "exact_identity_zero": rational_replay["identity_zero"],
                "heldout_replays": heldout_replays,
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
