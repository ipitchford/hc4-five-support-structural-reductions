#!/usr/bin/env python3
"""Extract only the frozen p181 pivot gauge for the target-blind rank run."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
SOURCE = CAMPAIGN / "artifacts/j2-secant-r10-third-colon-identity-extended-sparse-p181.json"
SOURCE_SHA256 = "e9841fee4f75e60adef26a8b10878b35f6db48e6d0a21876b197d7cbdef2064b"
COMPACT_SHA256 = "1da29807a38b0f9eceaf8606b120ea61e0a24605e959f7f2f88e4ed9bb073e1d"
PACKED_SHA256 = "3a4087b184540be80852650b26aecaddd561a2a866599e660d9359b3415dfed2"


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def compact_hash(value: object) -> str:
    return digest_bytes(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else CAMPAIGN / args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    if digest_bytes(SOURCE.read_bytes()) != SOURCE_SHA256:
        raise ValueError("prior p181 artifact drift")
    prior = json.loads(SOURCE.read_text(encoding="utf-8"))
    pivots = [int(value) for value in prior["pivot_unknown_indices"]]
    if len(pivots) != 35_881 or len(set(pivots)) != len(pivots):
        raise ValueError("pivot gauge dimension or uniqueness drift")
    if compact_hash(pivots) != COMPACT_SHA256:
        raise ValueError("pivot compact hash drift")
    packed = b"".join(struct.pack("<I", value) for value in pivots)
    if digest_bytes(packed) != PACKED_SHA256:
        raise ValueError("pivot packed hash drift")
    binary = output / "C_piv.u32le"
    binary.write_bytes(packed)
    receipt = {
        "schema": "hc4.decimic-j2-secant-r10-p181-target-blind-gauge.v1",
        "status": "PASS_EXTRACTED_P181_PIVOT_GAUGE_ONLY",
        "count": len(pivots),
        "compact_sha256": COMPACT_SHA256,
        "packed_u32le_sha256": PACKED_SHA256,
        "source": {"path": str(SOURCE.relative_to(CAMPAIGN)), "sha256": SOURCE_SHA256},
        "output": {"path": binary.name, "sha256": digest_bytes(packed), "bytes": len(packed)},
        "declarations": {
            "only_pivot_indices_emitted": True,
            "no_rhs_emitted": True,
            "no_target_coefficients_emitted": True,
            "no_solution_coordinates_emitted": True,
        },
        "claim_boundary": "This is retrospective transport of a frozen coordinate gauge and supplies no new mathematical evidence.",
    }
    (output / "gauge.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "output": str(output)}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
