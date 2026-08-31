#!/usr/bin/env python3
"""Independent coefficientwise replay of the explicit p=173 h4 identity.

This verifier imports neither the h4 certificate producer nor a sparse/dense
eliminator.  It reconstructs the frozen rational problem, rebuilds all 38,826
multiplier descriptors, validates the exported gauge, and computes the final
degree-eight polynomial remainder directly over GF(173).
"""

from __future__ import annotations

import json
import resource
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp

from verify_j2_secant_r10_third_colon_identity_p173 import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    EXPECTED_VARIABLE_NAMES,
    Exponent,
    ModularPolynomial,
    add_exponents,
    canonical_hash,
    character_weight,
    exact_exponent_tuples,
    load_candidate_polynomial,
    load_serialized_polynomial,
    multiply_add_modular,
    multiply_rational,
    producer_digest,
    reduce_modular,
    sha256,
    sympy_expression,
)


PRIME = 173
EXPECTED_HASHES = {
    "certificate": "45654ac41bfe50a76e9a396407734a7f94d3026ba68c9843e93ce432a656ebbe",
    "producer_receipt": "885fa837a2902718f8e76b228e5658b913dd6d77615ff3e52388cf3986ecbb71",
    "second_identity_qq": "32ffb748a88f59c6c7a1ad98d95beb84d5e3c1cdb1422a724677fca1a4ff5d61",
    "second_kernel": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "third_kernel": "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
    "fourth_kernel": "7939f8e57878be21f189ffbf4ac620707924b02f2dbb76f50348b5423a4b9bf2",
    "utility_source": "593b68b95d55de1d91129caaf47ba84d4cc4f8bc481f9f9e77b5e100dd39adbb",
    "descriptor_stream": "478302e341969ae2d8edec433bfd7fc12374598502b7f4e661884b31c4bd5f67",
    "monomial_stream": "ae88030860e7dc4de0ddf446c2b66a97285c4d98d42c6388c783c1c029b66446",
    "generator_stream": "688352a1e62824bdc4300d58e37bc681414d2755cee9da021cd47257d0832378",
    "target": "1d38a51f026483c3dc28ee80652bfc1c9d66f856903374c8a2e6c7392a6f262d",
}


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    paths = {
        "certificate": campaign
        / "artifacts/j2-secant-r10-fourth-colon-identity-sparse-macaulay-hybrid-p173.json",
        "producer_receipt": campaign
        / "receipts/hsop-j2-secant-r10-fourth-colon-identity-sparse-macaulay-hybrid-p173.json",
        "second_identity_qq": campaign
        / "artifacts/j2-secant-r10-second-colon-identity-qq.json",
        "second_kernel": campaign
        / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "third_kernel": campaign
        / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
        "fourth_kernel": campaign
        / "artifacts/j2-secant-r10-fourth-colon-kernel-qq-candidate.json",
    }
    utility_path = campaign / "scripts/verify_j2_secant_r10_third_colon_identity_p173.py"
    actual_hashes = {name: sha256(path) for name, path in paths.items()}
    actual_hashes["utility_source"] = sha256(utility_path)
    source_hash_checks = {
        name: actual_hashes[name] == EXPECTED_HASHES[name]
        for name in (*paths, "utility_source")
    }
    if not all(source_hash_checks.values()):
        raise ValueError(f"a frozen source hash changed: {source_hash_checks}")

    certificate = json.loads(paths["certificate"].read_text(encoding="ascii"))
    producer_receipt = json.loads(
        paths["producer_receipt"].read_text(encoding="ascii")
    )
    second_identity = json.loads(
        paths["second_identity_qq"].read_text(encoding="ascii")
    )
    second_kernel = json.loads(paths["second_kernel"].read_text(encoding="utf-8"))
    third_kernel = json.loads(paths["third_kernel"].read_text(encoding="utf-8"))
    fourth_kernel = json.loads(paths["fourth_kernel"].read_text(encoding="utf-8"))

    variable_names = tuple(second_identity["problem"]["variable_names"])
    if variable_names != EXPECTED_VARIABLE_NAMES:
        raise ValueError("the frozen variable stream changed")
    variable_count = len(variable_names)
    problem_without_hash = dict(second_identity["problem"])
    observed_problem_hash = problem_without_hash.pop("sha256")
    certificate_without_hash = dict(second_identity)
    observed_second_certificate_hash = certificate_without_hash.pop(
        "certificate_sha256"
    )
    internal_hash_checks = {
        "second_problem_hash": canonical_hash(problem_without_hash)
        == observed_problem_hash,
        "second_certificate_hash": canonical_hash(certificate_without_hash)
        == observed_second_certificate_hash,
    }

    generators = [
        load_serialized_polynomial(records, variable_count)
        for records in second_identity["problem"]["generators"]
    ]
    if len(generators) != 18:
        raise ValueError("expected the 17 cubics and h in the frozen problem")
    h2 = load_candidate_polynomial(second_kernel, variable_count)
    h3 = load_candidate_polynomial(third_kernel, variable_count)
    h4 = load_candidate_polynomial(fourth_kernel, variable_count)
    generators.extend([h2, h3])
    generator_degrees = [
        next(iter({sum(exponents) for exponents in polynomial}))
        for polynomial in generators
    ]
    generator_characters = [
        next(iter({character_weight(exponents) for exponents in polynomial}))
        for polynomial in generators
    ]
    expected_characters = [
        5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 7, 9, 10, 11, 0, 1, 4, 3, 2
    ]
    if generator_degrees != [3] * 17 + [4, 4, 4]:
        raise ValueError("generator degree stream changed")
    if generator_characters != expected_characters:
        raise ValueError("generator character stream changed")

    variable_index = {name: index for index, name in enumerate(variable_names)}
    open_factor = {}
    first = [0] * variable_count
    first[variable_index["f9"]] = 3
    first[variable_index["f10"]] = 1
    open_factor[tuple(first)] = Fraction(2)
    second = [0] * variable_count
    second[variable_index["f9"]] = 1
    second[variable_index["f10"]] = 2
    second[variable_index["g0"]] = 1
    open_factor[tuple(second)] = Fraction(5)
    target = multiply_rational(open_factor, h4)
    if len(target) != 495 or {character_weight(item) for item in target} != {2}:
        raise ValueError("the M*h4 target support or character changed")

    pools: dict[tuple[int, int], list[Exponent]] = {}
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(variable_count, degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)
    descriptors: list[tuple[int, Exponent]] = []
    for generator_index, (generator_character, multiplier_degree) in enumerate(
        zip(generator_characters, multiplier_degrees, strict=True)
    ):
        multiplier_character = (2 - generator_character) % CHARACTER_MODULUS
        descriptors.extend(
            (generator_index, monomial)
            for monomial in pools[(multiplier_degree, multiplier_character)]
        )
    descriptor_hash = canonical_hash(descriptors)
    if len(descriptors) != 38_826:
        raise ValueError("the multiplier-coordinate count changed")

    monomial_set = set(target)
    for generator_index, multiplier in descriptors:
        monomial_set.update(
            add_exponents(generator_exponents, multiplier)
            for generator_exponents in generators[generator_index]
        )
    monomials = sorted(monomial_set)
    monomial_hash = canonical_hash(monomials)
    if len(monomials) != 85_688:
        raise ValueError("the supported monomial-equation count changed")

    variables = sp.symbols(" ".join(variable_names))
    generator_expressions = [
        sympy_expression(polynomial, variables) for polynomial in generators
    ]
    target_expression = sympy_expression(target, variables)
    generator_hash = producer_digest(generator_expressions)
    target_hash = producer_digest((target_expression,))
    stream_checks = {
        "descriptor_stream": descriptor_hash
        == certificate["row_descriptor_sha256"]
        == EXPECTED_HASHES["descriptor_stream"],
        "monomial_stream": monomial_hash
        == certificate["monomial_stream_sha256"]
        == EXPECTED_HASHES["monomial_stream"],
        "generator_stream": generator_hash
        == certificate["generator_stream_sha256"]
        == EXPECTED_HASHES["generator_stream"],
        "target_stream": target_hash
        == certificate["target_sha256"]
        == EXPECTED_HASHES["target"],
    }

    coordinates = list(map(int, certificate["coordinate_vector"]))
    pivots = list(map(int, certificate["pivot_unknown_indices"]))
    free = list(map(int, certificate["free_unknown_indices"]))
    coordinate_checks = {
        "coordinate_count": len(coordinates) == len(descriptors) == 38_826,
        "coordinate_range": all(0 <= value < PRIME for value in coordinates),
        "coordinate_hash": canonical_hash(coordinates)
        == certificate["coordinate_vector_sha256"],
        "pivot_hash": canonical_hash(pivots)
        == certificate["pivot_unknown_indices_sha256"],
        "free_hash": canonical_hash(free)
        == certificate["free_unknown_indices_sha256"],
        "pivot_uniqueness": len(pivots) == len(set(pivots)) == 36_587,
        "free_sorted_unique": free == sorted(set(free)) and len(free) == 2_239,
        "pivot_free_partition": set(pivots).isdisjoint(free)
        and set(pivots) | set(free) == set(range(len(descriptors))),
        "free_coordinates_zero": all(coordinates[index] == 0 for index in free),
    }

    observed_support = {}
    support_well_formed = True
    for record in certificate["solution_support"]:
        unknown_index = int(record["unknown_index"])
        if unknown_index in observed_support or not 0 <= unknown_index < len(descriptors):
            support_well_formed = False
            continue
        generator_index, multiplier = descriptors[unknown_index]
        coefficient = int(record["coefficient"])
        if (
            int(record["generator_position"]) != generator_index
            or tuple(map(int, record["multiplier_exponents"])) != multiplier
            or coefficient != coordinates[unknown_index]
            or coefficient == 0
        ):
            support_well_formed = False
        observed_support[unknown_index] = coefficient
    expected_support = {
        index: coefficient
        for index, coefficient in enumerate(coordinates)
        if coefficient
    }
    coordinate_checks["support_well_formed"] = support_well_formed
    coordinate_checks["support_matches_all_nonzero_coordinates"] = (
        observed_support == expected_support and len(observed_support) == 22_557
    )

    multipliers: list[ModularPolynomial] = [{} for _ in generators]
    for unknown_index, coefficient in expected_support.items():
        generator_index, multiplier = descriptors[unknown_index]
        multipliers[generator_index][multiplier] = coefficient
    observed: ModularPolynomial = {}
    for generator, multiplier in zip(generators, multipliers, strict=True):
        multiply_add_modular(observed, reduce_modular(generator), multiplier)
    target_mod = reduce_modular(target)
    remainder = dict(target_mod)
    for exponents, coefficient in observed.items():
        updated = (remainder.get(exponents, 0) - coefficient) % PRIME
        if updated:
            remainder[exponents] = updated
        else:
            remainder.pop(exponents, None)
    replay = {
        "identity_zero": not remainder,
        "remainder_term_count": len(remainder),
        "target_term_count_mod_173": len(target_mod),
        "observed_term_count": len(observed),
        "multiplier_coordinate_count": len(coordinates),
        "nonzero_multiplier_coordinate_count": len(expected_support),
        "nonzero_generator_multiplier_count": sum(bool(item) for item in multipliers),
        "multiplier_term_counts": [len(item) for item in multipliers],
        "maximum_remainder_coefficient": max(remainder.values(), default=0),
    }

    metadata_checks = {
        "certificate_schema": certificate.get("schema")
        == "hc4.decimic-j2-secant-r10-fourth-colon-identity-sparse-macaulay-certificate.v1",
        "characteristic": certificate.get("characteristic") == PRIME,
        "variable_names": tuple(certificate.get("variable_names", ()))
        == variable_names,
        "character_metadata": certificate.get("character_modulus") == 12
        and tuple(certificate.get("character_weights", ())) == CHARACTER_WEIGHTS,
        "degree_metadata": certificate.get("generator_degrees") == generator_degrees
        and certificate.get("multiplier_degrees") == multiplier_degrees,
        "character_stream_metadata": certificate.get("generator_character_weights")
        == generator_characters
        and certificate.get("target_character_weight") == 2,
        "generator_count": certificate.get("generator_count") == 20
        and certificate.get("normal_cubic_generator_count") == 17,
        "producer_receipt_status": producer_receipt.get("status")
        == "PASS_EXACT_MODULAR_FOURTH_COLON_IDENTITY",
        "producer_receipt_certificate_hash": producer_receipt["certificate"]["sha256"]
        == actual_hashes["certificate"],
    }
    passed = (
        all(source_hash_checks.values())
        and all(internal_hash_checks.values())
        and all(stream_checks.values())
        and all(coordinate_checks.values())
        and all(metadata_checks.values())
        and replay["identity_zero"]
    )
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.decimic-j2-secant-r10-fourth-colon-identity-p173-independent-replay.v1",
        "status": (
            "PASS_INDEPENDENT_EXACT_MODULAR_FOURTH_COLON_IDENTITY_REPLAY"
            if passed
            else "FAIL_INDEPENDENT_FOURTH_COLON_IDENTITY_REPLAY"
        ),
        "assurance": (
            "independent termwise exact finite-field replay; h4 producer and "
            "eliminators not imported"
        ),
        "characteristic": PRIME,
        "claim": "M*h4 = sum_i q_i*G_i over GF(173)",
        "source_hash_checks": source_hash_checks,
        "internal_hash_checks": internal_hash_checks,
        "stream_checks": stream_checks,
        "coordinate_checks": coordinate_checks,
        "metadata_checks": metadata_checks,
        "replay": replay,
        "hashes": {
            "descriptor_stream_sha256": descriptor_hash,
            "monomial_stream_sha256": monomial_hash,
            "generator_stream_sha256": generator_hash,
            "target_sha256": target_hash,
        },
        "inputs": {
            **{
                name: {
                    "path": str(path.relative_to(campaign)),
                    "sha256": actual_hashes[name],
                    "byte_count": path.stat().st_size,
                }
                for name, path in paths.items()
            },
            "utility_source": {
                "path": str(utility_path.relative_to(campaign)),
                "sha256": actual_hashes["utility_source"],
                "byte_count": utility_path.stat().st_size,
            },
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
            "imports_h4_certificate_producer": False,
            "imports_sparse_eliminator": False,
        },
        "timings": {"wall_seconds": time.perf_counter() - started},
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "claim_boundary": (
            "A PASS proves only the displayed explicit multiplier identity over "
            "GF(173). It does not prove the identity over QQ, compute a colon or "
            "saturation, close the secant chart, or establish HC4."
        ),
    }
    output_path = campaign / (
        "receipts/hsop-j2-secant-r10-fourth-colon-identity-"
        "p173-independent-replay.json"
    )
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output_path),
                "stream_checks": stream_checks,
                "coordinate_checks": coordinate_checks,
                "replay": replay,
                "wall_seconds": result["timings"]["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
