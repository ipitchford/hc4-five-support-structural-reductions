#!/usr/bin/env python3
"""Freeze the exact terminal meaning of the v2 Phase-I timeout."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v2.json"
PREAUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-v2-preimplementation-audit.json"
QUARANTINE = CAMPAIGN / "artifacts/quarantine/third-colon-fixed-p181-dixon-phase1-20260831T-v2-001"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-phase1-v2-terminal.json"
EXPECTED = {
    "freeze": "710b5f768c1693dc79faf604b8581711cf6d277711acd84ac84206274525699d",
    "preaudit": "c434b7f7d6f6ea06f027d8404f70937fda32f26cef86a4b41efd77eef93ebfae",
    "not_evidence": "9ac52e2f5dd4ee7badbd7f8029e244f70060d753d1e36d034e4595ca08215671",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    first = re.search(r"^\s*([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys\s*$", text, re.MULTILINE)
    rss = re.findall(r"^\s*(\d+)\s+maximum resident set size\s*$", text, re.MULTILINE)
    swaps = re.findall(r"^\s*(\d+)\s+swaps\s*$", text, re.MULTILINE)
    if first is None or len(rss) != 1 or swaps != ["0"]:
        raise ValueError(f"invalid external telemetry: {path}")
    return {
        "real_seconds": float(first.group(1)),
        "user_seconds": float(first.group(2)),
        "system_seconds": float(first.group(3)),
        "maximum_rss_bytes": int(rss[0]),
        "process_swaps": 0,
        "sha256": digest(path),
    }


def main() -> int:
    if digest(FREEZE) != EXPECTED["freeze"] or digest(PREAUDIT) != EXPECTED["preaudit"]:
        raise ValueError("v2 freeze or preaudit drift")
    not_evidence = QUARANTINE / "NOT_EVIDENCE.json"
    observed_not_evidence = digest(not_evidence)
    if observed_not_evidence != EXPECTED["not_evidence"]:
        raise ValueError(f"quarantine receipt hash drift: {observed_not_evidence}")
    quarantine_receipt = json.loads(not_evidence.read_text(encoding="utf-8"))
    if quarantine_receipt.get("status") != "NOT_EVIDENCE" or quarantine_receipt.get("error") != "factorizer exited 124":
        raise ValueError("quarantine terminal drift")
    telemetry_root = QUARANTINE / "third-colon-fixed-p181-dixon-phase1-telemetry-v2-20260831T-v2-001"
    pre = parse_time(telemetry_root / "preprocessor.time.txt")
    factor = parse_time(telemetry_root / "factorizer.time.txt")
    if pre["maximum_rss_bytes"] > 3_500_000_000 or factor["maximum_rss_bytes"] > 3_500_000_000:
        raise ValueError("an RSS gate also failed")
    staged_root = QUARANTINE / "third-colon-fixed-p181-dixon-phase1-v2-20260831T-v2-001"
    staged_files = sorted(item.name for item in staged_root.iterdir())
    if staged_files != ["integer-system.bin", "integer-system.json"]:
        raise ValueError(f"unexpected partial staged files: {staged_files}")
    canonical = [
        "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v2",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-telemetry-v2",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v2.json",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-producer-8digit-bundle-v2",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-independent-8digit-bundle-v2",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v2.json",
    ]
    existing = [relative for relative in canonical if (CAMPAIGN / relative).exists()]
    if existing:
        raise ValueError(f"canonical v2 PASS output survived: {existing}")
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-phase1-v2-terminal.v1",
        "status": "STOP_PHASE1_THROUGHPUT_V2",
        "bindings": {
            "implementation_freeze_sha256": EXPECTED["freeze"],
            "preimplementation_audit_sha256": EXPECTED["preaudit"],
            "quarantine_not_evidence_sha256": observed_not_evidence,
        },
        "external_telemetry": {"preprocessor": pre, "factorizer": factor},
        "observations": {
            "preprocessor_completed": True,
            "factorizer_exit_code": 124,
            "factorization_artifact_emitted": False,
            "memory_gate_passed": True,
            "literal_zero_swap_gate_passed": True,
            "wall_gate_passed": False,
            "rank_conclusion_available": False,
            "algebra_failure_observed": False,
        },
        "canonical_v2_paths_existing": existing,
        "declarations": {
            "no_factorization_freeze_index": True,
            "no_arithmetic_modulo_181_squared": True,
            "no_Dixon_digit_computed": True,
            "quarantined_integer_system_cannot_feed_later_run": True,
        },
        "claim_boundary": "This terminal falsifies only the frozen v2 implementation under its 600-second Phase-I protocol. It does not falsify rank, the p181 lift, a QQ identity, ideal membership, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
