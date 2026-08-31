#!/usr/bin/env python3
"""Reconstruct and independently replay the first secant colon kernel."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

import sympy as sp
from sage.all import CRT, GF, Integer, lcm

from certify_j2_secant_r10_colon_kernel import degree_four_membership_test
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


def load_candidate(path: Path) -> tuple[int, dict[tuple[int, ...], int]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["status"] != "CANDIDATE_MODULAR_COLON_KERNEL_EXTRACTED":
        raise ValueError(f"{path} is not a passing candidate extraction")
    candidates = [
        candidate
        for candidate in data["candidates"]
        if candidate["reconstructed_total_degree"] == 4
        and candidate["degree_four_membership_test"]["nontrivial_quotient_class"]
    ]
    if len(candidates) != 1:
        raise ValueError(f"{path} does not contain exactly one nontrivial quartic")
    terms = {
        tuple(term["exponents"]): int(term["coefficient"])
        for term in candidates[0]["terms"]
    }
    return int(data["characteristic"]), terms


def reconstruct_coefficients(candidate_paths: list[Path]):
    loaded = [load_candidate(path) for path in candidate_paths]
    primes = [prime for prime, _ in loaded]
    supports = [set(terms) for _, terms in loaded]
    if any(support != supports[0] for support in supports[1:]):
        raise ValueError("candidate supports differ across discovery primes")
    modulus = Integer(1)
    for prime in primes:
        if modulus.gcd(prime) != 1:
            raise ValueError("discovery moduli are not pairwise coprime")
        modulus *= prime

    reconstructed = {}
    for exponents in sorted(supports[0]):
        residue = Integer(loaded[0][1][exponents])
        partial_modulus = Integer(primes[0])
        for prime, terms in loaded[1:]:
            residue = CRT(residue, Integer(terms[exponents]), partial_modulus, Integer(prime))
            partial_modulus *= prime
        coefficient = residue.rational_reconstruction(modulus)
        for prime, terms in loaded:
            field = GF(prime)
            reduced = field(coefficient.numerator()) / field(coefficient.denominator())
            if int(reduced) != terms[exponents] % prime:
                raise AssertionError("rational reconstruction failed residue replay")
        reconstructed[exponents] = coefficient
    return primes, modulus, reconstructed


def load_holdout_tsv(path: Path) -> dict[tuple[int, ...], int]:
    terms = {}
    expected_term_count = None
    for line in path.read_text(encoding="ascii").splitlines():
        fields = line.split("\t")
        if fields[0] == "polynomial":
            expected_term_count = int(fields[5])
        elif fields[0] == "term":
            coefficient = int(fields[1])
            exponents = tuple(map(int, fields[2:]))
            terms[exponents] = coefficient
    if expected_term_count is None or len(terms) != expected_term_count:
        raise ValueError("malformed held-out kernel TSV")
    return terms


def validate_holdout(
    path: Path,
    characteristic: int,
    reconstructed: dict,
) -> dict:
    held_out_terms = load_holdout_tsv(path)
    support_matches = set(held_out_terms) == set(reconstructed)
    mismatches = []
    if support_matches:
        field = GF(characteristic)
        for exponents, coefficient in reconstructed.items():
            reduced = field(coefficient.numerator()) / field(coefficient.denominator())
            if int(reduced) != held_out_terms[exponents] % characteristic:
                mismatches.append(list(exponents))
    return {
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "characteristic": characteristic,
        "role": "held out from CRT reconstruction",
        "term_count": len(held_out_terms),
        "support_matches": support_matches,
        "coefficient_mismatch_count": len(mismatches),
        "mismatch_exponents": mismatches,
        "all_coefficients_replay": support_matches and not mismatches,
        "terms": [
            {"exponents": list(exponents), "coefficient": coefficient}
            for exponents, coefficient in sorted(held_out_terms.items())
        ],
    }


def expression_from_rationals(terms, variables) -> sp.Expr:
    expression = sp.Integer(0)
    for exponents, coefficient in terms.items():
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += sp.Rational(
            int(coefficient.numerator()), int(coefficient.denominator())
        ) * monomial
    return sp.expand(expression)


def modular_terms(expression: sp.Expr, variables, characteristic: int):
    field = GF(characteristic)
    output = []
    for exponents, coefficient in sp.Poly(
        expression, *variables, domain=sp.QQ
    ).terms():
        residue = field(int(coefficient.p)) / field(int(coefficient.q))
        if residue:
            output.append((tuple(map(int, exponents)), int(residue)))
    return output


def expression_from_modular_terms(terms, variables) -> sp.Expr:
    expression = sp.Integer(0)
    for exponents, coefficient in terms:
        monomial = sp.Integer(1)
        for variable, exponent in zip(variables, exponents, strict=True):
            monomial *= variable**exponent
        expression += coefficient * monomial
    return sp.expand(expression)


def msolve_normal_form_replay(
    equations,
    target,
    variables,
    characteristic: int,
    executable: Path,
    threads: int,
    timeout: int,
) -> dict:
    modular_equations = [
        expression_from_modular_terms(
            modular_terms(equation, variables, characteristic), variables
        )
        for equation in equations
    ]
    modular_target = expression_from_modular_terms(
        modular_terms(target, variables, characteristic), variables
    )
    polynomials = modular_equations + [modular_target]
    source_lines = [",".join(map(str, variables)), str(characteristic)]
    source_lines.extend(
        render(polynomial) + ("," if index + 1 < len(polynomials) else "")
        for index, polynomial in enumerate(polynomials)
    )
    source = "\n".join(source_lines) + "\n"
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="hc4-colon-replay-") as directory:
        directory_path = Path(directory)
        input_path = directory_path / "normal-form.ms"
        output_path = directory_path / "normal-form.out"
        input_path.write_text(source, encoding="ascii")
        try:
            process = subprocess.run(
                [
                    str(executable),
                    "-f",
                    str(input_path),
                    "-o",
                    str(output_path),
                    "-n",
                    "1",
                    "-g",
                    "2",
                    "-v",
                    "2",
                    "-t",
                    str(threads),
                    "--random-seed",
                    "0",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=timeout,
            )
            timed_out = False
            return_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
            solver_output = (
                output_path.read_text(encoding="ascii") if output_path.is_file() else ""
            )
        except subprocess.TimeoutExpired as error:
            timed_out = True
            return_code = None
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            solver_output = ""
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", errors="replace")
    normalized_output = re.sub(r"\s+", "", solver_output)
    normal_form_zero = (
        not timed_out
        and return_code == 0
        and ("[0]:" in normalized_output or normalized_output.endswith("[0]"))
    )
    return {
        "backend": "unmodified msolve normal-form mode",
        "executable": str(executable),
        "characteristic": characteristic,
        "threads": threads,
        "random_seed": 0,
        "timed_out": timed_out,
        "return_code": return_code,
        "normal_form_zero": normal_form_zero,
        "solver_output": solver_output,
        "solver_output_sha256": hashlib.sha256(solver_output.encode("ascii")).hexdigest(),
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-12000:],
        "source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "wall_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", nargs="+", type=Path)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--msolve", type=Path, default=Path("/opt/homebrew/bin/msolve"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--holdout", type=Path)
    parser.add_argument("--holdout-characteristic", type=int)
    parser.add_argument("--skip-normal-form", action="store_true")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if len(arguments.candidates) < 2:
        parser.error("at least two discovery-prime candidates are required")
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("replay characteristic must be a prime greater than five")
    if arguments.threads < 1 or arguments.timeout < 1:
        parser.error("threads and timeout must be positive")
    candidate_paths = [path.resolve() for path in arguments.candidates]
    executable = arguments.msolve.resolve()
    if not executable.is_file():
        parser.error("--msolve executable does not exist")

    started = time.perf_counter()
    primes, modulus, reconstructed = reconstruct_coefficients(candidate_paths)
    holdout = None
    if arguments.holdout is not None:
        if arguments.holdout_characteristic is None:
            parser.error("--holdout requires --holdout-characteristic")
        if arguments.holdout_characteristic in primes:
            parser.error("the held-out prime must not be a reconstruction prime")
        holdout = validate_holdout(
            arguments.holdout.resolve(),
            arguments.holdout_characteristic,
            reconstructed,
        )
        if not holdout["all_coefficients_replay"]:
            raise AssertionError("held-out candidate does not match reconstruction")
    equations, variables, _, open_factor = homogeneous_saturation_system()
    h = expression_from_rationals(reconstructed, variables)
    h_polynomial = sp.Poly(h, *variables, domain=sp.QQ)
    h_degrees = {sum(exponents) for exponents, _ in h_polynomial.terms()}
    h_characters = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _ in h_polynomial.terms()
    }
    if h_degrees != {4} or len(h_characters) != 1:
        raise AssertionError("reconstructed h is not character-homogeneous of degree four")
    h_character = next(iter(h_characters))
    target = sp.expand(open_factor * h)
    target_polynomial = sp.Poly(target, *variables, domain=sp.QQ)
    target_characters = {
        character_weight(tuple(map(int, exponents)))
        for exponents, _ in target_polynomial.terms()
    }
    if target_polynomial.total_degree() != 8 or len(target_characters) != 1:
        raise AssertionError("M*h left the expected degree-eight character block")

    h_modular_terms = modular_terms(h, variables, arguments.characteristic)
    membership = degree_four_membership_test(
        h_modular_terms,
        equations,
        variables,
        arguments.characteristic,
        h_character,
    )
    normal_form = (
        {
            "backend": "not run",
            "normal_form_zero": False,
            "reason": "--skip-normal-form",
        }
        if arguments.skip_normal_form
        else msolve_normal_form_replay(
            equations,
            target,
            variables,
            arguments.characteristic,
            executable,
            arguments.threads,
            arguments.timeout,
        )
    )
    reconstruction_passed = (
        membership["nontrivial_quotient_class"]
        and (holdout is None or holdout["all_coefficients_replay"])
    )
    colon_replay_passed = reconstruction_passed and normal_form["normal_form_zero"]
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    rational_terms = [
        {
            "exponents": list(exponents),
            "numerator": str(coefficient.numerator()),
            "denominator": str(coefficient.denominator()),
        }
        for exponents, coefficient in sorted(reconstructed.items())
    ]
    common_denominator = Integer(1)
    for coefficient in reconstructed.values():
        common_denominator = lcm(common_denominator, coefficient.denominator())
    integer_coefficients = {
        exponents: Integer(coefficient * common_denominator)
        for exponents, coefficient in reconstructed.items()
    }
    integer_content = Integer(0)
    for coefficient in integer_coefficients.values():
        integer_content = integer_content.gcd(coefficient)
    primitive_integer_terms = [
        {
            "exponents": list(exponents),
            "coefficient": str(coefficient // integer_content),
        }
        for exponents, coefficient in sorted(integer_coefficients.items())
    ]
    reconstruction_uniqueness_bound = Integer(modulus // 2).isqrt()
    result = {
        "schema": "hc4.decimic-j2-secant-r10-colon-kernel-replay.v1",
        "status": (
            "PASS_MODULAR_FIRST_COLON_KERNEL_REPLAY"
            if colon_replay_passed
            else "PASS_QQ_CANDIDATE_RECONSTRUCTION_HELDOUT_REPLAY"
            if reconstruction_passed and arguments.skip_normal_form and holdout is not None
            else "INCOMPLETE_FIRST_COLON_KERNEL_REPLAY"
        ),
        "assurance": (
            "exact rational reconstruction with held-out finite-field replay; QQ colon identity pending"
            if reconstruction_passed and arguments.skip_normal_form
            else "exact finite-field replay; characteristic-zero identity not yet certified"
        ),
        "orbit": "secant",
        "chart": "r=10 and M=f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "colon_statement_replayed": "h not in I_4 and M*h in I_8",
        "replay_characteristic": arguments.characteristic,
        "discovery_primes": primes,
        "crt_modulus": str(modulus),
        "reconstruction_method": (
            "componentwise CRT at the two discovery primes followed by "
            "Sage rational_reconstruction; the held-out prime was not used"
        ),
        "rational_reconstruction_uniqueness_bound": str(
            reconstruction_uniqueness_bound
        ),
        "maximum_absolute_numerator": str(
            max(abs(coefficient.numerator()) for coefficient in reconstructed.values())
        ),
        "maximum_denominator": str(
            max(coefficient.denominator() for coefficient in reconstructed.values())
        ),
        "held_out_validation": holdout,
        "candidate_paths": [str(path) for path in candidate_paths],
        "candidate_sha256": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in candidate_paths
        },
        "variable_names": [str(variable) for variable in variables],
        "character_modulus": CHARACTER_MODULUS,
        "character_weights": list(CHARACTER_WEIGHTS),
        "h_total_degree": h_polynomial.total_degree(),
        "h_character_weight": h_character,
        "h_term_count": len(rational_terms),
        "h_rational_terms": rational_terms,
        "h_common_denominator": str(common_denominator),
        "h_integer_content_before_primitive_normalization": str(integer_content),
        "h_primitive_integer_terms": primitive_integer_terms,
        "h_expression": str(h),
        "h_expression_sha256": digest((h,)),
        "target_total_degree": target_polynomial.total_degree(),
        "target_character_weight": next(iter(target_characters)),
        "target_expression_sha256": digest((target,)),
        "degree_four_membership_test": membership,
        "normal_form_replay": normal_form,
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "open_factor_sha256": digest((open_factor,)),
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/replay_j2_secant_r10_colon_kernel.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_colon_kernel.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_colon_kernel.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "A passing receipt certifies one nonzero degree-four class in "
            "(I:M)/I over the replay finite field. It does not yet serialize "
            "original-generator multipliers, prove the reconstructed rational "
            "identity over QQ, determine the full colon ideal, decide saturation, "
            "or close the secant chart."
        ),
    }
    output = arguments.output or Path(
        f"research/j2_secant_r10_colon_kernel_replay_p{arguments.characteristic}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    printable = dict(result)
    printable.pop("h_rational_terms")
    printable.pop("h_primitive_integer_terms")
    printable["h_rational_terms_omitted_from_console"] = len(rational_terms)
    printable["h_primitive_integer_terms_omitted_from_console"] = len(
        primitive_integer_terms
    )
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0 if colon_replay_passed or (
        arguments.skip_normal_form and reconstruction_passed
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
