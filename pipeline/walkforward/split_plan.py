from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.common.io_safe import atomic_write_json, write_csv_rows


def write_wfa_split_plan(
    splits: list[tuple],
    files: list[Path],
    config: Any,
    *,
    json_path: str | Path = "reports/wfa/wfa_split_plan.json",
    csv_path: str | Path = "reports/wfa/wfa_split_plan_summary.csv",
) -> dict:
    file_map: dict[tuple[str, int], str] = {}
    for p in files:
        try:
            file_map[(p.parent.name, int(p.stem))] = str(p)
        except ValueError:
            continue

    rows = []
    failures = []
    for idx, split in enumerate(splits, 1):
        train_years = list(split[0])
        test_years = list(split[1])
        train_start = split[2] if len(split) > 2 else None
        train_end = split[3] if len(split) > 3 else None
        test_start = split[4] if len(split) > 4 else None
        test_end = split[5] if len(split) > 5 else None
        overlap = sorted(set(train_years) & set(test_years))
        temporal_overlap = bool(train_start and train_end and test_start and test_end and not (train_end <= test_start))
        status = "PASS"
        if overlap and not (train_start and test_start):
            status = "FAIL"
            failures.append(f"split {idx}: overlapping train/test years without timestamp windows: {overlap}")
        if temporal_overlap:
            status = "FAIL"
            failures.append(f"split {idx}: train/test timestamp overlap")
        symbols = list(getattr(config, "symbols", []) or [])
        train_files = [file_map.get((s, y), "") for s in symbols for y in train_years]
        test_files = [file_map.get((s, y), "") for s in symbols for y in test_years]
        rows.append(
            {
                "split_id": idx,
                "status": status,
                "symbols": ",".join(symbols),
                "train_years": ",".join(map(str, train_years)),
                "test_years": ",".join(map(str, test_years)),
                "train_start": str(train_start) if train_start is not None else "",
                "train_end": str(train_end) if train_end is not None else "",
                "test_start": str(test_start) if test_start is not None else "",
                "test_end": str(test_end) if test_end is not None else "",
                "train_file_count": sum(1 for x in train_files if x),
                "test_file_count": sum(1 for x in test_files if x),
                "purge_target_overlap": bool(getattr(getattr(config, "walkforward", object()), "purge_target_overlap", True)),
                "embargo_bars": int(getattr(getattr(config, "walkforward", object()), "embargo_bars", 0)),
            }
        )

    report = {
        "status": "FAIL" if failures else "PASS",
        "split_count": len(splits),
        "file_count": len(files),
        "symbols": list(getattr(config, "symbols", []) or []),
        "walkforward": getattr(getattr(config, "walkforward", object()), "model_dump", lambda: {})(),
        "failures": failures,
        "splits": rows,
    }
    atomic_write_json(json_path, report)
    write_csv_rows(csv_path, rows or [{"split_id": "", "status": "WARN"}])
    return report
