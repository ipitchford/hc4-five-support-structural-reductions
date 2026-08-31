#!/usr/bin/env python3
"""Run the Macaulay2 weight-space extractor and freeze its exact output."""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import shutil
import subprocess
import time
from pathlib import Path


BLOCKS = {
    "V0_QUADRATIC": ("V0_QUADRATIC_BEGIN", "V0_QUADRATIC_END", 1),
    "V6_CUBIC": ("V6_CUBIC_BEGIN", "V6_CUBIC_END", 1),
    "V2_WEIGHT_2_CANDIDATES": (
        "V2_WEIGHT_2_CANDIDATES_BEGIN",
        "V2_WEIGHT_2_CANDIDATES_END",
        2,
    ),
    "V8_QUARTIC": ("V8_QUARTIC_BEGIN", "V8_QUARTIC_END", 1),
    "V4_WEIGHT_4_CANDIDATES": (
        "V4_WEIGHT_4_CANDIDATES_BEGIN",
        "V4_WEIGHT_4_CANDIDATES_END",
        3,
    ),
    "V0_WEIGHT_0_CANDIDATES": (
        "V0_WEIGHT_0_CANDIDATES_BEGIN",
        "V0_WEIGHT_0_CANDIDATES_END",
        4,
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_block(lines: list[str], begin: str, end: str) -> list[str]:
    try:
        left = lines.index(begin)
        right = lines.index(end, left + 1)
    except ValueError as error:
        raise AssertionError(f"missing output marker: {error}") from error
    return [line.strip() for line in lines[left + 1 : right] if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("receipts/decimic-nullcone-weight-generators-exact.json"),
    )
    parser.add_argument("--timeout", type=int, default=300)
    arguments = parser.parse_args()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    extractor = campaign / "scripts/extract_decimic_nullcone_weight_generators.m2"
    executable = shutil.which("M2")
    if executable is None:
        raise SystemExit("M2 is required")

    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    completed = subprocess.run(
        [executable, "--stop", "--no-readline", "--silent", str(extractor)],
        text=True,
        capture_output=True,
        timeout=arguments.timeout,
        check=False,
    )
    wall_seconds = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    if completed.returncode != 0:
        raise AssertionError(
            f"Macaulay2 failed with {completed.returncode}: {completed.stderr[-2000:]}"
        )
    lines = completed.stdout.splitlines()
    if "STATUS PASS_EXACT_WEIGHT_SPACE_EXTRACTION" not in lines:
        raise AssertionError("the Macaulay2 producer did not print its passing status")
    polynomials = {}
    for name, (begin, end, expected_count) in BLOCKS.items():
        values = extract_block(lines, begin, end)
        if len(values) != expected_count:
            raise AssertionError(f"{name}: expected {expected_count} values, received {len(values)}")
        polynomials[name] = values

    result = {
        "schema": "hc4.decimic-nullcone-weight-generators.v1",
        "status": "PASS_EXACT_WEIGHT_SPACE_EXTRACTION",
        "field": "QQ",
        "partition": [6, 1, 1, 1, 1],
        "polynomials": polynomials,
        "polynomial_sha256": {
            name: [hashlib.sha256(value.encode("utf-8")).hexdigest() for value in values]
            for name, values in polynomials.items()
        },
        "calculation": {
            "command": [
                executable,
                "--stop",
                "--no-readline",
                "--silent",
                str(extractor),
            ],
            "return_code": completed.returncode,
            "wall_seconds": wall_seconds,
            "child_user_seconds": after.ru_utime - before.ru_utime,
            "child_system_seconds": after.ru_stime - before.ru_stime,
            "maximum_rss_native": after.ru_maxrss,
            "stderr_tail": completed.stderr[-2000:],
        },
        "source_sha256": {
            "scripts/capture_decimic_nullcone_weight_generators.py": sha256(script_path),
            "scripts/extract_decimic_nullcone_weight_generators.m2": sha256(extractor),
            "/opt/homebrew/share/Macaulay2/CoincidentRootLoci.m2": sha256(
                Path("/opt/homebrew/share/Macaulay2/CoincidentRootLoci.m2")
            ),
        },
        "claim_boundary": (
            "this is an exact extraction of selected torus-weight spaces from the "
            "minimal target generators; highest-weight correction modulo the lower "
            "quadratic ideal and normal-layer containment remain separate"
        ),
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    output = arguments.output if arguments.output.is_absolute() else campaign / arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
