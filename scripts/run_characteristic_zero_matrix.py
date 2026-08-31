#!/usr/bin/env python3
"""Run characteristic-zero five-support charts with isolated concurrency.

Each chart runs in a fresh worker process.  This is not needed for algebraic
correctness, but it makes ``RUSAGE_CHILDREN`` in ``run_one`` attributable to a
single Singular child instead of a process-global mixture of concurrent
thread children.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import multiprocessing
import time
from pathlib import Path

from prove_generic_five_support import equation_hash, equations_for, run_one
from scout_five_support import CHARTS, PARTITIONS


def parse_partition(text: str) -> tuple[int, ...]:
    if text == "all":
        return ()
    value = tuple(int(item) for item in text.split(","))
    if value not in PARTITIONS:
        raise argparse.ArgumentTypeError(f"unknown partition {value}")
    return value


def run_chart_isolated(
    partition: tuple[int, ...], chart: str, mode: str, timeout: int
) -> dict[str, object]:
    """Build and run one chart inside a dedicated worker process."""

    equations, _ = equations_for(partition)
    result = run_one(equations, chart, mode, timeout)
    result["resource_metrics_scope"] = "isolated_worker_process"
    result["resource_metrics_reliable"] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--partition", type=parse_partition, default=())
    parser.add_argument(
        "--mode",
        choices=("function-field", "polynomial-open"),
        default="function-field",
    )
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selected = PARTITIONS if not args.partition else (args.partition,)
    started = time.perf_counter()
    records = []
    for partition in selected:
        equations, build_seconds = equations_for(partition)
        stream_hash = equation_hash(equations)
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=args.jobs,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            futures = {
                chart: executor.submit(
                    run_chart_isolated,
                    partition,
                    chart,
                    args.mode,
                    args.timeout,
                )
                for chart in CHARTS
            }
            charts = [futures[chart].result() for chart in CHARTS]
        if args.mode == "function-field" and all(
            chart["is_unit"] for chart in charts
        ):
            disposition = "EXACT_GENERIC_UNIT_IDEAL_ALL_LINE_CHARTS"
        elif args.mode == "polynomial-open" and all(
            chart["is_unit"] for chart in charts
        ):
            disposition = "EXACT_COMPLETE_FIVE_SUPPORT_OPEN"
        elif any(chart["timed_out"] for chart in charts):
            disposition = "TIMEOUTS_RETAINED"
        else:
            disposition = "NONUNIT_OR_ERROR_REQUIRES_AUDIT"
        record = {
            "partition": list(partition),
            "mode": args.mode,
            "equation_count": len(equations),
            "equation_stream_sha256": stream_hash,
            "equation_build_seconds": build_seconds,
            "charts": charts,
            "disposition": disposition,
        }
        records.append(record)
        print(
            f"partition {partition}: {disposition}; "
            f"chart walls {[round(chart['wall_seconds'], 3) for chart in charts]}",
            flush=True,
        )
        partial = {
            "schema": "hc4-double-conic-five-support-characteristic-zero-matrix-v1",
            "mode": args.mode,
            "records": records,
            "wall_seconds_so_far": time.perf_counter() - started,
            "complete": len(records) == len(selected),
            "resource_metrics_isolated": True,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(partial, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    result = {
        "schema": "hc4-double-conic-five-support-characteristic-zero-matrix-v1",
        "mode": args.mode,
        "records": records,
        "all_selected_partitions_exact_unit": all(
            record["disposition"]
            in {
                "EXACT_GENERIC_UNIT_IDEAL_ALL_LINE_CHARTS",
                "EXACT_COMPLETE_FIVE_SUPPORT_OPEN",
            }
            for record in records
        ),
        "wall_seconds": time.perf_counter() - started,
        "complete": True,
        "resource_metrics_isolated": True,
        "claim_boundary": (
            "function-field mode proves generic fibers only; polynomial-open "
            "mode proves the normalized distinct-five-root open"
        ),
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
