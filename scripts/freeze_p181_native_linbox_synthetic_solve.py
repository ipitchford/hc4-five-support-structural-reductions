#!/usr/bin/env python3
"""Freeze the native target-free synthetic solve implementation before run."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-native-linbox-synthetic-solve-implementation-freeze.json"
PREREG = "research/THIRD_COLON_P181_NATIVE_LINBOX_SYNTHETIC_SOLVE_PREREGISTRATION.md"
BOUND = {
    "scripts/linbox_sparse_mod181_solve_driver.cpp": "aeaff16d117f8e8b5d64014be714db7ecac0e10446ad52e61a8814b5fa5b77b5",
    "artifacts/bin/linbox_sparse_mod181_solve_driver": "171b8b5fb7f26939d6be36f3024a6968476fd44a26f39b21a7831a9ae69f7a7b",
    "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr": "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef",
    "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json": "c6bec6f72d7ba5c0792cfe439383d1795ae82160c570148e1b7899807bd81c37",
    "scripts/run_p181_target_blind_linbox_rank_gated.py": None,
    "scripts/run_p181_native_linbox_synthetic_solve_gated.py": None,
    "scripts/freeze_p181_native_linbox_synthetic_solve.py": None,
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    return (completed.stdout or completed.stderr).strip()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    prereg_hash = file_hash(CAMPAIGN / PREREG)
    bound = {}
    for relative, expected in BOUND.items():
        observed = file_hash(CAMPAIGN / relative)
        if expected is not None and observed != expected:
            raise ValueError(f"bound file drift: {relative}")
        bound[relative] = observed
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-p181-native-linbox-synthetic-solve-implementation-freeze.v1",
        "status": "PASS_P181_NATIVE_LINBOX_SYNTHETIC_SOLVE_IMPLEMENTATION_FREEZE",
        "preregistration": {"path": PREREG, "sha256": prereg_hash},
        "bound_files": bound,
        "toolchain": {
            "clang_version": command_output(["clang++", "--version"]).splitlines()[:2],
            "linbox_version": command_output(["pkg-config", "--modversion", "linbox"]),
            "fflas_ffpack_version": command_output(["pkg-config", "--modversion", "fflas-ffpack"]),
            "givaro_version": command_output(["pkg-config", "--modversion", "givaro"]),
            "linbox_pkg_config_flags": command_output(["pkg-config", "--cflags", "--libs", "linbox"]),
            "compile_command": "clang++ -std=c++17 -O3 scripts/linbox_sparse_mod181_solve_driver.cpp -o artifacts/bin/linbox_sparse_mod181_solve_driver $(pkg-config --cflags --libs linbox)",
        },
        "known_vector": {"formula": "(((c+1)*37+11) mod 180)+1 for c=0..35880", "bytes": 35_881, "sha256": "ebcf2e6338e5eb81ba7b9fd58f8c9366a8b5ddb48c27cef7fcd34e9c27663d28"},
        "policy": {"wall_seconds_maximum": 600, "rss_bytes_maximum": 3_758_096_384, "process_swaps_maximum": 0},
        "canonical_outputs": {
            "artifact": "artifacts/third-colon-p181-native-linbox-synthetic-solve-v1",
            "telemetry": "receipts/telemetry/third-colon-p181-native-linbox-synthetic-solve-v1",
            "terminal": "receipts/hsop-j2-secant-r10-p181-native-linbox-synthetic-solve-v1.json",
        },
        "declarations": {"frozen_before_full_actual_coefficient_solve": True, "target_rhs_excluded": True, "no_mod181_squared": True},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("xb") as handle:
        handle.write((json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
