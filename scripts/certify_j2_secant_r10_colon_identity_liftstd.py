#!/usr/bin/env sage-python
"""Seek a proof-producing degree-eight identity ``M*h in I``.

The quartic ``h`` is rationally reconstructed from two independently tapped
finite-field F4SAT kernels.  Singular is then asked for a degree-bounded
standard basis together with its transformation matrix.  A passing run must
compose the lift back to the original 17 cubics and verify the resulting
polynomial identity inside Singular.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp
from sage.all import ZZ, crt

from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
)
from singular_process import run_singular_process


RECONSTRUCTION_PRIMES = (1073741827, 1073742851)


def candidate_terms(path: Path) -> tuple[int, dict[tuple[int, ...], int]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    characteristic = int(payload["characteristic"])
    candidates = payload["candidates"]
    if len(candidates) != 1:
        raise AssertionError("expected exactly one tapped colon candidate")
    candidate = candidates[0]
    if candidate["reconstructed_total_degree"] != 4:
        raise AssertionError("the tapped candidate is not quartic")
    terms = {
        tuple(map(int, term["exponents"])): int(term["coefficient"])
        for term in candidate["terms"]
    }
    if len(terms) != int(candidate["term_count"]):
        raise AssertionError("duplicate exponent vectors in tapped candidate")
    return characteristic, terms


def reconstruct_quartic(campaign: Path, variables) -> tuple[sp.Expr, dict[str, object]]:
    modular = []
    source_hashes = {}
    for characteristic in RECONSTRUCTION_PRIMES:
        path = campaign / "research" / (
            f"j2_secant_r10_colon_kernel_candidate_p{characteristic}.json"
        )
        observed_characteristic, terms = candidate_terms(path)
        if observed_characteristic != characteristic:
            raise AssertionError("candidate receipt characteristic mismatch")
        modular.append(terms)
        source_hashes[str(path.relative_to(campaign))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    if modular[0].keys() != modular[1].keys():
        raise AssertionError("reconstruction-prime supports differ")

    modulus = ZZ(RECONSTRUCTION_PRIMES[0] * RECONSTRUCTION_PRIMES[1])
    rational_terms = {}
    expression = sp.Integer(0)
    for exponents in modular[0]:
        residue = ZZ(
            crt(
                [modular[0][exponents], modular[1][exponents]],
                list(RECONSTRUCTION_PRIMES),
            )
        )
        coefficient = residue.rational_reconstruction(modulus)
        rational = sp.Rational(int(coefficient.numerator()), int(coefficient.denominator()))
        rational_terms[exponents] = rational
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += rational * monomial
    expression = sp.expand(expression)
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    if polynomial.total_degree() != 4 or len(polynomial.terms()) != 189:
        raise AssertionError("unexpected reconstructed quartic profile")
    denominators = [coefficient.q for _, coefficient in polynomial.terms()]
    numerators = [abs(coefficient.p) for _, coefficient in polynomial.terms()]
    return expression, {
        "reconstruction_primes": list(RECONSTRUCTION_PRIMES),
        "crt_modulus": int(modulus),
        "term_count": len(polynomial.terms()),
        "total_degree": polynomial.total_degree(),
        "common_denominator_lcm": int(sp.ilcm(*denominators)),
        "maximum_absolute_numerator": int(max(numerators)),
        "maximum_denominator": int(max(denominators)),
        "expression_sha256": hashlib.sha256(
            sp.srepr(expression).encode("utf-8")
        ).hexdigest(),
        "candidate_receipt_sha256": source_hashes,
    }


def render_in_field(expression: sp.Expr, variables, characteristic: int) -> str:
    polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    pieces = []
    for exponents, coefficient in polynomial.terms():
        if characteristic == 0:
            scalar = sp.Rational(coefficient)
            scalar_text = str(scalar)
        else:
            numerator = int(coefficient.p) % characteristic
            denominator = pow(int(coefficient.q), -1, characteristic)
            scalar_text = str((numerator * denominator) % characteristic)
        monomial = "*".join(
            str(variable) if exponent == 1 else f"{variable}^{exponent}"
            for variable, exponent in zip(variables, exponents, strict=True)
            if exponent
        )
        pieces.append(scalar_text + ("*" + monomial if monomial else ""))
    return "+".join(pieces) if pieces else "0"


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def singular_source(
    equations,
    target: sp.Expr,
    variables,
    characteristic: int,
    algorithm: str,
    degree_bound: int,
) -> str:
    variable_source = ",".join(map(str, variables))
    generators = ",".join(
        render_in_field(equation, variables, characteristic) for equation in equations
    )
    target_source = render_in_field(target, variables, characteristic)
    lines = [
        f"ring r={characteristic},({variable_source}),dp;",
        "option(redSB);",
        f"degBound={degree_bound};",
        "ideal I=" + generators + ";",
        "poly H=" + target_source + ";",
        "matrix T;",
        f'ideal J=liftstd(I,T,"{algorithm}");',
        'print("TRUNCATED_BASIS_SIZE");',
        "size(J);",
        'print("TRUNCATED_BASIS_MAX_DEGREE");',
        "maxdeg(J);",
        "ideal K=H;",
        "matrix C=lift(J,K);",
        "matrix V=T*C;",
        "matrix D=matrix(K)-matrix(I)*V;",
        'print("TARGET_REMAINDER");',
        "reduce(H,J);",
        'print("ORIGINAL_IDENTITY_ZERO");',
        "D==0;",
        'print("MULTIPLIER_ROWS");',
        "nrows(V);",
        'print("MULTIPLIER_COLUMNS");',
        "ncols(V);",
        'print("MULTIPLIERS_BEGIN");',
        "for (int k=1; k<=nrows(V); k++) { print(\"Q\"+string(k)+\"=\"+string(V[k,1])); }",
        'print("MULTIPLIERS_END");',
        "exit;",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--degree-bound", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--certificate-output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic < 0 or (
        arguments.characteristic > 0 and not sp.isprime(arguments.characteristic)
    ):
        parser.error("characteristic must be zero or prime")
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
    identity_zero = marker(stdout, "ORIGINAL_IDENTITY_ZERO") == "1"
    target_remainder = marker(stdout, "TARGET_REMAINDER")
    multiplier_rows = marker(stdout, "MULTIPLIER_ROWS")
    multiplier_columns = marker(stdout, "MULTIPLIER_COLUMNS")
    begin = stdout.find("MULTIPLIERS_BEGIN\n")
    end = stdout.find("\nMULTIPLIERS_END", begin + 1) if begin >= 0 else -1
    multiplier_lines = []
    if begin >= 0 and end >= 0:
        multiplier_lines = stdout[begin + len("MULTIPLIERS_BEGIN\n") : end].splitlines()
    passed = (
        not raw["timed_out"]
        and raw["return_code"] == 0
        and identity_zero
        and target_remainder == "0"
        and multiplier_rows == str(len(equations))
        and multiplier_columns == "1"
        and len(multiplier_lines) == len(equations)
        and not stderr.strip()
    )

    field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
    certificate_output = arguments.certificate_output or Path(
        f"artifacts/j2-secant-r10-colon-identity-liftstd-{field}.txt"
    )
    if not certificate_output.is_absolute():
        certificate_output = campaign / certificate_output
    certificate_sha256 = None
    if passed:
        certificate_output.parent.mkdir(parents=True, exist_ok=True)
        certificate_text = "\n".join(multiplier_lines) + "\n"
        certificate_output.write_text(certificate_text, encoding="ascii")
        certificate_sha256 = hashlib.sha256(certificate_text.encode("ascii")).hexdigest()

    status = (
        "PASS_EXACT_QQ_COLON_IDENTITY"
        if passed and arguments.characteristic == 0
        else "PASS_MODULAR_COLON_IDENTITY"
        if passed
        else "INCOMPLETE_COLON_IDENTITY_LIFT"
    )
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-identity-liftstd.v1",
        "status": status,
        "assurance": (
            "exact characteristic-zero polynomial identity"
            if passed and arguments.characteristic == 0
            else "exact finite-field polynomial identity only"
            if passed
            else "solver telemetry only"
        ),
        "characteristic": arguments.characteristic,
        "algorithm": f"Singular degBound={arguments.degree_bound} liftstd/{arguments.algorithm} plus lift",
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
        "truncated_basis_size": marker(stdout, "TRUNCATED_BASIS_SIZE"),
        "truncated_basis_max_degree": marker(stdout, "TRUNCATED_BASIS_MAX_DEGREE"),
        "target_remainder": target_remainder,
        "original_generator_identity_verified": identity_zero,
        "multiplier_matrix_shape": [
            None if multiplier_rows is None else int(multiplier_rows),
            None if multiplier_columns is None else int(multiplier_columns),
        ],
        "multiplier_certificate": (
            None
            if not passed
            else {
                "path": str(certificate_output),
                "sha256": certificate_sha256,
                "line_count": len(multiplier_lines),
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
            "scripts/certify_j2_secant_r10_colon_identity_liftstd.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest()
        },
        "claim_boundary": (
            "A characteristic-zero PASS proves only the displayed colon identity. "
            "A finite-field PASS is modular evidence only. Neither alone proves the "
            "full saturation is the unit ideal, secant containment, or HC4."
        ),
    }
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-colon-identity-liftstd-{field}.json"
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
                "target_remainder": target_remainder,
                "identity_zero": identity_zero,
                "basis_size": result["truncated_basis_size"],
                "wall_seconds": result["wall_seconds"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
