#!/usr/bin/env -S sage -python
"""Build the exact coefficient system for the preregistered next 18 columns."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

import build_p181_sparse4_coefficient_integral_system as base


SELECTED_LOCAL = (95, 59, 56, 1, 58, 30, 15, 74, 112, 57, 109, 78, 47, 91, 104, 81, 10, 13)
EXPECTED_SUPPORT = (270, 454, 477, 614, 666, 1156, 1632, 1780, 1873, 2630, 2639, 2820, 3001, 3460, 3627, 4335, 4689, 4929)


def output_directory() -> Path:
    position = sys.argv.index("--output-dir") + 1
    path = Path(sys.argv[position])
    return path if path.is_absolute() else base.CAMPAIGN / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    base.RHS_COUNT = len(SELECTED_LOCAL)
    base.SELECTED_LOCAL = SELECTED_LOCAL
    base.EXPECTED_SUPPORT = EXPECTED_SUPPORT
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        return_code = base.main()
    receipt_path = output_directory() / "integral-system.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema"] = "hc4.third-colon-p181-support18-coefficient-integral-system.v1"
    receipt["status"] = "PASS_P181_SUPPORT18_COEFFICIENT_PRIMITIVE_INTEGRAL_SYSTEM"
    receipt["declarations"]["selected_by_frozen_support_order"] = True
    receipt["claim_boundary"] = (
        "This PASS constructs the exact coefficient-only primitive integer system "
        "and 18 digit-zero modular solutions. It supplies no p^2 lift, QQ target "
        "identity, colon, saturation, secant closure, nullcone containment, or HC4 theorem."
    )
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
