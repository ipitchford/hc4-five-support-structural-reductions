#!/usr/bin/env sage-python
"""Certify ``M*h in I`` by Singular's target-directed ``lift``.

Unlike the companion ``liftstd`` experiment, this script does not retain a
transformation matrix for every element of a standard basis.  It asks Singular
directly for multipliers expressing the single degree-eight target ``M*h`` in
terms of the original 17 cubics.  A passing receipt requires both Singular's
matrix identity and an independent SymPy replay of the printed multipliers in
the same finite field.

This script is deliberately finite-field only.  A PASS is an exact modular
identity, not a characteristic-zero colon certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_colon_identity_liftstd import (
    RECONSTRUCTION_PRIMES,
    marker,
    reconstruct_quartic,
    render_in_field,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)
from singular_process import run_singular_process


def singular_source(
    equations,
    target: sp.Expr,
    variables,
    characteristic: int,
    algorithm: str,
    degree_bound: int,
) -> str:
    """Render the target-directed Singular lift and its in-process checks."""

    variable_source = ",".join(map(str, variables))
    generators = ",".join(
        render_in_field(equation, variables, characteristic) for equation in equations
    )
    target_source = render_in_field(target, variables, characteristic)
    return "\n".join(
        [
            f"ring r={characteristic},({variable_source}),dp;",
            "option(redSB);",
            f"degBound={degree_bound};",
            "ideal I=" + generators + ";",
            "poly H=" + target_source + ";",
            "ideal K=H;",
            "matrix U;",
            f'matrix V=lift(I,K,U,"{algorithm}");',
            'print("UNIT_ROWS");',
            "nrows(U);",
            'print("UNIT_COLUMNS");',
            "ncols(U);",
            'print("UNIT_ENTRY");',
            "U[1,1];",
            'print("MULTIPLIER_ROWS");',
            "nrows(V);",
            'print("MULTIPLIER_COLUMNS");',
            "ncols(V);",
            'print("SCALED_IDENTITY_ZERO");',
            "matrix(K)*U-matrix(I)*V==0;",
            'print("UNSCALED_IDENTITY_ZERO");',
            "matrix(K)-matrix(I)*V==0;",
            'print("MULTIPLIERS_BEGIN");',
            'for (int k=1; k<=nrows(V); k++) { print("Q"+string(k)+"="+string(V[k,1])); }',
            'print("MULTIPLIERS_END");',
            "exit;",
        ]
    ) + "\n"


def multiplier_lines(output: str) -> list[str]:
    """Extract the deliberately delimited Singular multiplier stream."""

    begin_marker = "MULTIPLIERS_BEGIN\n"
    begin = output.find(begin_marker)
    end = output.find("\nMULTIPLIERS_END", begin + 1) if begin >= 0 else -1
    if begin < 0 or end < 0:
        return []
    return output[begin + len(begin_marker) : end].splitlines()


def parse_multiplier_line(
    line: str,
    expected_index: int,
    variables,
    characteristic: int,
) -> sp.Poly:
    """Parse one ``Qk=...`` line as a polynomial over ``GF(p)``."""

    prefix = f"Q{expected_index}="
    if not line.startswith(prefix):
        raise ValueError(f"expected {prefix!r}, received {line[:40]!r}")
    expression_source = line[len(prefix) :].replace("^", "**")
    local_symbols = {str(variable): variable for variable in variables}
    expression = sp.sympify(expression_source, locals=local_symbols)
    return sp.Poly(expression, *variables, modulus=characteristic)


def replay_identity(
    lines: list[str],
    equations,
    target: sp.Expr,
    variables,
    characteristic: int,
) -> dict[str, object]:
    """Replay printed Singular multipliers in an independent polynomial engine."""

    try:
        multipliers = [
            parse_multiplier_line(line, index, variables, characteristic)
            for index, line in enumerate(lines, start=1)
        ]
        if len(multipliers) != len(equations):
            raise ValueError("multiplier count does not match generator count")
        target_polynomial = sp.Poly(target, *variables, modulus=characteristic)
        reconstruction = sp.Poly(0, *variables, modulus=characteristic)
        for equation, multiplier in zip(equations, multipliers, strict=True):
            reconstruction += sp.Poly(
                equation, *variables, modulus=characteristic
            ) * multiplier
        remainder = target_polynomial - reconstruction
        nonzero = [multiplier for multiplier in multipliers if not multiplier.is_zero]
        return {
            "completed": True,
            "identity_zero": remainder.is_zero,
            "remainder_term_count": len(remainder.terms()) if not remainder.is_zero else 0,
            "multiplier_count": len(multipliers),
            "nonzero_multiplier_count": len(nonzero),
            "multiplier_term_count": sum(len(multiplier.terms()) for multiplier in multipliers),
            "maximum_multiplier_total_degree": (
                max(multiplier.total_degree() for multiplier in nonzero) if nonzero else None
            ),
        }
    except (ValueError, TypeError, SyntaxError, sp.SympifyError) as error:
        return {
            "completed": False,
            "identity_zero": False,
            "error": f"{type(error).__name__}: {error}",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=103)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--degree-bound", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 0 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a positive prime")
    if arguments.characteristic in RECONSTRUCTION_PRIMES:
        parser.error("use a prime independent of the two reconstruction primes")
    if arguments.degree_bound < 8 or arguments.timeout < 1:
        parser.error("degree bound must be at least eight and timeout positive")

    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    equations, variables, _, open_factor = homogeneous_saturation_system()
    quartic, reconstruction = reconstruct_quartic(campaign, variables)
    target = sp.expand(open_factor * quartic)
    target_polynomial = sp.Poly(target, *variables, domain=sp.QQ)
    if target_polynomial.total_degree() != 8:
        raise AssertionError("M*h is not homogeneous of degree eight")

    source = singular_source(
        equations,
        target,
        variables,
        arguments.characteristic,
        arguments.algorithm,
        arguments.degree_bound,
    )
    raw = run_singular_process(source, arguments.timeout)
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    lines = multiplier_lines(stdout)
    replay = replay_identity(
        lines,
        equations,
        target,
        variables,
        arguments.characteristic,
    )

    unit_rows = marker(stdout, "UNIT_ROWS")
    unit_columns = marker(stdout, "UNIT_COLUMNS")
    unit_entry = marker(stdout, "UNIT_ENTRY")
    multiplier_rows = marker(stdout, "MULTIPLIER_ROWS")
    multiplier_columns = marker(stdout, "MULTIPLIER_COLUMNS")
    scaled_identity_zero = marker(stdout, "SCALED_IDENTITY_ZERO") == "1"
    unscaled_identity_zero = marker(stdout, "UNSCALED_IDENTITY_ZERO") == "1"
    passed = (
        not raw["timed_out"]
        and raw["return_code"] == 0
        and unit_rows == "1"
        and unit_columns == "1"
        and unit_entry == "1"
        and multiplier_rows == str(len(equations))
        and multiplier_columns == "1"
        and len(lines) == len(equations)
        and scaled_identity_zero
        and unscaled_identity_zero
        and replay.get("completed") is True
        and replay.get("identity_zero") is True
        and not stderr.strip()
    )

    field = f"p{arguments.characteristic}"
    certificate_output = arguments.certificate_output or Path(
        f"artifacts/j2-secant-r10-colon-identity-direct-lift-{field}.json"
    )
    if not certificate_output.is_absolute():
        certificate_output = campaign / certificate_output
    certificate_sha256 = None
    if passed:
        certificate_payload = {
            "schema": "hc4.decimic-j2-secant-r10-colon-identity-direct-lift-certificate.v1",
            "characteristic": arguments.characteristic,
            "variable_names": [str(variable) for variable in variables],
            "generator_count": len(equations),
            "normal_equation_stream_sha256": digest(tuple(equations)),
            "target_sha256": hashlib.sha256(sp.srepr(target).encode("utf-8")).hexdigest(),
            "unit_matrix": [[1]],
            "multipliers": [line.split("=", 1)[1] for line in lines],
            "singular_identity_verified": True,
            "sympy_identity_verified": True,
            "claim_boundary": (
                "Exact identity over the displayed finite field only; this is not "
                "a characteristic-zero identity or a saturation/HC4 certificate."
            ),
        }
        certificate_text = json.dumps(certificate_payload, indent=2, sort_keys=True) + "\n"
        certificate_output.parent.mkdir(parents=True, exist_ok=True)
        certificate_output.write_text(certificate_text, encoding="ascii")
        certificate_sha256 = hashlib.sha256(certificate_text.encode("ascii")).hexdigest()

    status = "PASS_EXACT_MODULAR_DIRECT_COLON_IDENTITY" if passed else "INCOMPLETE_DIRECT_COLON_IDENTITY_LIFT"
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-identity-direct-lift.v1",
        "status": status,
        "assurance": "exact finite-field polynomial identity only" if passed else "solver telemetry only",
        "characteristic": arguments.characteristic,
        "algorithm": (
            f"Singular degBound={arguments.degree_bound} "
            f'lift(I,K,U,"{arguments.algorithm}") plus independent SymPy replay'
        ),
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "claim": "M*h lies in the ideal generated by the 17 homogeneous cubics",
        "normal_generator_count": len(equations),
        "variable_names": [str(variable) for variable in variables],
        "quartic_reconstruction": reconstruction,
        "open_factor_M": str(open_factor),
        "target_total_degree": target_polynomial.total_degree(),
        "target_term_count": len(target_polynomial.terms()),
        "target_sha256": hashlib.sha256(sp.srepr(target).encode("utf-8")).hexdigest(),
        "unit_matrix_shape": [
            None if unit_rows is None else int(unit_rows),
            None if unit_columns is None else int(unit_columns),
        ],
        "unit_entry": unit_entry,
        "multiplier_matrix_shape": [
            None if multiplier_rows is None else int(multiplier_rows),
            None if multiplier_columns is None else int(multiplier_columns),
        ],
        "scaled_identity_verified": scaled_identity_zero,
        "unscaled_identity_verified": unscaled_identity_zero,
        "independent_sympy_replay": replay,
        "multiplier_certificate": (
            None
            if not passed
            else {
                "path": str(certificate_output),
                "sha256": certificate_sha256,
                "multiplier_count": len(lines),
            }
        ),
        "calculation": {
            **raw,
            "stdout_tail": stdout[-12000:],
            "stderr_tail": stderr[-4000:],
        },
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            str(script_path.relative_to(campaign)): hashlib.sha256(script_path.read_bytes()).hexdigest(),
            "scripts/certify_j2_secant_r10_colon_identity_liftstd.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_colon_identity_liftstd.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "A PASS proves the displayed identity over one finite field only. It does "
            "not prove the reconstructed rational identity over QQ, determine the full "
            "colon or saturated ideal, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-colon-identity-direct-lift-{field}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": status,
                "output": str(output),
                "unit_entry": unit_entry,
                "scaled_identity_zero": scaled_identity_zero,
                "unscaled_identity_zero": unscaled_identity_zero,
                "sympy_replay_zero": replay.get("identity_zero"),
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
