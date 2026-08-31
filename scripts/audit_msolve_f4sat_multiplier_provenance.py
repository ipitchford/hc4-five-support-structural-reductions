#!/usr/bin/env python3
"""Audit whether the pinned msolve F4SAT tap retains generator provenance.

This is a source-semantic audit, not an algebra solver.  It inspects the
pristine v0.10.1 sources through ``git show`` so that local discovery patches
cannot accidentally make the audit pass.  The output deliberately fails
closed: the existing kernel tap is never promoted to an original-generator
multiplier certificate unless every required provenance layer is present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


PINNED_COMMIT = "185e7b92fa0687f4db68b0f2f453a835668ac132"
PINNED_TAG = "v0.10.1"
SOURCE_FILES = (
    "src/neogb/data.h",
    "src/neogb/f4sat.c",
    "src/neogb/la_ff_32.c",
    "src/neogb/convert.c",
)


def git(source: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(source), *arguments],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def find_lines(text: str, needles: tuple[str, ...]) -> dict[str, int]:
    lines = text.splitlines()
    found: dict[str, int] = {}
    for needle in needles:
        matches = [index + 1 for index, line in enumerate(lines) if needle in line]
        if len(matches) != 1:
            raise AssertionError(
                f"expected exactly one source occurrence of {needle!r}; got {matches}"
            )
        found[needle] = matches[0]
    return found


def find_exact_lines(text: str, needles: tuple[str, ...]) -> dict[str, int]:
    lines = text.splitlines()
    found: dict[str, int] = {}
    for needle in needles:
        matches = [
            index + 1 for index, line in enumerate(lines) if line.strip() == needle
        ]
        if len(matches) != 1:
            raise AssertionError(
                f"expected exactly one exact source line {needle!r}; got {matches}"
            )
        found[needle] = matches[0]
    return found


def struct_body(text: str, name: str) -> str:
    match = re.search(
        rf"struct\s+{re.escape(name)}\s*\n\{{(?P<body>.*?)\n\}};",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"could not locate {name}")
    return match.group("body")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        type=Path,
        default=Path("research/j2_secant_r10_colon_kernel_candidate_p1073741827.json"),
    )
    parser.add_argument(
        "--tap-patch",
        type=Path,
        default=Path("research/msolve_colon_kernel_tap_v0.10.1.patch"),
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()

    campaign = Path(__file__).resolve().parent.parent
    source = arguments.source.resolve()
    commit = git(source, "rev-parse", "HEAD").strip()
    if commit != PINNED_COMMIT:
        raise AssertionError(f"expected pinned commit {PINNED_COMMIT}, got {commit}")
    tag = git(source, "describe", "--tags", "--exact-match", "HEAD").strip()
    if tag != PINNED_TAG:
        raise AssertionError(f"expected tag {PINNED_TAG}, got {tag}")

    pristine = {
        path: git(source, "show", f"{PINNED_COMMIT}:{path}") for path in SOURCE_FILES
    }
    data_h = pristine["src/neogb/data.h"]
    f4sat_c = pristine["src/neogb/f4sat.c"]
    la_c = pristine["src/neogb/la_ff_32.c"]

    bs_body = struct_body(data_h, "bs_t")
    mat_body = struct_body(data_h, "mat_t")
    forbidden_provenance_fields = (
        "original_generator",
        "module_representation",
        "transformation_matrix",
        "ancestry",
    )
    if any(token in bs_body or token in mat_body for token in forbidden_provenance_fields):
        raise AssertionError("unexpected original-generator provenance field found")
    if "rba_t **rba" not in mat_body or "if a reducer row is used" not in mat_body:
        raise AssertionError("reducer-incidence bitset semantics changed")

    data_lines = find_exact_lines(
        data_h,
        (
            "struct bs_t",
            "hm_t **hm;      /* hashed monomials representing exponents */",
            "cf32_t **cf_32; /* coefficients for finite fields (32 bit) */",
            "rba_t **rba;        /* bit array for each row to be reduced storing */",
            "/* if a reducer row is used during reduction. */",
        ),
    )
    f4sat_lines = find_lines(
        f4sat_c,
        (
            "linear_algebra(mat, bs, bs, st);",
            "compute_kernel_sat_ff_32(sat, mat, kernel, bs, st);",
            "copy_kernel_to_matrix(mat, kernel, sat->ld);",
        ),
    )
    f4sat_source_lines = f4sat_c.splitlines()
    conversion_lines = [
        index + 1
        for index, line in enumerate(f4sat_source_lines)
        if "convert_sparse_matrix_rows_to_basis_elements(" in line
    ]
    if len(conversion_lines) != 2:
        raise AssertionError(
            f"expected two F4 basis-conversion sites; got {conversion_lines}"
        )
    f4sat_lines["ordinary_basis_conversion"] = conversion_lines[-1]
    la_lines = find_lines(
        la_c,
        (
            "int64_t *drm    = calloc((uint64_t)sat->ld, sizeof(int64_t));",
            "drm[upivs[i][MULT]] = 1;",
            "kernel->hm[kernel->ld]          = mulh[tmp_pos];",
        ),
    )
    clear_lines = [
        index + 1
        for index, line in enumerate(f4sat_source_lines)
        if "clear_matrix(mat);" in line
    ]
    if not clear_lines:
        raise AssertionError("F4 matrix-clear site not found")

    candidate_path = arguments.candidate
    if not candidate_path.is_absolute():
        candidate_path = campaign / candidate_path
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    transcript = candidate["discovery"]["stderr_tail"]
    new_counts = [
        int(value)
        for value in re.findall(r"\s(\d+) new\s+\d+ zero", transcript)
    ]
    expected_counts = [23, 76, 273, 991, 3590]
    if new_counts[:5] != expected_counts:
        raise AssertionError(
            f"unexpected pre-kernel basis-growth trace: {new_counts[:5]}"
        )
    original_generator_count = 17
    basis_load_at_first_kernel = original_generator_count + sum(expected_counts)
    if "1 new kernel elements" not in transcript:
        raise AssertionError("candidate transcript lacks the first nonzero kernel event")

    patch_path = arguments.tap_patch
    if not patch_path.is_absolute():
        patch_path = campaign / patch_path
    patch_text = patch_path.read_text(encoding="utf-8")
    if "dump_first_colon_kernel" not in patch_text or "TERM %u" not in patch_text:
        raise AssertionError("the frozen discovery tap is not the expected polynomial dump")
    if any(token in patch_text for token in forbidden_provenance_fields):
        raise AssertionError("tap patch unexpectedly claims generator provenance")

    result = {
        "schema": "hc4.msolve-f4sat-multiplier-provenance-audit.v1",
        "status": "PROVENANCE_NOT_AVAILABLE_IN_PINNED_F4SAT_TAP",
        "pinned_upstream": {
            "tag": tag,
            "commit": commit,
            "source_sha256": {
                path: sha256(text.encode("utf-8")) for path, text in pristine.items()
            },
        },
        "runtime_witness": {
            "candidate_receipt": str(candidate_path.relative_to(campaign)),
            "candidate_receipt_sha256": sha256(candidate_path.read_bytes()),
            "characteristic": candidate["characteristic"],
            "discovery_wall_seconds": candidate["wall_seconds"],
            "discovery_solver_seconds": candidate["discovery"]["solver_seconds"],
            "discovery_threads": candidate["discovery"]["threads"],
            "discovery_timed_out": candidate["discovery"]["timed_out"],
            "original_generator_count": original_generator_count,
            "ordinary_f4_new_basis_counts_before_first_kernel": expected_counts,
            "stored_basis_load_at_first_kernel": basis_load_at_first_kernel,
            "largest_pre_kernel_matrix": {
                "rows": 355024,
                "columns": 792344,
                "reported_density_percent": 0.06,
            },
            "kernel_matrix": {"rows": 50000, "columns": 137889},
        },
        "source_evidence": {
            "basis_and_matrix_storage": {
                "file": "src/neogb/data.h",
                "lines": data_lines,
                "finding": (
                    "bs_t stores polynomial values, signatures, and coefficient arrays; "
                    "mat_t.rba stores reducer-incidence bits, not scalar row operations "
                    "or a 17-component original-generator module representation."
                ),
            },
            "ordinary_f4_loss_point": {
                "file": "src/neogb/f4sat.c",
                "lines": f4sat_lines,
                "matrix_clear_lines": clear_lines,
                "finding": (
                    "New pivot polynomials are converted into bs_t, after which the F4 "
                    "matrix is cleared; no original-generator transformation is attached."
                ),
            },
            "kernel_scope": {
                "file": "src/neogb/la_ff_32.c",
                "lines": la_lines,
                "finding": (
                    "The tracked vector has length sat->ld and is initialized by a "
                    "saturation-multiplier index.  The emitted kernel is therefore a "
                    "dependency among saturation inputs, not among the original generators."
                ),
            },
            "discovery_tap": {
                "file": str(patch_path.relative_to(campaign)),
                "sha256": sha256(patch_path.read_bytes()),
                "finding": (
                    "The tap serializes only the resulting kernel polynomial's terms and "
                    "exponents; it adds no transformation or module-provenance storage."
                ),
            },
        },
        "minimal_design_boundary": {
            "required_for_original_multipliers": [
                "attach a sparse 17-component polynomial module vector to every input and derived basis element",
                "propagate exact scalar row operations through every ordinary F4 matrix and every saturation normal-form reduction",
                "expand the final kernel dependency through that derivation DAG to the 17 original generators",
                "serialize the 17 multipliers and independently verify M*h-sum(q_i*F_i)=0",
            ],
            "assessment": (
                "This is a full proof-trace retrofit, not a minimal extension of the "
                "existing quartic tap.  The pre-kernel run already stores 4,970 basis "
                "elements and contains a 355,024 by 792,344 F4 matrix."
            ),
            "bounded_alternative": (
                "Use a target-specific proof-producing lift against the original 17 "
                "generators, then replay the displayed polynomial identity directly."
            ),
            "retrofit_experiment": {
                "attempted": False,
                "reason": (
                    "The source audit proves the required provenance is absent, and a "
                    "full module-trace retrofit was explicitly outside the bounded task."
                ),
            },
        },
        "claim_boundary": (
            "The existing msolve tap certifies a modular colon-kernel candidate only. "
            "It cannot emit or justify original-generator multipliers.  This source audit "
            "does not decide the characteristic-zero colon identity, saturation, the "
            "secant chart, or HC4."
        ),
    }

    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if arguments.output is None:
        print(encoded, end="")
    else:
        output = arguments.output
        if not output.is_absolute():
            output = campaign / output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
