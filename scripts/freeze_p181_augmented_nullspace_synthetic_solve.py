#!/usr/bin/env python3
"""Freeze the staged target-free augmented-nullspace solve implementation."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-implementation-freeze.json"
PREREG = "research/THIRD_COLON_P181_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_PREREGISTRATION.md"
BOUND = {
    "scripts/linbox_augmented_nullspace_mod181_solve_driver.cpp": "339566a8622a9b11fafaf2432e29ba40541689002e01de5d721d8f3d66b7560b",
    "artifacts/bin/linbox_augmented_nullspace_mod181_solve_driver": "3a1b5bc1647e313668d53f03a8cd58d225516630e8326d542966d50c7b8239f7",
    "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr": "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef",
    "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json": "c6bec6f72d7ba5c0792cfe439383d1795ae82160c570148e1b7899807bd81c37",
    "receipts/hsop-j2-secant-r10-p181-native-linbox-synthetic-solve-v2-postrun-adjudication.json": "7960996914d60d822dcff1b412bf0932725889d8b7780f503066e1e6cce6f832",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-scout.json": "652af633649c32af3322b9405eac8d6e60fdaba5668817de6a11330782bc752a",
    "receipts/hsop-j2-secant-r10-third-colon-residual-114-quotient-independent-audit.json": "7eba0e65e40abd7eea0065ecd84c3803237fa9cc5c51391f3202b4d300b7185a",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-p197-common-minor-independent-audit.json": "c93bc54d3a3a37c9d7d3445b5ee1e742f15af5efd3918a6bc862de7778a0ad0d",
    "scripts/run_p181_target_blind_linbox_rank_gated.py": "a282b31bca01c972ff5d294b64ddca103d2ea6c1c6bab8f6f12ddc7b800b83de",
    "scripts/run_p181_augmented_nullspace_synthetic_solve_gated.py": None,
    "scripts/freeze_p181_augmented_nullspace_synthetic_solve.py": None,
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    return (completed.stdout or completed.stderr).strip()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    bound = {}
    for relative, expected in BOUND.items():
        observed = file_hash(CAMPAIGN / relative)
        if expected is not None and observed != expected:
            raise ValueError(f"bound file drift: {relative}")
        bound[relative] = observed
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-implementation-freeze.v1",
        "status": "PASS_P181_AUGMENTED_NULLSPACE_SYNTHETIC_SOLVE_IMPLEMENTATION_FREEZE",
        "preregistration": {"path": PREREG, "sha256": file_hash(CAMPAIGN / PREREG)},
        "bound_files": bound,
        "toolchain": {
            "clang_version": command_output(["clang++", "--version"]).splitlines()[:2],
            "linbox_version": command_output(["pkg-config", "--modversion", "linbox"]),
            "fflas_ffpack_version": command_output(["pkg-config", "--modversion", "fflas-ffpack"]),
            "givaro_version": command_output(["pkg-config", "--modversion", "givaro"]),
            "linbox_pkg_config_flags": command_output(["pkg-config", "--cflags", "--libs", "linbox"]),
            "compile_command": "clang++ -std=c++17 -O3 scripts/linbox_augmented_nullspace_mod181_solve_driver.cpp -o artifacts/bin/linbox_augmented_nullspace_mod181_solve_driver $(pkg-config --cflags --libs linbox)",
        },
        "stages": {
            "4096": {"coefficient_nonzeros": 146642, "expected_solution_sha256": "b96a4e6c7023bcf352f716803c627f5381b59acd57672b31e5e0aba219b99bcb", "wall_seconds_maximum": 90, "rss_bytes_maximum": 1073741824},
            "8192": {"coefficient_nonzeros": 301450, "expected_solution_sha256": "a7ca07d2c1c68216056e685b057e94f54fe9da5714b3473622a649ad449f831c", "wall_seconds_maximum": 150, "rss_bytes_maximum": 1610612736},
            "16384": {"coefficient_nonzeros": 546088, "expected_solution_sha256": "d5bfcb5934119b4f29e7254d8cd620b21bc51bda0d17281bd348be2b3a3a609a", "wall_seconds_maximum": 300, "rss_bytes_maximum": 2684354560},
            "35881": {"coefficient_nonzeros": 1354540, "expected_solution_sha256": "ebcf2e6338e5eb81ba7b9fd58f8c9366a8b5ddb48c27cef7fcd34e9c27663d28", "wall_seconds_maximum": 600, "rss_bytes_maximum": 3758096384}
        },
        "policy": {"stage_order": [4096, 8192, 16384, 35881], "process_swaps_maximum": 0, "later_stage_requires_predecessor_pass": True},
        "canonical_outputs": {
            "artifact": "artifacts/third-colon-p181-augmented-nullspace-synthetic-solve-v1",
            "telemetry": "receipts/telemetry/third-colon-p181-augmented-nullspace-synthetic-solve-v1",
            "terminal": "receipts/hsop-j2-secant-r10-p181-augmented-nullspace-synthetic-solve-v1.json"
        },
        "declarations": {"frozen_before_actual_csr_execution": True, "target_rhs_excluded": True, "existing_multiplier_vectors_excluded": True, "no_mod181_squared": True},
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

