#!/usr/bin/env sage-python
"""Reconstruct and exactly replay a rational ``M*h in I`` certificate.

The inputs are proof-producing finite-field certificates emitted by
``certify_j2_secant_r10_colon_identity_direct_lift.py``.  Multiplier
representatives need not be unique: syzygies among the original cubics give a
genuine gauge freedom.  For sparse-Macaulay inputs this script therefore
requires the full ordered pivot/free profile to match; for legacy direct-lift
inputs it conservatively requires identical sparse supports.  It reconstructs
every coordinate by CRT and accepts the result only if the reconstructed
multipliers replay the target identity exactly over ``QQ``.

The gauge checks are not used as mathematical evidence for the identity: the
decisive check is the final coefficient-by-coefficient rational replay.
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

from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
    exact_exponent_tuples,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


DIRECT_CERTIFICATE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-colon-identity-direct-lift-certificate.v1"
)
SPARSE_CERTIFICATE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-colon-identity-sparse-macaulay-certificate.v2"
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rational_residue(coefficient: sp.Rational, characteristic: int) -> int:
    numerator = int(coefficient.p) % characteristic
    denominator = int(coefficient.q) % characteristic
    if denominator == 0:
        raise ValueError(
            f"coefficient denominator is zero modulo {characteristic}"
        )
    return numerator * pow(denominator, -1, characteristic) % characteristic


def polynomial_terms_qq(expression: sp.Expr, variables) -> dict[tuple[int, ...], sp.Rational]:
    polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    return {
        tuple(map(int, exponents)): sp.Rational(coefficient)
        for exponents, coefficient in polynomial.terms()
        if coefficient
    }


def parse_modular_polynomial(
    source: str, variables, characteristic: int
) -> dict[tuple[int, ...], int]:
    symbols = {str(variable): variable for variable in variables}
    expression = sp.sympify(source.replace("^", "**"), locals=symbols)
    polynomial = sp.Poly(expression, *variables, modulus=characteristic)
    return {
        tuple(map(int, exponents)): int(coefficient) % characteristic
        for exponents, coefficient in polynomial.terms()
        if int(coefficient) % characteristic
    }


def reduce_qq_terms(
    terms: dict[tuple[int, ...], sp.Rational], characteristic: int
) -> dict[tuple[int, ...], int]:
    return {
        exponents: residue
        for exponents, coefficient in terms.items()
        if (residue := rational_residue(coefficient, characteristic))
    }


def multiply_add_modular(
    accumulator: dict[tuple[int, ...], int],
    left: dict[tuple[int, ...], int],
    right: dict[tuple[int, ...], int],
    characteristic: int,
) -> None:
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = tuple(
                a + b for a, b in zip(left_exponents, right_exponents, strict=True)
            )
            coefficient = (
                accumulator.get(exponents, 0)
                + left_coefficient * right_coefficient
            ) % characteristic
            if coefficient:
                accumulator[exponents] = coefficient
            else:
                accumulator.pop(exponents, None)


def multiply_add_rational(
    accumulator: dict[tuple[int, ...], sp.Rational],
    left: dict[tuple[int, ...], sp.Rational],
    right: dict[tuple[int, ...], sp.Rational],
) -> None:
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = tuple(
                a + b for a, b in zip(left_exponents, right_exponents, strict=True)
            )
            coefficient = (
                accumulator.get(exponents, sp.Rational(0))
                + left_coefficient * right_coefficient
            )
            if coefficient:
                accumulator[exponents] = coefficient
            else:
                accumulator.pop(exponents, None)


def subtract_sparse(left: dict, right: dict) -> dict:
    remainder = dict(left)
    for exponents, coefficient in right.items():
        updated = remainder.get(exponents, 0) - coefficient
        if updated:
            remainder[exponents] = updated
        else:
            remainder.pop(exponents, None)
    return remainder


def sparse_stream_sha256(polynomials: list[dict]) -> str:
    stream = [
        [
            [list(exponents), str(coefficient)]
            for exponents, coefficient in sorted(polynomial.items())
        ]
        for polynomial in polynomials
    ]
    return hashlib.sha256(
        json.dumps(stream, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def encoded_coefficient(coefficient: sp.Rational) -> int | list[int]:
    coefficient = sp.Rational(coefficient)
    if coefficient.q == 1:
        return int(coefficient.p)
    return [int(coefficient.p), int(coefficient.q)]


def serialize_sparse_polynomial(polynomial: dict) -> list[list[object]]:
    return [
        [list(exponents), encoded_coefficient(coefficient)]
        for exponents, coefficient in sorted(polynomial.items())
    ]


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def canonical_descriptors(equations, variables) -> tuple[list[tuple], str]:
    """Rebuild the exact character-five multiplier-coordinate stream."""

    generator_weights = []
    for equation in equations:
        weights = {
            character_weight(tuple(map(int, exponents)))
            for exponents, _coefficient in sp.Poly(
                equation, *variables, domain=sp.QQ
            ).terms()
        }
        if len(weights) != 1:
            raise AssertionError("a canonical generator is not character homogeneous")
        generator_weights.append(next(iter(weights)))
    degree_five_by_weight: list[list[tuple[int, ...]]] = [
        [] for _index in range(CHARACTER_MODULUS)
    ]
    for monomial in exact_exponent_tuples(len(variables), 5):
        degree_five_by_weight[character_weight(monomial)].append(monomial)
    descriptors = []
    for generator_index, generator_weight in enumerate(generator_weights):
        multiplier_weight = (5 - generator_weight) % CHARACTER_MODULUS
        descriptors.extend(
            (generator_index, monomial)
            for monomial in degree_five_by_weight[multiplier_weight]
        )
    encoded = json.dumps(descriptors, separators=(",", ":")).encode("ascii")
    return descriptors, hashlib.sha256(encoded).hexdigest()


def load_certificate(
    path: Path,
    variables,
    generator_count: int,
    equation_stream_sha256: str,
    direct_target_sha256: str,
    sparse_target_sha256: str,
    descriptors: list[tuple],
    descriptor_sha256: str,
) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = payload.get("schema")
    if schema not in {DIRECT_CERTIFICATE_SCHEMA, SPARSE_CERTIFICATE_SCHEMA}:
        raise ValueError(f"{path}: unsupported certificate schema")
    characteristic = int(payload["characteristic"])
    if characteristic <= 5 or not sp.isprime(characteristic):
        raise ValueError(f"{path}: characteristic is not a prime greater than five")
    if payload.get("variable_names") != [str(variable) for variable in variables]:
        raise ValueError(f"{path}: variable stream changed")
    recorded_generator_count = payload.get(
        "generator_count",
        payload.get("normal_generator_count", -1),
    )
    if int(recorded_generator_count) != generator_count:
        raise ValueError(f"{path}: generator count changed")
    if payload.get("normal_equation_stream_sha256") != equation_stream_sha256:
        raise ValueError(f"{path}: generator stream hash changed")
    if schema == DIRECT_CERTIFICATE_SCHEMA:
        if payload.get("target_sha256") != direct_target_sha256:
            raise ValueError(f"{path}: target hash changed")
        if payload.get("unit_matrix") != [[1]]:
            raise ValueError(f"{path}: target scaling was not normalized to one")
        if not payload.get("singular_identity_verified"):
            raise ValueError(f"{path}: missing Singular identity check")
        if not payload.get("sympy_identity_verified"):
            raise ValueError(f"{path}: missing independent modular identity check")
        multiplier_sources = payload.get("multipliers")
        if not isinstance(multiplier_sources, list) or len(multiplier_sources) != generator_count:
            raise ValueError(f"{path}: malformed multiplier list")
        multipliers = [
            parse_modular_polynomial(source, variables, characteristic)
            for source in multiplier_sources
        ]
        certificate_format = "singular-direct-lift"
        coordinate_residues = None
        pivot_unknown_indices = None
        free_unknown_indices = None
    else:
        if payload.get("target_sha256") != sparse_target_sha256:
            raise ValueError(f"{path}: target hash changed")
        if payload.get("row_descriptor_sha256") != descriptor_sha256:
            raise ValueError(f"{path}: multiplier-coordinate stream changed")
        if payload.get("character_modulus") != CHARACTER_MODULUS:
            raise ValueError(f"{path}: character modulus changed")
        if payload.get("character_weights") != list(CHARACTER_WEIGHTS):
            raise ValueError(f"{path}: character weights changed")
        if payload.get("target_character_weight") != 5:
            raise ValueError(f"{path}: target character changed")
        if payload.get("deterministic_gauge") != (
            "all unpivoted multiplier coordinates set to zero"
        ):
            raise ValueError(f"{path}: sparse elimination gauge changed")
        pivot_unknown_indices = [int(value) for value in payload["pivot_unknown_indices"]]
        free_unknown_indices = [int(value) for value in payload["free_unknown_indices"]]
        unknown_count = len(descriptors)
        if len(set(pivot_unknown_indices)) != len(pivot_unknown_indices):
            raise ValueError(f"{path}: duplicate pivot coordinate")
        if len(set(free_unknown_indices)) != len(free_unknown_indices):
            raise ValueError(f"{path}: duplicate free coordinate")
        if set(pivot_unknown_indices) | set(free_unknown_indices) != set(range(unknown_count)):
            raise ValueError(f"{path}: pivot/free coordinates do not partition the block")
        if set(pivot_unknown_indices) & set(free_unknown_indices):
            raise ValueError(f"{path}: a coordinate is both pivot and free")
        pivot_hash = hashlib.sha256(
            json.dumps(pivot_unknown_indices, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        free_hash = hashlib.sha256(
            json.dumps(free_unknown_indices, separators=(",", ":")).encode("ascii")
        ).hexdigest()
        if pivot_hash != payload.get("pivot_unknown_indices_sha256"):
            raise ValueError(f"{path}: pivot-profile hash mismatch")
        if free_hash != payload.get("free_unknown_indices_sha256"):
            raise ValueError(f"{path}: free-profile hash mismatch")
        coordinate_residues: dict[int, int] = {}
        multipliers = [{} for _index in range(generator_count)]
        for record in payload.get("solution_support", []):
            unknown_index = int(record["unknown_index"])
            if unknown_index in coordinate_residues:
                raise ValueError(f"{path}: duplicate solution coordinate")
            if not (0 <= unknown_index < unknown_count):
                raise ValueError(f"{path}: solution coordinate outside the block")
            generator_index = int(record["normal_generator_position"])
            exponents = tuple(map(int, record["multiplier_exponents"]))
            if (generator_index, exponents) != descriptors[unknown_index]:
                raise ValueError(f"{path}: solution descriptor mismatch")
            coefficient = int(record["coefficient"]) % characteristic
            if not coefficient:
                raise ValueError(f"{path}: zero coefficient serialized in sparse support")
            coordinate_residues[unknown_index] = coefficient
            multipliers[generator_index][exponents] = coefficient
        if any(coordinate_residues.get(index, 0) for index in free_unknown_indices):
            raise ValueError(f"{path}: a free coordinate is nonzero")
        certificate_format = "deterministic-sparse-macaulay"
    return {
        "path": path,
        "sha256": file_sha256(path),
        "characteristic": characteristic,
        "multipliers": multipliers,
        "format": certificate_format,
        "coordinate_residues": coordinate_residues,
        "pivot_unknown_indices": pivot_unknown_indices,
        "free_unknown_indices": free_unknown_indices,
        "monomial_stream_sha256": payload.get("monomial_stream_sha256"),
    }


def replay_modular(
    certificate: dict[str, object],
    equation_terms: list[dict[tuple[int, ...], sp.Rational]],
    target_terms: dict[tuple[int, ...], sp.Rational],
) -> dict[str, object]:
    characteristic = int(certificate["characteristic"])
    equations_modular = [
        reduce_qq_terms(equation, characteristic) for equation in equation_terms
    ]
    target_modular = reduce_qq_terms(target_terms, characteristic)
    observed: dict[tuple[int, ...], int] = {}
    for equation, multiplier in zip(
        equations_modular, certificate["multipliers"], strict=True
    ):
        multiply_add_modular(observed, equation, multiplier, characteristic)
    remainder = subtract_sparse(target_modular, observed)
    return {
        "characteristic": characteristic,
        "identity_zero": not remainder,
        "remainder_term_count": len(remainder),
        "multiplier_support_count": sum(
            len(multiplier) for multiplier in certificate["multipliers"]
        ),
        "multiplier_stream_sha256": sparse_stream_sha256(certificate["multipliers"]),
    }


def reconstruct_residue_vector(
    residue_vectors: list[dict[object, int]],
    characteristics: list[int],
) -> tuple[dict[object, sp.Rational], dict[str, object]]:
    """CRT/reconstruct the union support of sparse modular vectors."""

    modulus = math.prod(characteristics)
    support = set().union(*(set(vector) for vector in residue_vectors))
    rational = {}
    numerator_maximum = 0
    denominator_maximum = 0
    uniqueness_budget_maximum = 0
    for coordinate in sorted(support):
        residues = [vector.get(coordinate, 0) for vector in residue_vectors]
        combined = ZZ(crt(residues, characteristics))
        try:
            coefficient = combined.rational_reconstruction(ZZ(modulus))
        except (ArithmeticError, ValueError) as error:
            raise ValueError(
                f"rational reconstruction failed at coordinate {coordinate}"
            ) from error
        value = sp.Rational(
            int(coefficient.numerator()), int(coefficient.denominator())
        )
        for characteristic, residue in zip(characteristics, residues, strict=True):
            if rational_residue(value, characteristic) != residue:
                raise AssertionError("CRT reconstruction did not replay an input residue")
        if value:
            rational[coordinate] = value
        numerator_maximum = max(numerator_maximum, abs(int(value.p)))
        denominator_maximum = max(denominator_maximum, int(value.q))
        uniqueness_budget_maximum = max(
            uniqueness_budget_maximum, 2 * abs(int(value.p)) * int(value.q)
        )
    return rational, {
        "crt_modulus": modulus,
        "equal_numerator_denominator_uniqueness_bound": math.isqrt(modulus // 2),
        "maximum_absolute_numerator": numerator_maximum,
        "maximum_denominator": denominator_maximum,
        "maximum_twice_numerator_times_denominator": uniqueness_budget_maximum,
        "all_coefficients_inside_product_uniqueness_budget": (
            uniqueness_budget_maximum < modulus
        ),
        "union_support_count": len(support),
        "reconstructed_nonzero_count": len(rational),
    }


def reconstruct_multipliers(
    certificates: list[dict[str, object]],
    descriptors: list[tuple],
) -> tuple[list[dict], dict]:
    characteristics = [int(certificate["characteristic"]) for certificate in certificates]
    if len(set(characteristics)) != len(characteristics):
        raise ValueError("reconstruction characteristics are not distinct")
    formats = {certificate["format"] for certificate in certificates}
    if len(formats) != 1:
        raise ValueError("cannot mix direct-lift and sparse-Macaulay gauges")
    certificate_format = next(iter(formats))
    if certificate_format == "deterministic-sparse-macaulay":
        pivot_profiles = [certificate["pivot_unknown_indices"] for certificate in certificates]
        free_profiles = [certificate["free_unknown_indices"] for certificate in certificates]
        monomial_hashes = {
            certificate["monomial_stream_sha256"] for certificate in certificates
        }
        # Elimination order may change with the prime.  The representative is
        # nevertheless unique once the same coordinate complement is fixed to
        # zero and every retained coordinate is pivoted.  Compare the pivot
        # sets/free list, not the adaptive pivot order.
        reference_pivot_set = set(pivot_profiles[0])
        if any(set(profile) != reference_pivot_set for profile in pivot_profiles[1:]):
            raise ValueError(
                "modular pivot-coordinate sets differ; the free-zero gauge is not stable"
            )
        if any(profile != free_profiles[0] for profile in free_profiles[1:]):
            raise ValueError(
                "modular free-coordinate profiles differ; the gauge is not stable"
            )
        if len(monomial_hashes) != 1:
            raise ValueError("modular monomial-equation streams differ")
        coordinates, metadata = reconstruct_residue_vector(
            [certificate["coordinate_residues"] for certificate in certificates],
            characteristics,
        )
        rational: list[dict[tuple[int, ...], sp.Rational]] = [
            {} for _index in range(17)
        ]
        for unknown_index, coefficient in coordinates.items():
            generator_index, exponents = descriptors[int(unknown_index)]
            rational[generator_index][exponents] = coefficient
        return rational, {
            **metadata,
            "characteristics": characteristics,
            "certificate_format": certificate_format,
            "gauge": (
                "identical pivot/free coordinate sets; all common free coordinates "
                "zero; adaptive elimination order may differ"
            ),
            "pivot_count": len(pivot_profiles[0]),
            "free_unknown_count": len(free_profiles[0]),
            "pivot_unknown_set_sha256": hashlib.sha256(
                json.dumps(sorted(reference_pivot_set), separators=(",", ":")).encode("ascii")
            ).hexdigest(),
            "free_unknown_indices_sha256": hashlib.sha256(
                json.dumps(free_profiles[0], separators=(",", ":")).encode("ascii")
            ).hexdigest(),
            "stable_support_count": metadata["union_support_count"],
            "stable_support_sha256": sparse_stream_sha256(rational),
        }

    supports = [
        [set(multiplier) for multiplier in certificate["multipliers"]]
        for certificate in certificates
    ]
    if any(support != supports[0] for support in supports[1:]):
        raise ValueError(
            "modular multiplier supports differ; the direct-lift gauge is not stable"
        )
    residue_vectors = []
    for certificate in certificates:
        vector = {}
        for multiplier_index, multiplier in enumerate(certificate["multipliers"]):
            vector.update(
                {
                    (multiplier_index, exponents): coefficient
                    for exponents, coefficient in multiplier.items()
                }
            )
        residue_vectors.append(vector)
    reconstructed_coordinates, metadata = reconstruct_residue_vector(
        residue_vectors, characteristics
    )
    rational = [{} for _index in range(17)]
    for (multiplier_index, exponents), coefficient in reconstructed_coordinates.items():
        rational[multiplier_index][exponents] = coefficient
    return rational, {
        **metadata,
        "characteristics": characteristics,
        "certificate_format": certificate_format,
        "gauge": "identical nonzero support from deterministic direct-lift output",
        "stable_support_count": sum(len(support) for support in supports[0]),
        "stable_support_sha256": sparse_stream_sha256(
            [{exponents: 1 for exponents in support} for support in supports[0]]
        ),
    }


def replay_rational(
    multipliers: list[dict[tuple[int, ...], sp.Rational]],
    equation_terms: list[dict[tuple[int, ...], sp.Rational]],
    target_terms: dict[tuple[int, ...], sp.Rational],
) -> dict[str, object]:
    observed: dict[tuple[int, ...], sp.Rational] = {}
    for equation, multiplier in zip(equation_terms, multipliers, strict=True):
        multiply_add_rational(observed, equation, multiplier)
    remainder = subtract_sparse(target_terms, observed)
    nonzero_multipliers = [multiplier for multiplier in multipliers if multiplier]
    return {
        "identity_zero": not remainder,
        "remainder_term_count": len(remainder),
        "observed_term_count": len(observed),
        "target_term_count": len(target_terms),
        "multiplier_count": len(multipliers),
        "nonzero_multiplier_count": len(nonzero_multipliers),
        "multiplier_support_count": sum(len(multiplier) for multiplier in multipliers),
        "maximum_multiplier_total_degree": max(
            (
                sum(exponents)
                for multiplier in nonzero_multipliers
                for exponents in multiplier
            ),
            default=None,
        ),
        "multiplier_stream_sha256": sparse_stream_sha256(multipliers),
    }


def heldout_replay(
    certificate: dict[str, object],
    rational_multipliers: list[dict[tuple[int, ...], sp.Rational]],
) -> dict[str, object]:
    characteristic = int(certificate["characteristic"])
    mismatches = 0
    union_count = 0
    for rational, observed in zip(
        rational_multipliers, certificate["multipliers"], strict=True
    ):
        support = set(rational) | set(observed)
        union_count += len(support)
        for exponents in support:
            expected = rational_residue(
                rational.get(exponents, sp.Rational(0)), characteristic
            )
            if expected != observed.get(exponents, 0):
                mismatches += 1
    return {
        "path": str(certificate["path"]),
        "sha256": certificate["sha256"],
        "characteristic": characteristic,
        "coefficient_union_count": union_count,
        "coefficient_mismatch_count": mismatches,
        "passed": mismatches == 0,
    }


def serialize_multipliers(multipliers: list[dict]) -> list[dict[str, object]]:
    return [
        {
            "normal_generator_position": index,
            "term_count": len(multiplier),
            "terms": [
                {
                    "exponents": list(exponents),
                    "numerator": str(coefficient.p),
                    "denominator": str(coefficient.q),
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
    equations, variables, _, open_factor = homogeneous_saturation_system()
    quartic, quartic_reconstruction = reconstruct_quartic(campaign, variables)
    target = sp.expand(open_factor * quartic)
    equation_stream_sha256 = digest(tuple(equations))
    direct_target_sha256 = hashlib.sha256(
        sp.srepr(target).encode("utf-8")
    ).hexdigest()
    sparse_target_sha256 = digest((target,))
    equation_terms = [polynomial_terms_qq(equation, variables) for equation in equations]
    target_terms = polynomial_terms_qq(target, variables)
    descriptors, descriptor_sha256 = canonical_descriptors(equations, variables)
    if len(descriptors) != 36906:
        raise AssertionError("the canonical multiplier-coordinate count changed")
    frozen_problem = {
        "variable_names": [str(variable) for variable in variables],
        "normal_generators": [
            serialize_sparse_polynomial(equation) for equation in equation_terms
        ],
        "target_M_times_h": serialize_sparse_polynomial(target_terms),
    }
    frozen_problem["sha256"] = canonical_digest(frozen_problem)

    paths = [path.resolve() for path in arguments.certificates]
    heldout_paths = [path.resolve() for path in arguments.heldout]
    if set(paths) & set(heldout_paths):
        parser.error("a reconstruction certificate cannot also be held out")
    certificates = [
        load_certificate(
            path,
            variables,
            len(equations),
            equation_stream_sha256,
            direct_target_sha256,
            sparse_target_sha256,
            descriptors,
            descriptor_sha256,
        )
        for path in paths
    ]
    heldout = [
        load_certificate(
            path,
            variables,
            len(equations),
            equation_stream_sha256,
            direct_target_sha256,
            sparse_target_sha256,
            descriptors,
            descriptor_sha256,
        )
        for path in heldout_paths
    ]
    modular_replays = [
        replay_modular(certificate, equation_terms, target_terms)
        for certificate in certificates + heldout
    ]
    if not all(replay["identity_zero"] for replay in modular_replays):
        raise ValueError("at least one input certificate failed independent modular replay")

    reconstructed, reconstruction = reconstruct_multipliers(
        certificates, descriptors
    )
    rational_replay = replay_rational(reconstructed, equation_terms, target_terms)
    heldout_replays = [
        heldout_replay(certificate, reconstructed) for certificate in heldout
    ]
    passed = (
        rational_replay["identity_zero"]
        and reconstruction["all_coefficients_inside_product_uniqueness_budget"]
        and all(replay["passed"] for replay in heldout_replays)
    )

    artifact_output = arguments.artifact_output or Path(
        "artifacts/j2-secant-r10-colon-identity-qq.json"
    )
    if not artifact_output.is_absolute():
        artifact_output = campaign / artifact_output
    artifact_sha256 = None
    if passed:
        artifact = {
            "schema": "hc4.decimic-j2-secant-r10-colon-identity-qq-certificate.v1",
            "status": "PASS_EXACT_QQ_COLON_IDENTITY",
            "variable_names": [str(variable) for variable in variables],
            "normal_generator_count": len(equations),
            "normal_equation_stream_sha256": equation_stream_sha256,
            "direct_target_sha256": direct_target_sha256,
            "sparse_target_sha256": sparse_target_sha256,
            "row_descriptor_sha256": descriptor_sha256,
            "problem": frozen_problem,
            "open_factor_M": str(open_factor),
            "quartic_reconstruction": quartic_reconstruction,
            "reconstruction": reconstruction,
            "exact_rational_replay": rational_replay,
            "multipliers": serialize_multipliers(reconstructed),
            "claim_boundary": (
                "This artifact proves only the displayed identity M*h=sum(q_i*F_i) "
                "over QQ. It does not determine the full colon or saturated ideal, "
                "close the secant chart, or establish HC4."
            ),
        }
        artifact["certificate_sha256"] = canonical_digest(artifact)
        artifact_text = json.dumps(artifact, indent=2, sort_keys=True) + "\n"
        artifact_output.parent.mkdir(parents=True, exist_ok=True)
        artifact_output.write_text(artifact_text, encoding="ascii")
        artifact_sha256 = hashlib.sha256(artifact_text.encode("ascii")).hexdigest()

    status = (
        "PASS_EXACT_QQ_COLON_IDENTITY"
        if passed
        else "INCOMPLETE_QQ_COLON_IDENTITY_RECONSTRUCTION"
    )
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-identity-qq-reconstruction.v1",
        "status": status,
        "assurance": (
            "exact characteristic-zero polynomial identity"
            if passed
            else "modular reconstruction attempt only"
        ),
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "claim": "M*h lies in the ideal generated by the 17 homogeneous cubics",
        "variable_names": [str(variable) for variable in variables],
        "normal_generator_count": len(equations),
        "normal_equation_stream_sha256": equation_stream_sha256,
        "row_descriptor_sha256": descriptor_sha256,
        "target_total_degree": 8,
        "target_term_count": len(target_terms),
        "direct_target_sha256": direct_target_sha256,
        "sparse_target_sha256": sparse_target_sha256,
        "input_certificates": [
            {
                "path": str(certificate["path"]),
                "sha256": certificate["sha256"],
                "characteristic": certificate["characteristic"],
            }
            for certificate in certificates
        ],
        "modular_replays": modular_replays,
        "reconstruction": reconstruction,
        "exact_rational_replay": rational_replay,
        "heldout_replays": heldout_replays,
        "certificate": (
            None
            if not passed
            else {"path": str(artifact_output), "sha256": artifact_sha256}
        ),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            str(script_path.relative_to(campaign)): file_sha256(script_path),
        },
        "claim_boundary": (
            "A PASS proves only the displayed colon identity over QQ. It does not "
            "determine the full colon or saturated ideal, close the secant chart, "
            "or establish HC4."
        ),
    }
    output = arguments.output or Path(
        "receipts/hsop-j2-secant-r10-colon-identity-qq-reconstruction.json"
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
                "certificate": result["certificate"],
                "crt_modulus": reconstruction["crt_modulus"],
                "stable_support_count": reconstruction["stable_support_count"],
                "exact_identity_zero": rational_replay["identity_zero"],
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
