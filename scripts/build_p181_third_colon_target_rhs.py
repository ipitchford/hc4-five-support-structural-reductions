#!/usr/bin/env -S sage -python
"""Rebuild the canonical p181 right-hand side for ``M*h3``.

The promoted coefficient matrix uses a coefficient-only primitive scaling on
each rational Macaulay row.  This producer reconstructs those same rows from
the frozen rational generators, proves byte-for-byte agreement with the
promoted CSR, and applies the identical scale to the independently loaded
target polynomial.  It deliberately never opens an existing multiplier or
solution artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import resource
import struct
import sys
import time
from array import array
from fractions import Fraction
from pathlib import Path

import sympy as sp
from sage.env import SAGE_VERSION

import benchmark_p181_target_blind_linbox_rank as base
from certify_j2_secant_r10_colon_identity_liftstd import reconstruct_quartic
from certify_j2_secant_r10_second_colon_identity_sparse_macaulay import (
    load_second_quartic,
)
from certify_j2_secant_r10_third_colon_identity_sparse_macaulay import (
    THIRD_CANDIDATE,
    load_third_quartic,
)
from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    character_weight,
    exact_exponent_tuples,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)


CAMPAIGN = Path(__file__).resolve().parents[1]
P = 181
CSR = CAMPAIGN / (
    "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/"
    "A_C_mod181_target_free.csr"
)
CSR_SHA256 = "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef"
GAUGE = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
GAUGE_SHA256 = "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2"
THIRD_CANDIDATE_SHA256 = "b7f37502a3b4a11739fe4e1e47746af68b2a8cc66cb18302bfe729927ed65b97"
TARGET_SHA256 = "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"
EXPECTED_RESIDUE_STREAM_SHA256 = (
    "4dde704c2d23c42a20e0468ec9e141c0d5cbec062957c9295f594ab000ce3051"
)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def rational_residue(value: Fraction) -> int:
    require(value.denominator % P != 0, "target row denominator is not a p181 unit")
    return (value.numerator % P) * pow(value.denominator % P, -1, P) % P


def build() -> dict[str, object]:
    started = time.perf_counter()
    require(file_hash(CSR) == CSR_SHA256, "promoted CSR drift")
    require(file_hash(GAUGE) == GAUGE_SHA256, "promoted pivot gauge drift")
    require(
        file_hash(CAMPAIGN / THIRD_CANDIDATE) == THIRD_CANDIDATE_SHA256,
        "third candidate drift",
    )
    pivots = base.read_pivots(GAUGE)
    global_to_local = {global_column: local for local, global_column in enumerate(pivots)}

    equations, variables, _leading_form, open_factor = homogeneous_saturation_system()
    first, first_metadata = reconstruct_quartic(CAMPAIGN, variables)
    second, second_metadata = load_second_quartic(CAMPAIGN, variables)
    third, third_metadata = load_third_quartic(CAMPAIGN, variables)
    generators = list(equations) + [first, second]
    generator_degrees = [3] * len(equations) + [4, 4]
    multiplier_degrees = [8 - degree for degree in generator_degrees]

    polynomial_terms: list[list[tuple[tuple[int, ...], tuple[int, int]]]] = []
    generator_weights: list[int] = []
    for generator, expected_degree in zip(generators, generator_degrees, strict=True):
        polynomial = sp.Poly(generator, *variables, domain=sp.QQ)
        terms = [
            (tuple(map(int, exponents)), base.rational_pair(coefficient))
            for exponents, coefficient in polynomial.terms()
        ]
        require(
            {sum(exponents) for exponents, _pair in terms} == {expected_degree},
            "generator degree drift",
        )
        weights = {character_weight(exponents) for exponents, _pair in terms}
        require(len(weights) == 1, "generator character drift")
        polynomial_terms.append(terms)
        generator_weights.append(next(iter(weights)))
    require(len(generators) == 19 and generator_weights[-2:] == [4, 3], "generator family drift")

    target_expression = sp.expand(open_factor * third)
    target_polynomial = sp.Poly(target_expression, *variables, domain=sp.QQ)
    require(target_polynomial.total_degree() == 8, "target degree drift")
    target_terms = {
        tuple(map(int, exponents)): base.rational_pair(coefficient)
        for exponents, coefficient in target_polynomial.terms()
    }
    require(len(target_terms) == 486, "target support drift")
    require({character_weight(item) for item in target_terms} == {3}, "target character drift")
    require(digest((target_expression,)) == TARGET_SHA256, "target expression hash drift")

    pools: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for degree in sorted(set(multiplier_degrees)):
        for monomial in exact_exponent_tuples(len(variables), degree):
            pools.setdefault((degree, character_weight(monomial)), []).append(monomial)

    equation_by_monomial: dict[tuple[int, ...], dict[int, tuple[int, int]]] = {}
    descriptors: list[tuple[int, tuple[int, ...]]] = []
    collision_additions = 0
    for generator_index, (terms, generator_weight, multiplier_degree) in enumerate(
        zip(polynomial_terms, generator_weights, multiplier_degrees, strict=True)
    ):
        multiplier_weight = (3 - generator_weight) % CHARACTER_MODULUS
        for multiplier in pools.get((multiplier_degree, multiplier_weight), []):
            column = len(descriptors)
            descriptors.append((generator_index, multiplier))
            for exponents, pair in terms:
                product = tuple(
                    left + right for left, right in zip(exponents, multiplier, strict=True)
                )
                row = equation_by_monomial.setdefault(product, {})
                if column in row:
                    collision_additions += 1
                    combined = base.add_pairs(row[column], pair)
                    if combined[0]:
                        row[column] = combined
                    else:
                        del row[column]
                else:
                    row[column] = pair

    require(not any(not row for row in equation_by_monomial.values()), "empty coefficient row retained")
    monomials = sorted(equation_by_monomial)
    rows = [equation_by_monomial[monomial] for monomial in monomials]
    require(set(target_terms).issubset(equation_by_monomial), "target leaves coefficient row domain")
    require(base.canonical_hash(descriptors) == base.EXPECTED["descriptor_sha256"], "descriptor hash drift")
    require(base.canonical_hash(monomials) == base.EXPECTED["monomial_sha256"], "monomial hash drift")
    require(digest(tuple(generators)) == base.EXPECTED["generator_sha256"], "generator hash drift")
    require(len(rows) == 85_651 and len(descriptors) == 38_048, "block dimensions drift")
    require(sum(map(len, rows)) == 1_473_071, "global coefficient support drift")

    offsets = array("Q", [0])
    selected_columns = array("I")
    selected_values = array("B")
    rhs = bytearray()
    row_scales = bytearray()
    exact_nonzero_rows: list[dict[str, object]] = []
    nonunit_coefficient_scales = 0
    target_denominator_nonunits = 0
    target_support_losses = 0
    for row_index, (monomial, row) in enumerate(zip(monomials, rows, strict=True)):
        denominator_lcm = math.lcm(*(pair[1] for pair in row.values()))
        integer_entries = [
            (column, pair[0] * (denominator_lcm // pair[1]))
            for column, pair in sorted(row.items())
        ]
        content = math.gcd(*(abs(value) for _column, value in integer_entries if value))
        sign = -1 if integer_entries[0][1] < 0 else 1
        if denominator_lcm % P == 0 or content % P == 0:
            nonunit_coefficient_scales += 1
        scale = Fraction(sign * denominator_lcm, content)
        row_scale = rational_residue(scale)
        row_scales.append(row_scale)

        selected: list[tuple[int, int]] = []
        for global_column, value in integer_entries:
            primitive = sign * (value // content)
            local = global_to_local.get(global_column)
            if local is not None:
                residue = primitive % P
                require(residue != 0, "selected coefficient vanished modulo 181")
                selected.append((local, residue))
        require(selected, "selected coefficient row is empty")
        for local, residue in sorted(selected):
            selected_columns.append(local)
            selected_values.append(residue)
        offsets.append(len(selected_columns))

        target_pair = target_terms.get(monomial, (0, 1))
        scaled_target = scale * Fraction(target_pair[0], target_pair[1])
        if scaled_target.denominator % P == 0:
            target_denominator_nonunits += 1
        target_residue = rational_residue(scaled_target)
        rhs.append(target_residue)
        if target_pair[0]:
            if target_residue == 0:
                target_support_losses += 1
            exact_nonzero_rows.append(
                {
                    "row": row_index,
                    "monomial": list(monomial),
                    "raw_target_numerator": target_pair[0],
                    "raw_target_denominator": target_pair[1],
                    "coefficient_scale_numerator": scale.numerator,
                    "coefficient_scale_denominator": scale.denominator,
                    "scaled_target_numerator": scaled_target.numerator,
                    "scaled_target_denominator": scaled_target.denominator,
                    "residue_mod181": target_residue,
                }
            )

    require(nonunit_coefficient_scales == 0, "coefficient scaling lost a p181 unit")
    require(target_denominator_nonunits == 0, "target scaling denominator lost a p181 unit")
    require(target_support_losses == 0, "target support vanished modulo 181")
    require(len(selected_columns) == 1_354_540, "selected support drift")
    require(len(exact_nonzero_rows) == 486, "nonzero target row count drift")
    csr_payload = bytearray(b"HC4AC181")
    csr_payload.extend(struct.pack("<QQQ", 85_651, 35_881, len(selected_columns)))
    csr_payload.extend(offsets.tobytes())
    csr_payload.extend(selected_columns.tobytes())
    csr_payload.extend(selected_values.tobytes())
    require(hashlib.sha256(selected_values.tobytes()).hexdigest() == EXPECTED_RESIDUE_STREAM_SHA256, "coefficient residue stream drift")
    require(hashlib.sha256(csr_payload).hexdigest() == CSR_SHA256, "reconstructed CSR differs from promoted CSR")
    return {
        "rhs": bytes(rhs),
        "row_scales": bytes(row_scales),
        "exact_nonzero_rows": exact_nonzero_rows,
        "metadata": {
            "rows": 85_651,
            "columns": 35_881,
            "selected_nonzeros": 1_354_540,
            "target_terms": 486,
            "target_nonzero_residues": sum(value != 0 for value in rhs),
            "row_scale_nonzero_residues": sum(value != 0 for value in row_scales),
            "collision_additions": collision_additions,
            "descriptor_sha256": base.canonical_hash(descriptors),
            "monomial_sha256": base.canonical_hash(monomials),
            "generator_sha256": digest(tuple(generators)),
            "target_sha256": digest((target_expression,)),
            "reconstructed_csr_sha256": hashlib.sha256(csr_payload).hexdigest(),
            "rhs_mod181_sha256": hashlib.sha256(rhs).hexdigest(),
            "row_scales_mod181_sha256": hashlib.sha256(row_scales).hexdigest(),
            "third_candidate": third_metadata,
            "first_quartic": first_metadata,
            "second_quartic": second_metadata,
            "build_seconds": time.perf_counter() - started,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output_dir if arguments.output_dir.is_absolute() else CAMPAIGN / arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    result = build()
    rhs_path = output / "target_rhs_mod181.u8"
    scales_path = output / "coefficient_row_scales_mod181.u8"
    exact_path = output / "target_rhs_nonzero_rational.json"
    rhs_path.write_bytes(result["rhs"])
    scales_path.write_bytes(result["row_scales"])
    exact_path.write_text(
        json.dumps(result["exact_nonzero_rows"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-explicit-target-rhs.v1",
        "status": "PASS_SOURCE_CLEAN_P181_EXPLICIT_TARGET_RHS_RECONSTRUCTION",
        "characteristic": P,
        "construction": result["metadata"],
        "outputs": {
            path.name: {"sha256": file_hash(path), "bytes": path.stat().st_size}
            for path in (rhs_path, scales_path, exact_path)
        },
        "bound_inputs": {
            str(CSR.relative_to(CAMPAIGN)): CSR_SHA256,
            str(GAUGE.relative_to(CAMPAIGN)): GAUGE_SHA256,
            str(THIRD_CANDIDATE): THIRD_CANDIDATE_SHA256,
        },
        "source": {
            "path": str(Path(__file__).resolve().relative_to(CAMPAIGN)),
            "sha256": file_hash(Path(__file__).resolve()),
            "python": sys.version,
            "sage": SAGE_VERSION,
        },
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        },
        "declarations": {
            "existing_multiplier_or_solution_not_read": True,
            "quarantined_dixon_rhs_not_read": True,
            "promoted_csr_reconstructed_byte_for_byte": True,
            "coefficient_only_row_scaling_used": True,
            "no_elimination_or_solve": True,
            "no_mod181_squared": True,
        },
        "claim_boundary": (
            "This PASS constructs and source-binds only the explicit M*h3 right-hand side over GF(181). "
            "It does not prove target membership, a QQ identity, a p-adic digit, colon or saturation, "
            "secant closure, nullcone containment, or HC4."
        ),
    }
    receipt_path = output / "target-rhs.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with receipt_path.open("rb") as handle:
        os.fsync(handle.fileno())
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": file_hash(receipt_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
