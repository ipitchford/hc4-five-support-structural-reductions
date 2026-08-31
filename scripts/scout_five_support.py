#!/usr/bin/env python3
"""Exact finite-field scouts for the clean five-support double-conic rows."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import resource
import shutil
import subprocess
import time
from pathlib import Path

import sympy as sp

from reconstruct_normal_layers import canonical_lift, q, s, t, x, y, z


PARTITIONS = (
    (6, 1, 1, 1, 1),
    (5, 2, 1, 1, 1),
    (4, 3, 1, 1, 1),
    (4, 2, 2, 1, 1),
    (3, 3, 2, 1, 1),
    (3, 2, 2, 2, 1),
    (2, 2, 2, 2, 2),
)
TRAINING = (
    {"prime": 32003, "lambda": 2, "mu": 3, "role": "training"},
    {"prime": 32009, "lambda": 2, "mu": 5, "role": "training"},
)
HOLDOUT = (
    {"prime": 65521, "lambda": 3, "mu": 7, "role": "holdout"},
    {"prime": 65537, "lambda": 5, "mu": 11, "role": "holdout"},
)
CHARTS = ("line_x", "line_y", "line_z")

g_coefficients = sp.symbols("g0:10")
line_x, line_y, line_z, inverse = sp.symbols(
    "line_x line_y line_z inv"
)
chart_symbols = {"line_x": line_x, "line_y": line_y, "line_z": line_z}
cubic_monomials = tuple(
    x**a * y**b * z ** (3 - a - b)
    for a in range(4)
    for b in range(4 - a)
)
general_cubic = sum(
    coefficient * monomial
    for coefficient, monomial in zip(g_coefficients, cubic_monomials)
)
unknowns = g_coefficients + (line_x, line_y, line_z, inverse)


def validate_profile() -> None:
    assert len(PARTITIONS) == 7
    assert len(set(PARTITIONS)) == 7
    assert all(len(partition) == 5 and sum(partition) == 10 for partition in PARTITIONS)
    assert tuple(sorted(PARTITIONS, reverse=True)) == PARTITIONS
    for evaluation in TRAINING + HOLDOUT:
        prime = evaluation["prime"]
        lam = evaluation["lambda"] % prime
        mu = evaluation["mu"] % prime
        assert sp.isprime(prime)
        assert lam not in (0, 1) and mu not in (0, 1) and lam != mu


def binary_form(
    partition: tuple[int, ...], lambda_value: int, mu_value: int
) -> sp.Expr:
    a, b, c, d, e = partition
    return sp.expand(
        s**a
        * t**b
        * (s - t) ** c
        * (s - lambda_value * t) ** d
        * (s - mu_value * t) ** e
    )


def equations_for(
    partition: tuple[int, ...], lambda_value: int, mu_value: int
) -> tuple[list[sp.Expr], float]:
    started = time.perf_counter()
    f = binary_form(partition, lambda_value, mu_value)
    h5 = canonical_lift(f, 5) + q * general_cubic
    target = q**4 * (line_x * x + line_y * y + line_z * z)
    difference = sp.Poly(
        sp.expand(sp.hessian(h5, (x, y, z)).det() - target), x, y, z
    )
    equations = [coefficient for _, coefficient in difference.terms()]
    assert len(equations) == 55
    return equations, time.perf_counter() - started


def singular_polynomial(expression: sp.Expr) -> str:
    polynomial = sp.Poly(sp.expand(expression), *unknowns, domain=sp.ZZ)
    return str(polynomial.as_expr()).replace("**", "^")


def singular_source(
    equations: list[sp.Expr], prime: int, chart: str
) -> tuple[str, str]:
    equation_strings = [singular_polynomial(equation) for equation in equations]
    equation_hash = hashlib.sha256(
        "\n".join(equation_strings).encode("ascii")
    ).hexdigest()
    chart_equation = singular_polynomial(inverse * chart_symbols[chart] - 1)
    source = "\n".join(
        [
            f"ring r={prime},({','.join(map(str, unknowns))}),dp;",
            "option(redSB);",
            "ideal I=" + ",".join(equation_strings + [chart_equation]) + ";",
            "ideal J=std(I);",
            "poly remainder=reduce(1,J);",
            'print("UNIT_REMAINDER");',
            "remainder;",
            'print("BASIS_SIZE");',
            "size(J);",
            "exit;",
        ]
    )
    return source, equation_hash


def parse_marker(output: str, marker: str) -> str | None:
    lines = output.splitlines()
    try:
        index = lines.index(marker)
    except ValueError:
        return None
    return lines[index + 1].strip() if index + 1 < len(lines) else None


def run_chart(
    equations: list[sp.Expr], prime: int, chart: str, timeout: int
) -> dict[str, object]:
    source, equation_hash = singular_source(equations, prime, chart)
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            ["Singular", "-q"],
            input=source,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        timed_out = False
        return_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        return_code = None
        stdout = error.stdout or ""
        stderr = error.stderr or ""
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall = time.perf_counter() - started
    remainder = parse_marker(stdout, "UNIT_REMAINDER")
    basis_size = parse_marker(stdout, "BASIS_SIZE")
    return {
        "chart": chart,
        "prime": prime,
        "equation_stream_sha256": equation_hash,
        "wall_seconds": wall,
        "child_user_seconds": after.ru_utime - before.ru_utime,
        "child_system_seconds": after.ru_stime - before.ru_stime,
        "maximum_rss_native": after.ru_maxrss,
        "timed_out": timed_out,
        "return_code": return_code,
        "unit_remainder": remainder,
        "basis_size": basis_size,
        "is_unit": (not timed_out and return_code == 0 and remainder == "0"),
        "stderr_tail": str(stderr)[-1000:],
        "stdout_tail": str(stdout)[-1000:],
    }


def evaluate(
    partition: tuple[int, ...], evaluation: dict[str, object], timeout: int, jobs: int
) -> dict[str, object]:
    equations, build_seconds = equations_for(
        partition, int(evaluation["lambda"]), int(evaluation["mu"])
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as executor:
        futures = [
            executor.submit(
                run_chart, equations, int(evaluation["prime"]), chart, timeout
            )
            for chart in CHARTS
        ]
        charts = [future.result() for future in futures]
    assert len({chart["equation_stream_sha256"] for chart in charts}) == 1
    return {
        "partition": list(partition),
        "role": evaluation["role"],
        "prime": evaluation["prime"],
        "lambda": evaluation["lambda"],
        "mu": evaluation["mu"],
        "equation_count": len(equations),
        "equation_build_seconds": build_seconds,
        "charts": charts,
        "all_charts_unit": all(chart["is_unit"] for chart in charts),
    }


def empty_system_control(prime: int = 32003) -> dict[str, object]:
    result = run_chart([], prime, "line_x", 30)
    assert not result["is_unit"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile", choices=("control", "pilot", "preregistered"), default="pilot"
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if shutil.which("Singular") is None:
        raise SystemExit("Singular is required")
    validate_profile()
    started = time.perf_counter()
    records = []
    controls: dict[str, object] = {"empty_system": empty_system_control()}

    if args.profile == "control":
        collapsed = {"prime": 32003, "lambda": 2, "mu": 2, "role": "control"}
        record = evaluate(PARTITIONS[0], collapsed, args.timeout, args.jobs)
        assert record["all_charts_unit"]
        controls["collapsed_four_support_6211"] = record
    elif args.profile == "pilot":
        records.append(evaluate(PARTITIONS[0], TRAINING[0], args.timeout, args.jobs))
    else:
        for partition in PARTITIONS:
            for evaluation in TRAINING + HOLDOUT:
                records.append(
                    evaluate(partition, evaluation, args.timeout, args.jobs)
                )

    partition_dispositions = []
    for partition in PARTITIONS:
        relevant = [record for record in records if record["partition"] == list(partition)]
        if len(relevant) == len(TRAINING) + len(HOLDOUT) and all(
            record["all_charts_unit"] for record in relevant
        ):
            disposition = "BOUNDED_GENERIC_UNIT_SIGNAL"
        elif relevant:
            disposition = "INCOMPLETE_OR_SURVIVOR_SIGNAL"
        else:
            disposition = "NOT_RUN"
        partition_dispositions.append(
            {"partition": list(partition), "disposition": disposition}
        )

    result = {
        "schema": "hc4-double-conic-five-support-scout-v1",
        "profile": args.profile,
        "status": "PASS" if all(
            not chart["timed_out"]
            for record in records
            for chart in record["charts"]
        ) else "TIMEOUTS_RETAINED",
        "protocol": {
            "partitions": [list(partition) for partition in PARTITIONS],
            "training": list(TRAINING),
            "holdout": list(HOLDOUT),
            "charts": list(CHARTS),
            "timeout_seconds": args.timeout,
            "jobs": args.jobs,
            "claim_boundary": (
                "finite-field unit signals are bounded falsification evidence, "
                "not characteristic-zero function-field proofs"
            ),
        },
        "controls": controls,
        "records": records,
        "partition_dispositions": partition_dispositions,
        "wall_seconds": time.perf_counter() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
