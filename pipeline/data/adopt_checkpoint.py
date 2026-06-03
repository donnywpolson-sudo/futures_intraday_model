from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.common.config import DEFAULT_MARKETS
from pipeline.common.io_safe import atomic_write_json, write_csv_rows
from pipeline.data.classify_checkpoint import canonical_stage, classify_checkpoint
from pipeline.data_gate.manifest import _sha256, build_data_manifest


SUPPORTED = {"auto", "validated", "session_normalized", "causally_gated_normalized", "labeled", "baseline_feature_matrix", "expanded_feature_matrix"}
ROOT_BY_STAGE = {
    "validated": "validated",
    "session_normalized": "session_normalized",
    "causally_gated_normalized": "causally_gated_normalized",
    "labeled": "labeled",
    "baseline_feature_matrix": "feature_matrices/baseline",
    "expanded_feature_matrix": "feature_matrices/expanded",
}


def _schema_hash(df: pl.DataFrame) -> str:
    import hashlib
    return hashlib.sha256("|".join(f"{c}:{t}" for c, t in zip(df.columns, df.dtypes)).encode()).hexdigest()


def _infer_market(path: Path, df: pl.DataFrame, allowed: list[str] | None) -> str | None:
    candidates = allowed or DEFAULT_MARKETS
    if path.parent.name in candidates:
        return path.parent.name
    if "symbol" in df.columns and df["symbol"].n_unique() == 1:
        return str(df["symbol"][0])
    name = path.stem.upper()
    for s in candidates:
        if re.search(rf"(^|[_\-]){re.escape(s)}([_\-]|$)", name):
            return s
    return candidates[0] if len(candidates) == 1 else None


def _infer_year(path: Path, df: pl.DataFrame) -> int | None:
    if re.fullmatch(r"\d{4}", path.stem):
        return int(path.stem)
    m = re.search(r"(20\d{2}|19\d{2})", path.name)
    if m:
        return int(m.group(1))
    if "ts_event" in df.columns and df.height:
        v = df["ts_event"].min()
        return int(v.year) if hasattr(v, "year") else None
    return None


def adopt_checkpoint(
    stage: str,
    source: str | Path,
    target: str | Path | None = None,
    *,
    target_root: str | Path | None = None,
    copy: bool = False,
    symlink: bool = False,
    in_place: bool = False,
    symbols: list[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if stage not in SUPPORTED:
        raise ValueError(f"unsupported checkpoint stage={stage}")
    source = Path(source)
    classification = None
    if stage == "auto":
        classification = classify_checkpoint(source)
        inferred = canonical_stage(classification["inferred_stage"])
        if inferred in {"unknown", "raw"} or inferred not in ROOT_BY_STAGE:
            report = {"status": "FAIL", "source_path": str(source), "target_path": "", "stage": "auto", "classification": classification, "files_discovered": len(list(source.rglob("*.parquet"))), "files_adopted": [], "files_skipped": [], "errors": [f"cannot auto-adopt inferred_stage={classification['inferred_stage']}"], "rows": []}
            atomic_write_json("reports/validation/checkpoint_adoption_report.json", report)
            write_csv_rows("reports/validation/checkpoint_adoption_summary.csv", [{"source_path": str(source), "target_path": "", "status": "FAIL", "errors": report["errors"][0]}])
            return report
        stage = inferred
        if target is None:
            if target_root is None:
                raise ValueError("--target-root is required when --stage auto and --target is omitted")
            target = Path(target_root) / ROOT_BY_STAGE[stage]
    if target is None:
        raise ValueError("target is required")
    target = Path(target if not in_place else source)
    files = sorted(source.rglob("*.parquet"))
    rows = []
    adopted = []
    skipped = []
    errors = []
    for p in files:
        try:
            df = pl.read_parquet(p)
            market = _infer_market(p, df, symbols)
            year = _infer_year(p, df)
            if market is None or year is None:
                raise ValueError(f"cannot infer market/year for {p}")
            if symbols and market not in symbols:
                skipped.append(str(p)); continue
            if start_year and year < start_year:
                skipped.append(str(p)); continue
            if end_year and year > end_year:
                skipped.append(str(p)); continue
            out = target / market / f"{year}.parquet"
            if out.exists() and not force and not in_place and out.resolve() != p.resolve():
                raise FileExistsError(f"target exists without --force: {out}")
            if not dry_run and not in_place:
                out.parent.mkdir(parents=True, exist_ok=True)
                if symlink:
                    try:
                        if out.exists() and force:
                            out.unlink()
                        out.symlink_to(p.resolve())
                    except OSError as exc:
                        raise OSError(f"symlink unavailable on this platform: {exc}") from exc
                else:
                    shutil.copy2(p, out)
            if not dry_run:
                adopted.append(str(out if not in_place else p))
            rows.append({
                "source_path": str(p), "target_path": str(out if not in_place else p), "stage": stage,
                "status": "DRY_RUN" if dry_run else "ADOPTED", "market": market, "year": year,
                "row_count": df.height, "ts_min": df["ts_event"].min() if "ts_event" in df.columns else None,
                "ts_max": df["ts_event"].max() if "ts_event" in df.columns else None,
                "schema_hash": _schema_hash(df), "sha256": _sha256(p), "warnings": "", "errors": "",
            })
        except Exception as exc:
            errors.append(str(exc))
            rows.append({"source_path": str(p), "target_path": "", "stage": stage, "status": "ERROR", "errors": str(exc)})
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
        build_data_manifest(target, stage=stage)
    report = {"status": "FAIL" if errors else "PASS", "source_path": str(source), "target_path": str(target), "stage": stage, "classification": classification, "files_discovered": len(files), "files_adopted": adopted, "files_skipped": skipped, "errors": errors, "rows": rows}
    if not dry_run:
        atomic_write_json("reports/validation/checkpoint_adoption_report.json", report)
        write_csv_rows("reports/validation/checkpoint_adoption_summary.csv", rows or [{"source_path": "", "target_path": "", "status": "WARN"}])
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True)
    p.add_argument("--source", required=True)
    p.add_argument("--target")
    p.add_argument("--target-root")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--copy", action="store_true")
    mode.add_argument("--symlink", action="store_true")
    mode.add_argument("--in-place", action="store_true")
    p.add_argument("--symbols")
    p.add_argument("--start-year", type=int)
    p.add_argument("--end-year", type=int)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    symbols = args.symbols.split(",") if args.symbols else None
    report = adopt_checkpoint(args.stage, args.source, args.target, target_root=args.target_root, copy=args.copy or not args.symlink, symlink=args.symlink, in_place=args.in_place, symbols=symbols, start_year=args.start_year, end_year=args.end_year, force=args.force, dry_run=args.dry_run)
    print(f"checkpoint_adoption={report['status']} discovered={report['files_discovered']} adopted={len(report['files_adopted'])}")
    if report["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
