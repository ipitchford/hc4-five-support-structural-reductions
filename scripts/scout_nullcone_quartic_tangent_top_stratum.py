#!/usr/bin/env python3
"""No-unipotent tangent top-index scouts for quartic target families."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from scout_decimic_nullcone_hsop import digest, f_coefficients, normal_equations, run_source
from scout_five_support import g_coefficients
from scout_j2_normalized_chart import singular_source


FAMILIES = ("V0", "V4_1", "V4_2", "V8")
top_inverse = sp.Symbol("topinv")


def load_family(campaign: Path, name: str) -> tuple[sp.Expr, dict[str, object], Path]:
    receipt_path = campaign / "receipts/decimic-nullcone-quartic-covariants-exact.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "PASS_EXACT_QUARTIC_COVARIANT_IDENTIFICATION":
        raise AssertionError("the exact quartic dictionary is unavailable")
    profile = receipt["families"][name]
    local = {str(symbol): symbol for symbol in f_coefficients}
    expression = sp.Poly(
        sp.sympify(profile["raw_polynomial"], locals=local),
        *f_coefficients,
        domain=sp.QQ,
    ).as_expr()
    if digest((expression,)) != profile["raw_sha256"]:
        raise AssertionError("the quartic target hash does not replay")
    return expression, profile, receipt_path


def stratum(family: str, top_index: int):
    campaign = Path(__file__).resolve().parent.parent
    target, profile, receipt_path = load_family(campaign, family)
    weight = int(profile["tangent_torus_weight"])
    if weight == 0:
        raise AssertionError("the quartic target cannot be normalized by the tangent torus")
    equations, build_seconds = normal_equations("tangent")
    substitutions = {
        f_coefficients[index]: 0 for index in range(top_index + 1, 11)
    }
    reduced = [sp.expand(equation.subs(substitutions)) for equation in equations]
    reduced_target = sp.expand(target.subs(substitutions))
    if reduced_target == 0:
        raise AssertionError("quartic target vanished on a claimed top stratum")
    auxiliary = [sp.expand(reduced_target - 1)]
    target_forces_top = sp.expand(
        reduced_target.subs({f_coefficients[top_index]: 0})
    ) == 0
    inverse_variables: tuple[sp.Symbol, ...] = ()
    if not target_forces_top:
        auxiliary.append(sp.expand(top_inverse * f_coefficients[top_index] - 1))
        inverse_variables = (top_inverse,)
    remaining_f = tuple(symbol for symbol in f_coefficients if symbol not in substitutions)
    variables = remaining_f + g_coefficients + inverse_variables
    if any(expression.free_symbols & set(substitutions) for expression in reduced + auxiliary):
        raise AssertionError("an eliminated coefficient survived the quartic top stratum")
    return {
        "equations": reduced,
        "auxiliary": auxiliary,
        "variables": variables,
        "substitutions": substitutions,
        "target": reduced_target,
        "target_forces_top": target_forces_top,
        "target_weight": weight,
        "profile": profile,
        "dictionary_receipt": receipt_path,
        "build_seconds": build_seconds,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=FAMILIES, required=True)
    parser.add_argument("--top-index", type=int, choices=range(5, 11), required=True)
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--algorithm", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic and not sp.isprime(arguments.characteristic):
        parser.error("positive characteristic must be prime")

    started = time.perf_counter()
    data = stratum(arguments.family, arguments.top_index)
    source = singular_source(
        data["equations"],
        data["auxiliary"],
        data["variables"],
        arguments.characteristic,
        arguments.algorithm,
    )
    calculation = run_source(source, arguments.timeout)
    if calculation["is_unit"] and arguments.characteristic == 0:
        status = "PASS_EXACT_QUARTIC_HIGHEST_RADICAL_ON_COVER_STRATUM"
    elif calculation["is_unit"]:
        status = "PASS_MODULAR_QUARTIC_HIGHEST_COVER_STRATUM"
    elif calculation["timed_out"]:
        status = "TIMEOUT_RETAINED"
    else:
        status = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4.decimic-nullcone-quartic-tangent-top-stratum.v1",
        "status": status,
        "orbit": "tangent",
        "family": arguments.family,
        "family_order": data["profile"]["order"],
        "top_index": arguments.top_index,
        "characteristic": arguments.characteristic,
        "algorithm": "Singular " + arguments.algorithm,
        "cover_statement": (
            f"{arguments.family}=1; f_(r+1)=...=f10=0; f_r!=0"
        ),
        "tangent_torus_weight": data["target_weight"],
        "target_normalized": True,
        "unipotent_used": False,
        "substitutions": {str(key): int(value) for key, value in data["substitutions"].items()},
        "target_after_substitution": str(data["target"]),
        "target_term_count": len(sp.Poly(data["target"], *data["variables"]).terms()),
        "target_sha256": digest((data["target"],)),
        "target_localizer_forces_top_nonzero": data["target_forces_top"],
        "normal_equation_count": len(data["equations"]),
        "auxiliary_equation_count": len(data["auxiliary"]),
        "variable_names": [str(variable) for variable in data["variables"]],
        "variable_count": len(data["variables"]),
        "maximum_total_degree": max(
            sp.Poly(expression, *data["variables"]).total_degree()
            for expression in data["equations"] + data["auxiliary"]
        ),
        "normal_equation_stream_sha256": digest(tuple(data["equations"])),
        "auxiliary_stream_sha256": digest(tuple(data["auxiliary"])),
        "equation_build_seconds": data["build_seconds"],
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "wall_seconds": time.perf_counter() - started,
        "input": {
            "quartic_dictionary": str(data["dictionary_receipt"].relative_to(campaign)),
            "quartic_dictionary_sha256": hashlib.sha256(
                data["dictionary_receipt"].read_bytes()
            ).hexdigest(),
        },
        "source_sha256": {
            "scripts/scout_nullcone_quartic_tangent_top_stratum.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "all six top-index strata need exact characteristic-zero units before "
            "claiming highest-coordinate containment; stabilizer propagation, the "
            "other quartic families, secant orbit, and HC4 remain separate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output
    if output is None:
        field = "qq" if arguments.characteristic == 0 else f"p{arguments.characteristic}"
        output = campaign / (
            f"receipts/nullcone-{arguments.family.lower()}-tangent-top-r{arguments.top_index}-"
            f"{field}-{arguments.algorithm}.json"
        )
    elif not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not calculation["timed_out"] and calculation["return_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
