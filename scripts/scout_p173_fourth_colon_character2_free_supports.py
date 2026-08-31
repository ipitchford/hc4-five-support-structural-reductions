#!/usr/bin/env -S sage -python
"""Exact support census for free columns in the fourth character-two block."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

import build_p173_fourth_colon_integral_lift_system as base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    certificate = json.loads(base.MODULAR_CERTIFICATE.read_text(encoding="ascii"))
    free = [int(value) for value in certificate["free_unknown_indices"]]
    base.require(
        len(free) == base.GLOBAL_COLUMNS - base.LOCAL_COLUMNS
        and free == sorted(set(free)),
        "free-index partition drift",
    )

    equations, variables, _leading, _open_factor = base.homogeneous_saturation_system()
    first, _first_metadata = base.reconstruct_quartic(base.CAMPAIGN, variables)
    second, _second_metadata = base.load_second_quartic(base.CAMPAIGN, variables)
    third, _third_metadata = base.load_third_quartic(base.CAMPAIGN, variables)
    generators = list(equations) + [first, second, third]
    generator_degrees = [3] * len(equations) + [4, 4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]

    term_counts: list[int] = []
    generator_weights: list[int] = []
    for generator, expected_degree in zip(
        generators, generator_degrees, strict=True
    ):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = polynomial.terms()
        base.require(
            {sum(map(int, exponents)) for exponents, _coefficient in terms}
            == {expected_degree},
            "generator degree drift",
        )
        weights = {
            base.character_weight(tuple(map(int, exponents)))
            for exponents, _coefficient in terms
        }
        base.require(len(weights) == 1, "generator character drift")
        term_counts.append(len(terms))
        generator_weights.append(next(iter(weights)))

    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in base.exact_exponent_tuples(len(variables), degree):
            pools.setdefault(
                (degree, base.character_weight(monomial)), []
            ).append(monomial)

    descriptors: list[tuple[int, tuple[int, ...]]] = []
    for generator_index, (weight, degree) in enumerate(
        zip(generator_weights, multiplier_degrees, strict=True)
    ):
        multiplier_weight = (2 - weight) % base.CHARACTER_MODULUS
        descriptors.extend(
            (generator_index, multiplier)
            for multiplier in pools.get((degree, multiplier_weight), [])
        )

    base.require(len(descriptors) == base.GLOBAL_COLUMNS, "descriptor count drift")
    observed_hash = base.canonical_hash(descriptors)
    base.require(
        observed_hash == base.EXPECTED_HASHES["descriptor"],
        "descriptor hash drift",
    )

    records = []
    histogram: dict[int, int] = {}
    family_histogram: dict[str, int] = {}
    for global_coordinate in free:
        generator_index, multiplier = descriptors[global_coordinate]
        support = term_counts[generator_index]
        histogram[support] = histogram.get(support, 0) + 1
        family = f"g{generator_index:02d}"
        family_histogram[family] = family_histogram.get(family, 0) + 1
        records.append(
            {
                "global_coordinate": global_coordinate,
                "generator_index": generator_index,
                "generator_support": support,
                "multiplier_exponents": list(multiplier),
            }
        )
    records.sort(
        key=lambda record: (record["generator_support"], record["global_coordinate"])
    )

    result = {
        "status": "PASS_EXACT_FOURTH_CHARACTER2_FREE_SUPPORT_CENSUS",
        "descriptor_sha256": observed_hash,
        "global_columns": len(descriptors),
        "free_columns": len(free),
        "support_histogram": {
            str(key): value for key, value in sorted(histogram.items())
        },
        "free_generator_histogram": dict(sorted(family_histogram.items())),
        "selected_first_16": records[:16],
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "claim_boundary": (
            "Exact descriptor/support census only; no matrix transfer, kernel "
            "direction, p-adic digit, rational syzygy, target identity, or HC4 result."
        ),
    }
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is not None:
        output = (
            arguments.output
            if arguments.output.is_absolute()
            else base.CAMPAIGN / arguments.output
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="ascii")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
