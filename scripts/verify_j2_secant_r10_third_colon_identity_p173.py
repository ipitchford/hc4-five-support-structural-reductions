#!/usr/bin/env python3
"""Independent coefficientwise replay of the explicit p=173 h3 identity.

The verifier imports neither the certificate producer nor either sparse
eliminator.  The 17 cubics and h are read from the frozen exact-Q second-colon
certificate, h2 and h3 are read from their rational reconstruction artifacts,
and the 38,048-coordinate multiplier stream is rebuilt from total degree and
the exact Z/12 character.  The final gate is a direct sparse convolution over
GF(173).
"""

from __future__ import annotations

import hashlib
import json
import resource
import time
from fractions import Fraction
from pathlib import Path

import sympy as sp


PRIME = 173
CHARACTER_MODULUS = 12
CHARACTER_WEIGHTS = (0, 1, 2, 3, 4, 5, 7, 5, 4, 3, 2, 3, 2, 1, 1, 0, 11, 6)
EXPECTED_VARIABLE_NAMES = (
    "f3", "f4", "f5", "f6", "f7", "f8", "f10", "g0", "g1",
    "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "f9",
)
EXPECTED_HASHES = {
    "certificate": "e55af2dc2d7f390227bda852f5366d68f078500e00794e3a60d7cc4452797ec1",
    "producer_receipt": "4a5a3adb555db8732e92856c1ed64ceac2ff3b9f93730e9b2be7bcd61786952e",
    "second_identity_qq": "32ffb748a88f59c6c7a1ad98d95beb84d5e3c1cdb1422a724677fca1a4ff5d61",
    "second_kernel": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "third_kernel": "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97",
    "descriptor_stream": "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639",
    "monomial_stream": "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614",
    "generator_stream": "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b",
    "target": "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e",
}

Exponent = tuple[int, ...]
RationalPolynomial = dict[Exponent, Fraction]
ModularPolynomial = dict[Exponent, int]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        raise ZeroDivisionError("a rational denominator vanishes modulo 173")
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
        expression += sp.Rational(coefficient.numerator, coefficient.denominator) * monomial
    return sp.expand(expression)


def producer_digest(expressions) -> str:
    payload = "\n".join(
        str(sp.expand(expression)).replace("**", "^") for expression in expressions
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    paths = {
        "certificate": campaign / "artifacts/j2-secant-r10-third-colon-identity-sparse-macaulay-hybrid-p173.json",
        "producer_receipt": campaign / "receipts/hsop-j2-secant-r10-third-colon-identity-sparse-macaulay-hybrid-p173.json",
        "second_identity_qq": campaign / "artifacts/j2-secant-r10-second-colon-identity-qq.json",
        "second_kernel": campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "third_kernel": campaign / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
    }
    actual_hashes = {name: sha256(path) for name, path in paths.items()}
    source_hash_checks = {
        name: actual_hashes[name] == EXPECTED_HASHES[name] for name in paths
    }
    if not all(source_hash_checks.values()):
        raise ValueError(f"a frozen source hash changed: {source_hash_checks}")

    certificate = json.loads(paths["certificate"].read_text(encoding="ascii"))
    producer_receipt = json.loads(
        paths["producer_receipt"].read_text(encoding="utf-8")
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
    second_identity_without_certificate_hash = dict(second_identity)
    observed_second_certificate_hash = second_identity_without_certificate_hash.pop(
        "certificate_sha256"
    )
    internal_hash_checks = {
        "second_problem_hash": canonical_hash(problem_without_hash)
        == observed_problem_hash,
        "second_certificate_hash": canonical_hash(second_identity_without_certificate_hash)
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
    generators.append(h2)
    generator_degrees = [next(iter({sum(item) for item in polynomial})) for polynomial in generators]
    generator_characters = [
        next(iter({character_weight(item) for item in polynomial}))
        for polynomial in generators
    ]
    if generator_degrees != [3] * 17 + [4, 4]:
        raise ValueError("generator degree stream changed")
    if generator_characters != [5, 6, 7, 8, 9, 10, 11, 0, 1, 2, 3, 7, 9, 10, 11, 0, 1, 4, 3]:
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
    descriptor_hash = canonical_hash(descriptors)
    if len(descriptors) != 38_048:
        raise ValueError("the multiplier-coordinate count changed")

    monomial_set = set(target)
    for generator_index, multiplier in descriptors:
        monomial_set.update(
            add_exponents(generator_exponents, multiplier)
            for generator_exponents in generators[generator_index]
        )
    monomials = sorted(monomial_set)
    monomial_hash = canonical_hash(monomials)
    if len(monomials) != 85_651:
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
        "coordinate_count": len(coordinates) == len(descriptors) == 38_048,
        "coordinate_range": all(0 <= value < PRIME for value in coordinates),
        "coordinate_hash": canonical_hash(coordinates)
        == certificate["coordinate_vector_sha256"],
        "pivot_hash": canonical_hash(pivots)
        == certificate["pivot_unknown_indices_sha256"],
        "free_hash": canonical_hash(free)
        == certificate["free_unknown_indices_sha256"],
        "pivot_uniqueness": len(pivots) == len(set(pivots)) == 35_881,
        "free_sorted_unique": free == sorted(set(free)) and len(free) == 2_167,
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
        observed_support == expected_support and len(observed_support) == 20_245
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
        == "hc4.decimic-j2-secant-r10-third-colon-identity-sparse-macaulay-certificate.v1",
        "characteristic": certificate.get("characteristic") == PRIME,
        "variable_names": tuple(certificate.get("variable_names", ()))
        == variable_names,
        "character_metadata": certificate.get("character_modulus") == 12
        and tuple(certificate.get("character_weights", ())) == CHARACTER_WEIGHTS,
        "degree_metadata": certificate.get("generator_degrees") == generator_degrees
        and certificate.get("multiplier_degrees") == multiplier_degrees,
        "character_stream_metadata": certificate.get("generator_character_weights")
        == generator_characters
        and certificate.get("target_character_weight") == 3,
        "generator_count": certificate.get("generator_count") == 19
        and certificate.get("normal_cubic_generator_count") == 17,
        "producer_receipt_status": producer_receipt.get("status")
        == "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY",
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
        "schema": "hc4.decimic-j2-secant-r10-third-colon-identity-p173-independent-replay.v1",
        "status": (
            "PASS_INDEPENDENT_EXACT_MODULAR_THIRD_COLON_IDENTITY_REPLAY"
            if passed
            else "FAIL_INDEPENDENT_THIRD_COLON_IDENTITY_REPLAY"
        ),
        "assurance": "independent termwise exact finite-field replay; producer and eliminator not imported",
        "characteristic": PRIME,
        "claim": "M*h3 = sum_i q_i*G_i over GF(173)",
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
            name: {
                "path": str(path.relative_to(campaign)),
                "sha256": actual_hashes[name],
                "byte_count": path.stat().st_size,
            }
            for name, path in paths.items()
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
            "imports_certificate_producer": False,
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
    output_path = (
        campaign
        / "receipts/hsop-j2-secant-r10-third-colon-identity-p173-independent-replay.json"
    )
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
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
