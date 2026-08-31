#!/usr/bin/env python3
"""Audit the reserved fixed-free source batch for the third colon identity.

This script performs no CRT or rational reconstruction.  It checks that every
reserved source is a passing, aligned modular identity certificate and freezes
the source hashes and resource telemetry needed by a separate reconstruction
lane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path


PRIMES = (
    2147483647,
    2147483629,
    2147483587,
    2147483579,
    2147483563,
    2147483549,
    2147483353,
    2147483269,
)
EXPECTED_STATUS = "PASS_EXACT_MODULAR_THIRD_COLON_IDENTITY"
EXPECTED_RECEIPT_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-identity-sparse-macaulay.v1"
)
EXPECTED_CERTIFICATE_SCHEMA = (
    "hc4.decimic-j2-secant-r10-third-colon-identity-"
    "sparse-macaulay-certificate.v1"
)
EXPECTED_GAUGE_SHA256 = "e55af2dc2d7f390227bda852f5366d68f078500e00794e3a60d7cc4452797ec1"
EXPECTED_FREE_HASH = "ddcaae88f432744341df10a77d66a5d791d1b7c46e3285020f08a1795815b8b1"
EXPECTED_GENERATOR_HASH = "4e5ca7f6ed60548f84d6a84a4fa272c044b76be4ab3788b091376bf54f9ada4b"
EXPECTED_TARGET_HASH = "32e84450b525fce0c9fca7d263e6d73a2b9508811fa4bd7e473002a08ab2c84e"
EXPECTED_DESCRIPTOR_HASH = "0f0e46bb94241fa478c6cbdcf33c4472128ad4ed48a8fdaebd88e19028948639"
EXPECTED_MONOMIAL_HASH = "153dd5ae53908e06fa5b4722c88cdffd823d5705a9a6ab1e8ca6f5f070665614"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "receipts/hsop-j2-secant-r10-third-colon-identity-"
            "fixed-free-source-batch-reserved.json"
        ),
    )
    arguments = parser.parse_args()
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    rows = []
    for prime in PRIMES:
        receipt_path = campaign / (
            "receipts/hsop-j2-secant-r10-third-colon-identity-"
            f"fixed-free-p{prime}.json"
        )
        require(receipt_path.is_file(), f"missing receipt for p={prime}")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        prefix = f"p={prime}"
        require(receipt.get("schema") == EXPECTED_RECEIPT_SCHEMA, f"{prefix}: schema")
        require(receipt.get("status") == EXPECTED_STATUS, f"{prefix}: status")
        require(int(receipt.get("characteristic", 0)) == prime, f"{prefix}: field")
        solver = receipt["solver"]
        require(solver.get("completed") is True, f"{prefix}: incomplete")
        require(solver.get("timed_out") is False, f"{prefix}: timeout")
        require(solver.get("consistent") is True, f"{prefix}: inconsistent")
        require(solver.get("fixed_gauge_failure") is None, f"{prefix}: gauge failure")
        require(int(solver.get("pivot_count", -1)) == 35881, f"{prefix}: pivots")
        require(int(solver.get("free_unknown_count", -1)) == 2167, f"{prefix}: free")
        require(int(solver.get("active_equation_count", -1)) == 0, f"{prefix}: active rows")
        replay = receipt["same_process_sparse_replay"]
        require(replay.get("completed") is True, f"{prefix}: replay incomplete")
        require(replay.get("identity_zero") is True, f"{prefix}: nonzero remainder")
        require(int(replay.get("mismatch_count", -1)) == 0, f"{prefix}: mismatches")
        gauge = receipt["gauge"]
        require(gauge.get("coverage_verified") is True, f"{prefix}: gauge coverage")
        require(gauge.get("free_unknown_indices_sha256") == EXPECTED_FREE_HASH, f"{prefix}: free hash")
        require(gauge["source"].get("sha256") == EXPECTED_GAUGE_SHA256, f"{prefix}: gauge source")
        hashes = receipt["hashes"]
        require(hashes.get("generator_stream_sha256") == EXPECTED_GENERATOR_HASH, f"{prefix}: generators")
        require(hashes.get("target_sha256") == EXPECTED_TARGET_HASH, f"{prefix}: target")
        require(hashes.get("row_descriptor_sha256") == EXPECTED_DESCRIPTOR_HASH, f"{prefix}: descriptors")
        require(hashes.get("monomial_stream_sha256") == EXPECTED_MONOMIAL_HASH, f"{prefix}: monomials")

        certificate_record = receipt["certificate"]
        require(certificate_record is not None, f"{prefix}: missing certificate")
        certificate_path = Path(certificate_record["path"])
        require(certificate_path.is_file(), f"{prefix}: certificate path")
        certificate_hash = sha256(certificate_path)
        require(certificate_hash == certificate_record["sha256"], f"{prefix}: certificate hash")
        require(certificate_path.stat().st_size == int(certificate_record["byte_count"]), f"{prefix}: certificate size")
        certificate = json.loads(certificate_path.read_text(encoding="ascii"))
        require(certificate.get("schema") == EXPECTED_CERTIFICATE_SCHEMA, f"{prefix}: certificate schema")
        require(int(certificate.get("characteristic", 0)) == prime, f"{prefix}: certificate field")
        require(certificate.get("free_unknown_indices_sha256") == EXPECTED_FREE_HASH, f"{prefix}: certificate gauge")
        require(certificate.get("generator_stream_sha256") == EXPECTED_GENERATOR_HASH, f"{prefix}: certificate generators")
        require(certificate.get("target_sha256") == EXPECTED_TARGET_HASH, f"{prefix}: certificate target")
        require(len(certificate.get("coordinate_vector", [])) == 38048, f"{prefix}: coordinate length")

        rows.append(
            {
                "characteristic": prime,
                "receipt": {
                    "path": str(receipt_path),
                    "sha256": sha256(receipt_path),
                    "byte_count": receipt_path.stat().st_size,
                },
                "certificate": {
                    "path": str(certificate_path),
                    "sha256": certificate_hash,
                    "byte_count": certificate_path.stat().st_size,
                    "coordinate_vector_sha256": certificate["coordinate_vector_sha256"],
                    "solution_support_count": len(certificate["solution_support"]),
                },
                "solver": {
                    "pivot_count": solver["pivot_count"],
                    "free_unknown_count": solver["free_unknown_count"],
                    "solve_seconds": solver["solve_seconds"],
                    "peak_total_nonzeros": solver["peak_total_nonzeros"],
                    "maximum_active_equation_length": solver["maximum_active_equation_length"],
                    "update_count": solver["update_count"],
                },
                "replay": replay,
                "timings": receipt["timings"],
                "resources": receipt["resources"],
                "source_hashes": hashes,
            }
        )

    walls = [float(row["timings"]["wall_seconds"]) for row in rows]
    solves = [float(row["solver"]["solve_seconds"]) for row in rows]
    rss = [int(row["resources"]["maximum_rss_native"]) for row in rows]
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-fixed-free-source-batch.v1",
        "status": "PASS_EIGHT_ALIGNED_FIXED_FREE_MODULAR_SOURCES",
        "assurance": "exact receipt and certificate integrity audit; no QQ reconstruction",
        "source_count": len(rows),
        "characteristics": list(PRIMES),
        "shared_invariants": {
            "unknown_multiplier_coordinates": 38048,
            "pivot_count": 35881,
            "free_unknown_count": 2167,
            "gauge_source_sha256": EXPECTED_GAUGE_SHA256,
            "free_unknown_indices_sha256": EXPECTED_FREE_HASH,
            "generator_stream_sha256": EXPECTED_GENERATOR_HASH,
            "target_sha256": EXPECTED_TARGET_HASH,
            "row_descriptor_sha256": EXPECTED_DESCRIPTOR_HASH,
            "monomial_stream_sha256": EXPECTED_MONOMIAL_HASH,
            "all_same_process_remainders_zero": True,
            "all_gauge_coverage_verified": True,
        },
        "sources": rows,
        "aggregate_telemetry": {
            "sum_wall_seconds": sum(walls),
            "minimum_wall_seconds": min(walls),
            "median_wall_seconds": statistics.median(walls),
            "maximum_wall_seconds": max(walls),
            "sum_solve_seconds": sum(solves),
            "maximum_rss_native": max(rss),
            "minimum_rss_native": min(rss),
        },
        "script": {
            "path": str(script_path.relative_to(campaign)),
            "sha256": sha256(script_path),
        },
        "wall_seconds": time.perf_counter() - started,
        "claim_boundary": (
            "These are eight aligned exact finite-field identities. This audit does "
            "not perform rational reconstruction, prove a QQ identity, compute a "
            "colon or saturation, close the secant chart, or establish HC4."
        ),
    }
    output = arguments.output
    if not output.is_absolute():
        output = campaign / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
