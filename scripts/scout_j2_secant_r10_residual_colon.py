#!/usr/bin/env python3
"""Bounded finite-field scout for the residual secant colon after adjoining h.

This is deliberately a discovery calculation.  It feeds the 17 homogeneous
cubics, the certified rational quartic ``h`` reduced modulo ``p``, and finally
the open factor ``M`` to an instrumented msolve F4-saturation build.  The tap
stops after the first new colon-kernel class, if one is found.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
    render,
)


TAP_BEGIN = "COLON_KERNEL_DUMP_BEGIN"
TAP_END = "COLON_KERNEL_DUMP_END"
PINNED_MSOLVE_COMMIT = "185e7b92fa0687f4db68b0f2f453a835668ac132"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_modular_polynomial(terms: list[dict], variables, prime: int) -> str:
    rendered = []
    for term in terms:
        coefficient = int(term["coefficient"]) % prime
        if coefficient == 0:
            continue
        exponents = tuple(map(int, term["exponents"]))
        if len(exponents) != len(variables):
            raise ValueError("quartic exponent vector has the wrong length")
        factors = [str(coefficient)]
        factors.extend(
            str(variable) if exponent == 1 else f"{variable}^{exponent}"
            for variable, exponent in zip(variables, exponents, strict=True)
            if exponent
        )
        rendered.append("*".join(factors))
    if not rendered:
        raise ValueError("quartic reduced to zero")
    return "+".join(rendered)


def parse_tap(path: Path, prime: int, variable_count: int) -> list[dict]:
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or lines[0] != TAP_BEGIN or lines[-1] != TAP_END:
        raise ValueError("incomplete or unrecognized kernel tap")
    polynomials = []
    position = 1
    while position < len(lines) - 1:
        header = lines[position].split()
        position += 1
        if len(header) != 6 or header[0] != "POLY" or header[2] != "DEG" or header[4] != "TERMS":
            raise ValueError("malformed POLY header")
        basis_index = int(header[1])
        reported_degree = int(header[3])
        term_count = int(header[5])
        terms = []
        for _ in range(term_count):
            coefficient_text, exponent_text = lines[position].split(":", 1)
            position += 1
            exponents = tuple(map(int, exponent_text.split(",")))
            if len(exponents) != variable_count:
                raise ValueError("wrong exponent-vector length in tap")
            terms.append(
                {
                    "coefficient": int(coefficient_text) % prime,
                    "exponents": list(exponents),
                }
            )
        total_degrees = {sum(term["exponents"]) for term in terms}
        characters = {
            sum(
                exponent * weight
                for exponent, weight in zip(
                    term["exponents"], CHARACTER_WEIGHTS, strict=True
                )
            )
            % CHARACTER_MODULUS
            for term in terms
        }
        if len(total_degrees) != 1 or len(characters) != 1:
            raise ValueError("tap polynomial is not homogeneous in degree and character")
        polynomials.append(
            {
                "basis_index": basis_index,
                "reported_degree": reported_degree,
                "reconstructed_total_degree": next(iter(total_degrees)),
                "character_weight_mod_12": next(iter(characters)),
                "term_count": term_count,
                "terms": terms,
            }
        )
    return polynomials


def git_text(root: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        check=True,
        text=True,
    )
    return process.stdout


def parse_time_l(stderr: str) -> dict:
    def integer_metric(label: str):
        match = re.search(rf"^\s*(\d+)\s+{re.escape(label)}\s*$", stderr, re.MULTILINE)
        return None if match is None else int(match.group(1))

    timing = re.search(
        r"^\s*([0-9.]+)\s+real\s+([0-9.]+)\s+user\s+([0-9.]+)\s+sys\s*$",
        stderr,
        re.MULTILINE,
    )
    return {
        "time_l_real_seconds": None if timing is None else float(timing.group(1)),
        "time_l_user_seconds": None if timing is None else float(timing.group(2)),
        "time_l_sys_seconds": None if timing is None else float(timing.group(3)),
        "maximum_resident_set_size_bytes": integer_metric("maximum resident set size"),
        "peak_memory_footprint_bytes": integer_metric("peak memory footprint"),
        "page_reclaims": integer_metric("page reclaims"),
        "page_faults": integer_metric("page faults"),
        "swaps": integer_metric("swaps"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=103)
    parser.add_argument("--msolve", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument(
        "--quartic",
        type=Path,
        default=Path("artifacts/j2-secant-r10-first-colon-kernel-qq.json"),
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if arguments.timeout < 1 or arguments.timeout > 180:
        parser.error("timeout must lie between 1 and the scout cap of 180 seconds")
    if arguments.threads < 1:
        parser.error("threads must be positive")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    quartic_path = arguments.quartic
    if not quartic_path.is_absolute():
        quartic_path = campaign / quartic_path
    msolve = arguments.msolve.resolve()
    if not msolve.is_file() or not os.access(msolve, os.X_OK):
        parser.error("--msolve must name the instrumented executable")

    msolve_root = msolve.parent
    commit = git_text(msolve_root, "rev-parse", "HEAD").strip()
    if commit != PINNED_MSOLVE_COMMIT:
        raise RuntimeError(f"unexpected msolve commit {commit}")
    source_diff = git_text(msolve_root, "diff", "--", "src/neogb/f4sat.c", "src/msolve/msolve.c")
    if "COLON_KERNEL_DUMP_BEGIN" not in source_diff or "STOP_AFTER_FIRST_KERNEL" not in source_diff:
        raise RuntimeError("the requested executable does not contain the expected bounded tap")

    quartic_data = json.loads(quartic_path.read_text(encoding="utf-8"))
    if quartic_data["status"] != "PASS_QQ_CANDIDATE_RECONSTRUCTION_HELDOUT_REPLAY":
        raise ValueError("quartic artifact does not have the expected passing status")
    terms = quartic_data["h_primitive_integer_terms"]
    equations, variables, _, open_factor = homogeneous_saturation_system()
    if list(map(str, variables)) != quartic_data["variable_names"]:
        raise ValueError("quartic and residual system variable orders differ")
    degrees = {sum(map(int, term["exponents"])) for term in terms}
    characters = {
        sum(
            exponent * weight
            for exponent, weight in zip(term["exponents"], CHARACTER_WEIGHTS, strict=True)
        )
        % CHARACTER_MODULUS
        for term in terms
    }
    if degrees != {4} or characters != {4}:
        raise ValueError("frozen h is not the expected degree-four, character-four form")

    h_mod_p = render_modular_polynomial(terms, variables, arguments.characteristic)
    generators = [render(equation) for equation in equations] + [h_mod_p, render(open_factor)]
    source = "\n".join(
        [",".join(map(str, variables)), str(arguments.characteristic)]
        + [
            generator + ("," if index + 1 < len(generators) else "")
            for index, generator in enumerate(generators)
        ]
    ) + "\n"

    stem = f"j2-secant-r10-residual-colon-p{arguments.characteristic}"
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
    environment["MSOLVE_DUMP_FIRST_KERNEL"] = "1"
    environment["MSOLVE_KERNEL_DUMP_PATH"] = str(tap_path)
    environment["MSOLVE_STOP_AFTER_FIRST_KERNEL"] = "1"
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
    kernel_polynomials = []
    tap_error = None
    if tap_path.is_file():
        try:
            kernel_polynomials = parse_tap(
                tap_path, arguments.characteristic, len(variables)
            )
            tap_valid = bool(kernel_polynomials)
        except ValueError as error:
            tap_error = str(error)

    if timed_out:
        status = "INCOMPLETE_TIMEOUT_NO_DECISION"
    elif process.returncode != 0:
        status = "INCOMPLETE_SOLVER_ERROR_NO_DECISION"
    elif tap_valid:
        status = "CANDIDATE_MODULAR_RESIDUAL_COLON_KERNEL_EXTRACTED"
    else:
        status = "NO_FURTHER_KERNEL_OBSERVED_IN_COMPLETED_MODULAR_RUN"

    artifact_paths = [input_path, stdout_path, stderr_path]
    if tap_path.is_file():
        artifact_paths.append(tap_path)
    if solver_output_path.is_file():
        artifact_paths.append(solver_output_path)
    actual_binary = msolve_root / ".libs" / "msolve"
    result = {
        "schema": "hc4.decimic-j2-secant-r10-residual-colon-scout.v1",
        "status": status,
        "assurance": "bounded exact finite-field discovery only",
        "characteristic": arguments.characteristic,
        "ideal": "I1=(17 retained homogeneous normal cubics, h)",
        "saturating_element": "M=f9*f10*(2*f9^2+5*f10*g0)",
        "colon_question": "first new class in (I1:M)/I1",
        "variable_names": list(map(str, variables)),
        "generator_order": [f"F{index + 1}" for index in range(len(equations))] + ["h", "M"],
        "normal_generator_count": len(equations),
        "h": {
            "source_artifact": str(quartic_path),
            "source_artifact_sha256": sha256(quartic_path),
            "source_expression_sha256": quartic_data["h_expression_sha256"],
            "primitive_term_count": len(terms),
            "total_degree": 4,
            "character_weight_mod_12": 4,
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
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "A kernel-emitted status identifies only a finite-field residual-colon "
            "candidate produced by the instrumented saturation algorithm. It does "
            "not independently prove membership, lift the candidate to QQ, compute "
            "the full colon or saturation, establish a unit, or close the secant chart. "
            "A timeout or solver error makes no mathematical decision."
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
