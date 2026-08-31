#!/usr/bin/env python3
"""Run one bounded target-normalized secant V2 highest-coordinate scout.

The exact torus receipt proves that ``V2_highest != 0`` is represented by the
single equation ``V2_highest = 1``.  This producer deliberately adds no
Rabinowitsch inverse.  A finite-field unit or proper ideal is exact only in the
stated characteristic; a timeout is telemetry only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, render
from scout_five_support import g_coefficients
from scout_nullcone_cubic_families import raw_coefficient_family
from singular_process import run_singular_process


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def marked_block(output: str, start: str, end: str) -> str | None:
    start_token = start + "\n"
    end_token = "\n" + end
    start_position = output.find(start_token)
    if start_position < 0:
        return None
    start_position += len(start_token)
    end_position = output.find(end_token, start_position)
    if end_position < 0:
        return None
    return output[start_position:end_position].rstrip() + "\n"


def swap_used_bytes() -> int | None:
    process = subprocess.run(
        ["sysctl", "-n", "vm.swapusage"],
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return None
    match = re.search(r"used = ([0-9.]+)([KMG])", process.stdout)
    if not match:
        return None
    value = float(match.group(1))
    multiplier = {"K": 1024, "M": 1024**2, "G": 1024**3}[match.group(2)]
    return round(value * multiplier)


def singular_source(
    equations: list[sp.Expr],
    normalized_target: sp.Expr,
    variables: tuple[sp.Symbol, ...],
    characteristic: int,
    algorithm: str,
) -> str:
    variable_source = ",".join(map(str, variables))
    generators = equations + [normalized_target]
    basis_command = "std(I)" if algorithm == "std" else "slimgb(I)"
    return "\n".join(
        [
            f"ring r={characteristic},({variable_source}),dp;",
            "option(redSB);",
            "ideal I=" + ",".join(render(expression) for expression in generators) + ";",
            f"ideal J={basis_command};",
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            'print("SURVIVOR_BASIS_BEGIN");',
            "J;",
            'print("SURVIVOR_BASIS_END");',
            "exit;",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/nullcone-v2-secant-target-normalized-p101.json"),
    )
    parser.add_argument(
        "--source-artifact",
        type=Path,
        default=Path("artifacts/nullcone-v2-secant-target-normalized-p101.sing"),
    )
    parser.add_argument(
        "--basis-artifact",
        type=Path,
        default=Path("artifacts/nullcone-v2-secant-target-normalized-p101-basis.txt"),
    )
    arguments = parser.parse_args()
    if arguments.characteristic != 101:
        parser.error("this frozen bounded unit is restricted to characteristic 101")
    if arguments.timeout != 120:
        parser.error("this frozen bounded unit is restricted to the 120-second cap")
    if not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be prime")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    source_artifact = (
        arguments.source_artifact
        if arguments.source_artifact.is_absolute()
        else campaign / arguments.source_artifact
    )
    basis_artifact = (
        arguments.basis_artifact
        if arguments.basis_artifact.is_absolute()
        else campaign / arguments.basis_artifact
    )

    normalization_path = campaign / "receipts/nullcone-v2-secant-torus-normalization.json"
    normalization = json.loads(normalization_path.read_text(encoding="utf-8"))
    if normalization.get("status") != "PASS_EXACT_SECANT_V2_HIGHEST_TORUS_NORMALIZATION":
        raise AssertionError("the exact secant V2 normalization receipt is not passing")

    equations, equation_build_seconds = normal_equations("secant")
    target = sp.expand(raw_coefficient_family("V2"))
    if digest(tuple(equations)) != normalization.get("normal_equation_stream_sha256"):
        raise AssertionError("the secant normal-equation stream drifted after normalization")
    if digest((target,)) != normalization.get("target_sha256"):
        raise AssertionError("the V2 target drifted after normalization")
    normalized_target = sp.expand(target - 1)
    variables = f_coefficients + g_coefficients
    generators = equations + [normalized_target]
    source = singular_source(
        equations,
        normalized_target,
        variables,
        arguments.characteristic,
        arguments.algorithm,
    )
    source_artifact.parent.mkdir(parents=True, exist_ok=True)
    source_artifact.write_text(source + "\n", encoding="utf-8")

    swap_before = swap_used_bytes()
    calculation_started = time.perf_counter()
    raw = run_singular_process(source, arguments.timeout)
    calculation_wall_seconds = time.perf_counter() - calculation_started
    swap_after = swap_used_bytes()
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    diagnostic_error = (
        "error occurred" in stdout
        or "error occurred" in stderr
        or "expected ideal-expression" in stdout
        or "expected ideal-expression" in stderr
    )
    remainder = marker(stdout, "UNIT_REMAINDER")
    basis_size = marker(stdout, "BASIS_SIZE")
    basis_text = marked_block(stdout, "SURVIVOR_BASIS_BEGIN", "SURVIVOR_BASIS_END")
    completed = not raw["timed_out"] and raw["return_code"] == 0 and not diagnostic_error
    is_unit = completed and remainder == "0"

    basis_record: dict[str, object] | None = None
    if completed:
        if basis_text is None:
            diagnostic_error = True
            completed = False
            is_unit = False
        else:
            basis_artifact.parent.mkdir(parents=True, exist_ok=True)
            basis_artifact.write_text(basis_text, encoding="utf-8")
            basis_record = {
                "path": str(basis_artifact),
                "sha256": sha256(basis_artifact),
                "byte_count": basis_artifact.stat().st_size,
                "basis_size": basis_size,
                "exact_field": f"GF({arguments.characteristic})",
            }

    if diagnostic_error:
        status = "DIAGNOSTIC_FAILURE_RETAINED"
        disposition = "NO_MATHEMATICAL_INFERENCE"
    elif raw["timed_out"]:
        status = "TIMEOUT_RETAINED"
        disposition = "ROUTE_COST_EVIDENCE_ONLY"
    elif is_unit:
        status = "PASS_EXACT_MODULAR_SECANT_V2_HIGHEST_NORMALIZED_UNIT"
        disposition = "EXACT_GF101_RADICAL_CONTAINMENT_AND_QQ_ROUTE_SIGNAL"
    elif completed and basis_record is not None:
        status = "PASS_EXACT_MODULAR_SECANT_V2_HIGHEST_SURVIVOR_IDEAL"
        disposition = "EXACT_GF101_PROPER_SURVIVOR_IDEAL_RETAINED"
    else:
        status = "INCOMPLETE_MODULAR_CALCULATION_RETAINED"
        disposition = "NO_MATHEMATICAL_INFERENCE"

    rational_term_counts = [len(sp.Poly(expression, *variables).terms()) for expression in generators]
    modular_term_counts = [
        len(sp.Poly(expression, *variables, modulus=arguments.characteristic).terms())
        for expression in generators
    ]
    rendered_generators = [render(expression) for expression in generators]
    variable_payload = ",".join(map(str, variables)).encode("ascii")
    generator_payload = "\n".join(rendered_generators).encode("ascii")
    result = {
        "schema": "hc4.decimic-nullcone-v2-secant-target-normalized-modular.v1",
        "status": status,
        "disposition": disposition,
        "orbit": "secant",
        "family": "V2",
        "coordinate": "highest",
        "characteristic": arguments.characteristic,
        "algorithm": f"Singular {arguments.algorithm}",
        "timeout_seconds": arguments.timeout,
        "arithmetic_assurance": "deterministic exact arithmetic over GF(101)",
        "normalization": {
            "equation": "V2_highest-1",
            "rabinowitsch_inverse_used": False,
            "torus_character": 1,
            "exact_normalization_receipt": str(normalization_path),
            "exact_normalization_receipt_sha256": sha256(normalization_path),
            "preconditions_replayed": True,
        },
        "dimensions": {
            "variable_count": len(variables),
            "variable_names": [str(variable) for variable in variables],
            "normal_equation_count": len(equations),
            "normalization_equation_count": 1,
            "generator_count": len(generators),
            "maximum_total_degree": max(
                sp.Poly(expression, *variables).total_degree() for expression in generators
            ),
            "rational_term_counts": rational_term_counts,
            "modular_term_counts": modular_term_counts,
            "rational_total_terms": sum(rational_term_counts),
            "modular_total_terms": sum(modular_term_counts),
        },
        "hashes": {
            "normal_equation_stream_sha256": digest(tuple(equations)),
            "target_sha256": digest((target,)),
            "normalized_target_sha256": digest((normalized_target,)),
            "variable_stream_sha256": hashlib.sha256(variable_payload).hexdigest(),
            "generator_stream_sha256": hashlib.sha256(generator_payload).hexdigest(),
            "solver_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        },
        "solver_source": {
            "path": str(source_artifact),
            "sha256": sha256(source_artifact),
            "byte_count": source_artifact.stat().st_size,
        },
        "basis_artifact": basis_record,
        "calculation": {
            **raw,
            "diagnostic_error": diagnostic_error,
            "completed": completed,
            "unit_remainder": remainder,
            "basis_size": basis_size,
            "is_unit": is_unit,
            "calculation_wall_seconds": calculation_wall_seconds,
            "stdout_tail": stdout[-2000:],
            "stderr_tail": stderr[-2000:],
        },
        "resources": {
            "swap_used_bytes_before": swap_before,
            "swap_used_bytes_after": swap_after,
            "swap_growth_bytes": (
                None if swap_before is None or swap_after is None else swap_after - swap_before
            ),
            "maximum_rss_native_immediate_scope": raw.get(
                "maximum_rss_native_immediate_scope"
            ),
            "resource_note": raw.get("resource_accounting"),
        },
        "timings": {
            "equation_build_seconds": equation_build_seconds,
            "solver_wall_seconds": raw.get("wall_seconds"),
            "total_wall_seconds": time.perf_counter() - started,
        },
        "conditional_exact_qq_lift_interface": {
            "ring": "Q[f0,...,f10,g0,...,g9]",
            "generators": "the same 55 frozen secant normal equations plus V2_highest-1",
            "variables": 21,
            "required_outcome": (
                "a deterministic characteristic-zero unit certificate or an explicit "
                "rational Bezout identity, replayed independently"
            ),
            "modular_unit_not_sufficient": True,
            "other_v2_coordinates_separate": True,
        },
        "source_sha256": {
            "scripts/scout_nullcone_v2_secant_target_normalized.py": sha256(script_path),
            "scripts/certify_nullcone_v2_secant_torus_normalization.py": sha256(
                script_path.parent / "certify_nullcone_v2_secant_torus_normalization.py"
            ),
            "scripts/scout_nullcone_cubic_families.py": sha256(
                script_path.parent / "scout_nullcone_cubic_families.py"
            ),
            "scripts/scout_decimic_nullcone_hsop.py": sha256(
                script_path.parent / "scout_decimic_nullcone_hsop.py"
            ),
            "scripts/singular_process.py": sha256(
                script_path.parent / "singular_process.py"
            ),
        },
        "claim_boundary": (
            "A modular unit proves only that the normalized V2-highest nonvanishing "
            "locus is empty over the algebraic closure of GF(101), and is route "
            "evidence for characteristic zero. A retained nonunit basis proves only "
            "an exact modular survivor ideal. Neither outcome proves a QQ statement, "
            "the other V2 coordinates, secant nullcone containment, polynomial-level "
            "lifting, HC4, or the quartic Hessian conjecture. A timeout proves nothing "
            "beyond the recorded route cost."
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if status.startswith("PASS_") or status == "TIMEOUT_RETAINED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
