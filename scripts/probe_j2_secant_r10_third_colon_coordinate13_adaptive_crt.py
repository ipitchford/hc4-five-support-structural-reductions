#!/usr/bin/env python3
"""Adaptive source/selector CRT probe for one fixed-gauge coordinate.

For source residue r modulo M, enumerate every reduced n/d satisfying

    n = r*d (mod M),  d > 0, gcd(d, M) = 1,  2*abs(n)*d < M.

Legendre's theorem implies that every such n/d comes from a convergent of
r/M, so the extended-Euclidean enumeration below is complete in this region.
Selectors do not enlarge M; they only record and filter predicted residues.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import sympy as sp


DEFAULT_COORDINATE = 13


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode(
        "ascii"
    )
    return hashlib.sha256(payload).hexdigest()


def crt_pair(value: int, modulus: int, residue: int, prime: int) -> tuple[int, int]:
    if math.gcd(modulus, prime) != 1:
        raise ValueError("CRT characteristics are not pairwise coprime")
    correction = (residue - value) % prime
    correction = correction * pow(modulus % prime, -1, prime) % prime
    combined_modulus = modulus * prime
    return (value + modulus * correction) % combined_modulus, combined_modulus


def complete_strict_product_candidates(
    residue: int, modulus: int
) -> tuple[list[tuple[int, int]], int]:
    residue %= modulus
    if residue == 0:
        return [(0, 1)], 0
    old_remainder, remainder = modulus, residue
    old_coefficient, coefficient = 0, 1
    candidates: set[tuple[int, int]] = set()
    steps = 0
    while remainder:
        steps += 1
        numerator, denominator = remainder, coefficient
        if denominator < 0:
            numerator, denominator = -numerator, -denominator
        common = math.gcd(abs(numerator), denominator)
        numerator //= common
        denominator //= common
        if (
            denominator > 0
            and math.gcd(denominator, modulus) == 1
            and 2 * abs(numerator) * denominator < modulus
            and (numerator - residue * denominator) % modulus == 0
        ):
            candidates.add((numerator, denominator))
        quotient = old_remainder // remainder
        old_remainder, remainder = (
            remainder,
            old_remainder - quotient * remainder,
        )
        old_coefficient, coefficient = (
            coefficient,
            old_coefficient - quotient * coefficient,
        )
    return sorted(candidates), steps


def load_artifact(path: Path, coordinate: int) -> dict[str, object]:
    path = path.resolve()
    payload = json.loads(path.read_text(encoding="ascii"))
    prime = int(payload["characteristic"])
    if prime <= 5 or not sp.isprime(prime):
        raise ValueError(f"inadmissible characteristic: {path}")
    vector = list(map(int, payload["coordinate_vector"]))
    if not 0 <= coordinate < len(vector):
        raise ValueError(f"coordinate outside vector: {path}")
    if payload.get("coordinate_vector_sha256") != canonical_hash(vector):
        raise ValueError(f"coordinate-vector hash mismatch: {path}")
    pivots = list(map(int, payload["pivot_unknown_indices"]))
    free = list(map(int, payload["free_unknown_indices"]))
    if payload.get("pivot_unknown_indices_sha256") != canonical_hash(pivots):
        raise ValueError(f"ordered pivot hash mismatch: {path}")
    if payload.get("free_unknown_indices_sha256") != canonical_hash(free):
        raise ValueError(f"free-coordinate hash mismatch: {path}")
    if (
        len(set(pivots)) != len(pivots)
        or free != sorted(set(free))
        or set(pivots) & set(free)
        or set(pivots) | set(free) != set(range(len(vector)))
    ):
        raise ValueError(f"invalid pivot/free partition: {path}")
    signature_keys = (
        "schema",
        "row_descriptor_sha256",
        "monomial_stream_sha256",
        "generator_stream_sha256",
        "target_sha256",
        "free_unknown_indices_sha256",
        "target_character_weight",
    )
    return {
        "path": path,
        "sha256": file_sha256(path),
        "characteristic": prime,
        "coordinate_residue": vector[coordinate] % prime,
        "coordinate_vector_length": len(vector),
        "signature": {
            **{key: payload.get(key) for key in signature_keys},
            "pivot_unknown_set_sha256": canonical_hash(sorted(pivots)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--selector", type=Path, action="append", default=[])
    parser.add_argument("--coordinate", type=int, default=DEFAULT_COORDINATE)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    source = [load_artifact(path, arguments.coordinate) for path in arguments.source]
    selectors = [
        load_artifact(path, arguments.coordinate) for path in arguments.selector
    ]
    all_inputs = source + selectors
    primes = [int(item["characteristic"]) for item in all_inputs]
    if len(set(primes)) != len(primes):
        raise ValueError("source and selector characteristics must be distinct")
    signatures = {canonical_hash(item["signature"]) for item in all_inputs}
    if len(signatures) != 1:
        raise ValueError("fixed-gauge problem signatures differ")
    vector_lengths = {int(item["coordinate_vector_length"]) for item in all_inputs}
    if len(vector_lengths) != 1:
        raise ValueError("coordinate-vector lengths differ")

    residue, modulus = 0, 1
    source_trace = []
    for item in source:
        prime = int(item["characteristic"])
        observed = int(item["coordinate_residue"])
        residue, modulus = crt_pair(residue, modulus, observed, prime)
        source_trace.append(
            {
                "characteristic": prime,
                "coordinate_residue": observed,
                "cumulative_modulus_bit_length": modulus.bit_length(),
            }
        )
    candidates, eea_steps = complete_strict_product_candidates(residue, modulus)

    selector_trace = []
    survivors = list(candidates)
    for selector in selectors:
        prime = int(selector["characteristic"])
        observed = int(selector["coordinate_residue"])
        filtered = []
        for numerator, denominator in survivors:
            if denominator % prime == 0:
                continue
            predicted = numerator % prime * pow(denominator % prime, -1, prime) % prime
            if predicted == observed:
                filtered.append((numerator, denominator))
        survivors = filtered
        selector_trace.append(
            {
                "characteristic": prime,
                "observed_coordinate_residue": observed,
                "survivor_count_after_selector": len(survivors),
            }
        )

    candidate_records = []
    survivor_set = set(survivors)
    for numerator, denominator in candidates:
        selector_residues = []
        for selector in selectors:
            prime = int(selector["characteristic"])
            observed = int(selector["coordinate_residue"])
            predicted = (
                None
                if denominator % prime == 0
                else numerator % prime * pow(denominator % prime, -1, prime) % prime
            )
            selector_residues.append(
                {
                    "characteristic": prime,
                    "predicted_residue": predicted,
                    "observed_residue": observed,
                    "matches": predicted == observed,
                }
            )
        candidate_records.append(
            {
                "numerator": str(numerator),
                "denominator": str(denominator),
                "numerator_bit_length": abs(numerator).bit_length(),
                "denominator_bit_length": denominator.bit_length(),
                "twice_product": str(2 * abs(numerator) * denominator),
                "twice_product_bit_length": (
                    2 * abs(numerator) * denominator
                ).bit_length(),
                "source_congruence_remainder": (
                    numerator - residue * denominator
                ) % modulus,
                "selector_residues": selector_residues,
                "survives_all_selectors": (numerator, denominator) in survivor_set,
            }
        )

    def input_record(item: dict[str, object]) -> dict[str, object]:
        return {
            "path": str(item["path"]),
            "sha256": item["sha256"],
            "characteristic": item["characteristic"],
            "coordinate_residue": item["coordinate_residue"],
        }

    output = arguments.output.resolve()
    result = {
        "schema": "hc4.third-colon-coordinate-adaptive-crt-probe.v1",
        "status": "PASS_BOUNDED_COORDINATE_CRT_PROBE",
        "coordinate": arguments.coordinate,
        "fixed_gauge_signature_sha256": next(iter(signatures)),
        "source_artifacts": [input_record(item) for item in source],
        "selector_artifacts": [input_record(item) for item in selectors],
        "source_trace": source_trace,
        "source_modulus": str(modulus),
        "source_modulus_bit_length": modulus.bit_length(),
        "combined_source_residue": str(residue),
        "complete_eea_step_count": eea_steps,
        "strict_product_candidate_count_before_selectors": len(candidates),
        "selector_trace": selector_trace,
        "survivor_count_after_all_selectors": len(survivors),
        "candidates": candidate_records,
        "source_script": {
            "path": str(Path(__file__).resolve()),
            "sha256": file_sha256(Path(__file__).resolve()),
        },
        "completeness_statement": (
            "For reduced n/d with d>0, gcd(d,M)=1, n=r*d mod M, and "
            "2*abs(n)*d<M, Legendre's theorem forces the corresponding "
            "approximation to be a convergent; the EEA list is complete in "
            "this strict-product region. This condition does not imply that "
            "the candidate is the characteristic-zero coefficient."
        ),
        "claim_boundary": (
            "This is a one-coordinate modular CRT probe. Even one surviving "
            "candidate is not a rational reconstruction or polynomial identity. "
            "No colon, saturation, secant, or HC4 claim follows."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(output),
                "source_modulus_bit_length": modulus.bit_length(),
                "candidate_count_before_selectors": len(candidates),
                "selector_trace": selector_trace,
                "survivor_count_after_all_selectors": len(survivors),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
