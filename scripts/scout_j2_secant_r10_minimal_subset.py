#!/usr/bin/env python3
"""Greedily find a small unit-generating subset of one ``r=10`` branch.

This is a route scout only.  Its output selects a smaller input for an exact
change-matrix or independent Bezout calculation; it is not itself a proof in
characteristic zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_f9_laurent_branch import BRANCH_NAMES, laurent_branches
from msolve_process import run_msolve_process
from scout_decimic_nullcone_hsop import digest
from scout_j2_normalized_chart import msolve_source


def is_unit(
    equations: list[sp.Expr],
    variables: tuple[sp.Symbol, ...],
    characteristic: int,
    timeout: int,
    threads: int,
) -> tuple[bool, dict[str, object]]:
    source = msolve_source(equations, [], variables, characteristic)
    raw = run_msolve_process(source, timeout, threads, verbose=0)
    solver_output = str(raw.pop("solver_output"))
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    clean_exit = not raw["timed_out"] and raw["return_code"] == 0
    unit = clean_exit and solver_output.strip().rstrip(":") == "[-1]"
    return unit, {
        **raw,
        "unit_signal": unit,
        "source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "solver_output_tail": solver_output[-500:],
        "stdout_tail": stdout[-500:],
        "stderr_tail": stderr[-500:],
    }


def removal_order(
    name: str,
    equations: list[sp.Expr],
    variables: tuple[sp.Symbol, ...],
    seed: int,
) -> list[int]:
    indices = list(range(len(equations)))
    if name == "forward":
        return indices
    if name == "reverse":
        return list(reversed(indices))
    if name == "complex_first":
        return sorted(
            indices,
            key=lambda index: (
                len(sp.Poly(equations[index], *variables).terms()),
                sp.Poly(equations[index], *variables).total_degree(),
                index,
            ),
            reverse=True,
        )
    if name == "simple_first":
        return sorted(
            indices,
            key=lambda index: (
                len(sp.Poly(equations[index], *variables).terms()),
                sp.Poly(equations[index], *variables).total_degree(),
                index,
            ),
        )
    if name == "seeded":
        random.Random(seed).shuffle(indices)
        return indices
    raise ValueError(f"unknown removal order: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", choices=BRANCH_NAMES, required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout-per-test", type=int, default=10)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--order",
        choices=("forward", "reverse", "complex_first", "simple_first", "seeded"),
        default="complex_first",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0:
        parser.error("characteristic must be nonnegative")
    if arguments.characteristic > 0 and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    _, _, _, _, branches = laurent_branches()
    branch = branches[arguments.branch]
    equations = list(branch["equations"])
    variables = tuple(branch["variables"])
    order = removal_order(arguments.order, equations, variables, arguments.seed)
    active = list(range(len(equations)))
    attempts: list[dict[str, object]] = []

    initial_unit, initial_calculation = is_unit(
        equations,
        variables,
        arguments.characteristic,
        arguments.timeout_per_test,
        arguments.threads,
    )
    if not initial_unit:
        raise RuntimeError("the full branch did not reproduce the expected unit signal")
    attempts.append(
        {
            "removed_index": None,
            "retained_indices": active,
            "calculation": initial_calculation,
        }
    )

    for candidate in order:
        if candidate not in active:
            continue
        trial = [index for index in active if index != candidate]
        unit, calculation = is_unit(
            [equations[index] for index in trial],
            variables,
            arguments.characteristic,
            arguments.timeout_per_test,
            arguments.threads,
        )
        attempts.append(
            {
                "removed_index": candidate,
                "retained_indices": trial,
                "calculation": calculation,
            }
        )
        if unit:
            active = trial

    # Recheck deletion-minimality in canonical order after the order-dependent pass.
    changed = True
    while changed:
        changed = False
        for candidate in list(active):
            trial = [index for index in active if index != candidate]
            unit, calculation = is_unit(
                [equations[index] for index in trial],
                variables,
                arguments.characteristic,
                arguments.timeout_per_test,
                arguments.threads,
            )
            attempts.append(
                {
                    "removed_index": candidate,
                    "retained_indices": trial,
                    "minimality_recheck": True,
                    "calculation": calculation,
                }
            )
            if unit:
                active = trial
                changed = True
                break

    final_unit, final_calculation = is_unit(
        [equations[index] for index in active],
        variables,
        arguments.characteristic,
        arguments.timeout_per_test,
        arguments.threads,
    )
    attempts.append(
        {
            "removed_index": None,
            "retained_indices": active,
            "final_replay": True,
            "calculation": final_calculation,
        }
    )
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4-decimic-j2-secant-r10-minimal-subset-scout-v1",
        "status": "PASS_ROUTE_SUBSET_SIGNAL" if final_unit else "INCOMPLETE_ROUTE_SUBSET",
        "assurance": (
            "deterministic finite-field route signal"
            if arguments.characteristic > 0
            else "probabilistic characteristic-zero route signal"
        ),
        "chart": "f9_laurent",
        "branch": arguments.branch,
        "characteristic": arguments.characteristic,
        "removal_order": arguments.order,
        "seed": arguments.seed,
        "original_generator_count": len(equations),
        "retained_generator_count": len(active),
        "retained_generator_indices": active,
        "retained_equation_stream_sha256": digest(tuple(equations[index] for index in active)),
        "attempt_count": len(attempts),
        "attempts": attempts,
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_secant_r10_minimal_subset.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
            "scripts/msolve_process.py": hashlib.sha256(
                (script_path.parent / "msolve_process.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "This is a route-selection signal only.  The retained subset must be "
            "proved to generate the unit ideal over QQ by an exact replayable certificate."
        ),
    }
    if arguments.output is None:
        field = f"p{arguments.characteristic}" if arguments.characteristic else "qq"
        output = campaign / (
            f"receipts/hsop-j2-secant-r10-f9-laurent-{arguments.branch}-"
            f"minimal-subset-{arguments.order}-{field}.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "status": result["status"],
                "retained_generator_count": len(active),
                "retained_generator_indices": active,
                "attempt_count": len(attempts),
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if final_unit else 1


if __name__ == "__main__":
    raise SystemExit(main())
