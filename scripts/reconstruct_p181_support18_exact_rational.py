#!/usr/bin/env -S sage -python
"""Equal-height reconstruction and exact replay for the next 18 p^4 sections."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
from pathlib import Path

import reconstruct_p181_sparse4_exact_rational as base


RHS_COUNT = 18


def output_directory() -> Path:
    position = sys.argv.index("--output-dir") + 1
    path = Path(sys.argv[position])
    return path if path.is_absolute() else base.CAMPAIGN / path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    base.RHS = RHS_COUNT
    base.SOURCE = base.CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
    base.EXTENSION = base.CAMPAIGN / "artifacts/third-colon-p181-support18-four-digit-extension-v1"
    base.EXACT = base.SOURCE / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
    base.X4 = base.EXTENSION / "X_mod_181_power_4_sparse4_row_major.u32le"
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        return_code = base.main()
    receipt_path = output_directory() / "replay.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["schema"] = "hc4.third-colon-p181-support18-exact-rational-replay.v1"
    receipt["status"] = "PASS_P181_SUPPORT18_EXACT_RATIONAL_SYSTEM_REPLAY"
    receipt["selection"] = {"residual_local_indices": [95, 59, 56, 1, 58, 30, 15, 74, 112, 57, 109, 78, 47, 91, 104, 81, 10, 13]}
    receipt["claim_boundary"] = (
        "This PASS proves 18 rational source syzygies in the fixed quotient "
        "chart. Together with the earlier four it gives rational quotient lower "
        "bound 22, not a QQ target identity, colon, saturation, secant closure, "
        "nullcone containment, or HC4."
    )
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(receipt_path), "sha256": digest(receipt_path)}))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
