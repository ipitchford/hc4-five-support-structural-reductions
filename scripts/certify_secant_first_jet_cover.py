#!/usr/bin/env python3
"""Certify the exhaustive secant first-nonzero-jet cover on j2 != 0."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import f_coefficients
from scout_j2_normalized_chart import primitive_j2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/secant-first-jet-cover.json"),
    )
    arguments = parser.parse_args()
    tau = sp.Symbol("tau", nonzero=True)
    weights = tuple(5 - index for index in range(11))
    j2 = primitive_j2()
    transformed = sp.expand(
        j2.subs(
            {
                f_coefficients[index]: tau ** weights[index] * f_coefficients[index]
                for index in range(11)
            },
            simultaneous=True,
        )
    )
    if sp.expand(transformed - j2) != 0:
        raise AssertionError("j2 is not invariant under the secant torus")
    if sp.expand(j2.subs({f_coefficients[index]: 0 for index in range(5, 11)})) != 0:
        raise AssertionError("j2 does not force a nonzero upper-half coefficient")

    strata = {}
    for top_index in range(5, 11):
        substitutions = {
            f_coefficients[index]: 0 for index in range(top_index + 1, 11)
        }
        if top_index >= 6:
            if weights[top_index] == 0:
                raise AssertionError("a claimed normalized coefficient has zero weight")
            substitutions[f_coefficients[top_index]] = 1
        specialized_j2 = sp.expand(j2.subs(substitutions))
        if top_index == 5 and specialized_j2 != -5 * f_coefficients[5] ** 2:
            raise AssertionError("the central secant stratum j2 identity changed")
        strata[str(top_index)] = {
            "zero_above": [f"f{index}" for index in range(top_index + 1, 11)],
            "top_coefficient": f"f{top_index}",
            "top_weight": weights[top_index],
            "normalization": (
                f"f{top_index}=1" if top_index >= 6 else "f5!=0 (not torus-normalized)"
            ),
            "j2_after_substitution": str(specialized_j2),
        }

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-secant-first-nonzero-jet-cover-v1",
        "status": "PASS",
        "orbit": "secant",
        "j2_torus_weight": 0,
        "coefficient_weights": list(weights),
        "first_nonzero_jet_indices": list(range(5, 11)),
        "strata": strata,
        "checks": {
            "j2_torus_invariant": True,
            "j2_forces_upper_half_nonzero": True,
            "all_noncentral_top_weights_nonzero": True,
            "central_identity_j2_minus_5f5_squared": True,
        },
        "source_sha256": {
            "scripts/certify_secant_first_jet_cover.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "receipts/residual-orbit-torus.json": hashlib.sha256(
                (campaign / "receipts/residual-orbit-torus.json").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this proves only that the six displayed secant strata exhaust j2!=0; "
            "it does not prove any stratum empty"
        ),
    }
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
