#!/usr/bin/env -S sage -python
"""Run the frozen source-level audit against the p96 recovery certificate."""
from pathlib import Path
import audit_p173_fourth_colon_target_exact_polynomial_identity as base
base.CERTIFICATE_DIR=base.CAMPAIGN/"artifacts/fourth-colon-p173-target-p96-exact-rational-recovery-v1"
base.CERTIFICATE=base.CERTIFICATE_DIR/"primitive_common_denominator_vector.json"
base.CERTIFICATE_RECEIPT=base.CERTIFICATE_DIR/"replay.json"
base.OUTPUT_DIR=base.CAMPAIGN/"artifacts/fourth-colon-p173-target-p96-exact-polynomial-identity-audit-v1"
base.OUTPUT_RECEIPT=base.CAMPAIGN/"receipts/hsop-j2-secant-r10-fourth-colon-p173-target-p96-exact-polynomial-identity-audit.json"
if __name__=="__main__":raise SystemExit(base.main())
