#!/usr/bin/env -S sage -python
"""Non-executing acceptance audit required before the v2 source freeze."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import py_compile
import struct
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


OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-v2-preimplementation-audit.json"
EXPECTED_DOCUMENTS = {
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION.md": "dcba29bf2b3396fcbfd2999aad09a363c2fc852e4fb04c142cb1e1636c5ad6cc",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_01.md": "5bff2bd3844744f854c2757aee4b8bf09d227ae487ba1b43f55682a009f5d08c",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_02.md": "dd07f5e0e6ca139383905bedae9b382304bcf2cf52ce74d0c496e30e32dc5def",
    "research/THIRD_COLON_FIXED_P181_ZERO_FREE_DIXON_8DIGIT_PREREGISTRATION_AMENDMENT_03.md": "2595d68aed6ed3e968f516386effdb09ede8c1f851bda717dc93f76cd8946b82",
}
EXPECTED_V1 = {
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1.json": "8b313ec2354c7afe21a041260a2dbc6bc6b167855a94b14fa21031c9538d1568",
    "receipts/hsop-j2-secant-r10-third-colon-dixon-p181-implementation-freeze-v1-failed-audit.json": "913c3ee41dd83084e7da570b468789dca351eb46fe259ff898f7c3152a078163",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def verify_hash_map(values: dict[str, str]) -> None:
    for relative, expected in values.items():
        require(file_hash(CAMPAIGN / relative) == expected, f"bound hash drift: {relative}")


def codec_test() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="hc4-dixon-v2-codec-") as directory:
        path = Path(directory) / "roundtrip.bin"
        arrays = {
            "a": codec.ArrayPayload("u8", (3,), bytes([0, 1, 180])),
            "b": codec.ArrayPayload("u32", (2,), codec.payload_u32([0, 2**32 - 1])),
            "c": codec.ArrayPayload("u64", (2,), codec.payload_u64([0, 2**64 - 1])),
            "d": codec.ArrayPayload("bigint", (5,), codec.payload_bigints([0, 1, -1, 2**100, -(2**99)])),
            "e": codec.ArrayPayload("bytes", (8,), b"HC4TEST1"),
        }
        manifest = codec.write_container(path, arrays)
        descriptors = codec.read_descriptors(path)
        for name, item in arrays.items():
            require(codec.read_array(path, descriptors[name]) == item.payload, f"codec mismatch: {name}")
        return {"status": "PASS_CODEC_ROUNDTRIP", "array_count": len(arrays), "file_sha256": manifest["sha256"]}


def factor_and_solver_test() -> dict[str, object]:
    equations = [{0: 1, 1: 1}, {0: 1, 1: 2}, {1: 1}]
    factored = factorizer.factor(equations, column_count=2)
    require(factored["pivot_source_rows"] == [0, 1], "toy pivot rows drift")
    require(factored["final_zero_rows"] == [2], "toy final zero row drift")
    trace = {
        "pivot_source_row": array("I", [0, 1]),
        "pivot_unknown": array("I", [0, 1]),
        "pivot_inverse": bytes([1, 1]),
        "pivot_tail_offsets": array("Q", [0, 1, 1]),
        "pivot_tail_columns": array("I", [1]),
        "pivot_tail_values": bytes([1]),
        "affected_offsets": array("Q", [0, 1, 2]),
        "affected_rows": array("I", [1, 2]),
        "affected_factors": bytes([1, 1]),
        "final_zero_rows": array("I", [2]),
    }
    arrays = {
        "A_C.row_offsets": array("Q", [0, 2, 4, 5]),
        "A_C.column_indices": array("I", [0, 1, 0, 1, 1]),
        "A_C.values": [1, 1, 1, 2, 1],
    }
    old_rows, old_columns = independent.ROWS, independent.C_COLUMNS
    try:
        independent.ROWS, independent.C_COLUMNS = 3, 2
        row_audit = independent.verify_trace_rowwise(arrays, trace)
        digit_independent, zero_independent = independent.solve_trace([7, 11, 4], trace)
    finally:
        independent.ROWS, independent.C_COLUMNS = old_rows, old_columns
    digit_producer, zero_producer = producer.replay_trace([7, 11, 4], trace)
    require(digit_independent == digit_producer == [3, 4], "toy solvers disagree")
    require(list(zero_independent) == zero_producer == [0], "toy zero-row replay disagrees")
    return {
        "status": "PASS_TOY_FACTORIZATION_ROW_WISE_TRACE_AND_TWO_SOLVERS",
        "digit": digit_producer,
        "row_audit": row_audit,
    }


def independent_import_audit() -> dict[str, object]:
    path = SCRIPTS / "replay_fixed_p181_dixon_8digit_independent.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = {
        "produce_fixed_p181_dixon_8digit_pilot",
        "preprocess_fixed_p181_dixon_integer_system",
        "factor_fixed_p181_dixon_coefficients",
    }
    observed = sorted(name for name in imported if name in forbidden)
    require(not observed, f"independent implementation imports a forbidden lineage: {observed}")
    return {"status": "PASS_INDEPENDENT_IMPORT_SEPARATION", "forbidden_imports_observed": observed}


def interface_audit() -> dict[str, object]:
    require(freezer.SCHEMA == wrapper.FREEZE_SCHEMA, "freeze schema mismatch")
    require(set(freezer.CANONICAL_PATHS) == wrapper.REQUIRED_CANONICAL_PATH_KEYS, "canonical path key mismatch")
    wrapper_text = (SCRIPTS / "run_fixed_p181_dixon_8digit_gated.py").read_text(encoding="utf-8")
    keys_read = set()
    tree = ast.parse(wrapper_text)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "paths"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        ):
            keys_read.add(node.slice.value)
    require(keys_read == wrapper.REQUIRED_CANONICAL_PATH_KEYS, f"wrapper path reads drift: {keys_read}")
    require(all("v2" in value or value in ("artifacts/quarantine", "artifacts/staging") for value in freezer.CANONICAL_PATHS.values()), "v2 canonical path value drift")
    return {"status": "PASS_MANIFEST_WRAPPER_INTERFACE", "keys": sorted(keys_read)}


def telemetry_parser_test() -> dict[str, object]:
    sample = "        0.01 real         0.00 user         0.00 sys\n             123456  maximum resident set size\n                   0  swaps\n"
    with tempfile.TemporaryDirectory(prefix="hc4-dixon-time-") as directory:
        path = Path(directory) / "sample.time.txt"
        path.write_text(sample, encoding="utf-8")
        parsed = wrapper.parse_time_file(path)
    require(parsed["maximum_rss_bytes"] == 123456 and parsed["process_swaps"] == 0, "telemetry parser drift")
    return {"status": "PASS_EXTERNAL_TELEMETRY_PARSER", "parsed": {key: value for key, value in parsed.items() if key != "raw_text"}}


def main() -> int:
    verify_hash_map(EXPECTED_DOCUMENTS)
    verify_hash_map(EXPECTED_V1)
    require(freezer.DOCUMENTS == EXPECTED_DOCUMENTS, "freezer document bindings drift")
    for relative, expected in EXPECTED_V1.items():
        require(freezer.ALGEBRA_AND_HISTORY.get(relative) == expected, f"freezer omitted v1 binding: {relative}")
    expected_sources = {
        "scripts/preprocess_fixed_p181_dixon_integer_system.py",
        "scripts/factor_fixed_p181_dixon_coefficients.py",
        "scripts/produce_fixed_p181_dixon_8digit_pilot.py",
        "scripts/replay_fixed_p181_dixon_8digit_independent.py",
        "scripts/run_fixed_p181_dixon_8digit_gated.py",
        "scripts/fixed_p181_dixon_codec.py",
        "scripts/fixed_p181_dixon_rr.py",
        "scripts/freeze_fixed_p181_dixon_implementation.py",
    }
    require(set(freezer.IMPLEMENTATION_SOURCES) == expected_sources, "implementation source set drift")
    source_hashes = {}
    for relative in freezer.IMPLEMENTATION_SOURCES:
        path = CAMPAIGN / relative
        py_compile.compile(str(path), doraise=True)
        source_hashes[relative] = file_hash(path)
    prospective = [relative for relative in freezer.PROSPECTIVE_PATHS if (CAMPAIGN / relative).exists()]
    require(not prospective and not freezer.OUTPUT.exists(), f"v2 prospective path already exists: {prospective}")
    results = {
        "codec": codec_test(),
        "rr": rr.regression(512),
        "factor_and_solvers": factor_and_solver_test(),
        "independent_imports": independent_import_audit(),
        "interface": interface_audit(),
        "telemetry": telemetry_parser_test(),
    }
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-dixon-p181-v2-preimplementation-audit.v1",
        "status": "PASS_V2_PREIMPLEMENTATION_SOURCE_AND_INTERFACE_AUDIT",
        "documents": EXPECTED_DOCUMENTS,
        "v1_terminal_bindings": EXPECTED_V1,
        "implementation_source_hashes": source_hashes,
        "tests": results,
        "prospective_v2_paths_existing": prospective,
        "declarations": {"no_fixed_algebra_opened": True, "no_preprocessing_launched": True, "no_factorization_launched": True, "no_arithmetic_modulo_181_squared": True, "v2_may_now_be_frozen": True},
        "claim_boundary": "This PASS establishes only pre-execution source and interface consistency. It computes no prospective algebra, Dixon digit, p-adic or QQ identity, colon, saturation, secant closure, nullcone containment, or HC4 result.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
