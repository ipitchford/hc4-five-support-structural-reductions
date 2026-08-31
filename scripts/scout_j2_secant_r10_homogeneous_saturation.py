#!/usr/bin/env python3
"""F4-saturation scout for the last secant ``j2`` degree-six branch."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

import sympy as sp

from certify_j2_secant_r10_f9_laurent_branch import laurent_branches
from msolve_process import run_msolve_process
from scout_decimic_nullcone_hsop import digest, f_coefficients
from scout_five_support import g_coefficients


RETAINED_NORMAL_INDICES = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 15, 16, 17, 18)
INVERSE_NAMES = {"j2inv", "f10inv", "leadinv"}


def homogeneous_saturation_system():
    _, _, _, _, branches = laurent_branches()
    branch = branches["degree_6"]
    affine_equations = [
        branch["equations"][index] for index in RETAINED_NORMAL_INDICES
    ]
    core_variables = tuple(
        variable
        for variable in branch["variables"]
        if str(variable) not in INVERSE_NAMES
        and any(equation.has(variable) for equation in affine_equations)
    )
    f9 = f_coefficients[9]
    variables = core_variables + (f9,)
    equations = []
    for index, affine in zip(RETAINED_NORMAL_INDICES, affine_equations, strict=True):
        homogeneous = sp.expand(
            sp.Poly(affine, *core_variables, domain=sp.QQ).homogenize(f9).as_expr()
        )
        if sp.expand(homogeneous.subs(f9, 1) - affine) != 0:
            raise AssertionError(f"equation {index} did not dehomogenize exactly")
        if sp.Poly(homogeneous, *variables, domain=sp.QQ).total_degree() != 3:
            raise AssertionError(f"equation {index} is not a homogeneous cubic")
        equations.append(homogeneous)

    f10 = f_coefficients[10]
    g0 = g_coefficients[0]
    leading_form = sp.expand(2 * f9**2 + 5 * f10 * g0)
    open_factor = sp.expand(f9 * f10 * leading_form)
    if sp.expand(leading_form.subs(f9, 1) - branch["leading_form"]) != 0:
        raise AssertionError("the homogeneous leading form changed")
    return equations, variables, leading_form, open_factor


def render(expression: sp.Expr) -> str:
    return sp.sstr(expression).replace("**", "^")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characteristic", type=int, default=101)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.characteristic <= 5 or not sp.isprime(arguments.characteristic):
        parser.error("characteristic must be a prime greater than five")
    if arguments.timeout < 1 or arguments.threads < 1:
        parser.error("timeout and threads must be positive")

    started = time.perf_counter()
    equations, variables, leading_form, open_factor = homogeneous_saturation_system()
    rows = [",".join(map(str, variables)), str(arguments.characteristic)]
    generators = equations + [open_factor]
    rows.extend(
        render(expression) + ("," if index + 1 < len(generators) else "")
        for index, expression in enumerate(generators)
    )
    source = "\n".join(rows) + "\n"
    raw = run_msolve_process(
        source,
        arguments.timeout,
        arguments.threads,
        verbose=2,
        extra_args=("-S", "-g", "2"),
    )
    solver_output = str(raw.pop("solver_output"))
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    clean_exit = not raw["timed_out"] and raw["return_code"] == 0
    unit = clean_exit and solver_output.strip().rstrip(":") == "[-1]"
    status = (
        "PASS_MODULAR_HOMOGENEOUS_SATURATION_UNIT"
        if unit
        else "INCOMPLETE_MODULAR_HOMOGENEOUS_SATURATION"
    )

    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    result = {
        "schema": "hc4.decimic-j2-secant-r10-homogeneous-saturation.v1",
        "status": status,
        "assurance": "exact finite-field F4 saturation; characteristic-zero certificate required",
        "orbit": "secant",
        "chart": "r=10, f9*f10*(2*f9^2+5*f10*g0) nonzero",
        "branch": "degree_6",
        "characteristic": arguments.characteristic,
        "algorithm": "msolve F4 saturation",
        "variable_names": [str(variable) for variable in variables],
        "variable_count": len(variables),
        "normal_generator_count": len(equations),
        "retained_affine_normal_indices": list(RETAINED_NORMAL_INDICES),
        "normal_generator_degree": 3,
        "leading_form": str(leading_form),
        "open_factor": str(open_factor),
        "open_factor_degree": sp.Poly(open_factor, *variables).total_degree(),
        "dehomogenization": "f9=1 recovers the frozen Laurent branch",
        "normal_equation_stream_sha256": digest(tuple(equations)),
        "open_factor_sha256": digest((open_factor,)),
        "msolve_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": {
            **raw,
            "is_unit": unit,
            "solver_output_tail": solver_output[-4000:],
            "stdout_tail": stdout[-12000:],
            "stderr_tail": stderr[-4000:],
        },
        "wall_seconds": time.perf_counter() - started,
        "source_sha256": {
            "scripts/scout_j2_secant_r10_homogeneous_saturation.py": hashlib.sha256(
                script_path.read_bytes()
            ).hexdigest(),
            "scripts/msolve_process.py": hashlib.sha256(
                (script_path.parent / "msolve_process.py").read_bytes()
            ).hexdigest(),
            "scripts/certify_j2_secant_r10_f9_laurent_branch.py": hashlib.sha256(
                (script_path.parent / "certify_j2_secant_r10_f9_laurent_branch.py").read_bytes()
            ).hexdigest(),
        },
        "claim_boundary": (
            "a passing receipt proves only that the displayed homogeneous saturation "
            "is the unit ideal in one finite characteristic; it is route evidence, "
            "not a characteristic-zero radical-containment certificate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    field = f"p{arguments.characteristic}"
    output = arguments.output or Path(
        f"receipts/hsop-j2-secant-r10-degree6-homogeneous-saturation-{field}.json"
    )
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if unit else 1


if __name__ == "__main__":
    raise SystemExit(main())
