#!/usr/bin/env -S sage -python
"""Synthetic-only capability and scaling scout for the post-Dixon route."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

from sage.all import GF, Matrix


CAMPAIGN = Path(__file__).resolve().parents[1]
OUTPUT = CAMPAIGN / "receipts/hsop-j2-secant-r10-third-colon-linbox-synthetic-capability-scout.json"
P = 181


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command: list[str]) -> str:
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    return (completed.stdout or completed.stderr).strip()


def build_synthetic(columns: int):
    rows = (239 * columns + 99) // 100
    field = GF(P)
    matrix = Matrix(field, rows, columns, sparse=True)
    # Sixteen deterministic positions per row; step 17 is coprime to all
    # power-of-two column counts used below.
    for row in range(rows):
        base = (37 * row + 11) % columns
        for offset in range(16):
            column = (base + 17 * offset) % columns
            matrix[row, column] = field((31 * row + 19 * offset + 1) % P or 1)
    # Certify full column rank independently of the black-box algorithm.
    for column in range(columns):
        matrix[column, column] = field(1)
    return matrix


def benchmark(columns: int) -> dict[str, object]:
    started = time.perf_counter()
    matrix = build_synthetic(columns)
    build_seconds = time.perf_counter() - started
    nnz = matrix.density() * matrix.nrows() * matrix.ncols()
    rank_started = time.perf_counter()
    observed = int(matrix.rank(algorithm="linbox"))
    rank_seconds = time.perf_counter() - rank_started
    if observed != columns:
        raise AssertionError(f"LinBox rank mismatch at {columns}: {observed}")
    generic = None
    if columns <= 512:
        copy = matrix.__copy__()
        generic_started = time.perf_counter()
        generic_rank = int(copy.rank(algorithm="generic"))
        generic = {
            "rank": generic_rank,
            "seconds": time.perf_counter() - generic_started,
        }
        if generic_rank != observed:
            raise AssertionError("LinBox/generic synthetic rank disagreement")
    return {
        "columns": columns,
        "rows": matrix.nrows(),
        "nonzeros": int(nnz),
        "average_nonzeros_per_row": float(nnz / matrix.nrows()),
        "build_seconds": build_seconds,
        "linbox_rank": observed,
        "linbox_rank_seconds": rank_seconds,
        "generic_crosscheck": generic,
        "maximum_rss_native_after_case": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(OUTPUT)
    toy = Matrix(GF(P), 3, 4, sparse=True)
    rank_doc = inspect.getdoc(toy.rank) or ""
    if "algorithm`` -- either ``'linbox'``" not in rank_doc:
        raise ValueError("Sage sparse prime-field LinBox rank API absent")
    headers = {
        "rank": Path("/opt/homebrew/include/linbox/solutions/rank.h"),
        "solve": Path("/opt/homebrew/include/linbox/solutions/solve.h"),
        "wiedemann": Path("/opt/homebrew/include/linbox/solutions/solve/solve-wiedemann.h"),
        "sparse_elimination": Path("/opt/homebrew/include/linbox/solutions/solve/solve-sparse-elimination.h"),
    }
    for name, path in headers.items():
        if not path.is_file():
            raise FileNotFoundError(f"LinBox {name} header absent: {path}")
    cases = [benchmark(columns) for columns in (512, 1024, 2048, 4096)]
    payload = {
        "schema": "hc4.decimic-j2-secant-r10-third-colon-linbox-synthetic-capability-scout.v1",
        "status": "PASS_SYNTHETIC_COMPILED_SPARSE_PRIME_FIELD_CAPABILITY_SIGNAL",
        "toolchain": {
            "sage_version": command_output(["sage", "--version"]),
            "python": sys.version,
            "linbox_version": command_output(["linbox-config", "--version"]),
            "fflas_ffpack_version": command_output(["fflas-ffpack-config", "--version"]),
            "matrix_backend": f"{type(toy).__module__}.{type(toy).__name__}",
            "sparse_rank_api": "rank(algorithm='linbox')",
        },
        "installed_header_sha256": {name: file_hash(path) for name, path in headers.items()},
        "target_shape_not_opened": {
            "rows": 85_651,
            "columns": 35_881,
            "nonzeros": 1_354_540,
            "source": "previously frozen campaign metadata only",
        },
        "synthetic_policy": {
            "row_to_column_ratio": "ceil(2.39*n)",
            "attempted_entries_per_row": 16,
            "known_full_rank_by_embedded_identity": True,
            "characteristic": P,
        },
        "cases": cases,
        "resources": {"maximum_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},
        "source": {"path": str(Path(__file__).resolve().relative_to(CAMPAIGN)), "sha256": file_hash(Path(__file__).resolve())},
        "declarations": {"fixed_HC4_matrix_not_built_or_opened": True, "b_Z_not_read": True, "no_p2_arithmetic": True, "synthetic_route_signal_only": True},
        "claim_boundary": "This scout proves only that the installed Sage/LinBox stack can compute correct ranks on deterministic synthetic sparse GF(181) matrices and exposes compiled sparse/black-box solve APIs. It does not benchmark, factor, rank, or solve the HC4 matrix; produce a pivot trace or Dixon digit; or prove a Q identity, colon, saturation, secant closure, nullcone containment, or HC4.",
    }
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with OUTPUT.open("xb") as handle:
        handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({"status": payload["status"], "receipt": str(OUTPUT), "sha256": file_hash(OUTPUT), "cases": cases}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
