from __future__ import annotations

import argparse
from pathlib import Path

from pipeline.common.cache import build_cache_metadata, config_hash, hash_paths, read_cache_metadata, write_cache_metadata
from pipeline.common.config import RootConfig, load_config
from pipeline.common.io_safe import atomic_write_json, write_csv_rows


def infer_output_stage(path: str | Path) -> str:
    s = Path(path).as_posix().lower()
    name = Path(path).name.lower()
    if "data/labeled" in s:
        return "labeled"
    if "feature_matrices/baseline" in s or "baseline_feature" in name:
        return "baseline_feature_matrix"
    if "feature_matrices/expanded" in s or "expanded_feature" in name:
        return "expanded_feature_matrix"
    if "column_registry" in name:
        return "column_registry"
    if "selectors" in s or "features.json" in name:
        return "frozen_feature_set"
    if "oos_predictions" in name:
        return "oos_predictions"
    if "backtest_results" in name:
        return "backtest_results"
    if "metrics" in s or "metrics" in name:
        return "metrics_report"
    if "stress" in s or "stress" in name:
        return "stress_report"
    if "acceptance" in s or "acceptance" in name:
        return "acceptance_report"
    return "unknown_artifact"


def _maybe_backfill_metadata(p: Path, config: RootConfig, trusted: bool) -> None:
    meta = build_cache_metadata(
        p,
        source_stage="unknown_backfill",
        output_stage=infer_output_stage(p),
        source_paths=[],
        config=config,
        code_paths=[],
        trusted_for_reuse=trusted,
        backfilled=True,
    )
    meta["backfill_note"] = (
        "historical sidecar generated from existing artifact only; not reusable unless trusted_for_reuse=true"
    )
    write_cache_metadata(p, meta)


def cache_status(
    root: str | Path = "data",
    artifacts: str | Path = "artifacts",
    reports: str | Path = "reports",
    *,
    config: RootConfig | None = None,
    write_missing_metadata: bool = False,
    trust_backfill: bool = False,
) -> dict:
    config = config or RootConfig()
    roots = [Path(root), Path(artifacts), Path(reports)]
    rows = []
    for base in roots:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.name.endswith(".metadata.json"):
                continue
            if p.suffix.lower() not in {".parquet", ".json", ".csv"}:
                continue
            meta = read_cache_metadata(p)
            if meta is None:
                if write_missing_metadata:
                    _maybe_backfill_metadata(p, config, trust_backfill)
                    status = "backfilled trusted" if trust_backfill else "backfilled untrusted"
                    reason = "metadata sidecar written"
                else:
                    status = "missing metadata"
                    reason = ""
            else:
                sources = meta.get("source_paths") or []
                existing_sources = [s for s in sources if s and Path(s).exists()]
                if meta.get("trusted_for_reuse") is False:
                    status = "backfilled untrusted"
                    reason = "not eligible for cache reuse"
                elif sources and not existing_sources:
                    status = "missing source"
                    reason = "no source_paths exist"
                elif sources and hash_paths(existing_sources) != meta.get("source_manifest_hash"):
                    status = "stale"
                    reason = "source mismatch"
                elif meta.get("config_hash") and meta.get("config_hash") != config_hash(config):
                    status = "config mismatch"
                    reason = "current config hash differs"
                else:
                    status = "fresh"
                    reason = ""
            rows.append({"artifact": str(p), "status": status, "reason": reason, "metadata": str(p) + ".metadata.json"})
    report = {"status": "PASS", "counts": {s: sum(1 for r in rows if r["status"] == s) for s in sorted({r["status"] for r in rows})}, "artifacts": rows}
    atomic_write_json("reports/validation/cache_status_report.json", report)
    write_csv_rows("reports/validation/cache_status_summary.csv", rows or [{"artifact": "", "status": "missing", "reason": "no artifacts"}])
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default="data")
    p.add_argument("--artifacts", default="artifacts")
    p.add_argument("--reports", default="reports")
    p.add_argument("--write-missing-metadata", action="store_true")
    p.add_argument("--trust-backfill", action="store_true", help="mark generated historical sidecars as reusable")
    args = p.parse_args()
    try:
        cfg = load_config()
    except Exception:
        cfg = RootConfig()
    report = cache_status(
        args.root,
        args.artifacts,
        args.reports,
        config=cfg,
        write_missing_metadata=args.write_missing_metadata,
        trust_backfill=args.trust_backfill,
    )
    print(f"cache_status={report['status']} counts={report['counts']}")


if __name__ == "__main__":
    main()
