#!/usr/bin/env python3
"""Validate a frozen structural subset on a tangent coefficient slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from certify_j2_tangent_coefficient_slice import coefficient_slice
from minimize_j2_tangent_r5_generators import trial_record
from scout_j2_normalized_chart import msolve_source, run_msolve


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(6, 11), required=True)
    parser.add_argument("--indices", type=int, nargs="+", required=True)
    parser.add_argument("--primes", type=int, nargs="+", default=(101, 32003, 65521))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    indices = sorted(set(arguments.indices))
    if indices != arguments.indices:
        parser.error("indices must be distinct and supplied in increasing order")

    started = time.perf_counter()
    normal_equations, auxiliary, variables, substitutions, j2 = coefficient_slice(
        arguments.top_index
    )
    if not indices or indices[0] < 0 or indices[-1] >= len(normal_equations):
        parser.error("an equation index is outside the reconstructed normal stream")
    selected = [normal_equations[index] for index in indices]
    validations: list[dict[str, object]] = []
    for prime in arguments.primes:
        calculation = run_msolve(
            msolve_source(selected, auxiliary, variables, prime),
            arguments.timeout,
            arguments.threads,
        )
        validation = {
            "prime": prime,
            **trial_record([], len(selected), calculation),
        }
        validations.append(validation)
        if not calculation["is_unit"]:
            raise SystemExit(f"structural subset failed validation at prime {prime}")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    selected_payload = "\n".join(str(expression) for expression in selected)
    result = {
        "schema": "hc4-decimic-j2-tangent-coefficient-structural-subset-v1",
        "status": "PASS_MODULAR_ROUTE_EVIDENCE",
        "selection_rule": (
            f"frozen explicit normal-equation indices {indices[0]} through {indices[-1]}"
            if indices == list(range(indices[0], indices[-1] + 1))
            else "frozen explicit normal-equation index list"
        ),
        "top_index": arguments.top_index,
        "coefficient_normalization": f"f{arguments.top_index}=1",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "validation_primes": list(arguments.primes),
        "threads": arguments.threads,
        "timeout_seconds": arguments.timeout,
        "original_normal_equation_count": len(normal_equations),
        "selected_normal_equation_indices": indices,
        "selected_normal_equation_count": len(selected),
        "auxiliary_equation_count": len(auxiliary),
        "variable_count": len(variables),
        "validations": validations,
        "selected_equation_stream_sha256": hashlib.sha256(
            selected_payload.encode("ascii")
        ).hexdigest(),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/validate_j2_tangent_coefficient_subset.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_coefficient_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_coefficient_slice.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "finite-characteristic validation is route evidence only; exact rational "
            "replay is required before this subset supports a stratum theorem"
        ),
    }
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-tangent-r{arguments.top_index}-coefficient-structural-subset.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
