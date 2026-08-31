#!/usr/bin/env python3
"""Compute exact parameter exceptions with Singular's Groebner cover.

The generic function-field calculation sees only the dense parameter segment.
This script computes the comprehensive cover over Q[lambda,mu], restricted to
the distinct-root open Delta != 0, and asks ``Grob1Levels`` for precisely the
segments whose specialized basis is not the unit ideal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

from prove_generic_five_support import (
    lambda_parameter,
    mu_parameter,
    parse_partition,
    render_expression,
)
from prove_polynomial_open_eliminated import eliminated_system, stream_digest
from scout_five_support import CHARTS, general_cubic
from singular_process import run_singular_process


def source_for(equations, chart_expression) -> str:
    cubic_symbols = tuple(
        sorted(general_cubic.free_symbols, key=lambda symbol: str(symbol))
    )
    variable_source = ",".join(map(str, cubic_symbols + ("inv",)))
    equation_source = ",".join(
        render_expression(equation) for equation in equations
    )
    chart_open = render_expression(chart_expression).replace("inv", "inv")
    delta = render_expression(
        lambda_parameter
        * mu_parameter
        * (lambda_parameter - 1)
        * (mu_parameter - 1)
        * (lambda_parameter - mu_parameter)
    )
    return "\n".join(
        [
            'LIB "grobcov.lib";',
            f"ring r=(0,{lambda_parameter},{mu_parameter}),"
            f"({variable_source}),dp;",
            "ideal I=" + equation_source + ",inv*(" + chart_open + ")-1;",
            "ideal distinct=" + delta + ";",
            'def cover=grobcov(I,"nonnull",distinct,"can",0,"rep",1);',
            "def nonunit=Grob1Levels(cover);",
            'print("SEGMENT_COUNT");',
            "size(cover);",
            'print("NONUNIT_LEVEL_COUNT");',
            "size(nonunit);",
            'print("NONUNIT_LEVEL_TYPE");',
            "typeof(nonunit[1]);",
            'print("NONUNIT_LEVEL_HEAD");',
            "string(nonunit[1]);",
            'if(typeof(nonunit[1])!="int"){print("NONUNIT_LEVELS_BEGIN");nonunit;print("NONUNIT_LEVELS_END");}',
            "exit;",
        ]
    )


def marker(output: str, name: str) -> str | None:
    lines = output.splitlines()
    try:
        position = lines.index(name)
    except ValueError:
        return None
    return lines[position + 1].strip() if position + 1 < len(lines) else None


def run_source(source: str, timeout: int) -> dict[str, object]:
    raw = run_singular_process(source, timeout)
    stdout = str(raw.pop("stdout"))
    stderr = str(raw.pop("stderr"))
    diagnostic_error = (
        "error occurred" in stdout
        or "error occurred" in stderr
        or "expected" in stdout and "expression" in stdout
    )
    segment_count = marker(stdout, "SEGMENT_COUNT")
    nonunit_count = marker(stdout, "NONUNIT_LEVEL_COUNT")
    nonunit_type = marker(stdout, "NONUNIT_LEVEL_TYPE")
    nonunit_head = marker(stdout, "NONUNIT_LEVEL_HEAD")
    return {
        **raw,
        "diagnostic_error": diagnostic_error,
        "segment_count": segment_count,
        "nonunit_level_count": nonunit_count,
        "nonunit_level_type": nonunit_type,
        "nonunit_level_head": nonunit_head,
        "complete_open_unit": (
            not raw["timed_out"]
            and raw["return_code"] == 0
            and not diagnostic_error
            and nonunit_type == "int"
            and nonunit_head == "1"
        ),
        "stdout_tail": stdout[-12000:],
        "stderr_tail": stderr[-4000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", type=parse_partition, required=True)
    parser.add_argument("--chart", choices=CHARTS, required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if shutil.which("Singular") is None:
        raise SystemExit("Singular is required")

    started = time.perf_counter()
    equations, lines, build_seconds = eliminated_system(arguments.partition)
    source = source_for(equations, lines[arguments.chart])
    calculation = run_source(source, arguments.timeout)
    if calculation["complete_open_unit"]:
        disposition = "EXACT_COMPLETE_FIVE_SUPPORT_CHART"
    elif calculation["timed_out"]:
        disposition = "TIMEOUT_RETAINED"
    elif calculation["nonunit_level_type"] not in (None, "int"):
        disposition = "EXACT_INTERIOR_EXCEPTION_RETAINED"
    else:
        disposition = "ERROR_REQUIRES_AUDIT"
    result = {
        "schema": "hc4-five-support-groebner-cover-open-v1",
        "partition": list(arguments.partition),
        "chart": arguments.chart,
        "parameter_open": "Delta != 0",
        "equation_count": len(equations),
        "equation_stream_sha256": stream_digest(equations),
        "line_coordinate_sha256": stream_digest([lines[arguments.chart]]),
        "equation_build_seconds": build_seconds,
        "singular_source_sha256": hashlib.sha256(source.encode("ascii")).hexdigest(),
        "calculation": calculation,
        "disposition": disposition,
        "claim_boundary": (
            "empty nonunit Groebner-cover levels prove the complete normalized "
            "distinct-five-root chart; nonempty levels are exact exceptional "
            "parameter strata and must be preserved"
        ),
        "wall_seconds": time.perf_counter() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
