#!/usr/bin/env python3
"""Aggregate the exact tangent certificates for all 31 nullcone generators."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


FAMILIES = (
    ("quadratic_V0", 2, 1, "receipts/hsop-j2-tangent-all-strata.json", "PASS_EXACT_TANGENT_J2_RADICAL_CONTAINMENT"),
    ("cubic_V2", 3, 3, "receipts/nullcone-v2-tangent-stabilizer-span.json", "PASS_EXACT_TANGENT_V2_FAMILY_RADICAL_CONTAINMENT"),
    ("cubic_V6", 3, 7, "receipts/nullcone-v6-tangent-stabilizer-span.json", "PASS_EXACT_TANGENT_V6_FAMILY_RADICAL_CONTAINMENT"),
    ("quartic_V0", 4, 1, "receipts/nullcone-v0-tangent-stabilizer-span.json", "PASS_EXACT_TANGENT_QUARTIC_FAMILY_RADICAL_CONTAINMENT"),
    ("quartic_V4_1", 4, 5, "receipts/nullcone-v4-1-tangent-stabilizer-span.json", "PASS_EXACT_TANGENT_QUARTIC_FAMILY_RADICAL_CONTAINMENT"),
    ("quartic_V4_2", 4, 5, "receipts/nullcone-v4-2-tangent-stabilizer-span.json", "PASS_EXACT_TANGENT_QUARTIC_FAMILY_RADICAL_CONTAINMENT"),
    ("quartic_V8", 4, 9, "receipts/nullcone-v8-tangent-stabilizer-span.json", "PASS_EXACT_TANGENT_QUARTIC_FAMILY_RADICAL_CONTAINMENT"),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    evidence = []
    degree_counts: dict[int, int] = {}
    for family, degree, dimension, relative_path, expected_status in FAMILIES:
        path = campaign / relative_path
        receipt = json.loads(path.read_text(encoding="utf-8"))
        actual_status = receipt.get("status")
        if actual_status != expected_status:
            raise AssertionError(
                f"{family}: expected {expected_status}, found {actual_status}"
            )
        if receipt.get("characteristic") != 0:
            raise AssertionError(f"{family}: receipt is not characteristic zero")
        degree_counts[degree] = degree_counts.get(degree, 0) + dimension
        evidence.append(
            {
                "family": family,
                "degree": degree,
                "dimension": dimension,
                "receipt": relative_path,
                "receipt_sha256": sha256(path),
                "status": actual_status,
            }
        )

    expected_degree_counts = {2: 1, 3: 10, 4: 20}
    if degree_counts != expected_degree_counts:
        raise AssertionError(
            f"generator dimensions do not match the target profile: {degree_counts}"
        )

    result = {
        "schema": "hc4.decimic-nullcone-tangent-all-generators.v1",
        "status": "PASS_EXACT_TANGENT_ALL_31_GENERATORS_RADICAL_CONTAINMENT",
        "claim": (
            "all 31 minimal generators of the binary-decimic multiplicity-six "
            "locus lie in the radical of the tangent residual-orbit normal-layer ideal"
        ),
        "characteristic": 0,
        "target_locus": "X_(6,1,1,1,1) in P(Sym^10)",
        "generator_profile": {
            "degree_2": degree_counts[2],
            "degree_3": degree_counts[3],
            "degree_4": degree_counts[4],
            "total": sum(degree_counts.values()),
            "sl2_families": len(FAMILIES),
        },
        "evidence": evidence,
        "source_sha256": {
            "scripts/audit_nullcone_tangent_all_generators.py": sha256(script_path),
        },
        "claim_boundary": (
            "this is an exact computer-assisted characteristic-zero radical-containment "
            "theorem for the tangent residual orbit on the clean normal layer; it does "
            "not prove the corresponding secant-orbit containment, polynomial-level "
            "lifting, full-family closure, HC4, or the quartic Hessian conjecture"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = campaign / "receipts/nullcone-tangent-all-31-generators.json"
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
