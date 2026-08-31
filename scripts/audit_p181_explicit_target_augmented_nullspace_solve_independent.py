#!/usr/bin/env python3
"""Standard-library all-row replay of the explicit p181 target solution."""

from __future__ import annotations

import hashlib
import json
import platform
import resource
import struct
import time
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
TERMINAL = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-explicit-target-solve.json"
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-explicit-target-solve-implementation-freeze.json"
CSR = CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr"
RHS = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-rhs-v1/target_rhs_mod181.u8"
SOLUTION = CAMPAIGN / "artifacts/third-colon-p181-explicit-target-solve-v1/solution_mod181.u8"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-explicit-target-solve-independent-audit.json"
CSR_SHA256 = "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef"
RHS_SHA256 = "72d15610c6630a4d1929029476cb9b01d8494bc502b9b68457674795dcd1c76f"
RANK_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json"
RHS_AUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-explicit-target-rhs-independent-audit.json"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def read_csr() -> tuple[list[int], list[int], bytes]:
    payload = CSR.read_bytes()
    require(file_hash(CSR) == CSR_SHA256, "CSR hash drift")
    require(payload[:8] == b"HC4AC181", "CSR magic drift")
    rows, columns, nonzeros = struct.unpack_from("<QQQ", payload, 8)
    require((rows, columns, nonzeros) == (85_651, 35_881, 1_354_540), "CSR dimensions drift")
    cursor = 32
    offsets = list(struct.unpack_from(f"<{rows + 1}Q", payload, cursor))
    cursor += 8 * (rows + 1)
    indices = [item[0] for item in struct.iter_unpack("<I", payload[cursor:cursor + 4 * nonzeros])]
    cursor += 4 * nonzeros
    values = payload[cursor:cursor + nonzeros]
    cursor += nonzeros
    require(cursor == len(payload), "CSR trailing bytes")
    require(offsets[0] == 0 and offsets[-1] == nonzeros, "CSR offset boundaries drift")
    return offsets, indices, values


def main() -> int:
    started = time.perf_counter()
    initial_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    require(not OUTPUT.exists(), "independent audit output already exists")
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    require(freeze.get("status") == "PASS_P181_EXPLICIT_TARGET_SOLVE_IMPLEMENTATION_FREEZE", "freeze PASS drift")
    relative_self = str(Path(__file__).resolve().relative_to(CAMPAIGN))
    require(freeze["bound_files"].get(relative_self) == file_hash(Path(__file__).resolve()), "audit source not bound by freeze")
    for relative, expected in freeze["bound_files"].items():
        require(file_hash(CAMPAIGN / relative) == expected, f"freeze-bound file drift: {relative}")

    terminal = json.loads(TERMINAL.read_text(encoding="utf-8"))
    require(terminal.get("status") == "PASS_P181_EXPLICIT_TARGET_AUGMENTED_NULLSPACE_SOLVE", "producer terminal is not PASS")
    require(terminal["driver"].get("replay_mismatches") == 0, "producer replay mismatch")
    require(terminal["driver"].get("augmented_nullity") == 1, "producer augmented nullity drift")
    require(0 < int(terminal["driver"].get("last_null_coordinate", 0)) < 181, "producer last coordinate drift")

    rank_audit = json.loads(RANK_AUDIT.read_text(encoding="utf-8"))
    rhs_audit = json.loads(RHS_AUDIT.read_text(encoding="utf-8"))
    require(
        rank_audit.get("status")
        == "PASS_INDEPENDENT_ACTUAL_COEFFICIENT_LINBOX_RANK_SCALING_AUDIT",
        "rank audit PASS drift",
    )
    require(rhs_audit.get("status") == "PASS_INDEPENDENT_P181_EXPLICIT_TARGET_RHS_REPLAY", "RHS audit PASS drift")
    rhs = RHS.read_bytes()
    solution = SOLUTION.read_bytes()
    require(file_hash(RHS) == RHS_SHA256 and len(rhs) == 85_651, "RHS drift")
    require(len(solution) == 35_881 and all(value < 181 for value in solution), "solution residue stream drift")
    require(terminal["solution"]["sha256"] == file_hash(SOLUTION), "terminal solution hash drift")
    require(terminal["solution"]["bytes"] == len(solution), "terminal solution length drift")

    offsets, indices, values = read_csr()
    replay = bytearray(85_651)
    mismatches = 0
    for row in range(85_651):
        total = 0
        for position in range(offsets[row], offsets[row + 1]):
            total += values[position] * solution[indices[position]]
        replay[row] = total % 181
        if replay[row] != rhs[row]:
            mismatches += 1
    require(mismatches == 0, "independent all-row target replay failed")
    external = terminal["telemetry"]["external_time"]
    require(
        external["real_seconds"] <= 600
        and external["maximum_rss_bytes"] <= 3_758_096_384
        and external["process_swaps"] == 0,
        "producer resource gate drift",
    )
    final_swaps = int(resource.getrusage(resource.RUSAGE_SELF).ru_nswap)
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-explicit-target-solve-independent-audit.v1",
        "status": "PASS_INDEPENDENT_P181_EXPLICIT_TARGET_IDENTITY_REPLAY",
        "bound_hashes": {
            "terminal": file_hash(TERMINAL),
            "freeze": file_hash(FREEZE),
            "csr": file_hash(CSR),
            "rhs": file_hash(RHS),
            "solution": file_hash(SOLUTION),
            "rank_audit": file_hash(RANK_AUDIT),
            "rhs_audit": file_hash(RHS_AUDIT),
        },
        "replay": {
            "rows": 85_651,
            "columns": 35_881,
            "coefficient_nonzeros": 1_354_540,
            "mismatches": mismatches,
            "replayed_rhs_sha256": hashlib.sha256(replay).hexdigest(),
            "expected_rhs_sha256": RHS_SHA256,
            "solution_sha256": file_hash(SOLUTION),
            "solution_nonzero_coordinates": sum(value != 0 for value in solution),
        },
        "resources": {
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_bytes": max_rss_bytes(),
            "process_swap_delta": final_swaps - initial_swaps,
            "producer_external": external,
        },
        "declarations": {
            "standard_library_replay": True,
            "producer_not_imported_or_executed": True,
            "linbox_not_called": True,
            "existing_prior_multiplier_not_read": True,
            "no_mod181_squared": True,
            "no_rational_reconstruction": True,
        },
        "claim_boundary": (
            "This PASS independently certifies the explicit fixed-gauge multiplier identity for M*h3 over "
            "GF(181). It does not establish the identity over QQ, a p-adic lift, a colon or saturation "
            "equality, secant closure, nullcone containment, or HC4."
        ),
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
