#!/usr/bin/env python3
"""Find a one-minimal modular subset for a coefficient-normalized tangent slice."""

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
    parser.add_argument("--prime", type=int, default=101)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--trial-timeout", type=int, default=10)
    parser.add_argument("--validation-timeout", type=int, default=60)
    parser.add_argument("--validation-primes", type=int, nargs="+", default=(101, 32003, 65521))
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    started = time.perf_counter()
    normal_equations, auxiliary, variables, substitutions, j2 = coefficient_slice(
        arguments.top_index
    )
    active = list(range(len(normal_equations)))
    trials: list[dict[str, object]] = []

    def is_unit(indices: list[int], prime: int, timeout: int):
        equations = [normal_equations[index] for index in indices]
        calculation = run_msolve(
            msolve_source(equations, auxiliary, variables, prime),
            timeout,
            arguments.threads,
        )
        return bool(calculation["is_unit"]), calculation

    unit, baseline = is_unit(active, arguments.prime, arguments.validation_timeout)
    if not unit:
        raise SystemExit("baseline coefficient-normalized system is not a modular unit")

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
                unit, calculation = is_unit(candidate, arguments.prime, arguments.trial_timeout)
                trials.append(trial_record(chunk, len(candidate), calculation))
                if unit:
                    active = candidate
                    changed = True
                    break
        chunk_size //= 2

    for index in list(reversed(active)):
        candidate = [current for current in active if current != index]
        unit, calculation = is_unit(candidate, arguments.prime, arguments.trial_timeout)
        trials.append(trial_record([index], len(candidate), calculation))
        if unit:
            active = candidate

    validations: list[dict[str, object]] = []
    for prime in arguments.validation_primes:
        unit, calculation = is_unit(active, prime, arguments.validation_timeout)
        validations.append({"prime": prime, **trial_record([], len(active), calculation)})
        if not unit:
            raise SystemExit(f"selected subset failed validation at prime {prime}")

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    selected_equations = [normal_equations[index] for index in active]
    selected_payload = "\n".join(str(expression) for expression in selected_equations)
    result = {
        "schema": "hc4-decimic-j2-tangent-coefficient-generator-minimization-v1",
        "status": "PASS_MODULAR_ROUTE_EVIDENCE",
        "top_index": arguments.top_index,
        "coefficient_normalization": f"f{arguments.top_index}=1",
        "substitutions": substitutions,
        "j2_after_substitution": str(j2),
        "discovery_prime": arguments.prime,
        "validation_primes": list(arguments.validation_primes),
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
            "scripts/minimize_j2_tangent_coefficient_generators.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_tangent_coefficient_slice.py": hashlib.sha256(
                (script_path.parent / "certify_j2_tangent_coefficient_slice.py").read_bytes()
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
    if arguments.output is None:
        output = campaign / (
            f"receipts/hsop-j2-tangent-r{arguments.top_index}-coefficient-minimal-generators.json"
        )
    else:
        output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
