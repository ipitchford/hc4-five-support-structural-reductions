#!/usr/bin/env python3
"""Extract and audit the first modular colon kernel in the open secant chart.

The discovery backend is a narrowly instrumented build of msolve 0.10.1.  Its
output is treated only as a candidate until the polynomial is replayed by a
separate ideal-membership calculation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

import sympy as sp
from sage.all import GF, matrix, vector

from certify_j2_secant_r10_z12_macaulay import (
    CHARACTER_MODULUS,
    CHARACTER_WEIGHTS,
    character_weight,
)
from scout_decimic_nullcone_hsop import digest
from scout_j2_secant_r10_homogeneous_saturation import (
    homogeneous_saturation_system,
    render,
)


TAP_HEADER = "MSOLVE_COLON_KERNEL_V1"
EXPECTED_TAP_RETURN_CODE = 86


def parse_tap(path: Path) -> dict:
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines:
        raise ValueError("empty colon-kernel tap")
    header = lines[0].split()
    if len(header) != 4 or header[0] != TAP_HEADER:
        raise ValueError("unrecognized colon-kernel tap header")
    characteristic, variable_count, polynomial_count = map(int, header[1:])
    position = 1
    polynomials = []
    for _ in range(polynomial_count):
        fields = lines[position].split()
        position += 1
        if len(fields) != 4 or fields[0] != "POLY":
            raise ValueError("missing POLY record")
        basis_index, reported_degree, term_count = map(int, fields[1:])
        terms = []
        for _ in range(term_count):
            fields = lines[position].split()
            position += 1
            if fields[0] != "TERM" or len(fields) != variable_count + 2:
                raise ValueError("malformed TERM record")
            coefficient = int(fields[1]) % characteristic
            exponents = tuple(map(int, fields[2:]))
            terms.append((exponents, coefficient))
        if lines[position] != "ENDPOLY":
            raise ValueError("missing ENDPOLY record")
        position += 1
        polynomials.append(
            {
                "basis_index": basis_index,
                "reported_degree": reported_degree,
                "terms": terms,
            }
        )
    if position >= len(lines) or lines[position] != "END":
        raise ValueError("missing tap terminator")
    if position + 1 != len(lines):
        raise ValueError("trailing colon-kernel tap data")
    return {
        "characteristic": characteristic,
        "variable_count": variable_count,
        "polynomials": polynomials,
    }


def expression_from_terms(terms, variables, characteristic: int) -> sp.Expr:
    expression = sp.Integer(0)
    for exponents, coefficient in terms:
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += (coefficient % characteristic) * monomial
    return sp.expand(expression)


def term_list(expression: sp.Expr, variables) -> list[tuple[tuple[int, ...], sp.Rational]]:
    polynomial = sp.Poly(expression, *variables, domain=sp.QQ)
    return [
        (tuple(map(int, exponents)), coefficient)
        for exponents, coefficient in polynomial.terms()
    ]


def degree_four_membership_test(
    candidate_terms,
    equations,
    variables,
    characteristic: int,
    candidate_character: int,
) -> dict:
    """Test whether a degree-four candidate was already in I_4."""

    field = GF(characteristic)
    rows = []
    row_terms = []
    monomial_set = {exponents for exponents, _ in candidate_terms}
    for generator_index, equation in enumerate(equations):
        generator_terms = term_list(equation, variables)
        generator_character = character_weight(generator_terms[0][0])
        for variable_index in range(len(variables)):
            multiplier = tuple(
                1 if index == variable_index else 0
                for index in range(len(variables))
            )
            if (
                generator_character + character_weight(multiplier)
            ) % CHARACTER_MODULUS != candidate_character:
                continue
            products = []
            for exponents, coefficient in generator_terms:
                product = tuple(
                    left + right
                    for left, right in zip(exponents, multiplier, strict=True)
                )
                products.append((product, coefficient))
                monomial_set.add(product)
            rows.append((generator_index, multiplier))
            row_terms.append(products)

    monomials = sorted(monomial_set)
    monomial_index = {monomial: index for index, monomial in enumerate(monomials)}
    entries = {}
    for row_index, products in enumerate(row_terms):
        for exponents, coefficient in products:
            value = field(int(coefficient.p)) / field(int(coefficient.q))
            column_index = monomial_index[exponents]
            entries[(row_index, column_index)] = (
                entries.get((row_index, column_index), field.zero()) + value
            )
    macaulay = matrix(field, len(rows), len(monomials), entries, sparse=True)
    target_entries = {
        monomial_index[exponents]: field(int(coefficient))
        for exponents, coefficient in candidate_terms
        if coefficient % characteristic
    }
    target = vector(field, len(monomials), target_entries, sparse=True)
    try:
        solution = macaulay.solve_left(target)
        in_ideal = solution * macaulay == target
    except ValueError:
        solution = None
        in_ideal = False
    return {
        "row_count": len(rows),
        "column_count": len(monomials),
        "nonzero_count": len(entries),
        "candidate_in_degree_four_ideal_piece": bool(in_ideal),
        "nontrivial_quotient_class": not bool(in_ideal),
        "solution_support_count": 0 if solution is None else len(solution.dict()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--msolve", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--tap-output", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if arguments.threads < 1 or arguments.timeout < 1:
        parser.error("threads and timeout must be positive")
    msolve = arguments.msolve.resolve()
    if not msolve.is_file() or not os.access(msolve, os.X_OK):
        parser.error("--msolve must name the instrumented executable")

    started = time.perf_counter()
    equations, variables, _, open_factor = homogeneous_saturation_system()
    campaign = Path(__file__).resolve().parent.parent
    tap_output = arguments.tap_output
    if tap_output is None:
        tap_output = campaign / "research" / (
            f"j2_secant_r10_colon_kernel_tap_p{arguments.characteristic}.txt"
        )
    elif not tap_output.is_absolute():
        tap_output = campaign / tap_output
    tap_output.parent.mkdir(parents=True, exist_ok=True)

    generators = equations + [open_factor]
    source_lines = [
        ",".join(map(str, variables)),
        str(arguments.characteristic),
    ]
    source_lines.extend(
        render(expression) + ("," if index + 1 < len(generators) else "")
        for index, expression in enumerate(generators)
    )
    source = "\n".join(source_lines) + "\n"
    solver_started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="hc4-colon-kernel-") as directory:
        directory_path = Path(directory)
        input_path = directory_path / "system.ms"
        output_path = directory_path / "solver.out"
        input_path.write_text(source, encoding="ascii")
        environment = os.environ.copy()
        environment["MSOLVE_COLON_KERNEL_OUT"] = str(tap_output)
        try:
            process = subprocess.run(
                [
                    str(msolve),
                    "-f",
                    str(input_path),
                    "-o",
                    str(output_path),
                    "-S",
                    "-g",
                    "2",
                    "-v",
                    "2",
                    "-t",
                    str(arguments.threads),
                    "--random-seed",
                    "0",
                ],
                capture_output=True,
                check=False,
                env=environment,
                text=True,
                timeout=arguments.timeout,
            )
            timed_out = False
            return_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as error:
            timed_out = True
            return_code = None
            stdout = error.stdout or ""
            stderr = error.stderr or ""
    solver_seconds = time.perf_counter() - solver_started

    if timed_out or return_code != EXPECTED_TAP_RETURN_CODE or not tap_output.is_file():
        raise RuntimeError(
            "instrumented saturation did not emit a first colon kernel: "
            f"timeout={timed_out}, return_code={return_code}"
        )
    tap = parse_tap(tap_output)
    if tap["characteristic"] != arguments.characteristic:
        raise AssertionError("tap characteristic mismatch")
    if tap["variable_count"] != len(variables):
        raise AssertionError("tap variable-count mismatch")

    candidates = []
    for polynomial in tap["polynomials"]:
        terms = polynomial["terms"]
        degrees = {sum(exponents) for exponents, _ in terms}
        characters = {character_weight(exponents) for exponents, _ in terms}
        expression = expression_from_terms(terms, variables, arguments.characteristic)
        canonical_terms = [
            (exponents, int(coefficient) % arguments.characteristic)
            for exponents, coefficient in term_list(expression, variables)
            if int(coefficient) % arguments.characteristic
        ]
        if len(degrees) != 1 or len(characters) != 1 or not canonical_terms:
            raise AssertionError("tap emitted a nonhomogeneous or zero polynomial")
        degree = next(iter(degrees))
        character = next(iter(characters))
        membership = degree_four_membership_test(
            canonical_terms,
            equations,
            variables,
            arguments.characteristic,
            character,
        )
        candidates.append(
            {
                "basis_index": polynomial["basis_index"],
                "reported_degree": polynomial["reported_degree"],
                "reconstructed_total_degree": degree,
                "character_weight": character,
                "term_count": len(canonical_terms),
                "terms": [
                    {"exponents": list(exponents), "coefficient": coefficient}
                    for exponents, coefficient in canonical_terms
                ],
                "expression_mod_p": str(expression),
                "degree_four_membership_test": membership,
                "expression_sha256": digest((expression,)),
            }
        )

    nontrivial = [
        candidate
        for candidate in candidates
        if candidate["reconstructed_total_degree"] == 4
        and candidate["degree_four_membership_test"]["nontrivial_quotient_class"]
    ]
    script_path = Path(__file__).resolve()
    patch_path = campaign / "research" / "msolve_colon_kernel_tap_v0.10.1.patch"
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-kernel-candidate.v1",
        "status": (
            "CANDIDATE_MODULAR_COLON_KERNEL_EXTRACTED"
            if nontrivial
            else "NO_NONTRIVIAL_DEGREE_FOUR_KERNEL_IN_TAP"
        ),
        "assurance": "exact finite-field candidate extraction; independent M*h membership replay pending",
        "characteristic": arguments.characteristic,
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "colon_target": "(I:M)_4 / I_4",
        "variable_names": [str(variable) for variable in variables],
        "character_modulus": CHARACTER_MODULUS,
        "character_weights": list(CHARACTER_WEIGHTS),
        "open_factor_character_weight": character_weight(
            term_list(open_factor, variables)[0][0]
        ),
        "candidate_count": len(candidates),
        "nontrivial_degree_four_candidate_count": len(nontrivial),
        "candidates": candidates,
        "discovery": {
            "backend": "instrumented msolve F4 saturation",
            "upstream_version": "0.10.1",
            "executable": str(msolve),
            "expected_tap_return_code": EXPECTED_TAP_RETURN_CODE,
            "actual_return_code": return_code,
            "timed_out": timed_out,
            "threads": arguments.threads,
            "random_seed": 0,
            "solver_seconds": solver_seconds,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-12000:],
            "msolve_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
            "tap_path": str(tap_output),
            "tap_sha256": hashlib.sha256(tap_output.read_bytes()).hexdigest(),
        },
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "open_factor_sha256": digest((open_factor,)),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/certify_j2_secant_r10_colon_kernel.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "research/msolve_colon_kernel_tap_v0.10.1.patch": hashlib.sha256(
                patch_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "This file records a finite-field colon candidate and proves only that "
            "its degree-four class is nonzero modulo the original cubic span. It "
            "does not yet independently replay M*h in I, prove a characteristic-zero "
            "colon identity, decide saturation, or close the secant chart."
        ),
    }
    output = arguments.output or Path(
        f"research/j2_secant_r10_colon_kernel_candidate_p{arguments.characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if nontrivial else 1


if __name__ == "__main__":
    raise SystemExit(main())
