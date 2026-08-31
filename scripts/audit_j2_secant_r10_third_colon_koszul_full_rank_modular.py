#!/usr/bin/env sage-python
"""Confirmatory full-rank audit for the integer Koszul lattice.

This is a standalone sequel to the stopped fixed-coordinate normalization.
It imports only that protocol's independently frozen reconstruction routine;
the stopped producer normalizer is neither imported nor executed.  The new
rank calculations are implemented locally and repeated with Sage's sparse
matrix rank.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import resource
import signal
import sys
import time
from collections import Counter
from pathlib import Path

from sage.all import GF, Matrix


PRIMES = (173, 181, 197)
EXPECTED_ROW_COUNT = 2053
EXPECTED_COORDINATE_COUNT = 38048
EXPECTED_INTEGER_NNZ = 154939
EXPECTED_FIXED_P181_PIVOT_HASH = (
    "c7b305a434025cf4b9eea5aa720f38f419fbed7da121f5b2bba2e9a60c7676dd"
)
EXPECTED_STOPPED_MINOR_RANK_P197 = 2052
WALL_CAP_SECONDS = 90.0
RSS_CAP_BYTES = 750_000_000

FROZEN_HASHES = {
    "research/THIRD_COLON_KOSZUL_FULL_RANK_MODULAR_AUDIT_REGISTRATION.md":
        "86843c6d3a525087c4d940f9004fb0bac7176b1f1ec07720a48231285a69a614",
    "research/THIRD_COLON_KOSZUL_FIXED_MINOR_NORMALIZATION_PREREGISTRATION.md":
        "927b640211638c5610b05ab34e663f77ead79565d86ad7d28784c0f1e94f1819",
    "scripts/normalize_j2_secant_r10_third_colon_koszul_fixed_minor.py":
        "fceb3a0a12ae5473bf48f72d2c37e864c6569897052c6d0f60235b0a4fe6a08f",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-normalization.json":
        "0ba428b62f3bf8b7ccca4aded1c12e3c9659a498eac300f65036f393a54622e1",
    "scripts/audit_j2_secant_r10_third_colon_koszul_fixed_minor_normalization_independent.py":
        "deaa1d47f73d21bc7609a46d6df0474e92ea2e59c622fd6cd1c92bfb6118619d",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-p197-independent-singularity-audit.json":
        "e97001a1c7232e903192e649f440fc8bfe81277229793a9905469288dec8936f",
    "scripts/audit_j2_secant_r10_third_colon_koszul_syzygy_scout_independent_audit.py":
        "eb265d352165c222e051baccd8f63406c5716bdf2fb4cbd6b7165413058e37ea",
    "receipts/hsop-j2-secant-r10-third-colon-koszul-syzygy-scout-independent-audit.json":
        "15e60fa02b0d5b62f330fe5b64c052a82101a1e2a77f83bf85389253132e5102",
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(value: object) -> str:
    payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("ascii")
    return sha256_bytes(payload)


def native_max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def process_swaps() -> int:
    return int(getattr(resource.getrusage(resource.RUSAGE_SELF), "ru_nswap", 0))


def guard(started: float, stage: str) -> None:
    wall = time.perf_counter() - started
    rss = native_max_rss_bytes()
    swaps = process_swaps()
    if wall >= WALL_CAP_SECONDS:
        raise TimeoutError(f"wall cap reached during {stage}: {wall:.6f}s")
    if rss >= RSS_CAP_BYTES:
        raise MemoryError(f"RSS cap reached during {stage}: {rss} bytes")
    if swaps:
        raise MemoryError(f"process swaps observed during {stage}: {swaps}")


def load_independent_reconstructor(campaign: Path):
    path = campaign / (
        "scripts/audit_j2_secant_r10_third_colon_"
        "koszul_fixed_minor_normalization_independent.py"
    )
    spec = importlib.util.spec_from_file_location("frozen_koszul_reconstructor", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load independent reconstructor: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sparse_full_column_rank(columns, preferred_coordinates, prime, started):
    """Incremental full-matrix column echelon over GF(prime).

    Unlike the stopped fixed-minor calculation, this routine may pivot in any
    of the 38,048 coordinates.  The p181 pivots are preferences only; if a
    preference vanishes after reduction, the least low-incidence coordinate
    is selected instead.
    """

    coordinate_degrees = Counter(
        coordinate for column in columns for coordinate, _value in column
    )
    basis = {}
    pivot_sequence = []
    dependent_columns = []
    preferred_hits = 0
    reductions = 0
    coefficient_updates = 0
    maximum_working_support = 0
    basis_nonzero_count = 0

    for column_index, integer_column in enumerate(columns):
        work = {
            coordinate: value % prime
            for coordinate, value in integer_column
            if value % prime
        }
        maximum_working_support = max(maximum_working_support, len(work))
        for pivot in pivot_sequence:
            factor = work.get(pivot, 0)
            if not factor:
                continue
            reductions += 1
            for coordinate, value in basis[pivot].items():
                updated = (work.get(coordinate, 0) - factor * value) % prime
                if updated:
                    work[coordinate] = updated
                else:
                    work.pop(coordinate, None)
                coefficient_updates += 1
            maximum_working_support = max(maximum_working_support, len(work))

        if not work:
            dependent_columns.append(column_index)
            continue

        preferred = preferred_coordinates[column_index]
        if preferred in work:
            pivot = preferred
            preferred_hits += 1
        else:
            pivot = min(
                work,
                key=lambda coordinate: (coordinate_degrees[coordinate], coordinate),
            )
        inverse = pow(work[pivot], -1, prime)
        normalized = {
            coordinate: value * inverse % prime for coordinate, value in work.items()
        }
        basis[pivot] = normalized
        pivot_sequence.append(pivot)
        basis_nonzero_count += len(normalized)

        if column_index % 64 == 0:
            guard(started, f"custom full rank modulo {prime}")

    return {
        "algorithm": "local incremental sparse full-matrix column echelon",
        "rank": len(pivot_sequence),
        "dependent_column_count": len(dependent_columns),
        "dependent_columns": dependent_columns,
        "preferred_pivot_hits": preferred_hits,
        "pivot_coordinates": pivot_sequence,
        "pivot_coordinates_sha256": canonical_hash(pivot_sequence),
        "reductions": reductions,
        "coefficient_updates": coefficient_updates,
        "maximum_working_support": maximum_working_support,
        "basis_nonzero_count": basis_nonzero_count,
    }


def sage_sparse_rank(columns, prime, started):
    entries = {
        (coordinate, column_index): value % prime
        for column_index, column in enumerate(columns)
        for coordinate, value in column
        if value % prime
    }
    guard(started, f"Sage matrix construction modulo {prime}")
    matrix = Matrix(
        GF(prime),
        EXPECTED_COORDINATE_COUNT,
        EXPECTED_ROW_COUNT,
        entries,
        sparse=True,
    )
    rank = int(matrix.rank())
    guard(started, f"Sage sparse rank modulo {prime}")
    return rank, len(entries)


def audit(campaign: Path, started: float):
    observed_hashes = {}
    for relative, expected in FROZEN_HASHES.items():
        observed = sha256_bytes((campaign / relative).read_bytes())
        observed_hashes[relative] = observed
        if observed != expected:
            raise ValueError(f"frozen input hash changed: {relative}")

    stopped = json.loads(
        (
            campaign
            / "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-normalization.json"
        ).read_text(encoding="utf-8")
    )
    independent_minor = json.loads(
        (
            campaign
            / "receipts/hsop-j2-secant-r10-third-colon-koszul-fixed-minor-p197-independent-singularity-audit.json"
        ).read_text(encoding="utf-8")
    )
    if stopped.get("status") != "FAIL_CLOSED_FIXED_MINOR_SINGULAR":
        raise ValueError("bound producer receipt is not the stopped singular-minor result")
    if independent_minor.get("status") != "PASS_INDEPENDENT_P197_FIXED_MINOR_SINGULARITY":
        raise ValueError("bound independent receipt is not the p197 singularity audit")
    minor_dimensions = independent_minor.get("dimensions", {})
    minor_hash = independent_minor.get("hashes", {}).get("pivot_coordinates_sha256")
    if (
        int(minor_dimensions.get("rank_mod_197", -1))
        != EXPECTED_STOPPED_MINOR_RANK_P197
        or minor_hash != EXPECTED_FIXED_P181_PIVOT_HASH
    ):
        raise ValueError("bound stopped-minor rank or pivot hash changed")

    reconstructor = load_independent_reconstructor(campaign)
    reconstruction_started = time.perf_counter()
    reconstruction = reconstructor.reconstruct(campaign, started)
    reconstruction_seconds = time.perf_counter() - reconstruction_started
    columns = reconstruction["columns"]
    preferred = reconstruction["pivots"]
    if (
        len(columns) != EXPECTED_ROW_COUNT
        or sum(map(len, columns)) != EXPECTED_INTEGER_NNZ
        or canonical_hash(preferred) != EXPECTED_FIXED_P181_PIVOT_HASH
    ):
        raise AssertionError("reconstructed Koszul matrix profile changed")
    guard(started, "independent Koszul reconstruction")

    prime_records = {}
    for prime in PRIMES:
        custom_started = time.perf_counter()
        custom = sparse_full_column_rank(columns, preferred, prime, started)
        custom_seconds = time.perf_counter() - custom_started

        sage_started = time.perf_counter()
        sage_rank, modular_nnz = sage_sparse_rank(columns, prime, started)
        sage_seconds = time.perf_counter() - sage_started
        if custom["rank"] != sage_rank:
            raise AssertionError(
                f"rank methods disagree modulo {prime}: "
                f"custom={custom['rank']}, Sage={sage_rank}"
            )
        if sage_rank != EXPECTED_ROW_COUNT:
            raise AssertionError(
                f"full Koszul rank modulo {prime} is {sage_rank}, "
                f"expected {EXPECTED_ROW_COUNT}"
            )
        prime_records[str(prime)] = {
            "characteristic": prime,
            "full_matrix_shape": [EXPECTED_COORDINATE_COUNT, EXPECTED_ROW_COUNT],
            "integer_nonzero_count": EXPECTED_INTEGER_NNZ,
            "modular_nonzero_count": modular_nnz,
            "custom_rank": custom["rank"],
            "sage_sparse_rank": sage_rank,
            "rank_methods_agree": custom["rank"] == sage_rank,
            "custom_rank_telemetry": custom,
            "timings": {
                "custom_rank_seconds": custom_seconds,
                "sage_matrix_and_rank_seconds": sage_seconds,
            },
            "determinantal_divisor_implication": (
                f"{prime} does not divide Delta_2053(K), because the recorded "
                "pivot stream selects a maximal minor nonzero modulo this prime."
            ),
        }
        guard(started, f"completed prime {prime}")

    p197 = prime_records["197"]
    if (
        p197["custom_rank"] != EXPECTED_ROW_COUNT
        or p197["sage_sparse_rank"] != EXPECTED_ROW_COUNT
        or p197["custom_rank_telemetry"]["pivot_coordinates_sha256"]
        == EXPECTED_FIXED_P181_PIVOT_HASH
    ):
        raise AssertionError("p197 alternative-minor witness is absent or unchanged")

    usage = resource.getrusage(resource.RUSAGE_SELF)
    wall = time.perf_counter() - started
    guard(started, "receipt assembly")
    return {
        "schema": "hc4.third-colon-koszul-full-rank-modular-audit.v1",
        "status": "PASS_FULL_KOSZUL_RANK_AT_173_181_197",
        "assurance": (
            "confirmatory bounded exact modular audit with independently frozen "
            "Koszul reconstruction and two local rank methods"
        ),
        "registration_status": (
            "confirmatory archival rerun; exploratory p197 full-rank outcome was "
            "observed before the method registration"
        ),
        "claim_boundary": (
            "A PASS proves only that the frozen 2053-row integer Koszul matrix has "
            "full rank over GF(173), GF(181), and GF(197), so none of these three "
            "primes divides its rank-2053 determinantal divisor. In particular, "
            "the p197 singularity of the stopped p181-selected coordinate minor is "
            "a bad-minor event rather than p197-primary nonsaturation of this row "
            "lattice. It does not compute the determinantal divisor, exclude any "
            "other torsion prime, prove saturation over Z, construct a single minor "
            "simultaneously invertible at all desired primes, normalize multiplier "
            "vectors, prove QQ target membership, determine the residual quotient, "
            "compute a colon or saturation, close the secant chart, establish "
            "nullcone containment, or prove HC4. The stopped normalization remains "
            "stopped."
        ),
        "independence_boundary": {
            "stopped_producer_normalizer_imported_or_executed": False,
            "independent_frozen_reconstruction_routine_reused": True,
            "full_matrix_custom_rank_implemented_locally": True,
            "second_rank_method": "Sage sparse Matrix.rank over GF(p)",
            "rank_methods_share_reconstructed_integer_columns": True,
        },
        "dimensions": {
            "integer_koszul_matrix_shape": [EXPECTED_ROW_COUNT, EXPECTED_COORDINATE_COUNT],
            "integer_nonzero_count": EXPECTED_INTEGER_NNZ,
            "stopped_selected_minor_shape": [EXPECTED_ROW_COUNT, EXPECTED_ROW_COUNT],
            "stopped_selected_minor_rank_mod_197": EXPECTED_STOPPED_MINOR_RANK_P197,
        },
        "exact_checks": {
            "all_frozen_hashes_match": True,
            "all_2053_primitive_integer_rows_reconstructed": True,
            "reconstructor_separately_verifies_exact_zero_macaulay_image": True,
            "stopped_minor_rank_mod_197_bound": EXPECTED_STOPPED_MINOR_RANK_P197,
            "stopped_minor_pivot_hash_bound": EXPECTED_FIXED_P181_PIVOT_HASH,
            "full_rank_at_all_admitted_primes": True,
            "two_rank_methods_agree_at_all_admitted_primes": True,
            "p197_alternative_maximal_minor_exists": True,
            "p197_not_in_rank_2053_determinantal_divisor": True,
        },
        "prime_records": prime_records,
        "hashes": {
            "frozen_inputs": observed_hashes,
            "source_sha256": sha256_bytes(Path(__file__).resolve().read_bytes()),
            "descriptor_stream_sha256": reconstructor.EXPECTED_DESCRIPTOR_HASH,
            "generator_stream_sha256": reconstructor.EXPECTED_GENERATOR_HASH,
            "fixed_p181_pivot_coordinates_sha256": EXPECTED_FIXED_P181_PIVOT_HASH,
            "alternative_p197_pivot_coordinates_sha256": p197[
                "custom_rank_telemetry"
            ]["pivot_coordinates_sha256"],
        },
        "timings": {
            "independent_reconstruction_seconds": reconstruction_seconds,
            "total_wall_seconds": wall,
        },
        "resources": {
            "wall_cap_seconds": WALL_CAP_SECONDS,
            "rss_cap_bytes": RSS_CAP_BYTES,
            "process_swap_cap": 0,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swaps": process_swaps(),
            "user_cpu_seconds": usage.ru_utime,
            "system_cpu_seconds": usage.ru_stime,
        },
    }


def main() -> int:
    started = time.perf_counter()
    script_path = Path(__file__).resolve()
    campaign = script_path.parent.parent
    output = campaign / (
        "receipts/hsop-j2-secant-r10-third-colon-koszul-full-rank-modular-audit.json"
    )
    signal.signal(
        signal.SIGALRM,
        lambda _signum, _frame: (_ for _ in ()).throw(
            TimeoutError("90-second archival audit alarm")
        ),
    )
    signal.setitimer(signal.ITIMER_REAL, WALL_CAP_SECONDS)
    try:
        receipt = audit(campaign, started)
        output.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "output": str(output),
                    "p197_rank": receipt["prime_records"]["197"]["custom_rank"],
                    "p197_alternative_pivot_hash": receipt["hashes"][
                        "alternative_p197_pivot_coordinates_sha256"
                    ],
                    "wall_seconds": receipt["timings"]["total_wall_seconds"],
                },
                sort_keys=True,
            )
        )
        return 0
    except Exception as error:
        failure = {
            "schema": "hc4.third-colon-koszul-full-rank-modular-audit.v1",
            "status": "FAIL_CLOSED_FULL_KOSZUL_RANK_AUDIT",
            "error_type": type(error).__name__,
            "error": str(error),
            "claim_boundary": (
                "No positive mathematical conclusion is licensed by this failed or "
                "incomplete archival audit. The stopped normalization remains stopped."
            ),
            "source_sha256": sha256_bytes(script_path.read_bytes()),
            "wall_seconds": time.perf_counter() - started,
            "maximum_rss_native": native_max_rss_bytes(),
            "process_swaps": process_swaps(),
        }
        output.write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="ascii"
        )
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    raise SystemExit(main())
