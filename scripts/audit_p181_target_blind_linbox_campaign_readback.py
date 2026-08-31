#!/usr/bin/env python3
"""Close the actual-coefficient rank turn with ledger/document readback."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-target-blind-linbox-campaign-readback.json"
BOUND = {
    "v1_terminal": ("receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal.json", "71de230e2166a8eaeff9e125fd2ef6d40527b0f5334fe19c39f4da288427f6c1"),
    "v2_freeze": ("receipts/hsop-j2-secant-r10-p181-target-blind-linbox-implementation-freeze-v2.json", "2510d05c50ba745ab3d64bdb8bcd6fdcc971444c3ba344f1120b549d16bd3c48"),
    "v2_terminal": ("receipts/hsop-j2-secant-r10-p181-target-blind-linbox-terminal-v2.json", "7b3da03bd0325b8a64340c9195632b85b6df7e33efc428f330e1698ec202aba9"),
    "v2_independent_audit": ("receipts/hsop-j2-secant-r10-p181-target-blind-linbox-v2-independent-audit.json", "c6bec6f72d7ba5c0792cfe439383d1795ae82160c570148e1b7899807bd81c37"),
    "v2_benchmark": ("artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/benchmark.json", "6a28f331c768a2fba46a32acacf181897a9522ce01428c3f9e4e2ca6c50480b9"),
    "v2_csr": ("artifacts/third-colon-p181-target-blind-linbox-benchmark-v2/A_C_mod181_target_free.csr", "2207744adde8f96a7d835fc078ffd188ce33814f2db880e1aef9b8a47b09a6ef"),
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> int:
    require(not OUTPUT.exists(), "campaign readback already exists")
    bindings = {}
    for label, (relative, expected) in BOUND.items():
        path = CAMPAIGN / relative
        require(path.is_file() and file_hash(path) == expected, f"bound artifact drift: {label}")
        bindings[label] = {"path": relative, "sha256": expected}
    terminal = json.loads((CAMPAIGN / BOUND["v2_terminal"][0]).read_text(encoding="utf-8"))
    benchmark = json.loads((CAMPAIGN / BOUND["v2_benchmark"][0]).read_text(encoding="utf-8"))
    audit = json.loads((CAMPAIGN / BOUND["v2_independent_audit"][0]).read_text(encoding="utf-8"))
    require(terminal["status"] == benchmark["status"] == "PASS_ACTUAL_COEFFICIENT_LINBOX_FULL_COLUMN_RANK_SCALING", "v2 PASS drift")
    require(audit["status"] == "PASS_INDEPENDENT_ACTUAL_COEFFICIENT_LINBOX_RANK_SCALING_AUDIT", "independent audit drift")
    require([(case["columns"], case["linbox_rank"]) for case in benchmark["cases"]] == [(4096, 4096), (8192, 8192), (16384, 16384), (35881, 35881)], "rank ledger drift")
    require(benchmark["construction"]["rows"] == 85_651 and benchmark["construction"]["selected_nonzeros"] == 1_354_540, "matrix dimensions drift")
    require(benchmark["construction"]["nonunit_row_scalings"] == 0, "row-unit condition drift")
    require(all(benchmark["declarations"].values()) and all(terminal["declarations"].values()), "target-blind declarations drift")

    ledger_path = CAMPAIGN / "CLAIM_LEDGER.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ids = [item["id"] for item in ledger["claims"]]
    require(len(ids) == len(set(ids)), "duplicate claim ID")
    claim = next(item for item in ledger["claims"] if item["id"] == "FS-HSOP-SECANT-J2-P181-TARGET-BLIND-LINBOX-RANK")
    require(claim["assurance"] == "exact_mod181_coefficient_rank_and_scaling_not_target_membership", "new claim assurance drift")
    missing = [relative for relative in claim["evidence"] if not (CAMPAIGN / relative).exists()]
    require(not missing, f"new claim evidence missing: {missing}")
    stretch = next(item for item in ledger["claims"] if item["id"] == "FS-HSOP-STRETCH")
    require(BOUND["v2_terminal"][0] in stretch["evidence"] and "no target-membership" in stretch["claim"], "stretch boundary not updated")

    documents = {}
    required_text = {
        "README.md": "licenses a separately frozen explicit solve",
        "RESEARCH_METRICS.md": "Actual target-blind p181 LinBox coefficient benchmark",
        "NEXT_GOAL_HSOP_NULLCONE.md": "deterministic explicit solve at",
    }
    for relative, needle in required_text.items():
        path = CAMPAIGN / relative
        require(needle in path.read_text(encoding="utf-8"), f"document decision missing: {relative}")
        documents[relative] = file_hash(path)
    documents["CLAIM_LEDGER.json"] = file_hash(ledger_path)
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-linbox-campaign-readback.v1",
        "status": "PASS_P181_TARGET_BLIND_LINBOX_CAMPAIGN_READBACK",
        "bindings": bindings,
        "updated_document_sha256": documents,
        "new_claim_id": claim["id"],
        "next_gate": "separately preregistered deterministic explicit mod181 solve plus independent all-row replay before p2",
        "declarations": {"coefficient_rank_full": True, "target_membership_not_established_by_this_route": True, "no_solution_vector_from_this_route": True, "no_p_adic_digit": True, "QQ_identity_open": True, "HC4_open": True},
        "claim_boundary": "This readback closes only the target-blind coefficient-rank route selection. It supplies no target solve, modular membership, p-adic lift, QQ identity, colon, saturation, secant closure, nullcone containment, or HC4 theorem.",
    }
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
