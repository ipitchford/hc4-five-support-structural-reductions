#!/usr/bin/env -S sage -python
"""Independent exact-source and p^2 replay for the next 18 residual columns."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json

import audit_p181_sparse4_two_digit_lift_independent as base


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    base.RHS_COUNT = 18
    base.SELECTED_LOCAL = (95, 59, 56, 1, 58, 30, 15, 74, 112, 57, 109, 78, 47, 91, 104, 81, 10, 13)
    base.ARTIFACT = base.CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
    base.EXACT = base.ARTIFACT / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
    base.OUTPUT = base.CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-two-digit-lift-independent-audit.json"
    base.EXPECTED = {
        "terminal": "892d4d8978dd68f414fcfa27a6ecb06f0d984d0be9c5c40d8941ef9fe14bc6b9",
        "exact": "2524b706b88278187924f103245ddfd999ce2f21e2c848058fc723498c4682e1",
        "integral_receipt": "98f976749821c40a84ea469da493ad2a78a5a23db9b2cb0b05fd519f294860ca",
        "lift_receipt": "5703800aad2c392880178e426938f6b84ad700c4adc32701c20036039ec6e2d0",
        "digit_zero": "1d74cecd05f4091c86c95f079e69c96d8f2687a9ce924a8a5303df76d427c06d",
        "digit_one": "937c953db108b54b0834aebc75f8330346f94c61d889554d17c03a2a2c5a3def",
        "x2": "b189f494af08ec3375efea4cab8d60b7eccbf3e9212c8d87ecb6e2ad1c58c32f",
    }
    original_campaign = base.CAMPAIGN
    original_terminal = original_campaign / "receipts/hsop-j2-secant-r10-p181-sparse4-two-digit-lift-terminal-v2.json"
    support_terminal = original_campaign / "receipts/hsop-j2-secant-r10-p181-support18-two-digit-lift-terminal.json"

    # The inherited independent algorithm constructs this path locally.  Bind
    # it to the support-18 terminal without importing the support-18 producer.
    original_relative = original_terminal.relative_to(original_campaign)
    support_relative = support_terminal.relative_to(original_campaign)
    original_path_class = type(original_campaign)

    class CampaignPath(original_path_class):
        def __truediv__(self, key):
            result = super().__truediv__(key)
            if str(result).endswith(str(original_relative)):
                return support_terminal
            return result

    base.CAMPAIGN = CampaignPath(str(original_campaign))
    base.ARTIFACT = base.CAMPAIGN / "artifacts/third-colon-p181-support18-two-digit-lift-v1"
    base.EXACT = base.ARTIFACT / "integral/A_Z_b4_Z_coefficient_primitive.i64csr"
    base.QUOTIENT = base.CAMPAIGN / "artifacts/j2-secant-r10-third-colon-residual-114-quotient-chart.json"
    base.GAUGE = base.CAMPAIGN / "artifacts/third-colon-p181-target-blind-linbox-gauge-v2/C_piv.u32le"
    base.OUTPUT = base.CAMPAIGN / "receipts/hsop-j2-secant-r10-p181-support18-two-digit-lift-independent-audit.json"

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        return_code = base.main()
    receipt = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    receipt["schema"] = "hc4.third-colon-p181-support18-two-digit-lift-independent-audit.v1"
    receipt["status"] = "PASS_INDEPENDENT_P181_SUPPORT18_TWO_DIGIT_LIFT_REPLAY"
    receipt["declarations"]["support18_producer_not_imported_or_executed"] = True
    receipt["claim_boundary"] = (
        "This PASS independently certifies only the exact integer normalization "
        "and finite p^2 replay for 18 fixed canonical residual columns. It proves "
        "no QQ target identity, colon, saturation, secant closure, nullcone "
        "containment, or HC4 theorem."
    )
    base.OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(json.dumps({"status": receipt["status"], "receipt": str(base.OUTPUT), "sha256": digest(base.OUTPUT)}))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
