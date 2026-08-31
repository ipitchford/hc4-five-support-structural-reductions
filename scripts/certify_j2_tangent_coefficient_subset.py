#!/usr/bin/env python3
"""Exact rational replay of a modularly selected tangent coefficient subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_tangent_coefficient_slice import coefficient_slice
from scout_decimic_nullcone_hsop import digest, run_source
from scout_j2_normalized_chart import singular_source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-index", type=int, choices=range(6, 11), required=True)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--algorithm", choices=("slimgb", "qstd", "modstd"), default="slimgb"
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    selection_path = arguments.selection or Path(
        f"receipts/hsop-j2-tangent-r{arguments.top_index}-coefficient-minimal-generators.json"
    )
    if not selection_path.is_absolute():
        selection_path = campaign / selection_path
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("status") != "PASS_MODULAR_ROUTE_EVIDENCE":
        raise SystemExit("selection receipt is not passing modular route evidence")
    if selection.get("top_index") != arguments.top_index:
        raise SystemExit("selection receipt targets a different top index")
    indices = [int(index) for index in selection["selected_normal_equation_indices"]]

    started = time.perf_counter()
    normal_equations, auxiliary, variables, substitutions, j2 = coefficient_slice(
        arguments.top_index
    )
    selected = [normal_equations[index] for index in indices]
    selected_payload = "\n".join(str(expression) for expression in selected)
    selected_sha256 = hashlib.sha256(selected_payload.encode("ascii")).hexdigest()
    if selected_sha256 != selection["selected_equation_stream_sha256"]:
        raise AssertionError("the selected equation stream does not match its receipt")

    source_algorithm = "std" if arguments.algorithm == "modstd" else arguments.algorithm
    source = singular_source(selected, auxiliary, variables, 0, source_algorithm)
    source = source.replace("exit;", 'print("BASIS_FIRST");\nJ[1];\nexit;')
    calculation = run_source(source, arguments.timeout)
    status = (
        "PASS_EXACT_TANGENT_STRATUM_EMPTY"
        if calculation["is_unit"]
        else "INCOMPLETE_EXACT_TANGENT_STRATUM"
    )
    result = {
        "schema": "hc4-decimic-j2-tangent-coefficient-subset-exact-v1",
        "status": status,
        "orbit": "tangent",
        "top_index": arguments.top_index,
        "coefficient_normalization": f"f{arguments.top_index}=1",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "characteristic": 0,
        "algorithm": "Singular " + arguments.algorithm,
        "selected_normal_equation_indices": indices,
        "selected_normal_equation_count": len(selected),
        "auxiliary_equation_count": len(auxiliary),
        "generator_count": len(selected) + len(auxiliary),
        "variable_count": len(variables),
        "maximum_total_degree": max(
            sp.Poly(expression, *variables).total_degree()
            for expression in selected + auxiliary
        ),
        "selected_equation_stream_sha256": selected_sha256,
        "auxiliary_stream_sha256": digest(tuple(auxiliary)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "selection_receipt_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_tangent_coefficient_subset.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_coefficient_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_coefficient_slice.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves exact characteristic-zero emptiness of this "
            "single tangent stratum; the modular selection itself carries no proof weight"
        ),
    }
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-tangent-r{arguments.top_index}-coefficient-subset-exact.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if calculation["is_unit"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
