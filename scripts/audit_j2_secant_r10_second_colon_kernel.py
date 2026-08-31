#!/usr/bin/env python3
"""Audit the second tapped quartic in the residual secant-colon scout.

This script deliberately proves only finite-field structural statements about
the polynomial emitted by the instrumented saturation run.  It does *not*
promote the tap to a colon-membership certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
)
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


EXPECTED_PRIME = 1_073_741_827
FLINT_REQUIREMENT = "python-flint==0.9.0"


SparseVector = dict[tuple[int, ...], int]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_vector(terms, prime: int) -> SparseVector:
    result: SparseVector = {}
    for exponents, coefficient in terms:
        exponent_tuple = tuple(map(int, exponents))
        value = int(coefficient) % prime
        if value:
            result[exponent_tuple] = (result.get(exponent_tuple, 0) + value) % prime
            if result[exponent_tuple] == 0:
                del result[exponent_tuple]
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


def scale(vector: SparseVector, scalar: int, prime: int) -> SparseVector:
    scalar %= prime
    return {
        exponents: coefficient * scalar % prime
        for exponents, coefficient in vector.items()
        if coefficient * scalar % prime
    }


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


def add_scaled_in_place(
    left: SparseVector,
    right: SparseVector,
    scalar: int,
    prime: int,
) -> None:
    scalar %= prime
    for exponents, coefficient in right.items():
        value = (left.get(exponents, 0) + scalar * coefficient) % prime
        if value:
            left[exponents] = value
        else:
            left.pop(exponents, None)


def reduce_against_basis(vector: SparseVector, basis: dict[tuple[int, ...], SparseVector], prime: int):
    reduced = dict(vector)
    while reduced:
        pivot = max(reduced)
        row = basis.get(pivot)
        if row is None:
            break
        add_scaled_in_place(reduced, row, -reduced[pivot], prime)
    return reduced


def row_basis(vectors: list[SparseVector], prime: int):
    """Return a deterministic reduced-enough sparse echelon basis."""

    basis: dict[tuple[int, ...], SparseVector] = {}
    for source in vectors:
        reduced = reduce_against_basis(source, basis, prime)
        if not reduced:
            continue
        pivot = max(reduced)
        reduced = scale(reduced, pow(reduced[pivot], -1, prime), prime)
        basis[pivot] = reduced
    return basis


def rank(vectors: list[SparseVector], prime: int) -> int:
    return len(row_basis(vectors, prime))


def is_in_span(vector: SparseVector, vectors: list[SparseVector], prime: int) -> bool:
    return not reduce_against_basis(vector, row_basis(vectors, prime), prime)


def vector_character(vector: SparseVector) -> int:
    characters = {character_weight(exponents) for exponents in vector}
    if len(characters) != 1:
        raise AssertionError(f"nonhomogeneous character set {characters}")
    return next(iter(characters))


def vector_degree(vector: SparseVector) -> int:
    degrees = {sum(exponents) for exponents in vector}
    if len(degrees) != 1:
        raise AssertionError(f"nonhomogeneous degree set {degrees}")
    return next(iter(degrees))


def support_profile(vector: SparseVector, variable_names: list[str]) -> dict:
    variables = []
    for index, name in enumerate(variable_names):
        histogram = Counter(exponents[index] for exponents in vector)
        positive = sum(count for exponent, count in histogram.items() if exponent > 0)
        variables.append(
            {
                "name": name,
                "support_term_count": positive,
                "maximum_exponent": max(histogram),
                "exponent_histogram": {
                    str(exponent): histogram.get(exponent, 0)
                    for exponent in range(max(histogram) + 1)
                },
            }
        )
    return {
        "term_count": len(vector),
        "depends_on_every_variable": all(
            item["support_term_count"] > 0 for item in variables
        ),
        "variables": variables,
    }


def flint_factor_audit(
    prime: int,
    variable_names: list[str],
    q: SparseVector,
    h: SparseVector,
    timeout: int,
) -> dict:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for the pinned python-flint factor audit")
    payload = {
        "prime": prime,
        "variable_names": variable_names,
        "q": [[list(exponents), coefficient] for exponents, coefficient in sorted(q.items())],
        "h": [[list(exponents), coefficient] for exponents, coefficient in sorted(h.items())],
    }
    program = r'''
import json, sys, time
import flint
from flint import nmod_mpoly_ctx

data = json.load(sys.stdin)
context = nmod_mpoly_ctx.get(
    data["variable_names"], data["prime"], "degrevlex"
)

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
        "wall_seconds": time.perf_counter() - started,
    }

q = polynomial(data["q"])
h = polynomial(data["h"])
gcd_started = time.perf_counter()
common = q.gcd(h)
result = {
    "python_flint_version": flint.__version__,
    "flint_version": flint.__FLINT_VERSION__,
    "q": factor_record(q),
    "h": factor_record(h),
    "gcd": {
        "total_degree": int(common.total_degree()),
        "term_count": len(list(common.terms())),
        "is_unit": int(common.total_degree()) == 0,
        "wall_seconds": time.perf_counter() - gcd_started,
    },
}
print(json.dumps(result, sort_keys=True))
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
            "FLINT factor audit failed: "
            f"return_code={process.returncode}, stderr={process.stderr[-2000:]}"
        )
    record = json.loads(process.stdout)
    record["subprocess_wall_seconds"] = time.perf_counter() - started
    record["requirement"] = FLINT_REQUIREMENT
    record["stderr"] = process.stderr
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--residual-receipt",
        type=Path,
        default=Path("receipts/hsop-j2-secant-r10-residual-colon-p1073741827.json"),
    )
    parser.add_argument(
        "--first-quartic",
        type=Path,
        default=Path("artifacts/j2-secant-r10-first-colon-kernel-qq.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-secant-r10-second-colon-kernel-structure-p1073741827.json"),
    )
    parser.add_argument("--factor-timeout", type=int, default=30)
    arguments = parser.parse_args()
    if arguments.factor_timeout < 1 or arguments.factor_timeout > 120:
        parser.error("--factor-timeout must lie between 1 and 120 seconds")

    started = time.perf_counter()
    campaign = Path(__file__).resolve().parent.parent
    residual_path = arguments.residual_receipt
    first_path = arguments.first_quartic
    output_path = arguments.output
    if not residual_path.is_absolute():
        residual_path = campaign / residual_path
    if not first_path.is_absolute():
        first_path = campaign / first_path
    if not output_path.is_absolute():
        output_path = campaign / output_path

    residual = json.loads(residual_path.read_text(encoding="utf-8"))
    first = json.loads(first_path.read_text(encoding="utf-8"))
    prime = int(residual["characteristic"])
    if prime != EXPECTED_PRIME or not sp.isprime(prime):
        raise ValueError("the residual receipt has the wrong characteristic")
    if residual["status"] != "CANDIDATE_MODULAR_RESIDUAL_COLON_KERNEL_EXTRACTED":
        raise ValueError("the residual receipt does not have the expected discovery status")
    if first["status"] != "PASS_QQ_CANDIDATE_RECONSTRUCTION_HELDOUT_REPLAY":
        raise ValueError("the first quartic artifact does not have the expected status")

    variable_names = list(residual["variable_names"])
    if variable_names != list(first["variable_names"]):
        raise ValueError("variable orders disagree")
    tapped = residual["calculation"]["kernel_polynomials"]
    if len(tapped) != 1:
        raise ValueError("expected exactly one bounded tapped polynomial")
    q_record = tapped[0]
    q = canonical_vector(
        ((term["exponents"], term["coefficient"]) for term in q_record["terms"]),
        prime,
    )
    h = canonical_vector(
        (
            (term["exponents"], int(term["coefficient"]))
            for term in first["h_primitive_integer_terms"]
        ),
        prime,
    )
    if len(q) != 211 or vector_degree(q) != 4 or vector_character(q) != 3:
        raise AssertionError("the second tapped quartic failed its frozen invariants")
    if len(h) != 189 or vector_degree(h) != 4 or vector_character(h) != 4:
        raise AssertionError("the first quartic failed its frozen invariants")

    equations, variables, _, _ = homogeneous_saturation_system()
    if [str(variable) for variable in variables] != variable_names:
        raise AssertionError("system and receipt variable orders disagree")
    generator_vectors = [
        sympy_terms_mod_p(equation, variables, prime) for equation in equations
    ]
    generator_characters = [vector_character(vector) for vector in generator_vectors]
    if any(vector_degree(vector) != 3 for vector in generator_vectors):
        raise AssertionError("a normal generator is not cubic")

    target_character = vector_character(q)
    i4_rows = []
    i4_descriptors = []
    for generator_index, (generator, generator_character) in enumerate(
        zip(generator_vectors, generator_characters, strict=True)
    ):
        for variable_index, variable_weight in enumerate(CHARACTER_WEIGHTS):
            if (generator_character + variable_weight) % CHARACTER_MODULUS != target_character:
                continue
            row = multiply_by_variable(generator, variable_index)
            if vector_character(row) != target_character or vector_degree(row) != 4:
                raise AssertionError("a Macaulay row left the target block")
            i4_rows.append(row)
            i4_descriptors.append(
                {
                    "generator_position": generator_index,
                    "multiplier_variable": variable_names[variable_index],
                }
            )

    i4_rank = rank(i4_rows, prime)
    q_in_i4 = is_in_span(q, i4_rows, prime)
    # h has a different character, so adjoining it cannot alter the character-3
    # piece.  We nevertheless record the direct augmented-rank check.
    i4_h_rank = rank(i4_rows + [h], prime)
    i4_h_q_rank = rank(i4_rows + [h, q], prime)

    differential_rows = []
    differential_descriptors = []
    for derivative_index, derivative_name in enumerate(variable_names):
        partial = derivative(h, derivative_index, prime)
        if not partial:
            continue
        for multiplier_index, multiplier_name in enumerate(variable_names):
            transform = multiply_by_variable(partial, multiplier_index)
            if vector_character(transform) != target_character:
                continue
            if vector_degree(transform) != 4:
                raise AssertionError("a first-order transform has the wrong degree")
            differential_rows.append(transform)
            differential_descriptors.append(
                {
                    "expression": f"{multiplier_name}*d/d{derivative_name}(h)",
                    "multiplier_position": multiplier_index,
                    "derivative_position": derivative_index,
                    "term_count": len(transform),
                }
            )

    first_order_rank = rank(i4_rows + differential_rows, prime)
    q_in_first_order_span = is_in_span(q, i4_rows + differential_rows, prime)
    single_transform_hits = []
    for descriptor, transform in zip(
        differential_descriptors, differential_rows, strict=True
    ):
        if is_in_span(q, i4_rows + [transform], prime):
            single_transform_hits.append(descriptor["expression"])

    factor_audit = flint_factor_audit(
        prime,
        variable_names,
        q,
        h,
        arguments.factor_timeout,
    )
    q_factors = factor_audit["q"]["factors"]
    h_factors = factor_audit["h"]["factors"]
    q_irreducible = (
        len(q_factors) == 1
        and q_factors[0]["total_degree"] == 4
        and q_factors[0]["multiplicity"] == 1
    )
    h_irreducible = (
        len(h_factors) == 1
        and h_factors[0]["total_degree"] == 4
        and h_factors[0]["multiplicity"] == 1
    )

    support_intersection = set(q).intersection(h)
    structurally_new = (
        not q_in_i4
        and i4_h_q_rank == i4_h_rank + 1
        and not q_in_first_order_span
        and q_irreducible
    )
    script_path = Path(__file__).resolve()
    result = {
        "schema": "hc4.decimic-j2-secant-r10-second-kernel-structure.v1",
        "status": (
            "PASS_MODULAR_SECOND_KERNEL_STRUCTURALLY_NEW"
            if structurally_new
            else "SECOND_KERNEL_STRUCTURE_NOT_SEPARATED"
        ),
        "assurance": "exact finite-field structure audit only",
        "characteristic": prime,
        "variable_names": variable_names,
        "character_modulus": CHARACTER_MODULUS,
        "character_weights": list(CHARACTER_WEIGHTS),
        "second_quartic": {
            "total_degree": vector_degree(q),
            "character_weight": vector_character(q),
            "support_profile": support_profile(q, variable_names),
            "term_stream_sha256": hashlib.sha256(
                json.dumps(
                    q_record["terms"], separators=(",", ":"), sort_keys=True
                ).encode("ascii")
            ).hexdigest(),
        },
        "first_quartic_mod_p": {
            "total_degree": vector_degree(h),
            "character_weight": vector_character(h),
            "support_profile": support_profile(h, variable_names),
        },
        "support_comparison": {
            "intersection_term_count": len(support_intersection),
            "disjoint_forced_by_distinct_character": len(support_intersection) == 0,
        },
        "degree_four_quotient_test": {
            "notation": "I1_4 is the degree-four piece generated by variable multiples of the 17 normal cubics",
            "row_count": len(i4_rows),
            "row_rank": i4_rank,
            "row_descriptors": i4_descriptors,
            "q_in_I1_4": q_in_i4,
            "rank_I1_4_plus_h": i4_h_rank,
            "rank_I1_4_plus_h_plus_q": i4_h_q_rank,
            "q_in_I1_4_plus_span_h": i4_h_q_rank == i4_h_rank,
            "new_quotient_dimension_contributed_by_q": i4_h_q_rank - i4_h_rank,
        },
        "first_order_multiplication_derivative_test": {
            "family": "all character-3 degree-preserving transforms x_a*d/dx_b(h)",
            "transform_count": len(differential_rows),
            "transform_descriptors": differential_descriptors,
            "rank_I1_4_plus_transforms": first_order_rank,
            "quotient_rank_contributed_by_transforms": first_order_rank - i4_rank,
            "q_in_joint_span": q_in_first_order_span,
            "single_transform_hit_count": len(single_transform_hits),
            "single_transform_hits": single_transform_hits,
        },
        "exact_factor_audit": {
            **factor_audit,
            "q_irreducible_over_prime_field": q_irreducible,
            "h_irreducible_over_prime_field": h_irreducible,
        },
        "input_sha256": {
            str(residual_path.relative_to(campaign)): sha256(residual_path),
            str(first_path.relative_to(campaign)): sha256(first_path),
        },
        "source_sha256": {
            str(script_path.relative_to(campaign)): sha256(script_path),
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "This proves at p=1073741827 that the 211-term character-3 quartic is "
            "irreducible and contributes a new class modulo I1_4, the first quartic, "
            "and every character-compatible first-order transform x_a*d/dx_b(h). "
            "It does not prove that the tapped polynomial lies in the residual colon, "
            "does not reconstruct it over QQ, and does not close the saturation chart."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "characteristic": prime,
                "q_term_count": len(q),
                "i4_rank": i4_rank,
                "q_in_i4": q_in_i4,
                "first_order_transform_count": len(differential_rows),
                "first_order_quotient_rank": first_order_rank - i4_rank,
                "q_in_first_order_span": q_in_first_order_span,
                "q_irreducible": q_irreducible,
                "h_irreducible": h_irreducible,
                "wall_seconds": result["wall_seconds"],
                "output": str(output_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if structurally_new else 2


if __name__ == "__main__":
    raise SystemExit(main())
