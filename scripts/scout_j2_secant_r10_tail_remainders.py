#!/usr/bin/env python3
"""Reduce omitted secant ``r=10`` equations modulo one modular tail basis."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_coefficient_slice import coefficient_slice
from certify_j2_secant_r10_degree_branches import clear_denominators
from certify_j2_secant_r10_tail_branch import BRANCH_NAMES, tail_branches
from scout_decimic_nullcone_hsop import digest, render
from singular_process import run_singular_process


def marker_values(stdout: str, marker: str, count: int) -> list[str] | None:
    lines = stdout.splitlines()
    try:
        position = lines.index(marker)
    except ValueError:
        return None
    values = lines[position + 1 : position + 1 + count]
    return [value.strip() for value in values] if len(values) == count else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, default="degree_3")
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than 5")

    started = time.perf_counter()
    normal_equations, _, _, _, _ = coefficient_slice(10)
    _, _, retained_indices, branches = tail_branches("tail")
    branch = branches[arguments.branch]
    omitted_indices = tuple(
        index for index in range(len(normal_equations)) if index not in retained_indices
    )
    omitted = [
        clear_denominators(normal_equations[index].subs(branch["zero_substitutions"]))
        for index in omitted_indices
    ]
    variable_source = ",".join(map(str, branch["variables"]))
    source_lines = [
        f"ring r={arguments.characteristic},({variable_source}),dp;",
        "option(redSB);",
        "ideal I=" + ",".join(render(equation) for equation in branch["equations"]) + ";",
        "ideal J=std(I);",
        'print("TAIL_BASIS");',
        "size(J);",
        "poly one_remainder=reduce(1,J);",
        "one_remainder;",
    ]
    for index, equation in zip(omitted_indices, omitted):
        source_lines.extend(
            [
                f"poly omitted_{index}={render(equation)};",
                f"poly remainder_{index}=reduce(omitted_{index},J);",
                f'print("ROW_{index}");',
                f"size(remainder_{index});",
                f"deg(remainder_{index});",
            ]
        )
    source_lines.append("exit;")
    source = "\n".join(source_lines)
    raw = run_singular_process(source, arguments.timeout)
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    diagnostic_error = "error occurred" in stdout or "error occurred" in stderr
    tail_marker = marker_values(stdout, "TAIL_BASIS", 2)
    rows = {}
    for index in omitted_indices:
        values = marker_values(stdout, f"ROW_{index}", 2)
        rows[str(index)] = (
            {"normal_form_term_count": int(values[0]), "normal_form_degree": int(values[1])}
            if values is not None and all(value.lstrip("-").isdigit() for value in values)
            else None
        )
    complete = (
        not raw["timed_out"]
        and raw["return_code"] == 0
        and not diagnostic_error
        and tail_marker is not None
        and all(value is not None for value in rows.values())
    )
    result = {
        "schema": "hc4-decimic-j2-secant-r10-tail-remainder-scout-v1",
        "status": "PASS_MODULAR_REMAINDER_AUDIT" if complete else "INCOMPLETE_MODULAR_REMAINDER_AUDIT",
        "orbit": "secant",
        "top_index": 10,
        "branch": arguments.branch,
        "characteristic": arguments.characteristic,
        "retained_normal_equation_indices": list(retained_indices),
        "omitted_normal_equation_indices": list(omitted_indices),
        "tail_equation_stream_sha256": digest(tuple(branch["equations"])),
        "omitted_equation_stream_sha256": digest(tuple(omitted)),
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "tail_basis_size": int(tail_marker[0]) if tail_marker and tail_marker[0].isdigit() else None,
        "tail_unit_remainder": tail_marker[1] if tail_marker else None,
        "normal_forms": rows,
        "calculation": {
            **raw,
            "diagnostic_error": diagnostic_error,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
        },
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_secant_r10_tail_remainders.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_tail_branch.py": hashlib.sha256(
                (Path(__file__).parent / "certify_j2_secant_r10_tail_branch.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "this is a characteristic-p equation-selection scout only; it neither "
            "proves characteristic-zero emptiness nor validates a selected separator"
        ),
    }
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-{arguments.branch}-tail-remainders-p{arguments.characteristic}.json"
    )
    output = output if output.is_absolute() else campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
