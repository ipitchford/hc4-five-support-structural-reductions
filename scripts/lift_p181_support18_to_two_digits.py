#!/usr/bin/env -S sage -python
"""Lift the preregistered next 18 residual sections through exactly p^2."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

import lift_p181_sparse4_to_two_digits as base


RHS_COUNT = 18


def output_directory() -> Path:
    position = sys.argv.index("--output-dir") + 1
    path = Path(sys.argv[position])
    return path if path.is_absolute() else base.CAMPAIGN / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    base.RHS_COUNT = RHS_COUNT
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        return_code = base.main()
    receipt_path = output_directory() / "lift.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema"] = "hc4.third-colon-p181-support18-two-digit-lift.v1"
    statuses = {
        "STOP_P181_SPARSE4_CORRECTION_OUTSIDE_COLUMN_SPACE": "STOP_P181_SUPPORT18_CORRECTION_OUTSIDE_COLUMN_SPACE",
        "PASS_P181_SPARSE4_TWO_DIGIT_LIFT": "PASS_P181_SUPPORT18_TWO_DIGIT_LIFT",
        "PASS_P181_SPARSE4_TWO_DIGIT_EXACT_RATIONAL_REPLAY": "PASS_P181_SUPPORT18_TWO_DIGIT_EXACT_RATIONAL_REPLAY",
    }
    receipt["status"] = statuses.get(receipt["status"], receipt["status"])
    declarations = receipt.setdefault("declarations", {})
    declarations["padded_zero_rhs_columns"] = base.PADDED_RHS_COUNT - RHS_COUNT
    declarations["selected_by_frozen_support_order"] = True
    receipt["claim_boundary"] = (
        "A two-digit PASS is finite p-adic evidence for 18 fixed canonical residual "
        "sections only. It does not prove a QQ target identity, colon, saturation, "
        "secant closure, nullcone containment, or HC4."
    )
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
