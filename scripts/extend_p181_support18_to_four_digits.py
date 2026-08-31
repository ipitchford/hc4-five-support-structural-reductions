#!/usr/bin/env -S sage -python
"""Extend the independently audited next-18 lift from p^2 through p^4."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

import extend_p181_sparse4_to_four_digits as base
import lift_p181_sparse4_to_two_digits as lift_base


RHS_COUNT = 18


def output_directory() -> Path:
    position = sys.argv.index("--output-dir") + 1
    path = Path(sys.argv[position])
    return path if path.is_absolute() else base.CAMPAIGN / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    source = base.CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
    base.RHS_COUNT = RHS_COUNT
    base.SOURCE = source
    base.EXACT = source / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
    base.MODULAR = source / "integral/A_mod181_coefficient_primitive.csr"
    base.X2 = source / "lift/X_mod_181_power_2_sparse4_row_major.u16le"
    lift_base.RHS_COUNT = RHS_COUNT
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        return_code = base.main()
    receipt_path = output_directory() / "extension.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema"] = "hc4.third-colon-p181-support18-four-digit-extension.v1"
    statuses = {
        "STOP_P181_SPARSE4_CORRECTION_OUTSIDE_COLUMN_SPACE": "STOP_P181_SUPPORT18_CORRECTION_OUTSIDE_COLUMN_SPACE",
        "PASS_P181_SPARSE4_FOUR_DIGIT_LIFT": "PASS_P181_SUPPORT18_FOUR_DIGIT_LIFT",
        "PASS_P181_SPARSE4_FOUR_DIGIT_EXACT_RATIONAL_REPLAY": "PASS_P181_SUPPORT18_FOUR_DIGIT_EXACT_RATIONAL_REPLAY",
    }
    receipt["status"] = statuses.get(receipt["status"], receipt["status"])
    declarations = receipt.setdefault("declarations", {})
    declarations["padded_zero_rhs_columns"] = base.PADDED - RHS_COUNT
    declarations["starting_p2_independent_audit_sha256"] = "1990c2a85f6826c06aed49660f192ef1f7c109b1b33fecf7e4f54682faee0948"
    receipt["claim_boundary"] = (
        "A finite four-digit PASS is evidence for 18 fixed source-kernel "
        "directions only, not a QQ target identity, colon, saturation, secant "
        "closure, nullcone containment, or HC4 theorem."
    )
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
