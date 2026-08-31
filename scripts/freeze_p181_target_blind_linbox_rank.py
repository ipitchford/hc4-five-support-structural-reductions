#!/usr/bin/env python3
"""Freeze the complete implementation before the actual p181 rank benchmark."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze.json"
PREREG = "research/THIRD_COLON_P181_TARGET_BLIND_LINBOX_RANK_PREREGISTRATION.md"
PREREG_SHA256 = "d719e43e886bd771564110ea18dd4e1476c87ca658f925ee573bf86aa2669a58"
IMPLEMENTATION = (
    "scripts/extract_p181_target_blind_linbox_gauge.py",
    "scripts/benchmark_p181_target_blind_linbox_rank.py",
    "scripts/run_p181_target_blind_linbox_rank_gated.py",
    "scripts/freeze_p181_target_blind_linbox_rank.py",
)
ALGEBRA = {
    "scripts/certify_j2_secant_r10_colon_identity_liftstd.py": "e946e9e4b5ad1f7e7b62b688c03502f4331c463cd691e66b4f207d4b2b96f34c",
    "scripts/certify_j2_secant_r10_second_colon_identity_sparse_macaulay.py": "ea20fb8719bb583c424f0cc4e2730b46c7f38e130558fa7e6d2422865fb1af6b",
    "scripts/certify_j2_secant_r10_z12_macaulay.py": "fd49512f605cb257d62aea850fe795d61db04ca23df9504910f157cfe1436d26",
    "scripts/scout_j2_secant_r10_homogeneous_saturation.py": "8ba0c949784491272323cf2b411b0055c7d81d810513faa5428ed90fe1293a14",
    "scripts/scout_decimic_nullcone_hsop.py": "b07062cc86c2f5adf40a0d236648871b54c6ace1403886b51670ed539c425061",
    "research/j2_secant_r10_colon_kernel_candidate_p1073741827.json": "1787ac75c59d553bfe64f767f739a1a0f6a4cb0f19dc18228f748476ea4292a3",
    "research/j2_secant_r10_colon_kernel_candidate_p1073742851.json": "d57655a3efe5c949488f916a641cb98c133b88181e2a4028946bda610c1ced04",
    "artifacts/j2-secant-r10-second-colon-kernel-qq-candidate.json": "c41e7c02e7163a0f1a2e71cd7fd5f0d38167b37f3f832019fa069c0ffd2bf37e",
    "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json": "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    if file_hash(CAMPAIGN / PREREG) != PREREG_SHA256:
        raise ValueError("preregistration changed before freeze")
    for relative, expected in ALGEBRA.items():
        if file_hash(CAMPAIGN / relative) != expected:
            raise ValueError(f"frozen prior source drift: {relative}")
    implementation = {relative: file_hash(CAMPAIGN / relative) for relative in IMPLEMENTATION}
    toolchain = {
        "sage": "/Users/admin/.local/bin/sage",
        "sage_version": subprocess.run(["/Users/admin/.local/bin/sage", "--version"], text=True, capture_output=True, check=True).stdout.strip(),
        "external_time": "/usr/bin/time",
        "gtimeout": "/opt/homebrew/bin/gtimeout",
    }
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-implementation-freeze.v1",
        "status": "PASS_P181_TARGET_BLIND_LINBOX_IMPLEMENTATION_FREEZE",
        "preregistration": {"path": PREREG, "sha256": PREREG_SHA256},
        "implementation_sources": implementation,
        "algebra_and_prior_sources": ALGEBRA,
        "toolchain": toolchain,
        "policy": {
            "rank_wall_seconds_maximum": 600,
            "rank_rss_bytes_maximum": 3_758_096_384,
            "process_swaps_maximum": 0,
            "prefixes": [4_096, 8_192, 16_384, 35_881],
        },
        "canonical_outputs": {
            "gauge": "artifacts/third-colon-p181-target-blind-linbox-gauge-v1",
            "benchmark": "artifacts/third-colon-p181-target-blind-linbox-benchmark-v1",
            "telemetry": "receipts/telemetry/third-colon-p181-target-blind-linbox-v1",
            "terminal": "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal.json",
        },
        "declarations": {"frozen_before_gauge_extraction": True, "frozen_before_actual_coefficient_construction": True},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
