#!/usr/bin/env python3
"""Bounded modular scout after adjoining both certified quartics.

The input ideal is I2=(F_1,...,F_17,h,h2), followed by the saturating element
M as the final polynomial.  A pinned, instrumented msolve F4SAT executable
stops at the first new kernel event.  The only accepted positive outputs are a
literal unit event or one parsed homogeneous modular candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_z12_macaulay import CHARACTER_MODULUS, CHARACTER_WEIGHTS
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
    render,
)
from scout_j2_secant_r10_residual_colon import (
    PINNED_MSOLVE_COMMIT,
    git_text,
    parse_tap,
    parse_time_l,
    render_modular_polynomial,
    sha256,
)


def degree_character(terms: list[dict]) -> tuple[set[int], set[int]]:
    degrees = {sum(map(int, term["exponents"])) for term in terms}
    characters = {
        sum(
            exponent * weight
            for exponent, weight in zip(
                map(int, term["exponents"]), CHARACTER_WEIGHTS, strict=True
            )
        )
        % CHARACTER_MODULUS
        for term in terms
    }
    return degrees, characters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=1073741827)
    parser.add_argument("--msolve", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--first-quartic",
        type=Path,
        default=Path("artifacts/j2-secant-r10-first-colon-kernel-qq.json"),
    )
    parser.add_argument(
        "--second-quartic",
        type=Path,
        default=Path("artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json"),
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if not 1 <= arguments.timeout <= 180:
        parser.error("timeout must lie between 1 and 180 seconds")
    if arguments.threads < 1:
        parser.error("threads must be positive")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    first_path = arguments.first_quartic
    second_path = arguments.second_quartic
    if not first_path.is_absolute():
        first_path = campaign / first_path
    if not second_path.is_absolute():
        second_path = campaign / second_path
    msolve = arguments.msolve.resolve()
    if not msolve.is_file() or not os.access(msolve, os.X_OK):
        parser.error("--msolve must name the instrumented executable")

    msolve_root = msolve.parent
    commit = git_text(msolve_root, "rev-parse", "HEAD").strip()
    if commit != PINNED_MSOLVE_COMMIT:
        raise RuntimeError(f"unexpected msolve commit {commit}")
    source_diff = git_text(
        msolve_root, "diff", "--", "src/neogb/f4sat.c", "src/msolve/msolve.c"
    )
    if "COLON_KERNEL_DUMP_BEGIN" not in source_diff or "STOP_AFTER_FIRST_KERNEL" not in source_diff:
        raise RuntimeError("instrumented executable lacks the bounded kernel tap")

    first = json.loads(first_path.read_text(encoding="utf-8"))
    second = json.loads(second_path.read_text(encoding="utf-8"))
    if first.get("status") != "PASS_QQ_CANDIDATE_RECONSTRUCTION_HELDOUT_REPLAY":
        raise ValueError("first quartic artifact has the wrong status")
    if second.get("status") != "RATIONAL_CANDIDATE_RECONSTRUCTED_FROM_TWO_MODULAR_TAPS":
        raise ValueError("second quartic artifact has the wrong status")
    first_terms = first["h_primitive_integer_terms"]
    second_terms = second["primitive_integer_terms"]
    equations, variables, _, open_factor = homogeneous_saturation_system()
    variable_names = list(map(str, variables))
    if first.get("variable_names") != variable_names or second.get("variable_names") != variable_names:
        raise ValueError("quartic and system variable streams differ")
    if degree_character(first_terms) != ({4}, {4}):
        raise ValueError("h is not the expected degree-four, character-four form")
    if degree_character(second_terms) != ({4}, {3}):
        raise ValueError("h2 is not the expected degree-four, character-three form")

    h_mod_p = render_modular_polynomial(first_terms, variables, arguments.characteristic)
    h2_mod_p = render_modular_polynomial(second_terms, variables, arguments.characteristic)
    generators = [
        *[render(equation) for equation in equations],
        h_mod_p,
        h2_mod_p,
        render(open_factor),
    ]
    source = "\n".join(
        [",".join(variable_names), str(arguments.characteristic)]
        + [
            generator + ("," if index + 1 < len(generators) else "")
            for index, generator in enumerate(generators)
        ]
    ) + "\n"

    stem = f"j2-secant-r10-second-residual-colon-p{arguments.characteristic}"
    input_path = campaign / "research" / f"{stem}.ms"
    tap_path = campaign / "research" / f"{stem}-first-kernel.txt"
    stdout_path = campaign / "research" / f"{stem}-stdout.txt"
    stderr_path = campaign / "research" / f"{stem}-stderr.txt"
    solver_output_path = campaign / "research" / f"{stem}-solver.out"
    for path in (tap_path, stdout_path, stderr_path, solver_output_path):
        if path.exists():
            path.unlink()
    input_path.write_text(source, encoding="ascii")

    command = [
        "/usr/bin/time", "-l", str(msolve),
        "-f", str(input_path), "-o", str(solver_output_path),
        "-S", "-g", "2", "-v", "2", "-t", str(arguments.threads),
        "--random-seed", "0",
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "MSOLVE_DUMP_FIRST_KERNEL": "1",
            "MSOLVE_KERNEL_DUMP_PATH": str(tap_path),
            "MSOLVE_STOP_AFTER_FIRST_KERNEL": "1",
        }
    )
    solver_started = time.perf_counter()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=arguments.timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    solver_wall_seconds = time.perf_counter() - solver_started
    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")

    tap_valid = False
    tap_error = None
    kernel_polynomials = []
    if tap_path.is_file():
        try:
            kernel_polynomials = parse_tap(
                tap_path, arguments.characteristic, len(variables)
            )
            tap_valid = bool(kernel_polynomials)
        except ValueError as error:
            tap_error = str(error)
    unit_event = (
        len(kernel_polynomials) == 1
        and kernel_polynomials[0]["reconstructed_total_degree"] == 0
        and kernel_polynomials[0]["term_count"] == 1
        and kernel_polynomials[0]["terms"][0]["exponents"] == [0] * len(variables)
        and kernel_polynomials[0]["terms"][0]["coefficient"] % arguments.characteristic != 0
    )
    if timed_out:
        status = "INCOMPLETE_TIMEOUT_NO_DECISION"
    elif process.returncode != 0:
        status = "INCOMPLETE_SOLVER_ERROR_NO_DECISION"
    elif unit_event:
        status = "MODULAR_UNIT_KERNEL_EVENT"
    elif tap_valid:
        status = "CANDIDATE_MODULAR_SECOND_RESIDUAL_COLON_KERNEL_EXTRACTED"
    else:
        status = "NO_FURTHER_KERNEL_OBSERVED_IN_COMPLETED_MODULAR_RUN"

    artifact_paths = [input_path, stdout_path, stderr_path]
    if tap_path.is_file():
        artifact_paths.append(tap_path)
    if solver_output_path.is_file():
        artifact_paths.append(solver_output_path)
    actual_binary = msolve_root / ".libs/msolve"
    result = {
        "schema": "hc4.decimic-j2-secant-r10-second-residual-colon-scout.v1",
        "status": status,
        "assurance": "bounded exact finite-field discovery only",
        "characteristic": arguments.characteristic,
        "ideal": "I2=(17 retained homogeneous cubics,h,h2)",
        "saturating_element": "M=f9*f10*(2*f9^2+5*f10*g0)",
        "colon_question": "first new class in (I2:M)/I2",
        "variable_names": variable_names,
        "generator_order": [f"F{index + 1}" for index in range(len(equations))]
        + ["h", "h2", "M"],
        "normal_generator_count": len(equations),
        "h": {
            "source_artifact": str(first_path),
            "source_artifact_sha256": sha256(first_path),
            "primitive_term_count": len(first_terms),
            "total_degree": 4,
            "character_weight_mod_12": 4,
        },
        "h2": {
            "source_artifact": str(second_path),
            "source_artifact_sha256": sha256(second_path),
            "primitive_term_count": len(second_terms),
            "total_degree": 4,
            "character_weight_mod_12": 3,
            "qq_identity_artifact": str(
                campaign / "artifacts/j2-secant-r10-second-colon-identity-qq.json"
            ),
            "qq_identity_artifact_sha256": sha256(
                campaign / "artifacts/j2-secant-r10-second-colon-identity-qq.json"
            ),
        },
        "input": {
            "path": str(input_path),
            "sha256": sha256(input_path),
            "byte_count": input_path.stat().st_size,
            "polynomial_count": len(generators),
            "last_polynomial_is_saturating_element": True,
            "normal_equation_stream_sha256": digest(tuple(equations)),
            "open_factor_sha256": digest((open_factor,)),
        },
        "tool": {
            "name": "msolve",
            "version": "0.10.1",
            "commit": commit,
            "commit_pinned": commit == PINNED_MSOLVE_COMMIT,
            "wrapper_path": str(msolve),
            "wrapper_sha256": sha256(msolve),
            "binary_path": str(actual_binary),
            "binary_sha256": sha256(actual_binary),
            "source_diff_sha256": hashlib.sha256(source_diff.encode("utf-8")).hexdigest(),
            "source_diff": source_diff,
        },
        "calculation": {
            "command": command,
            "environment": {
                "MSOLVE_DUMP_FIRST_KERNEL": "1",
                "MSOLVE_KERNEL_DUMP_PATH": str(tap_path),
                "MSOLVE_STOP_AFTER_FIRST_KERNEL": "1",
            },
            "threads": arguments.threads,
            "random_seed": 0,
            "timeout_seconds": arguments.timeout,
            "timed_out": timed_out,
            "return_code": process.returncode,
            "solver_wall_seconds": solver_wall_seconds,
            "resource_metrics": parse_time_l(stderr),
            "stdout_tail": stdout[-8000:],
            "stderr_tail": stderr[-8000:],
            "tap_present": tap_path.is_file(),
            "tap_valid": tap_valid,
            "tap_parse_error": tap_error,
            "unit_event": unit_event,
            "kernel_polynomial_count": len(kernel_polynomials),
            "kernel_polynomials": kernel_polynomials,
        },
        "artifacts": {
            str(path.relative_to(campaign)): {
                "sha256": sha256(path), "byte_count": path.stat().st_size
            }
            for path in artifact_paths
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
            "dependency": {
                "path": "scripts/scout_j2_secant_r10_residual_colon.py",
                "sha256": sha256(
                    campaign / "scripts/scout_j2_secant_r10_residual_colon.py"
                ),
            },
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "A unit status or kernel candidate is only a finite-field event from "
            "the pinned instrumented saturation algorithm. It is not a QQ lift, "
            "an independent membership proof, a computation of the full colon or "
            "saturation, a secant-chart closure, or HC4. A timeout or solver error "
            "makes no mathematical decision."
        ),
    }
    output = arguments.output or campaign / "receipts" / f"hsop-{stem}.json"
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
