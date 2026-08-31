#!/usr/bin/env python3
"""Find a small modular unit-generating subset on the tangent r=5 stratum."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from scout_j2_normalized_chart import msolve_source, run_msolve
from scout_j2_tangent_root_stratum import stratum_system


def trial_record(
    removed: list[int], candidate_size: int, calculation: dict[str, object]
) -> dict[str, object]:
    return {
        "removed_chunk": removed,
        "candidate_normal_equation_count": candidate_size,
        "is_unit": calculation["is_unit"],
        "timed_out": calculation["timed_out"],
        "diagnostic_error": calculation["diagnostic_error"],
        "wall_seconds": calculation["wall_seconds"],
        "child_user_seconds_immediate_scope": calculation[
            "child_user_seconds_immediate_scope"
        ],
        "maximum_rss_native_immediate_scope": calculation[
            "maximum_rss_native_immediate_scope"
        ],
        "solver_output_tail": calculation.get("solver_output_tail", "")[-80:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prime", type=int, default=101)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--trial-timeout", type=int, default=10)
    parser.add_argument("--validation-timeout", type=int, default=60)
    parser.add_argument(
        "--validation-primes", type=int, nargs="+", default=(101, 32003, 65521)
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/hsop-j2-tangent-r5-minimal-generators.json"),
    )
    arguments = parser.parse_args()

    started = time.perf_counter()
    normal_equations, auxiliary, variables, substitutions = stratum_system(5)
    active = list(range(len(normal_equations)))
    trials: list[dict[str, object]] = []

    def is_unit(indices: list[int], prime: int, timeout: int) -> tuple[bool, dict[str, object]]:
        equations = [normal_equations[index] for index in indices]
        source = msolve_source(equations, auxiliary, variables, prime)
        calculation = run_msolve(source, timeout, arguments.threads)
        return bool(calculation["is_unit"]), calculation

    unit, baseline = is_unit(active, arguments.prime, arguments.validation_timeout)
    if not unit:
        raise SystemExit("baseline r=5 system did not reproduce a modular unit")

    chunk_size = max(1, len(active) // 2)
    while chunk_size >= 1:
        changed = True
        while changed:
            changed = False
            for start in range(0, len(active), chunk_size):
                chunk = active[start : start + chunk_size]
                if len(chunk) == len(active):
                    continue
                removed = set(chunk)
                candidate = [index for index in active if index not in removed]
                unit, calculation = is_unit(
                    candidate, arguments.prime, arguments.trial_timeout
                )
                trials.append(trial_record(chunk, len(candidate), calculation))
                if unit:
                    active = candidate
                    changed = True
                    break
        chunk_size //= 2

    # A final reverse single-deletion pass makes the result one-minimal in a
    # deterministic order even if earlier chunk decisions changed redundancy.
    for index in list(reversed(active)):
        candidate = [current for current in active if current != index]
        unit, calculation = is_unit(candidate, arguments.prime, arguments.trial_timeout)
        trials.append(trial_record([index], len(candidate), calculation))
        if unit:
            active = candidate

    validations: list[dict[str, object]] = []
    for prime in arguments.validation_primes:
        unit, calculation = is_unit(active, prime, arguments.validation_timeout)
        validations.append(
            {
                "prime": prime,
                **trial_record([], len(active), calculation),
            }
        )
        if not unit:
            raise SystemExit(f"minimal subset failed validation at prime {prime}")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    selected_equations = [normal_equations[index] for index in active]
    selected_payload = "\n".join(str(expression) for expression in selected_equations)
    result = {
        "schema": "hc4-decimic-j2-tangent-r5-generator-minimization-v1",
        "status": "PASS_MODULAR_ROUTE_EVIDENCE",
        "top_index": 5,
        "substitutions": substitutions,
        "discovery_prime": arguments.prime,
        "threads": arguments.threads,
        "trial_timeout_seconds": arguments.trial_timeout,
        "original_normal_equation_count": len(normal_equations),
        "selected_normal_equation_indices": active,
        "selected_normal_equation_count": len(active),
        "discarded_normal_equation_indices": [
            index for index in range(len(normal_equations)) if index not in active
        ],
        "auxiliary_equation_count": len(auxiliary),
        "variable_count": len(variables),
        "trial_count": len(trials),
        "trials": trials,
        "validations": validations,
        "selected_equation_stream_sha256": hashlib.sha256(
            selected_payload.encode("ascii")
        ).hexdigest(),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/minimize_j2_tangent_r5_generators.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/scout_j2_tangent_root_stratum.py": hashlib.sha256(
                (script_path.parent / "scout_j2_tangent_root_stratum.py").read_bytes()
            ).hexdigest(),
            "scripts/msolve_process.py": hashlib.sha256(
                (script_path.parent / "msolve_process.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "the subset is selected and validated only in finite characteristic; "
            "it is a route to, not a substitute for, a characteristic-zero unit"
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
