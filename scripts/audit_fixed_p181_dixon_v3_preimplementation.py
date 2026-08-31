#!/usr/bin/env -S sage -python
"""Prospective source/interface/encoder audit required before the v3 freeze."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import py_compile
import random
import struct
import subprocess
import sys
import tempfile
from array import array
from pathlib import Path


CAMPAIGN = Path(__file__).resolve().parents[1]
SCRIPTS = CAMPAIGN / "scripts"
sys.path.insert(0, str(SCRIPTS))

import factor_fixed_p181_dixon_coefficients as factorizer
import fixed_p181_dixon_codec as codec
import fixed_p181_dixon_rr as rr
import freeze_fixed_p181_dixon_implementation as freezer
import produce_fixed_p181_dixon_8digit_pilot as producer
import replay_fixed_p181_dixon_8digit_independent as independent
import run_fixed_p181_dixon_8digit_gated as wrapper


OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-v3-preimplementation-audit.json"
DOCUMENTS = {
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION.md": "dcba29bf2b3396fcbfd2999aad09a363c2fc852e4fb04c142cb1e1636c5ad6cc",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_01.md": "5bff2bd3844744f854c2757aee4b8bf09d227ae487ba1b43f55682a009f5d08c",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_02.md": "dd07f5e0e6ca139383905bedae9b382304bcf2cf52ce74d0c496e30e32dc5def",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_03.md": "2595d68aed6ed3e968f516386effdb09ede8c1f851bda717dc93f76cd8946b82",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_04.md": "194ebeca8c2270f6287ec7169424bc7a6ad11fe7f263137ffd78844dc9d36273",
}
TERMINALS = {
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1.json": "8b313ec2354c7afe21a041260a2dbc6bc6b167855a94b14fa21031c9538d1568",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1-failed-audit.json": "913c3ee41dd83084e7da570b468789dca351eb46fe259ff898f7c3152a078163",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v2.json": "710b5f768c1693dc79faf604b8581711cf6d277711acd84ac84206274525699d",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-phase1-v2-terminal.json": "859b47008f61569f77cab502fc46912ff22339144738604a8316f5973b759596",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_hashes(values: dict[str, str]) -> None:
    for relative, expected in values.items():
        require(file_hash(CAMPAIGN / relative) == expected, f"binding drift: {relative}")


def oracle_bigint(value: int) -> bytes:
    value = int(value)
    if value == 0:
        return b"\x00" + struct.pack("<I", 0)
    magnitude = abs(value)
    length = (magnitude.bit_length() + 7) // 8
    return bytes([1 if value > 0 else 2]) + struct.pack("<I", length) + magnitude.to_bytes(length, "little")


def optimized_encoder_audit() -> dict[str, object]:
    generator = random.Random(181_35881)
    u32 = [0, 1, 2**32 - 1] + [generator.randrange(2**32) for _ in range(20_000)]
    u64 = [0, 1, 2**64 - 1] + [generator.randrange(2**64) for _ in range(20_000)]
    bigints = [0, 1, -1, 2**8 - 1, 2**8, -(2**64 - 1), 2**511, -(2**509)]
    bigints += [generator.randrange(-(2**256), 2**256) for _ in range(20_000)]
    checks = {
        "u32_empty": codec.payload_u32([]) == b"",
        "u64_empty": codec.payload_u64([]) == b"",
        "bigint_empty": codec.payload_bigints([]) == b"",
        "u32_oracle": codec.payload_u32(u32) == b"".join(struct.pack("<I", value) for value in u32),
        "u64_oracle": codec.payload_u64(u64) == b"".join(struct.pack("<Q", value) for value in u64),
        "bigint_oracle": codec.payload_bigints(bigints) == b"".join(oracle_bigint(value) for value in bigints),
    }
    require(all(checks.values()), f"optimized encoder differs from oracle: {checks}")
    return {"status": "PASS_BYTE_IDENTICAL_OPTIMIZED_ENCODERS", "checks": checks, "random_seed": 181_35881, "u32_cases": len(u32), "u64_cases": len(u64), "bigint_cases": len(bigints)}


def codec_container_audit() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="hc4-v3-codec-") as directory:
        path = Path(directory) / "test.bin"
        arrays = {
            "u32": codec.ArrayPayload("u32", (3,), codec.payload_u32([0, 1, 2**32 - 1])),
            "u64": codec.ArrayPayload("u64", (3,), codec.payload_u64([0, 1, 2**64 - 1])),
            "big": codec.ArrayPayload("bigint", (5,), codec.payload_bigints([0, 1, -1, 2**100, -(2**99)])),
            "raw": codec.ArrayPayload("bytes", (8,), b"HC4TEST3"),
        }
        manifest = codec.write_container(path, arrays)
        descriptors = codec.read_descriptors(path)
        for name, item in arrays.items():
            require(codec.read_array(path, descriptors[name]) == item.payload, f"container roundtrip drift: {name}")
    return {"status": "PASS_V3_CODEC_CONTAINER", "sha256": manifest["sha256"]}


def toy_algebra_audit() -> dict[str, object]:
    result = factorizer.factor([{0: 1, 1: 1}, {0: 1, 1: 2}, {1: 1}], column_count=2)
    require(result["pivot_source_rows"] == [0, 1] and result["final_zero_rows"] == [2], "toy factorization drift")
    trace = {
        "pivot_source_row": array("I", [0, 1]), "pivot_unknown": array("I", [0, 1]),
        "pivot_inverse": bytes([1, 1]), "pivot_tail_offsets": array("Q", [0, 1, 1]),
        "pivot_tail_columns": array("I", [1]), "pivot_tail_values": bytes([1]),
        "affected_offsets": array("Q", [0, 1, 2]), "affected_rows": array("I", [1, 2]),
        "affected_factors": bytes([1, 1]), "final_zero_rows": array("I", [2]),
    }
    arrays = {"A_C.row_offsets": array("Q", [0, 2, 4, 5]), "A_C.column_indices": array("I", [0, 1, 0, 1, 1]), "A_C.values": [1, 1, 1, 2, 1]}
    old = independent.ROWS, independent.C_COLUMNS
    try:
        independent.ROWS, independent.C_COLUMNS = 3, 2
        row_audit = independent.verify_trace_rowwise(arrays, trace)
        left, zero_left = independent.solve_trace([7, 11, 4], trace)
    finally:
        independent.ROWS, independent.C_COLUMNS = old
    right, zero_right = producer.replay_trace([7, 11, 4], trace)
    require(left == right == [3, 4] and list(zero_left) == zero_right == [0], "two-solver toy drift")
    return {"status": "PASS_V3_TOY_FACTOR_TRACE_TWO_SOLVERS", "row_audit": row_audit}


def interface_and_import_audit() -> dict[str, object]:
    require(freezer.SCHEMA == wrapper.FREEZE_SCHEMA, "implementation schema drift")
    require(set(freezer.CANONICAL_PATHS) == wrapper.REQUIRED_CANONICAL_PATH_KEYS, "path interface drift")
    tree = ast.parse((SCRIPTS / "run_fixed_p181_dixon_8digit_gated.py").read_text(encoding="utf-8"))
    path_reads = {
        node.slice.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
        and node.value.id == "paths" and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, str)
    }
    require(path_reads == wrapper.REQUIRED_CANONICAL_PATH_KEYS, "wrapper does not read exact path interface")
    independent_tree = ast.parse((SCRIPTS / "replay_fixed_p181_dixon_8digit_independent.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(independent_tree):
        if isinstance(node, ast.Import): imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module: imports.add(node.module)
    forbidden = {"produce_fixed_p181_dixon_8digit_pilot", "preprocess_fixed_p181_dixon_integer_system", "factor_fixed_p181_dixon_coefficients"}
    require(not imports.intersection(forbidden), "independent source imports a forbidden lineage")
    return {"status": "PASS_V3_INTERFACE_AND_IMPORT_SEPARATION", "path_keys": sorted(path_reads), "forbidden_imports": []}


def freezer_safety_audit() -> dict[str, object]:
    require(not freezer.OUTPUT.exists(), "v3 freeze predates audit")
    completed = subprocess.run([sys.executable, str(SCRIPTS / "freeze_fixed_p181_dixon_implementation.py")], cwd=CAMPAIGN, capture_output=True)
    require(completed.returncode == 2 and not freezer.OUTPUT.exists(), "freezer acted without --install")
    return {"status": "PASS_FREEZER_REQUIRES_LITERAL_INSTALL", "return_code_without_install": completed.returncode}


def main() -> int:
    check_hashes(DOCUMENTS); check_hashes(TERMINALS)
    require(freezer.DOCUMENTS == DOCUMENTS, "freezer document set drift")
    for relative, expected in TERMINALS.items():
        require(freezer.ALGEBRA_AND_HISTORY.get(relative) == expected, f"freezer omitted prior terminal: {relative}")
    expected_sources = {
        "scripts/preprocess_fixed_p181_dixon_integer_system.py", "scripts/factor_fixed_p181_dixon_coefficients.py",
        "scripts/produce_fixed_p181_dixon_8digit_pilot.py", "scripts/replay_fixed_p181_dixon_8digit_independent.py",
        "scripts/run_fixed_p181_dixon_8digit_gated.py", "scripts/fixed_p181_dixon_codec.py",
        "scripts/fixed_p181_dixon_rr.py", "scripts/freeze_fixed_p181_dixon_implementation.py",
    }
    require(set(freezer.IMPLEMENTATION_SOURCES) == expected_sources, "v3 source set drift")
    source_hashes = {}
    for relative in freezer.IMPLEMENTATION_SOURCES:
        py_compile.compile(str(CAMPAIGN / relative), doraise=True)
        source_hashes[relative] = file_hash(CAMPAIGN / relative)
    existing = [relative for relative in freezer.PROSPECTIVE_PATHS if (CAMPAIGN / relative).exists()]
    require(not existing, f"v3 prospective output exists: {existing}")
    tests = {
        "optimized_encoders": optimized_encoder_audit(), "container": codec_container_audit(),
        "rr": rr.regression(512), "toy_algebra": toy_algebra_audit(),
        "interface_imports": interface_and_import_audit(), "freezer_safety": freezer_safety_audit(),
    }
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-v3-preimplementation-audit.v1",
        "status": "PASS_V3_PREIMPLEMENTATION_SOURCE_INTERFACE_AND_ENCODER_AUDIT",
        "documents": DOCUMENTS, "prior_terminals": TERMINALS,
        "implementation_source_hashes": source_hashes, "tests": tests,
        "prospective_v3_paths_existing": existing,
        "declarations": {"no_fixed_algebra_opened": True, "no_preprocessing_launched": True, "no_factorization_launched": True, "no_arithmetic_modulo_181_squared": True, "v3_may_now_be_frozen": True},
        "claim_boundary": "This PASS establishes only byte-identical encoder and pre-execution implementation consistency. It supplies no prospective algebraic or p-adic evidence.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
