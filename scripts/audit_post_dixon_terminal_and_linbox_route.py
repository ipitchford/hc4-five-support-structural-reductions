#!/usr/bin/env python3
"""Final readback audit for the Dixon terminal and successor route signal."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-post-dixon-terminal-and-linbox-route-audit.json"
EXPECTED = {
    "v3_freeze": ("receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v3.json", "728854a2bb435667ed993af8e3d8afc82c592d89c25db87cc49c0d4fc0c3983b"),
    "v3_terminal": ("receipts/hsop-j2-secant-r10-third-colon-dixon-p181-phase1-v3-terminal.json", "8fc302fece32a36ad22d2fc282280debeb52b987364f4fda551532108fe47541"),
    "linbox_scout": ("receipts/hsop-j2-secant-r10-third-colon-linbox-synthetic-capability-scout.json", "7efab56e0eeb5f2dcfea8a86873ea1bb8ad51f6578842b44865002bc2e5d1763"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    bindings = {}
    for name, (relative, expected) in EXPECTED.items():
        path = CAMPAIGN / relative
        require(path.is_file() and digest(path) == expected, f"binding drift: {name}")
        bindings[name] = {"path": relative, "sha256": expected}
    freeze = json.loads((CAMPAIGN / EXPECTED["v3_freeze"][0]).read_text(encoding="utf-8"))
    for relative, expected in freeze["implementation_sources"].items():
        require(digest(CAMPAIGN / relative) == expected, f"frozen v3 source changed: {relative}")
    terminal = json.loads((CAMPAIGN / EXPECTED["v3_terminal"][0]).read_text(encoding="utf-8"))
    require(terminal.get("status") == "STOP_PHASE1_WALL_AND_RSS_V3_IMPLEMENTATION_FAMILY_TERMINAL", "v3 terminal status drift")
    require(terminal["observations"]["elimination_complete_milestone_observed"] is False, "v3 elimination terminal drift")
    require(terminal["declarations"]["no_Dixon_digit_computed"] is True, "digit absence declaration drift")
    scout = json.loads((CAMPAIGN / EXPECTED["linbox_scout"][0]).read_text(encoding="utf-8"))
    require(scout.get("status") == "PASS_SYNTHETIC_COMPILED_SPARSE_PRIME_FIELD_CAPABILITY_SIGNAL", "LinBox scout status drift")
    require(scout["declarations"]["fixed_HC4_matrix_not_built_or_opened"] is True and scout["declarations"]["b_Z_not_read"] is True, "LinBox claim boundary drift")
    source_record = scout["source"]
    require(digest(CAMPAIGN / source_record["path"]) == source_record["sha256"], "LinBox scout source changed after run")

    ledger = json.loads((CAMPAIGN / "CLAIM_LEDGER.json").read_text(encoding="utf-8"))
    claims = ledger["claims"]
    ids = [claim["id"] for claim in claims]
    require(len(ids) == len(set(ids)), "duplicate claim ids")
    target_ids = {
        "FS-HSOP-SECANT-J2-THIRD-COLON-DIXON-P181-PHASE1-TERMINAL",
        "FS-HSOP-SECANT-J2-LINBOX-SYNTHETIC-CAPABILITY",
    }
    selected = {claim["id"]: claim for claim in claims if claim["id"] in target_ids}
    require(set(selected) == target_ids, "new ledger claim missing")
    missing_evidence = []
    for claim in selected.values():
        for relative in claim["evidence"]:
            if not (CAMPAIGN / relative).exists():
                missing_evidence.append(relative)
    require(not missing_evidence, f"new claim evidence absent: {missing_evidence}")

    canonical = [
        "artifacts/j2-secant-r10-third-colon-dixon-p181-phase1-bundle-v3",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-factorization-freeze-v3.json",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-producer-8digit-bundle-v3",
        "artifacts/j2-secant-r10-third-colon-dixon-p181-independent-8digit-bundle-v3",
        "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-8digit-terminal-v3.json",
    ]
    existing = [relative for relative in canonical if (CAMPAIGN / relative).exists()]
    require(not existing, f"forbidden canonical v3 output exists: {existing}")
    documents = {
        relative: digest(CAMPAIGN / relative)
        for relative in ("README.md", "RESEARCH_METRICS.md", "NEXT_GOAL_HSOP_NULLCONE.md", "CLAIM_LEDGER.json")
    }
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-post-dixon-terminal-and-linbox-route-audit.v1",
        "status": "PASS_POST_DIXON_TERMINAL_AND_SUCCESSOR_ROUTE_READBACK",
        "bindings": bindings,
        "frozen_v3_implementation_source_count": len(freeze["implementation_sources"]),
        "frozen_v3_sources_still_match": True,
        "new_claim_ids": sorted(target_ids),
        "new_claim_evidence_missing": missing_evidence,
        "forbidden_canonical_v3_outputs_existing": existing,
        "updated_document_sha256": documents,
        "declarations": {"Dixon_implementation_family_terminal_preserved": True, "no_factorization_index": True, "no_Dixon_digit": True, "LinBox_signal_synthetic_only": True, "HC4_still_open": True},
        "claim_boundary": "This readback certifies only documentation, immutable-source, evidence-path, and terminal-state consistency. It supplies no new rank, solve, p-adic digit, Q identity, colon, saturation, secant closure, nullcone containment, or HC4 result.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": digest(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
