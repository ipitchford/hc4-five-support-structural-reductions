#!/usr/bin/env python3
"""Characteristic-zero certificate for the minimized tangent r=5 subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import singular_source
from scout_j2_tangent_root_stratum import stratum_system


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--selection",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r5-minimal-generators.json"),
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument(
        "--algorithm", choices=("modstd", "qstd", "slimgb", "msolve"), default="modstd"
    )
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r5-char0-subset.json"),
    )
    arguments = parser.parse_args()

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    selection_path = arguments.selection
    if not selection_path.is_absolute():
        selection_path = campaign / selection_path
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("status") != "PASS_MODULAR_ROUTE_EVIDENCE":
        raise SystemExit("selection receipt is not a passing modular route artifact")
    indices = [int(index) for index in selection["selected_normal_equation_indices"]]

    started = time.perf_counter()
    normal_equations, auxiliary, variables, substitutions = stratum_system(5)
    selected = [normal_equations[index] for index in indices]
    stream = "\n".join(str(expression) for expression in selected)
    stream_sha256 = hashlib.sha256(stream.encode("ascii")).hexdigest()
    if stream_sha256 != selection["selected_equation_stream_sha256"]:
        raise AssertionError("selected equation stream does not match the frozen receipt")
    if arguments.algorithm == "msolve":
        from scout_j2_normalized_chart import msolve_source, run_msolve

        source = msolve_source(selected, auxiliary, variables, 0)
        calculation = run_msolve(source, arguments.timeout, arguments.threads)
    else:
        source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
        source = singular_source(selected, auxiliary, variables, 0, source_algorithm)
        calculation = run_source(source, arguments.timeout)
    if calculation["diagnostic_error"]:
        status = "DIAGNOSTIC_ERROR"
    elif calculation["is_unit"] and arguments.algorithm == "msolve":
        status = "PROBABILISTIC_CHARACTERISTIC_ZERO_UNIT_SIGNAL"
    elif calculation["is_unit"]:
        status = "PASS_EXACT_CHARACTERISTIC_ZERO_UNIT"
    elif calculation["timed_out"]:
        status = "TIMEOUT_RETAINED"
    else:
        status = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    result = {
        "schema": "hc4-decimic-j2-tangent-r5-char0-subset-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": 5,
        "gauge": "primitive_j2=1",
        "substitutions": substitutions,
        "characteristic": 0,
        "algorithm": (
            "msolve characteristic-zero F4"
            if arguments.algorithm == "msolve"
            else "Singular " + arguments.algorithm
        ),
        "arithmetic_assurance": (
            "probabilistic modular reconstruction over characteristic zero"
            if arguments.algorithm == "msolve"
            else "deterministic exact rational arithmetic"
        ),
        "threads": arguments.threads if arguments.algorithm == "msolve" else 1,
        "selected_normal_equation_indices": indices,
        "selected_normal_equation_count": len(selected),
        "auxiliary_equation_count": len(auxiliary),
        "generator_count": len(selected) + len(auxiliary),
        "variable_count": len(variables),
        "selected_equation_stream_sha256": stream_sha256,
        "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        "solver_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "selection_receipt_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_r5_subset.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_j2_tangent_root_stratum.py": hashlib.sha256(
                (script_path.parent / "scout_j2_tangent_root_stratum.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a deterministic passing receipt proves emptiness of the normalized "
            "tangent r=5 stratum only; msolve in characteristic zero supplies "
            "probabilistic route evidence only; the other five tangent strata "
            "and the secant orbit remain"
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if status == "PASS_EXACT_CHARACTERISTIC_ZERO_UNIT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
