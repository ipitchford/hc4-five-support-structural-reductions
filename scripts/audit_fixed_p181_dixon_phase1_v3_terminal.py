#!/usr/bin/env python3
"""Freeze the wall/RSS terminal of the registered v3 factorizer family."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
FREEZE = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v3.json"
PREAUDIT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-v3-preimplementation-audit.json"
QUARANTINE = CAMPAIGN / "artifacts/quarantine/third-colon-fixed-p181-dixon-phase1-20260831T-v3-001"
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-phase1-v3-terminal.json"
EXPECTED = {
    "freeze": "728854a2bb435667ed993af8e3d8afc82c592d89c25db87cc49c0d4fc0c3983b",
    "preaudit": "39c7673064e6c3e1f2998b427e12d5b249dfa006b2affd14b5b71f8a096e8582",
    "not_evidence": "05cab42e7bf5381c8461a0692647eb447ccd98462bb23d88cd5e9a80545fff43",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    first = re.search(r"^\s*([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys\s*$", text, re.MULTILINE)
    rss = re.findall(r"^\s*(\d+)\s+maximum resident set size\s*$", text, re.MULTILINE)
    swaps = re.findall(r"^\s*(\d+)\s+swaps\s*$", text, re.MULTILINE)
    if first is None or len(rss) != 1 or swaps != ["0"]:
        raise ValueError(f"invalid telemetry: {path}")
    return {
        "real_seconds": float(first.group(1)), "user_seconds": float(first.group(2)),
        "system_seconds": float(first.group(3)), "maximum_rss_bytes": int(rss[0]),
        "process_swaps": 0, "sha256": digest(path),
    }


def main() -> int:
    if digest(FREEZE) != EXPECTED["freeze"] or digest(PREAUDIT) != EXPECTED["preaudit"]:
        raise ValueError("v3 freeze or preaudit drift")
    not_evidence = QUARANTINE / "NOT_EVIDENCE.json"
    if digest(not_evidence) != EXPECTED["not_evidence"]:
        raise ValueError("v3 quarantine receipt drift")
    quarantine = json.loads(not_evidence.read_text(encoding="utf-8"))
    if quarantine.get("status") != "NOT_EVIDENCE" or quarantine.get("error") != "factorizer exited 124":
        raise ValueError("v3 quarantine terminal changed")
    telemetry_root = QUARANTINE / "third-colon-fixed-p181-dixon-phase1-telemetry-v3-20260831T-v3-001"
    pre = parse_time(telemetry_root / "preprocessor.time.txt")
    factor = parse_time(telemetry_root / "factorizer.time.txt")
    milestones = [
        json.loads(line)
        for line in (telemetry_root / "factorizer.stderr.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if [item.get("milestone") for item in milestones] != ["INPUT_LOADED"]:
        raise ValueError(f"unexpected milestone terminal: {milestones}")
    if factor["maximum_rss_bytes"] <= 3_500_000_000:
        raise ValueError("registered v3 RSS failure not reproduced")
    staged = QUARANTINE / "third-colon-fixed-p181-dixon-phase1-v3-20260831T-v3-001"
    if sorted(item.name for item in staged.iterdir()) != ["integer-system.bin", "integer-system.json"]:
        raise ValueError("unexpected v3 partial output set")
    canonical = [
        "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v3",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-telemetry-v3",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v3.json",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-producer-8digit-bundle-v3",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-independent-8digit-bundle-v3",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v3.json",
    ]
    existing = [relative for relative in canonical if (CAMPAIGN / relative).exists()]
    if existing:
        raise ValueError(f"canonical v3 output survived: {existing}")
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-phase1-v3-terminal.v1",
        "status": "STOP_PHASE1_WALL_AND_RSS_V3_IMPLEMENTATION_FAMILY_TERMINAL",
        "bindings": {"implementation_freeze_sha256": EXPECTED["freeze"], "preimplementation_audit_sha256": EXPECTED["preaudit"], "quarantine_not_evidence_sha256": EXPECTED["not_evidence"]},
        "external_telemetry": {"preprocessor": pre, "factorizer": factor},
        "factorizer_milestones": milestones,
        "observations": {
            "preprocessor_completed": True, "factorizer_exit_code": 124,
            "input_loaded_milestone_observed": True, "elimination_complete_milestone_observed": False,
            "factorization_artifact_emitted": False, "wall_gate_passed": False,
            "memory_gate_passed": False, "literal_zero_swap_gate_passed": True,
            "serialization_bottleneck_hypothesis_supported": False,
            "python_sparse_factorizer_family_terminated_by_amendment_04": True,
            "rank_conclusion_available": False, "algebra_failure_observed": False,
        },
        "canonical_v3_paths_existing": existing,
        "declarations": {"no_factorization_freeze_index": True, "no_arithmetic_modulo_181_squared": True, "no_Dixon_digit_computed": True, "quarantined_integer_system_cannot_feed_later_run": True, "no_v4_retry_licensed": True},
        "claim_boundary": "This terminal ends only the registered Python sparse-factorization implementation family. It does not falsify rank, the p181 lift, a QQ identity, ideal membership, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
