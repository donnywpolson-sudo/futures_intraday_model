from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


class DatabentoTimeseriesClient(Protocol):
    def get_range(self, **kwargs: object) -> object: ...


class DatabentoClient(Protocol):
    timeseries: DatabentoTimeseriesClient


def _relative_path(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"missing input: {_relative_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"unreadable input: {exc}"]
    if not isinstance(payload, dict):
        return None, ["input JSON top-level is not an object"]
    return payload, []


def _store_to_frame(store: object) -> pd.DataFrame:
    to_df = getattr(store, "to_df")
    try:
        frame_or_frames = to_df(pretty_ts=True, map_symbols=True)
    except TypeError:
        frame_or_frames = to_df()
    if isinstance(frame_or_frames, pd.DataFrame):
        return frame_or_frames.copy()
    return pd.concat(frame_or_frames, ignore_index=False).copy()


def _timestamp_series(frame: pd.DataFrame) -> pd.Series:
    if "ts_event" in frame.columns:
        return pd.to_datetime(frame["ts_event"], utc=True, errors="coerce")
    if "ts" in frame.columns:
        return pd.to_datetime(frame["ts"], utc=True, errors="coerce")
    if isinstance(frame.index, pd.DatetimeIndex):
        return pd.Series(pd.to_datetime(frame.index, utc=True, errors="coerce"), index=frame.index)
    raise ValueError("downloaded frame missing ts_event/ts timestamp")


def _safe_file_stem(task: dict[str, Any]) -> str:
    start = str(task["start"]).replace(":", "").replace("-", "").replace("Z", "Z")
    end = str(task["end"]).replace(":", "").replace("-", "").replace("Z", "Z")
    return f"{task['market']}_{task['year']}_{task['schema']}_{task['symbols']}_{start}_{end}"


def _task_output_path(output_root: Path, task: dict[str, Any]) -> Path:
    return (
        output_root
        / str(task["schema"])
        / str(task["market"])
        / str(task["year"])
        / f"{_safe_file_stem(task)}.parquet"
    )


def _estimate_total(payload: dict[str, Any]) -> float | None:
    value = payload.get("total_estimated_cost_usd")
    if value is not None:
        return float(value)
    estimates = payload.get("estimates", [])
    if not isinstance(estimates, list):
        return None
    total = 0.0
    for item in estimates:
        if not isinstance(item, dict) or item.get("status") != "ok":
            return None
        total += float(item.get("estimated_cost_usd", 0.0))
    return total


def validate_estimate(
    estimate: dict[str, Any],
    *,
    max_total_cost_usd: float,
) -> list[str]:
    failures: list[str] = []
    if estimate.get("status") != "PASS":
        failures.append("cost estimate status is not PASS")
    if estimate.get("api_called") is not True:
        failures.append("cost estimate did not call provider metadata API")
    if estimate.get("download_allowed") is not False:
        failures.append("cost estimate must have download_allowed=false")
    total = _estimate_total(estimate)
    if total is None:
        failures.append("cost estimate missing total estimated cost")
    elif total > max_total_cost_usd:
        failures.append(f"estimated cost {total} exceeds max {max_total_cost_usd}")
    estimates = estimate.get("estimates")
    if not isinstance(estimates, list) or not estimates:
        failures.append("cost estimate has no estimates")
    elif any(not isinstance(item, dict) or item.get("status") != "ok" for item in estimates):
        failures.append("cost estimate contains non-ok estimate rows")
    return failures


def _audit_downloaded_frame(frame: pd.DataFrame, task: dict[str, Any], output_path: Path) -> dict[str, Any]:
    ts = _timestamp_series(frame)
    gap = task.get("source_gap_timestamps", {})
    first = pd.Timestamp(str(gap.get("first_synthetic_ts")))
    last = pd.Timestamp(str(gap.get("last_synthetic_ts"))) + pd.Timedelta(minutes=1)
    if first.tzinfo is None:
        first = first.tz_localize("UTC")
    if last.tzinfo is None:
        last = last.tz_localize("UTC")
    in_gap = ts.ge(first) & ts.lt(last)
    valid_ts = ts.dropna()
    return {
        "market": task.get("market"),
        "year": task.get("year"),
        "schema": task.get("schema"),
        "dataset": task.get("dataset"),
        "stype_in": task.get("stype_in"),
        "symbols": task.get("symbols"),
        "output_path": _relative_path(output_path),
        "downloaded_rows": int(len(frame)),
        "rows_inside_ohlcv_gap": int(in_gap.fillna(False).sum()),
        "first_ts_event": valid_ts.min().isoformat() if not valid_ts.empty else None,
        "last_ts_event": valid_ts.max().isoformat() if not valid_ts.empty else None,
        "source_gap_timestamps": gap,
        "has_trade_or_book_activity_inside_gap": bool(in_gap.fillna(False).any()),
    }


def run_download_audit(
    estimate: dict[str, Any],
    client: DatabentoClient,
    *,
    output_root: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for task in estimate.get("estimates", []):
        if not isinstance(task, dict):
            continue
        output_path = _task_output_path(output_root, task)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            store = client.timeseries.get_range(
                dataset=task["dataset"],
                symbols=task["symbols"],
                schema=task["schema"],
                stype_in=task["stype_in"],
                start=task["start"],
                end=task["end"],
            )
            frame = _store_to_frame(store)
            frame.to_parquet(output_path, index=False)
            rows.append(_audit_downloaded_frame(frame, task, output_path))
        except Exception as exc:
            failures.append(
                f"{task.get('market')} {task.get('year')} {task.get('schema')}: {exc}"
            )
    return rows, failures


def build_report(
    estimate: dict[str, Any] | None,
    *,
    estimate_path: Path,
    output_root: Path,
    max_total_cost_usd: float,
    allow_download: bool,
    client: DatabentoClient | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    audit_rows: list[dict[str, Any]] = []
    api_called = False
    if estimate is None:
        failures.append(f"missing cost estimate: {_relative_path(estimate_path)}")
    else:
        failures.extend(validate_estimate(estimate, max_total_cost_usd=max_total_cost_usd))
    if not allow_download:
        failures.append("--allow-download is required")
    if not failures:
        if client is None:
            from scripts.phase1A_download.download_databento_raw import get_client

            client = get_client()
        audit_rows, download_failures = run_download_audit(
            estimate or {}, client, output_root=output_root
        )
        failures.extend(download_failures)
        api_called = True
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "status": "FAIL" if failures else "PASS",
        "download_api_called": api_called,
        "download_allowed": bool(allow_download),
        "cost_estimate_json": _relative_path(estimate_path),
        "output_root": _relative_path(output_root),
        "max_total_cost_usd": max_total_cost_usd,
        "failures": failures,
        "audits": audit_rows,
    }


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cost-estimate-json", required=True)
    parser.add_argument("--output-root", default="data/source_gap_audit")
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--max-total-cost-usd", type=float, default=0.01)
    parser.add_argument("--allow-download", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    estimate_path = Path(args.cost_estimate_json)
    estimate, load_failures = _load_json(estimate_path)
    report = build_report(
        estimate,
        estimate_path=estimate_path,
        output_root=Path(args.output_root),
        max_total_cost_usd=float(args.max_total_cost_usd),
        allow_download=bool(args.allow_download),
    )
    if load_failures:
        report["failures"] = [*load_failures, *report["failures"]]
        report["status"] = "FAIL"
    write_json(report, Path(args.report_out))
    if report["status"] != "PASS":
        print(f"FAIL tick/source gap download audit: failures={len(report['failures'])}")
        return 1
    print(f"PASS tick/source gap download audit: audits={len(report['audits'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
