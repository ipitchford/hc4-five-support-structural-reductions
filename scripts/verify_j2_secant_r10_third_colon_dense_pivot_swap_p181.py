#!/usr/bin/env python3
"""Independent coefficientwise audit of the p=181 dense-pivot swap.

This verifier imports neither the dense-pivot constructor nor any Macaulay
producer/eliminator.  It rebuilds the 19 generators, target, 38,048
multiplier descriptors, and 85,651 coefficient equations from the frozen
exact-Q inputs, then directly convolves the explicit coordinate vector over
GF(181).  It also checks that the new gauge exchanges exactly the 581 old
dense pivots for 581 old free coordinates and binds the construction receipt
to its original p=181 source.
"""

from __future__ import annotations

import hashlib
import json
import resource
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp


PRIME = 181
CHARACTER_MODULUS = 12
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
EXPECTED_VARIABLE_NAMES = (
    "f3", "f4", "f5", "f6", "f7", "f8", "f10", "g0", "g1",
    "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "f9",
)
EXPECTED_INPUT_HASHES = {
    "certificate": "c3e8c2e8f5bb514a3c53944c93a1051c1264323b11624c237217fde091672c3a",
    "producer_receipt": "7765fbec47517b5f90c580b008aa6f3c0352324e23e11dec479d626d781e1798",
    "source_certificate": "26be0a64574c3cdbe6f7d0c323f9a5e4beb9b8df8e568f9daa054744160bc0a1",
    "source_receipt": "fe32cc53e81cf50e6c34881c5c61605938178a366986fae6ce872670aa9ddc6a",
    "second_identity_qq": "32ffb748a88f59c6c7a1ad98d95beb84d5e3c1cdb1422a724677fca1a4ff5d61",
    "second_kernel": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "third_kernel": "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
}
EXPECTED_LINEAGE_HASHES = {
    "scripts/certify_j2_secant_r10_colon_identity_sparse_macaulay.py":
        "76ba50cd9cf226ffd07169b4aac619974c35027fa20153136e354263f005c27b",
    "scripts/certify_j2_secant_r10_second_colon_identity_sparse_macaulay.py":
        "ea20fb8719bb583c424f0cc4e2730b46c7f38e130558fa7e6d2422865fb1af6b",
    "scripts/certify_j2_secant_r10_third_colon_identity_sparse_macaulay.py":
        "c0e1557c1a18d85af997e24c739d799d58c7d0b655d0662a0215f30e9b42ae74",
    "scripts/construct_j2_secant_r10_third_colon_dense_pivot_swap.py":
        "b47b42cf599306f4ab426299dfdd3dfe5a516d0249f34446f4858851fa82beff",
}
EXPECTED_STREAM_HASHES = {
    "descriptor_stream": "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639",
    "monomial_stream": "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614",
    "generator_stream": "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b",
    "target": "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e",
}

Exponent = tuple[int, ...]
RationalPolynomial = dict[Exponent, Fraction]
ModularPolynomial = dict[Exponent, int]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()


def character_weight(exponents: Exponent) -> int:
    return sum(
        exponent * weight
        for exponent, weight in zip(exponents, CHARACTER_WEIGHTS, strict=True)
    ) % CHARACTER_MODULUS


def exact_exponent_tuples(variable_count: int, degree: int):
    def recurse(position: int, remaining: int, prefix: Exponent):
        if position + 1 == variable_count:
            yield prefix + (remaining,)
            return
        for exponent in range(remaining + 1):
            yield from recurse(
                position + 1, remaining - exponent, prefix + (exponent,)
            )

    yield from recurse(0, degree, ())


def decode_coefficient(value) -> Fraction:
    if isinstance(value, int):
        return Fraction(value, 1)
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(item, int) for item in value)
    ):
        return Fraction(value[0], value[1])
    raise ValueError(f"unsupported frozen coefficient {value!r}")


def load_serialized_polynomial(records, variable_count: int) -> RationalPolynomial:
    result = {}
    for exponents, encoded in records:
        exponent_tuple = tuple(map(int, exponents))
        if len(exponent_tuple) != variable_count or exponent_tuple in result:
            raise ValueError("malformed or duplicate serialized polynomial term")
        coefficient = decode_coefficient(encoded)
        if not coefficient:
            raise ValueError("zero term in serialized polynomial")
        result[exponent_tuple] = coefficient
    return result


def load_candidate_polynomial(payload, variable_count: int) -> RationalPolynomial:
    result = {}
    for record in payload["terms"]:
        exponents = tuple(map(int, record["exponents"]))
        if len(exponents) != variable_count or exponents in result:
            raise ValueError("malformed or duplicate candidate term")
        coefficient = Fraction(int(record["numerator"]), int(record["denominator"]))
        if not coefficient:
            raise ValueError("zero candidate term")
        result[exponents] = coefficient
    if len(result) != int(payload["term_count"]):
        raise ValueError("candidate term count changed")
    return result


def add_exponents(left: Exponent, right: Exponent) -> Exponent:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def multiply_rational(
    left: RationalPolynomial, right: RationalPolynomial
) -> RationalPolynomial:
    result: RationalPolynomial = {}
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = add_exponents(left_exponents, right_exponents)
            coefficient = (
                result.get(exponents, Fraction(0))
                + left_coefficient * right_coefficient
            )
            if coefficient:
                result[exponents] = coefficient
            else:
                result.pop(exponents, None)
    return result


def residue(value: Fraction) -> int:
    denominator = value.denominator % PRIME
    if denominator == 0:
        raise ZeroDivisionError("a rational denominator vanishes modulo 181")
    return value.numerator % PRIME * pow(denominator, -1, PRIME) % PRIME


def reduce_modular(polynomial: RationalPolynomial) -> ModularPolynomial:
    return {
        exponents: coefficient
        for exponents, rational in polynomial.items()
        if (coefficient := residue(rational))
    }


def multiply_add_modular(
    accumulator: ModularPolynomial,
    left: ModularPolynomial,
    right: ModularPolynomial,
) -> None:
    for left_exponents, left_coefficient in left.items():
        for right_exponents, right_coefficient in right.items():
            exponents = add_exponents(left_exponents, right_exponents)
            coefficient = (
                accumulator.get(exponents, 0)
                + left_coefficient * right_coefficient
            ) % PRIME
            if coefficient:
                accumulator[exponents] = coefficient
            else:
                accumulator.pop(exponents, None)


def sympy_expression(polynomial: RationalPolynomial, variables) -> sp.Expr:
    expression = sp.Integer(0)
    for exponents, coefficient in polynomial.items():
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += sp.Rational(
            coefficient.numerator, coefficient.denominator
        ) * monomial
    return sp.expand(expression)


def expression_digest(expressions) -> str:
    payload = "\n".join(
        str(sp.expand(expression)).replace("**", "^") for expression in expressions
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def resolved_path_matches(recorded: str, actual: Path) -> bool:
    try:
        return Path(recorded).resolve() == actual.resolve()
    except (OSError, TypeError):
        return False


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    paths = {
        "certificate": campaign / "artifacts/j2-secant-r10-third-colon-identity-dense-pivot-swap-p181.json",
        "producer_receipt": campaign / "receipts/hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-p181.json",
        "source_certificate": campaign / "artifacts/j2-secant-r10-third-colon-identity-alt-gauge-p181.json",
        "source_receipt": campaign / "receipts/hsop-j2-secant-r10-third-colon-identity-alt-gauge-p181.json",
        "second_identity_qq": campaign / "artifacts/j2-secant-r10-second-colon-identity-qq.json",
        "second_kernel": campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "third_kernel": campaign / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
    }
    actual_hashes = {name: file_sha256(path) for name, path in paths.items()}
    input_hash_checks = {
        name: actual_hashes[name] == EXPECTED_INPUT_HASHES[name] for name in paths
    }
    if not all(input_hash_checks.values()):
        raise ValueError(f"a pinned audit input changed: {input_hash_checks}")

    lineage_actual = {
        relative: file_sha256(campaign / relative)
        for relative in EXPECTED_LINEAGE_HASHES
    }
    lineage_file_checks = {
        relative: lineage_actual[relative] == expected
        for relative, expected in EXPECTED_LINEAGE_HASHES.items()
    }
    if not all(lineage_file_checks.values()):
        raise ValueError(f"a pinned construction source changed: {lineage_file_checks}")

    certificate = json.loads(paths["certificate"].read_text(encoding="ascii"))
    producer_receipt = json.loads(
        paths["producer_receipt"].read_text(encoding="utf-8")
    )
    source_certificate = json.loads(
        paths["source_certificate"].read_text(encoding="ascii")
    )
    source_receipt = json.loads(
        paths["source_receipt"].read_text(encoding="utf-8")
    )
    second_identity = json.loads(
        paths["second_identity_qq"].read_text(encoding="ascii")
    )
    second_kernel = json.loads(paths["second_kernel"].read_text(encoding="utf-8"))
    third_kernel = json.loads(paths["third_kernel"].read_text(encoding="utf-8"))

    variable_names = tuple(second_identity["problem"]["variable_names"])
    if variable_names != EXPECTED_VARIABLE_NAMES:
        raise ValueError("the frozen variable stream changed")
    variable_count = len(variable_names)
    problem_without_hash = dict(second_identity["problem"])
    observed_problem_hash = problem_without_hash.pop("sha256")
    second_without_hash = dict(second_identity)
    observed_second_hash = second_without_hash.pop("certificate_sha256")
    internal_hash_checks = {
        "second_problem_hash": canonical_hash(problem_without_hash)
        == observed_problem_hash,
        "second_certificate_hash": canonical_hash(second_without_hash)
        == observed_second_hash,
    }

    generators = [
        load_serialized_polynomial(records, variable_count)
        for records in second_identity["problem"]["generators"]
    ]
    if len(generators) != 18:
        raise ValueError("expected exactly the 17 cubics and first quartic")
    h2 = load_candidate_polynomial(second_kernel, variable_count)
    h3 = load_candidate_polynomial(third_kernel, variable_count)
    generators.append(h2)
    generator_degrees = [
        next(iter({sum(exponents) for exponents in polynomial}))
        for polynomial in generators
    ]
    generator_characters = [
        next(iter({character_weight(exponents) for exponents in polynomial}))
        for polynomial in generators
    ]
    if generator_degrees != [3] * 17 + [4, 4]:
        raise ValueError("generator degree stream changed")
    expected_generator_characters = [
        5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 7, 9, 10, 11, 0, 1, 4, 3
    ]
    if generator_characters != expected_generator_characters:
        raise ValueError("generator character stream changed")

    variable_index = {name: index for index, name in enumerate(variable_names)}
    open_factor: RationalPolynomial = {}
    first = [0] * variable_count
    first[variable_index["f9"]] = 3
    first[variable_index["f10"]] = 1
    open_factor[tuple(first)] = Fraction(2)
    second = [0] * variable_count
    second[variable_index["f9"]] = 1
    second[variable_index["f10"]] = 2
    second[variable_index["g0"]] = 1
    open_factor[tuple(second)] = Fraction(5)
    target = multiply_rational(open_factor, h3)
    if len(target) != 486:
        raise ValueError("the M*h3 target term count changed")

    pools: dict[tuple[int, int], list[Exponent]] = {}
    multiplier_degrees = [8 - degree for degree in generator_degrees]
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(variable_count, degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)
    descriptors: list[tuple[int, Exponent]] = []
    for generator_index, (generator_character, multiplier_degree) in enumerate(
        zip(generator_characters, multiplier_degrees, strict=True)
    ):
        multiplier_character = (3 - generator_character) % CHARACTER_MODULUS
        descriptors.extend(
            (generator_index, monomial)
            for monomial in pools[(multiplier_degree, multiplier_character)]
        )
    if len(descriptors) != 38_048:
        raise ValueError("the multiplier descriptor count changed")

    monomial_set = set(target)
    for generator_index, multiplier in descriptors:
        monomial_set.update(
            add_exponents(generator_exponents, multiplier)
            for generator_exponents in generators[generator_index]
        )
    monomials = sorted(monomial_set)
    if len(monomials) != 85_651:
        raise ValueError("the coefficient-equation count changed")

    variables = sp.symbols(" ".join(variable_names))
    generator_expressions = [
        sympy_expression(polynomial, variables) for polynomial in generators
    ]
    target_expression = sympy_expression(target, variables)
    computed_stream_hashes = {
        "descriptor_stream": canonical_hash(descriptors),
        "monomial_stream": canonical_hash(monomials),
        "generator_stream": expression_digest(generator_expressions),
        "target": expression_digest((target_expression,)),
    }
    certificate_stream_fields = {
        "descriptor_stream": "row_descriptor_sha256",
        "monomial_stream": "monomial_stream_sha256",
        "generator_stream": "generator_stream_sha256",
        "target": "target_sha256",
    }
    stream_checks = {
        name: computed_stream_hashes[name]
        == EXPECTED_STREAM_HASHES[name]
        == certificate[field]
        == source_certificate[field]
        == source_receipt["hashes"][field]
        for name, field in certificate_stream_fields.items()
    }

    source_coordinates = list(map(int, source_certificate["coordinate_vector"]))
    old_pivots = list(map(int, source_certificate["pivot_unknown_indices"]))
    old_free = list(map(int, source_certificate["free_unknown_indices"]))
    source_coordinate_checks = {
        "coordinate_count": len(source_coordinates) == 38_048,
        "coordinate_hash": canonical_hash(source_coordinates)
        == source_certificate["coordinate_vector_sha256"],
        "pivot_count_unique": len(old_pivots) == len(set(old_pivots)) == 35_881,
        "pivot_hash": canonical_hash(old_pivots)
        == source_certificate["pivot_unknown_indices_sha256"],
        "free_count_sorted_unique": old_free == sorted(set(old_free))
        and len(old_free) == 2_167,
        "free_hash": canonical_hash(old_free)
        == source_certificate["free_unknown_indices_sha256"],
        "partition": set(old_pivots).isdisjoint(old_free)
        and set(old_pivots) | set(old_free) == set(range(38_048)),
        "free_coordinates_zero": all(source_coordinates[index] == 0 for index in old_free),
    }

    coordinates = list(map(int, certificate["coordinate_vector"]))
    pivots = list(map(int, certificate["pivot_unknown_indices"]))
    free = list(map(int, certificate["free_unknown_indices"]))
    old_sparse_prefix = old_pivots[:35_300]
    old_dense_pivots = old_pivots[35_300:]
    dense_swap = producer_receipt["dense_swap"]
    selected_old_free = list(map(int, dense_swap["selected_old_free_indices"]))
    expected_new_free = sorted(
        set(old_dense_pivots) | (set(old_free) - set(selected_old_free))
    )
    coordinate_checks = {
        "coordinate_count": len(coordinates) == len(descriptors) == 38_048,
        "coordinate_range": all(0 <= value < PRIME for value in coordinates),
        "coordinate_hash": canonical_hash(coordinates)
        == certificate["coordinate_vector_sha256"]
        == dense_swap["new_coordinate_vector_sha256"],
        "pivot_count_unique": len(pivots) == len(set(pivots)) == 35_881,
        "pivot_hash": canonical_hash(pivots)
        == certificate["pivot_unknown_indices_sha256"]
        == dense_swap["new_pivot_unknown_indices_sha256"],
        "free_count_sorted_unique": free == sorted(set(free)) and len(free) == 2_167,
        "free_hash": canonical_hash(free)
        == certificate["free_unknown_indices_sha256"]
        == dense_swap["new_free_unknown_indices_sha256"],
        "pivot_free_partition": set(pivots).isdisjoint(free)
        and set(pivots) | set(free) == set(range(38_048)),
        "free_coordinates_zero": all(coordinates[index] == 0 for index in free),
    }
    swap_checks = {
        "old_dense_suffix_count": len(old_dense_pivots) == 581,
        "old_dense_suffix_hash": canonical_hash(old_dense_pivots)
        == dense_swap["zeroed_old_dense_pivot_indices_sha256"]
        == producer_receipt["frozen_dimensions"]["old_dense_pivot_indices_sha256"],
        "all_old_dense_pivots_zero": all(
            coordinates[index] == 0 for index in old_dense_pivots
        ),
        "old_dense_pivots_are_new_free": set(old_dense_pivots) <= set(free),
        "sparse_prefix_preserved": pivots[:35_300] == old_sparse_prefix,
        "selected_count_unique": len(selected_old_free)
        == len(set(selected_old_free))
        == 581,
        "selected_indices_hash": canonical_hash(selected_old_free)
        == dense_swap["selected_old_free_indices_sha256"],
        "selected_are_old_free": set(selected_old_free) <= set(old_free),
        "selected_are_new_dense_suffix": pivots[35_300:] == selected_old_free,
        "new_free_set_exact": free == expected_new_free,
        "zeroed_count_metadata": dense_swap["zeroed_old_dense_pivot_count"] == 581,
        "selected_value_profile": sum(bool(coordinates[index]) for index in selected_old_free)
        == dense_swap["selected_old_free_nonzero_value_count"]
        == 576
        and sum(not coordinates[index] for index in selected_old_free)
        == dense_swap["selected_old_free_zero_value_count"]
        == 5,
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
    support_checks = {
        "support_well_formed": support_well_formed,
        "support_matches_every_nonzero_coordinate": observed_support == expected_support,
        "support_count": len(observed_support)
        == int(producer_receipt["solution_support_count"])
        == 20_283,
    }

    multipliers: list[ModularPolynomial] = [{} for _ in generators]
    for unknown_index, coefficient in expected_support.items():
        generator_index, multiplier = descriptors[unknown_index]
        multipliers[generator_index][multiplier] = coefficient
    observed: ModularPolynomial = {}
    for generator, multiplier in zip(generators, multipliers, strict=True):
        multiply_add_modular(observed, reduce_modular(generator), multiplier)
    target_mod = reduce_modular(target)
    mismatch_count = 0
    first_mismatch = None
    for equation_index, monomial in enumerate(monomials):
        actual = observed.get(monomial, 0)
        expected = target_mod.get(monomial, 0)
        if actual != expected:
            mismatch_count += 1
            if first_mismatch is None:
                first_mismatch = {
                    "equation_index": equation_index,
                    "monomial": list(monomial),
                    "actual": actual,
                    "expected": expected,
                }
    outside_support = (set(observed) | set(target_mod)) - set(monomials)
    replay = {
        "method": "fresh direct sparse convolution and coefficientwise comparison",
        "checked_equation_count": len(monomials),
        "mismatch_count": mismatch_count,
        "first_mismatch": first_mismatch,
        "outside_frozen_monomial_count": len(outside_support),
        "identity_zero": mismatch_count == 0 and not outside_support,
        "target_term_count_mod_181": len(target_mod),
        "observed_term_count": len(observed),
        "multiplier_coordinate_count": len(coordinates),
        "nonzero_multiplier_coordinate_count": len(expected_support),
        "nonzero_generator_multiplier_count": sum(bool(item) for item in multipliers),
        "multiplier_term_counts": [len(item) for item in multipliers],
    }

    artifact_source = certificate["construction_source"]
    receipt_source = producer_receipt["source"]
    source_binding_checks = {
        "artifact_source_path": resolved_path_matches(
            artifact_source["path"], paths["source_certificate"]
        ),
        "artifact_source_hash": artifact_source["sha256"]
        == actual_hashes["source_certificate"],
        "artifact_source_receipt_path": resolved_path_matches(
            artifact_source["receipt_path"], paths["source_receipt"]
        ),
        "artifact_source_receipt_hash": artifact_source["receipt_sha256"]
        == actual_hashes["source_receipt"],
        "artifact_source_characteristic": artifact_source["characteristic"] == PRIME,
        "artifact_source_partition_hashes": artifact_source["pivot_unknown_set_sha256"]
        == canonical_hash(sorted(old_pivots))
        and artifact_source["free_unknown_indices_sha256"] == canonical_hash(old_free),
        "artifact_source_partition_counts": artifact_source["pivot_count"] == 35_881
        and artifact_source["free_unknown_count"] == 2_167,
        "receipt_source_paths": resolved_path_matches(
            receipt_source["artifact"], paths["source_certificate"]
        ) and resolved_path_matches(receipt_source["receipt"], paths["source_receipt"]),
        "receipt_source_hashes": receipt_source["artifact_sha256"]
        == actual_hashes["source_certificate"]
        and receipt_source["receipt_sha256"] == actual_hashes["source_receipt"],
        "source_receipt_statuses": receipt_source["receipt_status"]
        == source_receipt["status"]
        == "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
        "source_receipt_artifact_binding": source_receipt["certificate"]["sha256"]
        == actual_hashes["source_certificate"]
        and source_receipt["certificate"]["byte_count"]
        == paths["source_certificate"].stat().st_size,
        "source_receipt_replay": source_receipt["same_process_sparse_replay"]["identity_zero"]
        is True
        and source_receipt["same_process_sparse_replay"]["mismatch_count"] == 0,
    }
    lineage_checks = {
        "artifact_dependencies_match_current_files": certificate["source_dependencies"]
        == lineage_actual,
        "receipt_dependencies_match_current_files": producer_receipt["source_sha256"]
        == lineage_actual,
        "artifact_receipt_dependencies_agree": certificate["source_dependencies"]
        == producer_receipt["source_sha256"],
        "quartic_metadata_preserved": certificate["first_quartic"]
        == source_certificate["first_quartic"]
        and certificate["second_quartic"] == source_certificate["second_quartic"]
        and certificate["third_quartic"] == source_certificate["third_quartic"],
    }
    producer_binding_checks = {
        "receipt_status": producer_receipt["status"]
        == "PASS_EXACT_MODULAR_THIRD_COLON_DENSE_PIVOT_SWAP",
        "receipt_characteristic": producer_receipt["characteristic"] == PRIME,
        "receipt_certificate_hash": producer_receipt["certificate"]["sha256"]
        == actual_hashes["certificate"],
        "receipt_certificate_bytes": producer_receipt["certificate"]["byte_count"]
        == paths["certificate"].stat().st_size,
        "receipt_certificate_path": resolved_path_matches(
            producer_receipt["certificate"]["path"], paths["certificate"]
        ),
        "receipt_replay": producer_receipt["replay"]["identity_zero"] is True
        and producer_receipt["replay"]["mismatch_count"] == 0,
        "receipt_dimensions": producer_receipt["frozen_dimensions"]["equation_count"]
        == 85_651
        and producer_receipt["frozen_dimensions"]["unknown_count"] == 38_048
        and producer_receipt["frozen_dimensions"]["total_pivot_count"] == 35_881
        and producer_receipt["frozen_dimensions"]["global_free_count"] == 2_167,
    }
    metadata_checks = {
        "certificate_schema": certificate["schema"]
        == "hc4.decimic-j2-secant-r10-third-colon-identity-sparse-macaulay-certificate.v1",
        "characteristic": certificate["characteristic"] == PRIME,
        "variable_names": tuple(certificate["variable_names"]) == variable_names,
        "character_metadata": certificate["character_modulus"] == CHARACTER_MODULUS
        and tuple(certificate["character_weights"]) == CHARACTER_WEIGHTS,
        "degree_metadata": certificate["generator_degrees"] == generator_degrees
        and certificate["multiplier_degrees"] == multiplier_degrees,
        "character_stream_metadata": certificate["generator_character_weights"]
        == generator_characters
        and certificate["target_character_weight"] == 3,
        "generator_count": certificate["generator_count"] == 19
        and certificate["normal_cubic_generator_count"] == 17,
        "gauge_source_null": certificate["gauge_source"] is None,
    }

    check_groups = {
        "input_hash_checks": input_hash_checks,
        "lineage_file_checks": lineage_file_checks,
        "internal_hash_checks": internal_hash_checks,
        "stream_checks": stream_checks,
        "source_coordinate_checks": source_coordinate_checks,
        "coordinate_checks": coordinate_checks,
        "swap_checks": swap_checks,
        "support_checks": support_checks,
        "source_binding_checks": source_binding_checks,
        "lineage_checks": lineage_checks,
        "producer_binding_checks": producer_binding_checks,
        "metadata_checks": metadata_checks,
    }
    passed = all(all(group.values()) for group in check_groups.values()) and replay[
        "identity_zero"
    ]
    usage = resource.getrusage(resource.RUSAGE_SELF)
    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dense-pivot-swap-p181-independent-replay.v1",
        "status": (
            "PASS_INDEPENDENT_EXACT_MODULAR_DENSE_PIVOT_SWAP_REPLAY"
            if passed
            else "FAIL_INDEPENDENT_DENSE_PIVOT_SWAP_REPLAY"
        ),
        "assurance": (
            "independent termwise GF(181) replay and gauge-lineage audit; "
            "constructor, producer, and eliminators not imported or executed"
        ),
        "characteristic": PRIME,
        "claim": "M*h3 = sum_i q_i*G_i over GF(181) in the dense-pivot-swap gauge",
        **check_groups,
        "replay": replay,
        "verified_swap_profile": {
            "total_coordinates": len(coordinates),
            "new_pivot_count": len(pivots),
            "new_free_count": len(free),
            "old_dense_pivots_checked_zero": len(old_dense_pivots),
            "selected_old_free_coordinates": len(selected_old_free),
            "nonzero_coordinates": len(expected_support),
        },
        "hashes": {
            "descriptor_stream_sha256": computed_stream_hashes["descriptor_stream"],
            "monomial_stream_sha256": computed_stream_hashes["monomial_stream"],
            "generator_stream_sha256": computed_stream_hashes["generator_stream"],
            "target_sha256": computed_stream_hashes["target"],
            "coordinate_vector_sha256": canonical_hash(coordinates),
            "pivot_unknown_indices_sha256": canonical_hash(pivots),
            "free_unknown_indices_sha256": canonical_hash(free),
            "old_dense_pivot_indices_sha256": canonical_hash(old_dense_pivots),
            "selected_old_free_indices_sha256": canonical_hash(selected_old_free),
        },
        "inputs": {
            name: {
                "path": str(path.relative_to(campaign)),
                "sha256": actual_hashes[name],
                "byte_count": path.stat().st_size,
            }
            for name, path in paths.items()
        },
        "construction_lineage": {
            relative: {
                "sha256": lineage_actual[relative],
                "byte_count": (campaign / relative).stat().st_size,
            }
            for relative in lineage_actual
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": file_sha256(script_path),
            "imports_dense_pivot_constructor": False,
            "imports_macaulay_producer": False,
            "imports_sparse_eliminator": False,
        },
        "timings": {"wall_seconds": time.perf_counter() - started},
        "resources": {
            "maximum_rss_native": usage.ru_maxrss,
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
        "claim_boundary": (
            "A PASS proves only the displayed explicit multiplier identity and "
            "the stated gauge exchange over GF(181). It does not prove a QQ "
            "identity, validate any transfer-prime artifact, reconstruct rational "
            "multipliers, compute a colon or saturation, close the secant chart, "
            "or establish HC4."
        ),
    }
    output_path = campaign / (
        "receipts/hsop-j2-secant-r10-third-colon-identity-dense-pivot-swap-"
        "p181-independent-replay.json"
    )
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output_path),
                "replay": replay,
                "verified_swap_profile": result["verified_swap_profile"],
                "failed_checks": {
                    group_name: [name for name, ok in group.items() if not ok]
                    for group_name, group in check_groups.items()
                    if not all(group.values())
                },
                "wall_seconds": result["timings"]["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
