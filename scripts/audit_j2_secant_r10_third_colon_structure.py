#!/usr/bin/env sage-python
"""Independent structural audit of the third secant colon candidate.

This script deliberately avoids the third-identity solver.  It checks the
three reconstructed quartics against the degree-four character blocks of the
17-cubic ideal, tests whether the apparent character 4,3,2 staircase is
explained by degree-preserving first-order differential transforms, audits
factorization and pairwise gcds over two large prime fields, and computes the
purely combinatorial connected-component profile of the prospective h3
Macaulay identity.

All positive algebraic statements are finite-field statements unless marked
as exact integer/rational consistency checks.  In particular, this script
does not prove M*h3 lies in (I,h,h2).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


DEFAULT_PRIMES = (1_073_741_827, 1_073_742_851)
FLINT_REQUIREMENT = "python-flint==0.9.0"

SparseVector = dict[tuple[int, ...], int]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    ).hexdigest()


def exact_exponent_tuples(variable_count: int, degree: int):
    def recurse(position: int, remaining: int, prefix: tuple[int, ...]):
        if position + 1 == variable_count:
            yield prefix + (remaining,)
            return
        for exponent in range(remaining + 1):
            yield from recurse(position + 1, remaining - exponent, prefix + (exponent,))

    yield from recurse(0, degree, ())


def canonical_vector(records, prime: int) -> SparseVector:
    result: SparseVector = {}
    for exponents, coefficient in records:
        exponents = tuple(map(int, exponents))
        value = int(coefficient) % prime
        if value:
            result[exponents] = (result.get(exponents, 0) + value) % prime
            if result[exponents] == 0:
                del result[exponents]
    return result


def sympy_terms_mod_p(expression, variables, prime: int) -> SparseVector:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    terms = []
    for exponents, coefficient in polynomial.terms():
        denominator = int(coefficient.q) % prime
        if denominator == 0:
            raise ZeroDivisionError("a normal-generator denominator vanished modulo p")
        residue = int(coefficient.p) * pow(denominator, -1, prime) % prime
        terms.append((exponents, residue))
    return canonical_vector(terms, prime)


def vector_degree(vector: SparseVector) -> int:
    degrees = {sum(exponents) for exponents in vector}
    if len(degrees) != 1:
        raise AssertionError(f"nonhomogeneous degree set {degrees}")
    return next(iter(degrees))


def vector_character(vector: SparseVector) -> int:
    characters = {character_weight(exponents) for exponents in vector}
    if len(characters) != 1:
        raise AssertionError(f"nonhomogeneous character set {characters}")
    return next(iter(characters))


def scale(vector: SparseVector, scalar: int, prime: int) -> SparseVector:
    scalar %= prime
    return {
        exponents: coefficient * scalar % prime
        for exponents, coefficient in vector.items()
        if coefficient * scalar % prime
    }


def add_scaled_in_place(
    left: SparseVector, right: SparseVector, scalar: int, prime: int
) -> None:
    scalar %= prime
    for exponents, coefficient in right.items():
        value = (left.get(exponents, 0) + scalar * coefficient) % prime
        if value:
            left[exponents] = value
        else:
            left.pop(exponents, None)


def reduce_against_basis(
    vector: SparseVector,
    basis: dict[tuple[int, ...], SparseVector],
    prime: int,
) -> SparseVector:
    reduced = dict(vector)
    while reduced:
        pivot = max(reduced)
        row = basis.get(pivot)
        if row is None:
            break
        add_scaled_in_place(reduced, row, -reduced[pivot], prime)
    return reduced


def row_basis(vectors, prime: int) -> dict[tuple[int, ...], SparseVector]:
    basis: dict[tuple[int, ...], SparseVector] = {}
    for source in vectors:
        reduced = reduce_against_basis(source, basis, prime)
        if not reduced:
            continue
        pivot = max(reduced)
        reduced = scale(reduced, pow(reduced[pivot], -1, prime), prime)
        basis[pivot] = reduced
    return basis


def rank(vectors, prime: int) -> int:
    return len(row_basis(vectors, prime))


def in_span(vector: SparseVector, vectors, prime: int) -> bool:
    return not reduce_against_basis(vector, row_basis(vectors, prime), prime)


def multiply_by_variable(vector: SparseVector, variable_index: int) -> SparseVector:
    result = {}
    for exponents, coefficient in vector.items():
        product = list(exponents)
        product[variable_index] += 1
        result[tuple(product)] = coefficient
    return result


def derivative(vector: SparseVector, variable_index: int, prime: int) -> SparseVector:
    result = {}
    for exponents, coefficient in vector.items():
        exponent = exponents[variable_index]
        if exponent == 0:
            continue
        derived = list(exponents)
        derived[variable_index] -= 1
        result[tuple(derived)] = coefficient * exponent % prime
    return result


def support_profile(vector: SparseVector, variable_names: list[str]) -> dict[str, object]:
    variables = []
    for index, name in enumerate(variable_names):
        histogram = Counter(exponents[index] for exponents in vector)
        variables.append(
            {
                "name": name,
                "support_term_count": sum(
                    count for exponent, count in histogram.items() if exponent
                ),
                "maximum_exponent": max(histogram),
            }
        )
    return {
        "term_count": len(vector),
        "depends_on_every_variable": all(
            item["support_term_count"] > 0 for item in variables
        ),
        "variables": variables,
    }


def load_artifacts(campaign: Path) -> tuple[list[str], dict[str, dict[str, object]]]:
    paths = {
        "h": campaign / "artifacts/j2-secant-r10-first-colon-kernel-qq.json",
        "h2": campaign / "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json",
        "h3": campaign / "artifacts/j2-secant-r10-third-colon-kernel-qq-candidate.json",
    }
    payloads = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    expected_statuses = {
        "h": "PASS_QQ_CANDIDATE_RECONSTRUCTION_HELDOUT_REPLAY",
        "h2": "RATIONAL_CANDIDATE_RECONSTRUCTED_FROM_TWO_MODULAR_TAPS",
        "h3": "RATIONAL_THIRD_COLON_CANDIDATE_RECONSTRUCTED",
    }
    if any(payloads[name].get("status") != status for name, status in expected_statuses.items()):
        raise ValueError("a quartic artifact has an unexpected status")
    variable_names = list(payloads["h"]["variable_names"])
    if any(payload.get("variable_names") != variable_names for payload in payloads.values()):
        raise ValueError("quartic variable streams disagree")

    term_keys = {
        "h": ("h_rational_terms", "h_primitive_integer_terms"),
        "h2": ("terms", "primitive_integer_terms"),
        "h3": ("terms", "primitive_integer_terms"),
    }
    quartics: dict[str, dict[str, object]] = {}
    for name, payload in payloads.items():
        rational_key, primitive_key = term_keys[name]
        rational = {
            tuple(map(int, record["exponents"])): Fraction(
                int(record["numerator"]), int(record["denominator"])
            )
            for record in payload[rational_key]
        }
        primitive = {
            tuple(map(int, record["exponents"])): int(record["coefficient"])
            for record in payload[primitive_key]
        }
        if set(rational) != set(primitive) or len(rational) != len(payload[primitive_key]):
            raise ValueError(f"{name}: rational and primitive supports disagree")
        primitive_content = math.gcd(*(abs(coefficient) for coefficient in primitive.values()))
        if primitive_content != 1:
            raise ValueError(f"{name}: displayed primitive integer stream has content {primitive_content}")
        scales = {Fraction(primitive[exponents], 1) / coefficient for exponents, coefficient in rational.items()}
        if len(scales) != 1:
            raise ValueError(f"{name}: primitive and rational streams are not proportional")
        degree = {sum(exponents) for exponents in primitive}
        character = {character_weight(exponents) for exponents in primitive}
        if degree != {4} or len(character) != 1:
            raise ValueError(f"{name}: quartic grading changed")
        quartics[name] = {
            "path": paths[name],
            "payload": payload,
            "primitive": primitive,
            "rational_to_primitive_scale": next(iter(scales)),
            "primitive_integer_content": primitive_content,
            "character": next(iter(character)),
        }
    if [quartics[name]["character"] for name in ("h", "h2", "h3")] != [4, 3, 2]:
        raise ValueError("the frozen quartic character staircase changed")
    return variable_names, quartics


def first_order_transforms(
    source: SparseVector,
    target_character: int,
    variable_names: list[str],
    prime: int,
) -> tuple[list[SparseVector], list[dict[str, object]]]:
    transforms = []
    descriptors = []
    for derivative_index, derivative_name in enumerate(variable_names):
        partial = derivative(source, derivative_index, prime)
        if not partial:
            continue
        for multiplier_index, multiplier_name in enumerate(variable_names):
            transform = multiply_by_variable(partial, multiplier_index)
            if vector_character(transform) != target_character:
                continue
            transforms.append(transform)
            descriptors.append(
                {
                    "expression": f"{multiplier_name}*d/d{derivative_name}",
                    "term_count": len(transform),
                }
            )
    return transforms, descriptors


def flint_audit(
    prime: int,
    variable_names: list[str],
    quartics: dict[str, SparseVector],
    timeout: int,
) -> dict[str, object]:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for the pinned python-flint audit")
    payload = {
        "prime": prime,
        "variable_names": variable_names,
        "quartics": {
            name: [[list(exponents), coefficient] for exponents, coefficient in sorted(vector.items())]
            for name, vector in quartics.items()
        },
    }
    program = r'''
import json, sys, time
import flint
from flint import nmod_mpoly_ctx

data = json.load(sys.stdin)
context = nmod_mpoly_ctx.get(data["variable_names"], data["prime"], "degrevlex")

def polynomial(records):
    return context.from_dict({tuple(exponents): coefficient for exponents, coefficient in records})

def factor_record(poly):
    started = time.perf_counter()
    unit, factors = poly.factor()
    return {
        "unit": int(unit),
        "factor_count": len(factors),
        "factors": [
            {
                "total_degree": int(factor.total_degree()),
                "multiplicity": int(multiplicity),
                "term_count": len(list(factor.terms())),
            }
            for factor, multiplicity in factors
        ],
        "squarefree_from_factor_multiplicities": all(int(multiplicity) == 1 for _factor, multiplicity in factors),
        "wall_seconds": time.perf_counter() - started,
    }

polynomials = {name: polynomial(records) for name, records in data["quartics"].items()}
factors = {name: factor_record(poly) for name, poly in polynomials.items()}
gcds = {}
for left, right in (("h", "h2"), ("h", "h3"), ("h2", "h3")):
    started = time.perf_counter()
    common = polynomials[left].gcd(polynomials[right])
    gcds[f"{left},{right}"] = {
        "total_degree": int(common.total_degree()),
        "term_count": len(list(common.terms())),
        "is_unit": int(common.total_degree()) == 0,
        "wall_seconds": time.perf_counter() - started,
    }
print(json.dumps({
    "python_flint_version": flint.__version__,
    "flint_version": flint.__FLINT_VERSION__,
    "factors": factors,
    "pairwise_gcds": gcds,
}, sort_keys=True))
'''
    started = time.perf_counter()
    process = subprocess.run(
        [uv, "run", "--with", FLINT_REQUIREMENT, "python", "-c", program],
        input=json.dumps(payload, separators=(",", ":")),
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout,
    )
    if process.returncode != 0:
        raise RuntimeError(
            "FLINT audit failed: "
            f"return_code={process.returncode}, stderr={process.stderr[-2000:]}"
        )
    result = json.loads(process.stdout)
    result.update(
        {
            "requirement": FLINT_REQUIREMENT,
            "subprocess_wall_seconds": time.perf_counter() - started,
            "stderr": process.stderr,
        }
    )
    return result


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.size = [1] * size

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left = self.find(left)
        right = self.find(right)
        if left == right:
            return
        if self.size[left] < self.size[right]:
            left, right = right, left
        self.parent[right] = left
        self.size[left] += self.size[right]


def add_exponents(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(a + b for a, b in zip(left, right, strict=True))


def target_terms_for_h3(h3: dict[tuple[int, ...], int], variable_names: list[str]):
    index = {name: position for position, name in enumerate(variable_names)}
    f9 = index["f9"]
    f10 = index["f10"]
    g0 = index["g0"]
    open_terms = []
    first = [0] * len(variable_names)
    first[f9] = 3
    first[f10] = 1
    open_terms.append((tuple(first), 2))
    second = [0] * len(variable_names)
    second[f9] = 1
    second[f10] = 2
    second[g0] = 1
    open_terms.append((tuple(second), 5))
    target: dict[tuple[int, ...], int] = {}
    for h_exponents, h_coefficient in h3.items():
        for m_exponents, m_coefficient in open_terms:
            exponents = add_exponents(h_exponents, m_exponents)
            target[exponents] = target.get(exponents, 0) + h_coefficient * m_coefficient
            if target[exponents] == 0:
                del target[exponents]
    return target, dict(open_terms)


def identity_block_profile(
    generator_supports: list[list[tuple[int, ...]]],
    generator_degrees: list[int],
    generator_characters: list[int],
    h3: dict[tuple[int, ...], int],
    variable_names: list[str],
) -> dict[str, object]:
    target_character = 3
    target_degree = 8
    pools: dict[tuple[int, int], list[tuple[int, ...]]] = defaultdict(list)
    for degree in sorted({target_degree - degree for degree in generator_degrees}):
        for monomial in exact_exponent_tuples(len(variable_names), degree):
            pools[(degree, character_weight(monomial))].append(monomial)

    descriptors: list[tuple[int, tuple[int, ...]]] = []
    per_generator = []
    for generator_index, (degree, character) in enumerate(
        zip(generator_degrees, generator_characters, strict=True)
    ):
        multiplier_degree = target_degree - degree
        multiplier_character = (target_character - character) % CHARACTER_MODULUS
        pool = pools[(multiplier_degree, multiplier_character)]
        start = len(descriptors)
        descriptors.extend((generator_index, monomial) for monomial in pool)
        per_generator.append(
            {
                "generator_position": generator_index,
                "generator_degree": degree,
                "generator_character": character,
                "generator_term_count": len(generator_supports[generator_index]),
                "multiplier_degree": multiplier_degree,
                "multiplier_character": multiplier_character,
                "multiplier_coordinate_count": len(pool),
                "coordinate_start": start,
                "coordinate_stop": len(descriptors),
            }
        )

    target, open_terms = target_terms_for_h3(h3, variable_names)
    monomial_set = set(target)
    nonzero_count = 0
    for generator_index, multiplier in descriptors:
        support = generator_supports[generator_index]
        nonzero_count += len(support)
        monomial_set.update(add_exponents(exponents, multiplier) for exponents in support)
    monomials = sorted(monomial_set)
    monomial_index = {monomial: index for index, monomial in enumerate(monomials)}

    unknown_count = len(descriptors)
    equation_offset = unknown_count
    union = UnionFind(unknown_count + len(monomials))
    for unknown_index, (generator_index, multiplier) in enumerate(descriptors):
        for generator_exponents in generator_supports[generator_index]:
            equation_index = monomial_index[add_exponents(generator_exponents, multiplier)]
            union.union(unknown_index, equation_offset + equation_index)

    target_roots = {
        union.find(equation_offset + monomial_index[monomial]) for monomial in target
    }
    component_unknowns: Counter[int] = Counter()
    component_equations: Counter[int] = Counter()
    component_nonzeros: Counter[int] = Counter()
    component_target_terms: Counter[int] = Counter()
    for unknown_index in range(unknown_count):
        component_unknowns[union.find(unknown_index)] += 1
    for equation_index in range(len(monomials)):
        component_equations[union.find(equation_offset + equation_index)] += 1
    for unknown_index, (generator_index, multiplier) in enumerate(descriptors):
        component_nonzeros[union.find(unknown_index)] += len(generator_supports[generator_index])
    for monomial in target:
        component_target_terms[
            union.find(equation_offset + monomial_index[monomial])
        ] += 1

    roots = set(component_unknowns) | set(component_equations)
    components = sorted(
        (
            {
                "unknown_count": component_unknowns[root],
                "equation_count": component_equations[root],
                "nonzero_count": component_nonzeros[root],
                "target_term_count": component_target_terms[root],
                "target_bearing": root in target_roots,
            }
            for root in roots
        ),
        key=lambda item: (item["target_bearing"], item["unknown_count"] + item["equation_count"]),
        reverse=True,
    )
    active = [component for component in components if component["target_bearing"]]
    small_target_free_components = []
    for root in roots:
        if root in target_roots or component_unknowns[root] > 16 or component_equations[root] > 64:
            continue
        component_descriptors = []
        for unknown_index, (generator_index, multiplier) in enumerate(descriptors):
            if union.find(unknown_index) != root:
                continue
            component_descriptors.append(
                {
                    "unknown_index": unknown_index,
                    "generator_position": generator_index,
                    "multiplier_exponents": list(multiplier),
                }
            )
        component_monomials = [
            list(monomial)
            for equation_index, monomial in enumerate(monomials)
            if union.find(equation_offset + equation_index) == root
        ]
        small_target_free_components.append(
            {
                "unknown_count": component_unknowns[root],
                "equation_count": component_equations[root],
                "nonzero_count": component_nonzeros[root],
                "descriptors": component_descriptors,
                "equation_monomials": component_monomials,
                "forced_zero_reason": (
                    "zero right-hand side on this component and at least one nonzero "
                    "coefficient in every listed coordinate column"
                ),
            }
        )
    return {
        "target_degree": target_degree,
        "target_character": target_character,
        "target_primitive_term_count": len(target),
        "open_factor_terms": [
            {"exponents": list(exponents), "coefficient": coefficient}
            for exponents, coefficient in sorted(open_terms.items())
        ],
        "generator_count": len(generator_supports),
        "generator_degrees": generator_degrees,
        "generator_characters": generator_characters,
        "per_generator_coordinate_profile": per_generator,
        "multiplier_coordinate_count": unknown_count,
        "supported_monomial_equation_count": len(monomials),
        "matrix_nonzero_count": nonzero_count,
        "descriptor_stream_sha256": canonical_sha256(descriptors),
        "monomial_stream_sha256": canonical_sha256(monomials),
        "connected_component_count": len(components),
        "target_bearing_component_count": len(active),
        "active_multiplier_coordinate_count": sum(item["unknown_count"] for item in active),
        "active_equation_count": sum(item["equation_count"] for item in active),
        "active_nonzero_count": sum(item["nonzero_count"] for item in active),
        "inactive_multiplier_coordinate_count": unknown_count - sum(item["unknown_count"] for item in active),
        "inactive_equation_count": len(monomials) - sum(item["equation_count"] for item in active),
        "small_target_free_components": small_target_free_components,
        "components": components,
        "reduction_conclusion": (
            "discard target-free incidence components before elimination"
            if len(active) < len(components)
            else "the support incidence graph gives no component-level reduction"
        ),
    }


def modular_audit(
    prime: int,
    variables,
    equations,
    quartic_integer_terms: dict[str, dict[tuple[int, ...], int]],
    variable_names: list[str],
    monomial_counts: list[int],
    factor_timeout: int,
) -> dict[str, object]:
    generator_vectors = [sympy_terms_mod_p(equation, variables, prime) for equation in equations]
    generator_characters = [vector_character(vector) for vector in generator_vectors]
    quartics = {
        name: canonical_vector(terms.items(), prime)
        for name, terms in quartic_integer_terms.items()
    }
    if any(vector_degree(vector) != 4 for vector in quartics.values()):
        raise AssertionError("a quartic changed degree modulo the audit prime")
    if [vector_character(quartics[name]) for name in ("h", "h2", "h3")] != [4, 3, 2]:
        raise AssertionError("a quartic changed character modulo the audit prime")

    rows_by_character: dict[int, list[SparseVector]] = defaultdict(list)
    for generator, generator_character in zip(
        generator_vectors, generator_characters, strict=True
    ):
        for variable_index, variable_weight in enumerate(CHARACTER_WEIGHTS):
            character = (generator_character + variable_weight) % CHARACTER_MODULUS
            rows_by_character[character].append(multiply_by_variable(generator, variable_index))

    quotient_blocks = []
    for character in range(CHARACTER_MODULUS):
        rows = rows_by_character[character]
        base_rank = rank(rows, prime)
        matching = [
            name for name in ("h", "h2", "h3")
            if vector_character(quartics[name]) == character
        ]
        ranks = [base_rank]
        augmented = list(rows)
        for name in matching:
            augmented.append(quartics[name])
            ranks.append(rank(augmented, prime))
        quotient_blocks.append(
            {
                "character": character,
                "ambient_monomial_count": monomial_counts[character],
                "cubic_multiple_row_count": len(rows),
                "cubic_multiple_rank": base_rank,
                "degree_four_quotient_dimension": monomial_counts[character] - base_rank,
                "adjoined_quartics": matching,
                "successive_augmented_ranks": ranks,
                "all_matching_quartics_contribute_new_classes": all(
                    right == left + 1 for left, right in zip(ranks, ranks[1:])
                ),
            }
        )

    def orbit_record(source_name: str, target_name: str) -> dict[str, object]:
        target_character = vector_character(quartics[target_name])
        base = rows_by_character[target_character]
        transforms, descriptors = first_order_transforms(
            quartics[source_name], target_character, variable_names, prime
        )
        base_rank = rank(base, prime)
        orbit_rank = rank(base + transforms, prime)
        target_in_orbit = in_span(quartics[target_name], base + transforms, prime)
        single_hits = [
            descriptor["expression"]
            for descriptor, transform in zip(descriptors, transforms, strict=True)
            if in_span(quartics[target_name], base + [transform], prime)
        ]
        return {
            "source": source_name,
            "target": target_name,
            "source_character": vector_character(quartics[source_name]),
            "target_character": target_character,
            "character_shift": (
                target_character - vector_character(quartics[source_name])
            ) % CHARACTER_MODULUS,
            "family": "all character-compatible degree-preserving x_a*d/dx_b transforms",
            "transform_count": len(transforms),
            "base_cubic_rank": base_rank,
            "rank_with_transform_family": orbit_rank,
            "quotient_rank_contributed_by_transform_family": orbit_rank - base_rank,
            "target_in_joint_span_mod_cubic_degree_four_piece": target_in_orbit,
            "single_transform_hit_count": len(single_hits),
            "single_transform_hits": single_hits,
            "descriptor_stream_sha256": canonical_sha256(descriptors),
        }

    h_to_h2 = orbit_record("h", "h2")
    h2_to_h3 = orbit_record("h2", "h3")
    h_to_h3 = orbit_record("h", "h3")
    target_character = vector_character(quartics["h3"])
    base = rows_by_character[target_character]
    transforms_h2, _ = first_order_transforms(
        quartics["h2"], target_character, variable_names, prime
    )
    transforms_h, _ = first_order_transforms(
        quartics["h"], target_character, variable_names, prime
    )
    combined_rank = rank(base + transforms_h2 + transforms_h, prime)
    h3_in_combined = in_span(
        quartics["h3"], base + transforms_h2 + transforms_h, prime
    )

    factorization = flint_audit(
        prime, variable_names, quartics, factor_timeout
    )
    all_irreducible = all(
        len(factorization["factors"][name]["factors"]) == 1
        and factorization["factors"][name]["factors"][0]["total_degree"] == 4
        and factorization["factors"][name]["factors"][0]["multiplicity"] == 1
        for name in ("h", "h2", "h3")
    )
    pairwise_coprime = all(
        record["is_unit"] for record in factorization["pairwise_gcds"].values()
    )
    return {
        "characteristic": prime,
        "generator_characters": generator_characters,
        "quartic_profiles": {
            name: {
                "degree": vector_degree(vector),
                "character": vector_character(vector),
                "support": support_profile(vector, variable_names),
            }
            for name, vector in quartics.items()
        },
        "degree_four_character_blocks": quotient_blocks,
        "differential_orbit_tests": {
            "h_to_h2": h_to_h2,
            "h2_to_h3": h2_to_h3,
            "h_to_h3": h_to_h3,
            "combined_earlier_orbits_to_h3": {
                "rank_with_both_transform_families": combined_rank,
                "quotient_rank_contributed_by_both_families": combined_rank - rank(base, prime),
                "h3_in_joint_span_mod_cubic_degree_four_piece": h3_in_combined,
            },
        },
        "factorization_and_gcd": {
            **factorization,
            "all_three_irreducible_quartics": all_irreducible,
            "all_three_pairs_coprime": pairwise_coprime,
        },
        "simple_character_ladder_rejected": (
            not h_to_h2["target_in_joint_span_mod_cubic_degree_four_piece"]
            and not h2_to_h3["target_in_joint_span_mod_cubic_degree_four_piece"]
            and not h3_in_combined
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prime", type=int, action="append", dest="primes",
        help="audit prime; repeat for multiple primes (defaults to two discovery primes)",
    )
    parser.add_argument("--factor-timeout", type=int, default=120)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-third-colon-kernel-structure-two-prime.json"
        ),
    )
    arguments = parser.parse_args()
    primes = tuple(arguments.primes or DEFAULT_PRIMES)
    if len(set(primes)) != len(primes) or any(
        prime <= 5 or not sp.isprime(prime) for prime in primes
    ):
        parser.error("audit primes must be distinct primes greater than five")
    if not 1 <= arguments.factor_timeout <= 300:
        parser.error("--factor-timeout must lie between 1 and 300 seconds")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    variable_names, quartic_metadata = load_artifacts(campaign)
    equations, variables, _, open_factor = homogeneous_saturation_system()
    if list(map(str, variables)) != variable_names:
        raise ValueError("normal system and quartic variable streams disagree")
    if len(equations) != 17:
        raise ValueError("normal cubic stream changed")

    quartic_integer_terms = {
        name: metadata["primitive"] for name, metadata in quartic_metadata.items()
    }
    degree_four_monomials = list(exact_exponent_tuples(len(variables), 4))
    monomial_counts = [0] * CHARACTER_MODULUS
    for monomial in degree_four_monomials:
        monomial_counts[character_weight(monomial)] += 1
    if sum(monomial_counts) != 5_985:
        raise AssertionError("degree-four monomial count changed")

    normal_supports = [
        [tuple(map(int, exponents)) for exponents, _ in sp.Poly(equation, *variables, domain=sp.QQ).terms()]
        for equation in equations
    ]
    normal_characters = [
        next(iter({character_weight(exponents) for exponents in support}))
        for support in normal_supports
    ]
    generator_supports = normal_supports + [
        sorted(quartic_integer_terms["h"]),
        sorted(quartic_integer_terms["h2"]),
    ]
    generator_degrees = [3] * len(equations) + [4, 4]
    generator_characters = normal_characters + [4, 3]
    identity_profile = identity_block_profile(
        generator_supports,
        generator_degrees,
        generator_characters,
        quartic_integer_terms["h3"],
        variable_names,
    )

    modular = [
        modular_audit(
            prime,
            variables,
            equations,
            quartic_integer_terms,
            variable_names,
            monomial_counts,
            arguments.factor_timeout,
        )
        for prime in primes
    ]
    stable_block_profiles = all(
        [
            (
                block["ambient_monomial_count"],
                block["cubic_multiple_row_count"],
                block["cubic_multiple_rank"],
                block["degree_four_quotient_dimension"],
                block["successive_augmented_ranks"],
            )
            for block in audit["degree_four_character_blocks"]
        ]
        == [
            (
                block["ambient_monomial_count"],
                block["cubic_multiple_row_count"],
                block["cubic_multiple_rank"],
                block["degree_four_quotient_dimension"],
                block["successive_augmented_ranks"],
            )
            for block in modular[0]["degree_four_character_blocks"]
        ]
        for audit in modular[1:]
    )
    stable_differential_decisions = all(
        audit["simple_character_ladder_rejected"] == modular[0]["simple_character_ladder_rejected"]
        for audit in modular[1:]
    )
    passed = (
        stable_block_profiles
        and stable_differential_decisions
        and all(audit["simple_character_ladder_rejected"] for audit in modular)
        and all(
            audit["factorization_and_gcd"]["all_three_irreducible_quartics"]
            and audit["factorization_and_gcd"]["all_three_pairs_coprime"]
            for audit in modular
        )
        and all(
            all(
                block["all_matching_quartics_contribute_new_classes"]
                for block in audit["degree_four_character_blocks"]
            )
            for audit in modular
        )
    )
    qq_irreducibility_from_reduction = (
        all(metadata["primitive_integer_content"] == 1 for metadata in quartic_metadata.values())
        and all(
            audit["factorization_and_gcd"]["all_three_irreducible_quartics"]
            and all(
                profile["degree"] == 4
                for profile in audit["quartic_profiles"].values()
            )
            for audit in modular
        )
    )
    qq_pairwise_coprime = (
        qq_irreducibility_from_reduction
        and len({metadata["character"] for metadata in quartic_metadata.values()}) == 3
    )

    artifact_inputs = {
        name: {
            "path": str(metadata["path"].relative_to(campaign)),
            "sha256": sha256(metadata["path"]),
            "rational_to_primitive_scale": {
                "numerator": str(metadata["rational_to_primitive_scale"].numerator),
                "denominator": str(metadata["rational_to_primitive_scale"].denominator),
            },
            "primitive_integer_content": metadata["primitive_integer_content"],
            "character": metadata["character"],
            "term_count": len(metadata["primitive"]),
        }
        for name, metadata in quartic_metadata.items()
    }
    result = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-structure-audit.v1",
        "status": (
            "PASS_TWO_PRIME_THIRD_COLON_STRUCTURALLY_NEW"
            if passed
            else "THIRD_COLON_STRUCTURE_NOT_SEPARATED"
        ),
        "assurance": (
            "exact rational/integer stream consistency, exact combinatorics, and exact finite-field linear algebra/factorization"
        ),
        "variable_names": variable_names,
        "character_modulus": CHARACTER_MODULUS,
        "character_weights": list(CHARACTER_WEIGHTS),
        "quartic_character_sequence": [4, 3, 2],
        "quartic_artifacts": artifact_inputs,
        "degree_four_monomial_counts_by_character": monomial_counts,
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "open_factor_sha256": digest((open_factor,)),
        "identity_block_combinatorics": identity_profile,
        "modular_audits": modular,
        "cross_prime_checks": {
            "primes": list(primes),
            "degree_four_block_profiles_identical": stable_block_profiles,
            "differential_orbit_decisions_identical": stable_differential_decisions,
            "all_factor_and_gcd_decisions_pass": all(
                audit["factorization_and_gcd"]["all_three_irreducible_quartics"]
                and audit["factorization_and_gcd"]["all_three_pairs_coprime"]
                for audit in modular
            ),
        },
        "characteristic_zero_factor_consequences": {
            "all_displayed_integer_forms_primitive": all(
                metadata["primitive_integer_content"] == 1
                for metadata in quartic_metadata.values()
            ),
            "degree_four_preserved_at_every_audit_prime": all(
                all(profile["degree"] == 4 for profile in audit["quartic_profiles"].values())
                for audit in modular
            ),
            "irreducible_reduction_at_every_audit_prime": all(
                audit["factorization_and_gcd"]["all_three_irreducible_quartics"]
                for audit in modular
            ),
            "all_three_irreducible_over_QQ_by_gauss_lemma": qq_irreducibility_from_reduction,
            "pairwise_distinct_characters_preclude_associates": len(
                {metadata["character"] for metadata in quartic_metadata.values()}
            ) == 3,
            "all_three_pairwise_coprime_over_QQ": qq_pairwise_coprime,
            "argument": (
                "A nontrivial factorization of a primitive integer quartic over QQ "
                "lifts by Gauss's lemma to primitive positive-degree integer factors. "
                "At a prime where total degree is preserved, their nonzero reductions "
                "would factor the reduction, contradicting the exact irreducibility "
                "audit. Distinct Z/12 characters show the three irreducibles are not "
                "scalar associates, hence they are pairwise coprime over QQ."
            ),
        },
        "interpretation": {
            "proved_modularly": (
                "At both displayed primes h3 is a new irreducible degree-four character-two class, coprime to h and h2, and it is not generated modulo the cubic degree-four piece by any character-compatible first-order x_a*d/dx_b transforms of h or h2."
            ),
            "character_sequence": (
                "The characters 4,3,2 are exact, but the two-prime differential-orbit tests reject the simplest interpretation as a first-order linear derivation ladder. The decrement remains a colon-algorithm pattern, not an identified SL2 module structure."
            ),
            "identity_reduction": identity_profile["reduction_conclusion"],
            "proved_over_QQ": (
                "The three displayed primitive quartics are irreducible and pairwise "
                "coprime over QQ by the recorded degree-preserving irreducible "
                "reductions and Gauss's lemma."
                if qq_irreducibility_from_reduction and qq_pairwise_coprime
                else "No characteristic-zero factor conclusion passed."
            ),
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "A PASS proves the displayed exact finite-field rank, orbit, factorization, gcd, and support-incidence statements at the listed primes, plus exact stream/combinatorial identities. It does not prove M*h3 in (I,h,h2), reconstruct identity multipliers over QQ, compute a colon or saturation, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "primes": list(primes),
                "quartic_characters": [4, 3, 2],
                "degree_four_quotient_dimensions": [
                    block["degree_four_quotient_dimension"]
                    for block in modular[0]["degree_four_character_blocks"]
                ],
                "simple_character_ladder_rejected": [
                    audit["simple_character_ladder_rejected"] for audit in modular
                ],
                "identity_block": {
                    key: identity_profile[key]
                    for key in (
                        "multiplier_coordinate_count",
                        "supported_monomial_equation_count",
                        "matrix_nonzero_count",
                        "connected_component_count",
                        "target_bearing_component_count",
                        "active_multiplier_coordinate_count",
                        "active_equation_count",
                        "reduction_conclusion",
                    )
                },
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
