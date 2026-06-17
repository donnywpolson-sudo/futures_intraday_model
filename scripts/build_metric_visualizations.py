#!/usr/bin/env python3
"""Build a static diagnostic dashboard from the Phase 0 report inventory."""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import struct
import subprocess
import sys
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd


FEASIBLE_CHARTS = {
    "Locked Tier 1 costed OOS summary cards",
    "net/gross/cost by market",
    "promotion gate blockers",
    "artifact provenance/readiness summary",
    "feature hypothesis statuses",
    "target hypothesis statuses",
    "Phase 9 stopped/rejected branch summary",
}
COMBINED_HYPOTHESIS_CHART = "Feature and target hypothesis statuses"
MISSING_METRIC_ROWS = [
    [
        "Equity curve / cumulative PnL",
        "Skipped by Phase 0 inventory",
        "Needed to inspect path dependency, drawdown timing, and recovery behavior.",
    ],
    [
        "Fold/year/hour attribution",
        "Not available in the approved Phase 0 source files",
        "Needed to detect time, fold, or market concentration before trusting alpha.",
    ],
    [
        "Live fills, queue position, latency, and capacity",
        "No live execution source-of-truth artifact",
        "Needed before treating research PnL as executable.",
    ],
    [
        "Final holdout performance",
        "Intentionally skipped",
        "Must remain untouched until a branch passes pre-registered research gates.",
    ],
]


@dataclass
class BuildContext:
    reports_dir: Path
    out_dir: Path
    inventory_path: Path
    strict: bool = False
    derive_predictions: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_files_read: list[str] = field(default_factory=list)
    source_files_missing: list[str] = field(default_factory=list)
    charts_generated: list[dict[str, Any]] = field(default_factory=list)
    tables_generated: list[dict[str, Any]] = field(default_factory=list)
    charts_skipped: list[dict[str, Any]] = field(default_factory=list)
    displayed_metric_ids: list[str] = field(default_factory=list)
    metric_contract: dict[str, Any] = field(default_factory=dict)
    metric_audit_markdown: str = ""
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)

    @property
    def repo_root(self) -> Path:
        return self.reports_dir.parent if self.reports_dir.name == "reports" else Path.cwd()

    @property
    def charts_dir(self) -> Path:
        return self.out_dir / "charts"

    def resolve(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return self.repo_root / path

    def rel(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return payload


def read_json_source(ctx: BuildContext, raw_path: str, *, required: bool = False) -> dict[str, Any]:
    path = ctx.resolve(raw_path)
    if not path.exists():
        message = f"missing source file: {raw_path}"
        ctx.source_files_missing.append(raw_path)
        if required or ctx.strict:
            ctx.errors.append(message)
        else:
            ctx.warnings.append(message)
        return {}
    try:
        payload = load_json(path)
    except Exception as exc:
        message = f"could not read JSON source {raw_path}: {exc}"
        if required or ctx.strict:
            ctx.errors.append(message)
        else:
            ctx.warnings.append(message)
        return {}
    ctx.source_files_read.append(raw_path)
    return payload


def read_text_source(ctx: BuildContext, raw_path: str, *, required: bool = False) -> str:
    path = ctx.resolve(raw_path)
    if not path.exists():
        message = f"missing source file: {raw_path}"
        ctx.source_files_missing.append(raw_path)
        if required or ctx.strict:
            ctx.errors.append(message)
        else:
            ctx.warnings.append(message)
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        message = f"could not read text source {raw_path}: {exc}"
        if required or ctx.strict:
            ctx.errors.append(message)
        else:
            ctx.warnings.append(message)
        return ""
    ctx.source_files_read.append(raw_path)
    return text


def value_at(payload: Mapping[str, Any], path: Sequence[str], default: Any = None) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def fmt(value: Any) -> str:
    if value is None:
        return "MISSING"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:,.4f}" if abs(value) < 1000 else f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) else None


def git_commit() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def write_fallback_bar_png(path: Path, labels: Sequence[str], values: Sequence[float]) -> None:
    width, height = 760, 420
    margin_left, margin_right, margin_top, margin_bottom = 70, 30, 35, 70
    image = bytearray([255, 255, 255] * width * height)

    def pixel(x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 3
            image[idx : idx + 3] = bytes(color)

    def rect(x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
        for y in range(max(0, y0), min(height, y1)):
            for x in range(max(0, x0), min(width, x1)):
                pixel(x, y, color)

    for x in range(margin_left, width - margin_right):
        pixel(x, height - margin_bottom, (180, 180, 180))
    for y in range(margin_top, height - margin_bottom):
        pixel(margin_left, y, (180, 180, 180))

    clean_values = [float(value) for value in values if pd.notna(value)]
    if not clean_values:
        clean_values = [0.0]
    min_value = min(0.0, min(clean_values))
    max_value = max(0.0, max(clean_values))
    span = max(max_value - min_value, 1.0)
    plot_w = width - margin_left - margin_right
    plot_h = height - margin_top - margin_bottom
    zero_y = int(margin_top + (max_value / span) * plot_h)
    for x in range(margin_left, width - margin_right):
        pixel(x, zero_y, (120, 120, 120))

    count = max(len(values), 1)
    slot = plot_w / count
    colors = [(45, 105, 180), (220, 120, 45), (80, 150, 90), (170, 70, 130)]
    for idx, value in enumerate(values):
        val = float(value) if pd.notna(value) else 0.0
        x0 = int(margin_left + idx * slot + slot * 0.15)
        x1 = int(margin_left + (idx + 1) * slot - slot * 0.15)
        y_val = int(margin_top + ((max_value - val) / span) * plot_h)
        rect(x0, min(y_val, zero_y), x1, max(y_val, zero_y) + 1, colors[idx % len(colors)])

    raw = b"".join(b"\x00" + image[y * width * 3 : (y + 1) * width * 3] for y in range(height))
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(png)


def write_bar_chart(
    ctx: BuildContext,
    filename: str,
    labels: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    ylabel: str,
    source_files: Sequence[str],
) -> str | None:
    ctx.charts_dir.mkdir(parents=True, exist_ok=True)
    path = ctx.charts_dir / filename
    numeric = [safe_float(value) for value in values]
    if not labels or not numeric or all(value is None for value in numeric):
        ctx.warnings.append(f"skipped chart {title}: no numeric values")
        return None
    clean_values = [0.0 if value is None else value for value in numeric]
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        frame = pd.DataFrame({"label": list(labels), "value": clean_values})
        fig, ax = plt.subplots(figsize=(8, 4.5))
        colors = ["#2f6fbb" if value >= 0 else "#b84a4a" for value in frame["value"]]
        ax.bar(frame["label"], frame["value"], color=colors)
        ax.axhline(0, color="#555", linewidth=0.8)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="x", rotation=25)
        fig.tight_layout()
        fig.savefig(path, dpi=130)
        plt.close(fig)
    except ModuleNotFoundError:
        if "matplotlib is not installed; using built-in PNG fallback charts" not in ctx.warnings:
            ctx.warnings.append("matplotlib is not installed; using built-in PNG fallback charts")
        write_fallback_bar_png(path, labels, clean_values)
    except Exception as exc:
        ctx.warnings.append(f"matplotlib failed for {title}; using fallback PNG: {exc}")
        write_fallback_bar_png(path, labels, clean_values)
    chart = {
        "name": title,
        "path": ctx.rel(path),
        "source_files": list(source_files),
        "type": "bar_png",
    }
    ctx.charts_generated.append(chart)
    return chart["path"]


def html_table(headers: Sequence[str], rows: Sequence[Sequence[Any]], source_files: Sequence[str]) -> str:
    out = [
        '<div class="table-wrap">',
        f'<div class="source">Source: {html.escape(", ".join(source_files) or "MISSING")}</div>',
        "<table>",
        "<thead><tr>",
        *[f"<th>{html.escape(str(header))}</th>" for header in headers],
        "</tr></thead>",
        "<tbody>",
    ]
    for row in rows:
        out.append("<tr>")
        out.extend(f"<td>{html.escape(fmt(cell))}</td>" for cell in row)
        out.append("</tr>")
    out.extend(["</tbody>", "</table>", "</div>"])
    return "\n".join(out)


def status_class(status: Any) -> str:
    text = str(status).upper()
    if text in {"PASS", "OK", "READY", "YES", "TRUE"}:
        return "ok"
    if text in {"FAIL", "NO", "FALSE", "BLOCKED", "REJECTED", "STOP", "STOP_BRANCH_PERMANENTLY"}:
        return "fail"
    return "watch"


def metric_cards(headers: Sequence[str], rows: Sequence[Sequence[Any]], source_files: Sequence[str]) -> str:
    out = [
        '<div class="source">Source: ' + html.escape(", ".join(source_files) or "MISSING") + "</div>",
        '<div class="cards">',
    ]
    for row in rows:
        label = row[0] if len(row) > 0 else ""
        value = row[1] if len(row) > 1 else None
        status = row[2] if len(row) > 2 else "WATCH"
        use = row[3] if len(row) > 3 else ""
        out.extend(
            [
                '<div class="metric-card">',
                f"<div class=\"metric-label\">{html.escape(str(label))}</div>",
                f"<div class=\"metric-value\">{html.escape(fmt(value))}</div>",
                f"<div class=\"pill {status_class(status)}\">{html.escape(str(status))}</div>",
                f"<p>{html.escape(str(use))}</p>",
                "</div>",
            ]
        )
    out.append("</div>")
    return "\n".join(out)


def callout(title: str, body: str) -> str:
    return (
        '<div class="callout">'
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{html.escape(body)}</p>"
        "</div>"
    )


def chart_block(title: str, chart_path: str | None, source_files: Sequence[str], caption: str = "") -> str:
    if not chart_path:
        return ""
    rel_path = Path(chart_path).relative_to("reports/visualizations").as_posix() if chart_path.startswith("reports/visualizations/") else chart_path
    return "\n".join(
        [
            '<div class="chart">',
            f"<h3>{html.escape(title)}</h3>",
            f'<div class="source">Source: {html.escape(", ".join(source_files))}</div>',
            f'<img src="{html.escape(rel_path)}" alt="{html.escape(title)}">',
            f'<p class="explain">{html.escape(caption)}</p>' if caption else "",
            "</div>",
        ]
    )


def validate_inventory_sources(ctx: BuildContext, inventory: Mapping[str, Any]) -> None:
    if ctx.strict:
        for row in inventory.get("source_of_truth_report_files", []):
            if not isinstance(row, Mapping):
                continue
            raw_path = str(row.get("path", ""))
            if raw_path and not ctx.resolve(raw_path).exists():
                ctx.errors.append(f"missing source-of-truth file: {raw_path}")


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def chart_sources(inventory: Mapping[str, Any], chart_name: str) -> list[str]:
    wanted = normalize_name(chart_name)
    aliases = {
        "net gross cost by market": {"net gross cost by market", "net by market"},
        "promotion gate blockers": {"promotion gate blockers", "promotion blockers"},
        "artifact provenance readiness summary": {
            "artifact provenance readiness summary",
            "artifact provenance readiness",
        },
        "phase 9 stopped rejected branch summary": {
            "phase 9 stopped rejected branch summary",
            "phase 9 no go decisions gates",
        },
        "feature hypothesis statuses": {"feature and target hypothesis statuses"},
        "target hypothesis statuses": {"feature and target hypothesis statuses"},
    }
    accepted = {wanted, *aliases.get(wanted, set())}
    sources: list[str] = []
    for row in inventory.get("charts", []):
        if not isinstance(row, Mapping):
            continue
        name = normalize_name(str(row.get("chart", "")))
        if name in accepted or (
            chart_name in {"feature hypothesis statuses", "target hypothesis statuses"}
            and normalize_name(COMBINED_HYPOTHESIS_CHART) == name
        ):
            sources.extend(str(item) for item in row.get("sources", []) if item)
    return list(dict.fromkeys(sources))


def skipped_charts_from_inventory(inventory: Mapping[str, Any]) -> list[dict[str, Any]]:
    skipped: list[dict[str, Any]] = []
    for row in inventory.get("charts", []):
        if not isinstance(row, Mapping):
            continue
        if row.get("status") == "skipped":
            skipped.append(
                {
                    "name": str(row.get("chart")),
                    "reason": str(row.get("notes", "Phase 0 marked this chart infeasible.")),
                    "source_files": list(row.get("sources", [])),
                }
            )
    return skipped


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "yes", "1"}:
        return True
    if text in {"false", "no", "0"}:
        return False
    return None


def metric_status(value: Any, pass_threshold: str | None = None) -> str:
    if value is None:
        return "MISSING"
    if pass_threshold is None:
        return "AVAILABLE"
    numeric = safe_float(value)
    if pass_threshold == "> 0":
        return "PASS" if numeric is not None and numeric > 0 else "FAIL"
    if pass_threshold == ">= 0":
        return "PASS" if numeric is not None and numeric >= 0 else "FAIL"
    if pass_threshold == "< 1":
        return "PASS" if numeric is not None and numeric < 1 else "FAIL"
    if pass_threshold == "<= 0":
        return "PASS" if numeric is not None and numeric <= 0 else "FAIL"
    if pass_threshold == "true":
        return "PASS" if as_bool(value) is True else "FAIL"
    if pass_threshold == "zero":
        return "PASS" if numeric == 0 else "FAIL"
    return "AVAILABLE"


def init_contract(run: str | None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run": run,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "metrics": [],
        "missing_evidence": [],
    }


def add_metric(
    ctx: BuildContext,
    *,
    metric_id: str,
    name: str,
    display_name: str,
    dashboard_section: str,
    value: Any,
    definition: str,
    formula: str,
    source_file: str,
    source_key: str,
    aggregation_level: str,
    oos_only: bool,
    causal_leakage_safe: bool,
    promotion_metric: bool,
    diagnostic_metric: bool,
    required: bool,
    pass_threshold: str | None,
    warning_threshold: str | None,
    interpretation: str,
    failure_modes: Sequence[str],
    recommended_next_action_when_bad: str,
    display: bool = True,
) -> dict[str, Any]:
    if not ctx.metric_contract:
        ctx.metric_contract = init_contract(None)
    record = {
        "id": metric_id,
        "name": name,
        "display_name": display_name,
        "dashboard_section": dashboard_section,
        "definition": definition,
        "formula": formula,
        "source_file": source_file,
        "source_key": source_key,
        "aggregation_level": aggregation_level,
        "oos_only": oos_only,
        "causal_leakage_safe": causal_leakage_safe,
        "promotion_metric": promotion_metric,
        "diagnostic_metric": diagnostic_metric,
        "required": required,
        "pass_threshold": pass_threshold,
        "warning_threshold": warning_threshold,
        "interpretation": interpretation,
        "failure_modes": list(failure_modes),
        "recommended_next_action_when_bad": recommended_next_action_when_bad,
        "status": metric_status(value, pass_threshold),
        "value": value,
        "displayed": display,
    }
    ctx.metric_contract["metrics"].append(record)
    if display:
        ctx.displayed_metric_ids.append(metric_id)
    return record


def add_missing_evidence(
    ctx: BuildContext,
    metric_id: str,
    reason: str,
    required_for: Sequence[str],
    *,
    stage: str = "research",
    current_research_blocker: bool = True,
) -> None:
    item = {
        "metric_id": metric_id,
        "reason": reason,
        "required_for": list(required_for),
        "stage": stage,
        "current_research_blocker": current_research_blocker,
    }
    if item not in ctx.missing_evidence:
        ctx.missing_evidence.append(item)


def metric_lookup(ctx: BuildContext) -> dict[str, dict[str, Any]]:
    return {str(row["id"]): row for row in ctx.metric_contract.get("metrics", [])}


def metric_card_rows(ctx: BuildContext, metric_ids: Sequence[str]) -> list[list[Any]]:
    lookup = metric_lookup(ctx)
    rows: list[list[Any]] = []
    for metric_id in metric_ids:
        row = lookup.get(metric_id)
        if row:
            rows.append(
                [
                    row["display_name"],
                    row.get("value"),
                    row.get("status"),
                    row.get("interpretation"),
                ]
            )
    return rows


def metric_table_rows(ctx: BuildContext, metric_ids: Sequence[str]) -> list[list[Any]]:
    lookup = metric_lookup(ctx)
    rows: list[list[Any]] = []
    for metric_id in metric_ids:
        row = lookup.get(metric_id)
        if row:
            rows.append(
                [
                    row["display_name"],
                    row.get("value"),
                    row.get("aggregation_level"),
                    row.get("status"),
                    row.get("interpretation"),
                ]
            )
    return rows


def get_costed_value(costed: Mapping[str, Any], key: str) -> Any:
    return costed.get(key)


def sum_metric(rows: Sequence[Mapping[str, Any]], key: str) -> float:
    return float(sum(safe_float(row.get(key)) or 0.0 for row in rows))


def sharpe(values: pd.Series, *, periods_per_year: int | None = None) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if len(numeric) < 2:
        return None
    std = float(numeric.std(ddof=0))
    if std <= 0.0:
        return None
    value = float(numeric.mean() / std)
    return value * math.sqrt(periods_per_year) if periods_per_year else value


def sortino(values: pd.Series, *, periods_per_year: int | None = None) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if len(numeric) < 2:
        return None
    downside = numeric[numeric < 0.0]
    if len(downside) < 2:
        return None
    std = float(downside.std(ddof=0))
    if std <= 0.0:
        return None
    value = float(numeric.mean() / std)
    return value * math.sqrt(periods_per_year) if periods_per_year else value


def max_drawdown(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0.0)
    if numeric.empty:
        return None
    equity = numeric.cumsum()
    drawdown = equity - equity.cummax()
    return float(drawdown.min())


def profit_factor(values: pd.Series) -> float | None:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    wins = float(numeric[numeric > 0.0].sum())
    losses = float(numeric[numeric < 0.0].sum())
    if losses == 0.0:
        return None
    return wins / abs(losses)


def average_win_loss(values: pd.Series) -> tuple[float | None, float | None, float | None]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    wins = numeric[numeric > 0.0]
    losses = numeric[numeric < 0.0]
    avg_win = float(wins.mean()) if not wins.empty else None
    avg_loss = float(losses.mean()) if not losses.empty else None
    payoff = avg_win / abs(avg_loss) if avg_win is not None and avg_loss not in {None, 0.0} else None
    return avg_win, avg_loss, payoff


def classify_markets(markets: Sequence[Mapping[str, Any]], *, min_active_rows: int = 100) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for row in markets:
        market = row.get("market")
        active_rows = int(safe_float(row.get("trade_count")) or 0)
        net = safe_float(row.get("net_return_dollars")) or 0.0
        if active_rows == 0:
            status = "zero_trade_market"
        elif active_rows < min_active_rows:
            status = "insufficient_trade_count_market"
        elif net <= 0.0:
            status = "negative_net_market"
        else:
            status = "positive_but_not_robust_market"
        rows.append([market, status, active_rows, net])
    return rows


def exclusive_blocker_counts(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty:
        return {}
    categories = pd.Series("trade_or_active", index=frame.index)
    if "position" in frame:
        categories.loc[pd.to_numeric(frame["position"], errors="coerce").fillna(0).eq(0)] = "flat_or_blocked"
    if "blocked_by_fade_filter" in frame:
        categories.loc[frame["blocked_by_fade_filter"].fillna(False).astype(bool)] = "fade_filter_block"
    if "blocked_by_trend_danger" in frame:
        categories.loc[frame["blocked_by_trend_danger"].fillna(False).astype(bool)] = "trend_danger_block"
    if "blocked_by_flat_probability" in frame:
        categories.loc[frame["blocked_by_flat_probability"].fillna(False).astype(bool)] = "flat_probability_block"
    if "no_direction_signal" in frame:
        categories.loc[frame["no_direction_signal"].fillna(False).astype(bool)] = "no_direction_signal"
    return {str(key): int(value) for key, value in categories.value_counts(dropna=False).sort_index().items()}


def derive_policy_frame(
    ctx: BuildContext,
    metrics: Mapping[str, Any],
    wfa_manifest: Mapping[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not ctx.derive_predictions:
        add_missing_evidence(
            ctx,
            "prediction.locked_oos_policy_frame",
            "Fast dashboard mode skipped locked prediction-parquet derivation.",
            ["diagnosis", "trade lifecycle", "score diagnostics"],
            stage="research",
            current_research_blocker=False,
        )
        return pd.DataFrame(), pd.DataFrame()
    prediction_path = (
        metrics.get("prediction_path")
        or metrics.get("predictions_manifest_path")
        or wfa_manifest.get("prediction_path")
    )
    if not prediction_path:
        add_missing_evidence(ctx, "prediction.locked_oos_policy_frame", "No prediction path in dashboard inputs.", ["diagnosis"])
        return pd.DataFrame(), pd.DataFrame()
    path = ctx.resolve(str(prediction_path))
    if not path.exists():
        add_missing_evidence(ctx, "prediction.locked_oos_policy_frame", f"Prediction parquet missing: {prediction_path}", ["diagnosis"])
        return pd.DataFrame(), pd.DataFrame()
    try:
        predictions = pd.read_parquet(path)
        ctx.source_files_read.append(ctx.rel(path))
        repo_root = str(ctx.repo_root.resolve())
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from scripts.phase8_model_selection.evaluate_predictions import PolicyConfig, build_policy_frame

        policy_config = metrics.get("policy_config", {})
        if not isinstance(policy_config, Mapping):
            policy_config = {}
        policy = PolicyConfig(
            long_short_margin=float(policy_config.get("long_short_margin", 0.05)),
            min_fade_success=float(policy_config.get("min_fade_success", 0.5)),
            max_trend_danger=float(policy_config.get("max_trend_danger", 0.5)),
        )
        policy_frame, failures, warnings = build_policy_frame(
            predictions,
            ctx.resolve(str(metrics.get("costs_config") or "configs/costs.yaml")),
            policy,
        )
        for warning in warnings:
            if warning not in ctx.warnings:
                ctx.warnings.append(warning)
        if failures:
            add_missing_evidence(
                ctx,
                "prediction.locked_oos_policy_frame",
                "; ".join(failures),
                ["diagnosis", "trade lifecycle", "score diagnostics"],
            )
            return predictions, pd.DataFrame()
        return predictions, policy_frame
    except Exception as exc:
        add_missing_evidence(
            ctx,
            "prediction.locked_oos_policy_frame",
            f"Could not derive policy frame from locked predictions: {exc}",
            ["diagnosis", "trade lifecycle", "score diagnostics"],
        )
        return pd.DataFrame(), pd.DataFrame()


def lifecycle_metrics(policy_frame: pd.DataFrame) -> dict[str, Any]:
    if policy_frame.empty or "position" not in policy_frame:
        return {}
    sort_cols = [col for col in ("market", "fold_id", "timestamp") if col in policy_frame.columns]
    frame = policy_frame.sort_values(sort_cols).copy()
    group_cols = [col for col in ("market", "fold_id") if col in frame.columns]
    previous = frame.groupby(group_cols, dropna=False)["position"].shift(1).fillna(0)
    position = pd.to_numeric(frame["position"], errors="coerce").fillna(0)
    entries = position.ne(0) & previous.eq(0)
    exits = position.eq(0) & previous.ne(0)
    flips = position.ne(0) & previous.ne(0) & position.ne(previous)
    active = frame[position.ne(0)].copy()
    run_lengths: list[int] = []
    if not active.empty:
        changed = position.ne(previous)
        run_id = changed.groupby([frame[col] for col in group_cols], dropna=False).cumsum() if group_cols else changed.cumsum()
        for _, group in frame[position.ne(0)].groupby(run_id[position.ne(0)], dropna=False):
            run_lengths.append(int(len(group)))
    days = pd.to_datetime(frame["timestamp"], errors="coerce").dt.date.nunique() if "timestamp" in frame else None
    boundary_exposure = 0
    if "session_segment_id" in frame and group_cols:
        last_rows = frame.sort_values(sort_cols).groupby([*group_cols, "session_segment_id"], dropna=False).tail(1)
        boundary_exposure = int(pd.to_numeric(last_rows["position"], errors="coerce").fillna(0).ne(0).sum())
    trade_count = int(entries.sum() + flips.sum())
    return {
        "entries": int(entries.sum()),
        "exits": int(exits.sum()),
        "flips": int(flips.sum()),
        "lifecycle_trade_count": trade_count,
        "position_change_sum": safe_float(frame.get("position_change_abs", pd.Series(dtype=float)).sum()) or 0.0,
        "round_turn_estimate": (safe_float(frame.get("position_change_abs", pd.Series(dtype=float)).sum()) or 0.0) / 2.0,
        "average_holding_period_bars": float(pd.Series(run_lengths).mean()) if run_lengths else None,
        "median_holding_period_bars": float(pd.Series(run_lengths).median()) if run_lengths else None,
        "max_holding_period_bars": int(max(run_lengths)) if run_lengths else None,
        "trades_per_day": trade_count / days if days else None,
        "overnight_exposure_count": boundary_exposure,
    }


def derived_tables(policy_frame: pd.DataFrame) -> dict[str, list[list[Any]]]:
    if policy_frame.empty:
        return {}
    frame = policy_frame.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True).dt.tz_convert(None) if "timestamp" in frame else pd.NaT
    frame["date"] = frame["timestamp"].dt.date if "timestamp" in frame else None
    frame["month"] = frame["timestamp"].dt.to_period("M").astype(str) if "timestamp" in frame else None
    frame["hour"] = frame["timestamp"].dt.hour if "timestamp" in frame else None
    active = frame[pd.to_numeric(frame["position"], errors="coerce").fillna(0).ne(0)].copy()

    def grouped_rows(group_col: str, limit: int = 12) -> list[list[Any]]:
        if group_col not in frame:
            return []
        rows: list[list[Any]] = []
        for key, group in frame.groupby(group_col, dropna=False):
            rows.append(
                [
                    key,
                    int(group["trade_count"].sum()) if "trade_count" in group else None,
                    float(group["gross_dollars"].sum()) if "gross_dollars" in group else None,
                    float(group["cost_dollars"].sum()) if "cost_dollars" in group else None,
                    float(group["net_dollars"].sum()) if "net_dollars" in group else None,
                ]
            )
        return rows[:limit]

    side_rows: list[list[Any]] = []
    if not active.empty:
        for side, group in active.groupby("position", dropna=False):
            gross = group["gross_dollars"]
            net = group["net_dollars"]
            cost = float(group["cost_dollars"].sum())
            gross_sum = float(gross.sum())
            side_rows.append(
                [
                    "long" if int(side) == 1 else "short",
                    int(len(group)),
                    gross_sum,
                    cost,
                    float(net.sum()),
                    float(net.mean()) if len(group) else None,
                    float(net.gt(0.0).mean()) if len(group) else None,
                    cost / abs(gross_sum) if abs(gross_sum) > 0.0 else None,
                ]
            )

    score_rows: list[list[Any]] = []
    if not frame.empty and "direction_probability" in frame:
        scored = frame[frame["direction_probability"].notna()].copy()
        if len(scored) >= 10:
            scored["score_bucket"] = pd.qcut(
                pd.to_numeric(scored["direction_probability"], errors="coerce"),
                q=min(10, scored["direction_probability"].nunique()),
                duplicates="drop",
            )
            for bucket, group in scored.groupby("score_bucket", dropna=False, observed=False):
                active_group = group[group["trade_count"].eq(1)]
                score_rows.append(
                    [
                        str(bucket),
                        int(len(group)),
                        int(len(active_group)),
                        float(active_group["net_dollars"].mean()) if len(active_group) else None,
                        float(active_group["net_dollars"].gt(0.0).mean()) if len(active_group) else None,
                    ]
                )

    return {
        "side": side_rows,
        "fold": grouped_rows("fold_id", limit=60),
        "month": grouped_rows("month", limit=24),
        "hour": grouped_rows("hour", limit=24),
        "score": score_rows,
    }


def blocker_lift(policy_frame: pd.DataFrame) -> dict[str, Any]:
    if policy_frame.empty or "base_position" not in policy_frame:
        return {}
    frame = policy_frame.copy()
    frame["base_gross_dollars"] = frame["base_position"] * frame["price_move"] * frame["point_value"]
    frame["base_cost_dollars"] = frame["base_position"].ne(0).astype(float) * frame["round_turn_cost_dollars"]
    frame["base_net_dollars"] = frame["base_gross_dollars"] - frame["base_cost_dollars"]
    base_active = frame[frame["base_position"].ne(0)]
    blocked = frame[frame["base_position"].ne(0) & frame["position"].eq(0)]
    return {
        "blocked_rows": int(len(blocked)),
        "saved_loss": float(-blocked.loc[blocked["base_net_dollars"] < 0.0, "base_net_dollars"].sum()) if len(blocked) else None,
        "missed_profit": float(blocked.loc[blocked["base_net_dollars"] > 0.0, "base_net_dollars"].sum()) if len(blocked) else None,
        "true_block_rate": float(blocked["base_net_dollars"].le(0.0).mean()) if len(blocked) else None,
        "false_block_rate": float(blocked["base_net_dollars"].gt(0.0).mean()) if len(blocked) else None,
        "expectancy_before_blockers": float(base_active["base_net_dollars"].mean()) if len(base_active) else None,
        "expectancy_after_blockers": float(frame.loc[frame["trade_count"].eq(1), "net_dollars"].mean()) if int(frame["trade_count"].sum()) else None,
    }


def label_integrity(predictions: pd.DataFrame, policy_frame: pd.DataFrame) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if predictions.empty:
        return out
    out["prediction_rows"] = int(len(predictions))
    if "target_valid" in predictions:
        out["target_valid_rows"] = int(predictions["target_valid"].fillna(False).astype(bool).sum())
    if "causal_valid" in predictions:
        out["causal_valid_rows"] = int(predictions["causal_valid"].fillna(False).astype(bool).sum())
    returns = predictions[predictions.get("target_name", pd.Series(dtype=str)).eq("target_ret_15m")]
    if not returns.empty and "y_true" in returns:
        observed = pd.to_numeric(returns["y_true"], errors="coerce").dropna()
        out["realized_15m_move_mean"] = float(observed.mean()) if not observed.empty else None
        out["realized_15m_move_abs_median"] = float(observed.abs().median()) if not observed.empty else None
    if not policy_frame.empty and {"price_move", "point_value", "round_turn_cost_dollars"}.issubset(policy_frame.columns):
        future_abs_dollars = (policy_frame["price_move"] * policy_frame["point_value"]).abs()
        out["cost_clearable_future_move_pct"] = float(future_abs_dollars.gt(policy_frame["round_turn_cost_dollars"]).mean())
    return out


def build_metric_audit_markdown(ctx: BuildContext) -> str:
    lines = [
        "# Dashboard Metric Audit",
        "",
        "Generated from the dashboard metric contract. The dashboard is diagnostic only and does not alter model logic, WFA, labels, features, configs, or trading assumptions.",
        "",
        "| Metric | Source | Key | Formula | Aggregation | OOS-only | Use | Action | Reason |",
        "|---|---|---|---|---|---:|---|---|---|",
    ]
    for row in ctx.metric_contract.get("metrics", []):
        action = "keep"
        reason = row.get("interpretation", "")
        if row["name"] in {"active_signal_rows", "long_positioned_rows", "short_positioned_rows"}:
            action = "rename"
            reason = "Renamed from trade/long/short counts because source counts positioned rows, not lifecycle trades."
        elif "sharpe_like" in row["name"]:
            action = "demote"
            reason = "Sharpe-like is a sample-scaled row diagnostic, not daily or trade Sharpe."
        elif row["status"] == "MISSING":
            action = "add warning"
        use = []
        if row.get("promotion_metric"):
            use.append("promotion gate")
        if row.get("diagnostic_metric"):
            use.append("debugging")
        lines.append(
            "| {metric} | {source} | {key} | {formula} | {agg} | {oos} | {use} | {action} | {reason} |".format(
                metric=row.get("display_name"),
                source=row.get("source_file"),
                key=row.get("source_key"),
                formula=str(row.get("formula", "")).replace("|", "/"),
                agg=row.get("aggregation_level"),
                oos=row.get("oos_only"),
                use=", ".join(use) or "dashboard context",
                action=action,
                reason=str(reason).replace("|", "/"),
            )
        )
    lines.extend(["", "## Missing Evidence", ""])
    for item in ctx.missing_evidence:
        lines.append(
            f"- `{item['metric_id']}` ({item.get('stage')}, "
            f"current_research_blocker={item.get('current_research_blocker')}): "
            f"{item['reason']} Required for: {', '.join(item['required_for'])}."
        )
    return "\n".join(lines) + "\n"


def build_dashboard(ctx: BuildContext) -> dict[str, Any]:
    if not ctx.inventory_path.exists():
        raise FileNotFoundError(f"inventory missing: {ctx.inventory_path}")
    inventory = load_json(ctx.inventory_path)
    validate_inventory_sources(ctx, inventory)

    phase8_sources = chart_sources(inventory, "Locked Tier 1 costed OOS summary cards")
    phase8 = read_json_source(ctx, "reports/phase8/alpha_promotion_decision.json", required=ctx.strict)
    metrics = read_json_source(ctx, "reports/metrics/tier1_locked_baseline_20260616_metrics.json", required=ctx.strict)
    market_sources = chart_sources(inventory, "net/gross/cost by market")
    gate_sources = chart_sources(inventory, "promotion gate blockers")
    provenance_sources = chart_sources(inventory, "artifact provenance/readiness summary")
    wfa_manifest = read_json_source(ctx, "reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json", required=ctx.strict)
    model_selection = read_json_source(ctx, "reports/model_selection/model_selection_report.json", required=ctx.strict)
    feature_sources = chart_sources(inventory, "feature hypothesis statuses")
    target_sources = chart_sources(inventory, "target hypothesis statuses")
    feature_registry = read_json_source(ctx, "manifests/feature_hypotheses/registry.json", required=ctx.strict)
    target_registry = read_json_source(ctx, "manifests/target_hypotheses/registry.json", required=ctx.strict)
    phase9_sources = chart_sources(inventory, "Phase 9 stopped/rejected branch summary")
    cost_clear_text = read_text_source(ctx, "reports/pipeline_audit/phase9_cost_clearability_harness_audit_20260617.md", required=ctx.strict)
    balanced_text = read_text_source(ctx, "reports/pipeline_audit/phase9_market_balanced_cost_clearability_harness_audit_20260617.md", required=ctx.strict)
    liquidity = read_json_source(ctx, "reports/pipeline_audit/liquidity_cost_state_features_v1_smoke_20260617T045008Z.json", required=ctx.strict)
    directional = read_json_source(ctx, "reports/pipeline_audit/directional_path_quality_target_v1_smoke_20260617T095912Z.json", required=ctx.strict)

    if ctx.errors:
        return {"inventory": inventory, "html": ""}

    costed = phase8.get("costed_oos", {})
    if not isinstance(costed, Mapping):
        ctx.warnings.append("phase8 costed_oos missing or invalid")
        costed = {}
    markets = phase8.get("markets", [])
    if not isinstance(markets, list):
        ctx.warnings.append("phase8 markets missing or invalid")
        markets = []
    blockers = phase8.get("blockers", [])
    if not isinstance(blockers, list):
        ctx.warnings.append("phase8 blockers missing or invalid")
        blockers = []

    performance_chart = write_bar_chart(
        ctx,
        "locked_tier1_cost_summary.png",
        ["gross", "costs", "net"],
        [
            safe_float(costed.get("gross_return_dollars")) or 0.0,
            -(safe_float(costed.get("cost_dollars")) or 0.0),
            safe_float(costed.get("net_return_dollars")) or 0.0,
        ],
        title="Locked Tier 1 Costed OOS Summary",
        ylabel="Dollars",
        source_files=phase8_sources,
    )

    market_frame = pd.DataFrame(markets)
    market_chart = None
    if not market_frame.empty and {"market", "net_return_dollars"}.issubset(market_frame.columns):
        market_chart = write_bar_chart(
            ctx,
            "net_by_market.png",
            market_frame["market"].astype(str).tolist(),
            pd.to_numeric(market_frame["net_return_dollars"], errors="coerce").fillna(0.0).tolist(),
            title="Net Return By Market",
            ylabel="Dollars",
            source_files=market_sources,
        )
    else:
        ctx.warnings.append("market net chart skipped: phase8 markets are missing required fields")

    cost_component_chart = write_bar_chart(
        ctx,
        "cost_components.png",
        ["slippage", "commission"],
        [
            safe_float(costed.get("slippage_cost_dollars")) or 0.0,
            safe_float(costed.get("commission_cost_dollars")) or 0.0,
        ],
        title="Cost Components",
        ylabel="Dollars",
        source_files=phase8_sources,
    )
    trade_activity_chart = write_bar_chart(
        ctx,
        "trade_activity.png",
        ["trades", "long rows", "short rows"],
        [
            safe_float(costed.get("trade_count")) or 0.0,
            safe_float(costed.get("long_count")) or 0.0,
            safe_float(costed.get("short_count")) or 0.0,
        ],
        title="Trade Activity / Directional Balance",
        ylabel="Count",
        source_files=phase8_sources,
    )
    policy_blocker_chart = write_bar_chart(
        ctx,
        "policy_blocker_counts.png",
        ["fade", "flat prob", "trend danger", "no direction"],
        [
            safe_float(costed.get("blocked_by_fade_filter")) or 0.0,
            safe_float(costed.get("blocked_by_flat_probability")) or 0.0,
            safe_float(costed.get("blocked_by_trend_danger")) or 0.0,
            safe_float(costed.get("no_direction_signal")) or 0.0,
        ],
        title="Policy Blocker Counts",
        ylabel="Rows",
        source_files=phase8_sources,
    )

    blocker_categories = {
        "net_return": 0,
        "sharpe": 0,
        "cost_drag": 0,
        "market": 0,
        "fold": 0,
        "other": 0,
    }
    for blocker in blockers:
        text = str(blocker)
        if "net_return" in text and "folds" not in text and "markets" not in text:
            blocker_categories["net_return"] += 1
        elif "sharpe" in text.lower():
            blocker_categories["sharpe"] += 1
        elif "cost_drag" in text:
            blocker_categories["cost_drag"] += 1
        elif "markets" in text:
            blocker_categories["market"] += 1
        elif "folds" in text:
            blocker_categories["fold"] += 1
        else:
            blocker_categories["other"] += 1
    gate_chart = write_bar_chart(
        ctx,
        "promotion_gate_blockers.png",
        list(blocker_categories.keys()),
        list(blocker_categories.values()),
        title="Promotion Gate Blockers",
        ylabel="Count",
        source_files=gate_sources,
    )

    readiness = {
        "artifact_evidence_ready": bool(wfa_manifest.get("artifact_evidence_ready")),
        "manifest_failures_zero": int(wfa_manifest.get("failure_count", 1) or 0) == 0,
        "metrics_failures_zero": int(metrics.get("failure_count", 1) or 0) == 0,
        "model_selection_failures_zero": int(model_selection.get("failure_count", 1) or 0) == 0,
        "promotion_allowed": bool(model_selection.get("model_promotion_allowed")),
        "final_holdout_excluded": bool(model_selection.get("final_holdout_excluded_from_selection")),
    }
    provenance_chart = write_bar_chart(
        ctx,
        "artifact_readiness.png",
        list(readiness.keys()),
        [1.0 if value else 0.0 for value in readiness.values()],
        title="Artifact Provenance / Readiness",
        ylabel="True=1 / False=0",
        source_files=provenance_sources,
    )

    feature_rows = [
        [
            row.get("hypothesis_id"),
            row.get("status"),
            row.get("wfa_allowed"),
            row.get("feature_family"),
        ]
        for row in feature_registry.get("hypotheses", [])
        if isinstance(row, Mapping)
    ]
    target_rows = [
        [
            row.get("target_hypothesis_id"),
            row.get("status"),
            row.get("wfa_allowed"),
            row.get("target_family"),
        ]
        for row in target_registry.get("hypotheses", [])
        if isinstance(row, Mapping)
    ]
    status_counts: dict[str, int] = {}
    for row in feature_rows + target_rows:
        status = str(row[1])
        status_counts[status] = status_counts.get(status, 0) + 1
    hypothesis_chart = write_bar_chart(
        ctx,
        "hypothesis_statuses.png",
        list(status_counts.keys()),
        list(status_counts.values()),
        title="Feature / Target Hypothesis Statuses",
        ylabel="Count",
        source_files=list(dict.fromkeys([*feature_sources, *target_sources])),
    )

    def md_decision(text: str) -> str:
        match = re.search(r"Decision:\s*`?([A-Z0-9_]+)`?", text)
        return match.group(1) if match else "MISSING"

    phase9_rows = [
        ["cost_clearability", md_decision(cost_clear_text), "Phase 9 audit markdown"],
        ["market_balanced_cost_clearability", md_decision(balanced_text), "Phase 9 audit markdown"],
        ["liquidity_cost_state_features_v1", liquidity.get("decision"), "Smoke JSON"],
        ["directional_path_quality_target_v1", directional.get("decision"), "Smoke JSON"],
    ]
    phase9_status_counts: dict[str, int] = {}
    for row in phase9_rows:
        decision = str(row[1])
        phase9_status_counts[decision] = phase9_status_counts.get(decision, 0) + 1
    phase9_chart = write_bar_chart(
        ctx,
        "phase9_decisions.png",
        list(phase9_status_counts.keys()),
        list(phase9_status_counts.values()),
        title="Phase 9 Stopped / Rejected Decisions",
        ylabel="Count",
        source_files=phase9_sources,
    )

    skipped = skipped_charts_from_inventory(inventory)
    ctx.charts_skipped.extend(skipped)

    ctx.tables_generated.extend(
        [
            {"name": "Executive summary", "source_files": ["reports/report_inventory.json", *phase8_sources]},
            {"name": "Alpha research scorecard", "source_files": [*phase8_sources, *provenance_sources]},
            {"name": "Costed OOS metrics", "source_files": phase8_sources},
            {"name": "Market metrics", "source_files": market_sources},
            {"name": "Research next-use guide", "source_files": [*phase8_sources, *gate_sources, *phase9_sources]},
            {"name": "Unavailable metrics", "source_files": ["reports/report_inventory.json"]},
            {"name": "Promotion blockers", "source_files": gate_sources},
            {"name": "Provenance/readiness", "source_files": provenance_sources},
            {"name": "Feature hypotheses", "source_files": feature_sources},
            {"name": "Target hypotheses", "source_files": target_sources},
            {"name": "Phase 9 decisions", "source_files": phase9_sources},
            {"name": "Skipped charts", "source_files": ["reports/report_inventory.json"]},
        ]
    )

    net_value = safe_float(costed.get("net_return_dollars"))
    gross_value = safe_float(costed.get("gross_return_dollars"))
    cost_drag_value = safe_float(costed.get("cost_drag_to_abs_gross"))
    net_sharpe_value = safe_float(costed.get("net_sharpe_like"))
    drawdown_value = safe_float(costed.get("max_drawdown_dollars"))
    win_rate_value = safe_float(costed.get("win_rate_net_positive"))
    trade_count_value = safe_float(costed.get("trade_count"))
    turnover_value = safe_float(costed.get("turnover_per_bar"))
    promotion_allowed = bool(model_selection.get("model_promotion_allowed"))
    artifacts_ready = all(readiness.values())

    alpha_score_rows = [
        [
            "Net after costs",
            net_value,
            "PASS" if net_value is not None and net_value > 0 else "FAIL",
            "Primary costed alpha check. Negative net means the branch should not advance.",
        ],
        [
            "Gross before costs",
            gross_value,
            "PASS" if gross_value is not None and gross_value > 0 else "FAIL",
            "Separates signal failure from cost/turnover failure.",
        ],
        [
            "Cost drag / abs gross",
            cost_drag_value,
            "PASS" if cost_drag_value is not None and cost_drag_value < 1.0 else "FAIL",
            "Shows whether costs consume the estimated edge before any execution upgrade.",
        ],
        [
            "Net Sharpe-like",
            net_sharpe_value,
            "PASS" if net_sharpe_value is not None and net_sharpe_value > 0 else "FAIL",
            "Checks whether average costed outcomes are stable enough to study further.",
        ],
        [
            "Max drawdown dollars",
            drawdown_value,
            "WATCH",
            "Risk screen for path severity. Needs an equity curve before final interpretation.",
        ],
        [
            "Net-positive win rate",
            win_rate_value,
            "PASS" if win_rate_value is not None and win_rate_value > 0.5 else "FAIL",
            "Quick read on whether selected trades clear costs more often than not.",
        ],
        [
            "Trade count",
            trade_count_value,
            "WATCH",
            "Power check. Too few trades makes apparent edge fragile; too many can imply churn.",
        ],
        [
            "Turnover per bar",
            turnover_value,
            "WATCH",
            "Execution pressure check. Use with cost drag before changing policy aggressiveness.",
        ],
        [
            "Promotion allowed",
            promotion_allowed,
            "PASS" if promotion_allowed else "FAIL",
            "Hard gate from model-selection evidence, not a dashboard opinion.",
        ],
        [
            "Artifact readiness",
            artifacts_ready,
            "PASS" if artifacts_ready else "FAIL",
            "Provenance gate. Do not use metrics if manifests/reports are not internally ready.",
        ],
    ]
    research_use_rows = [
        [
            "Net negative after costs",
            "Stop model/policy tuning on this run; research should move to target/feature hypotheses.",
        ],
        [
            "Gross negative before costs",
            "Prioritize signal/target construction before execution tweaks.",
        ],
        [
            "Costs exceed gross edge",
            "Study lower-turnover labels, event selection, or execution-cost state before WFA.",
        ],
        [
            "Market/fold/time concentration",
            "Require separate concentration diagnostics before treating a pocket as reusable alpha.",
        ],
        [
            "Rejected Phase 9 branch",
            "Do not rescue by nearby retuning; register a materially different hypothesis first.",
        ],
        [
            "Unavailable metric listed below",
            "Add source-of-truth diagnostics before asking the dashboard to plot it.",
        ],
    ]
    behavior_rows = [
        ["Long rows", costed.get("long_count")],
        ["Short rows", costed.get("short_count")],
        ["Flat rows", costed.get("flat_count")],
        ["Average gross dollars per row", costed.get("avg_gross_dollars_per_row")],
        ["Average net dollars per row", costed.get("avg_net_dollars_per_row")],
        ["Gross Sharpe-like", costed.get("gross_sharpe_like")],
        ["Net Sharpe-like", costed.get("net_sharpe_like")],
        ["Max drawdown dollars", costed.get("max_drawdown_dollars")],
        ["Win rate net positive", costed.get("win_rate_net_positive")],
        ["Turnover per bar", costed.get("turnover_per_bar")],
        ["Round turns per bar", costed.get("round_turns_per_bar")],
        ["Absolute position-change sum", costed.get("position_change_abs_sum")],
        ["Slippage cost dollars", costed.get("slippage_cost_dollars")],
        ["Commission cost dollars", costed.get("commission_cost_dollars")],
        ["Blocked by fade filter", costed.get("blocked_by_fade_filter")],
        ["Blocked by flat probability", costed.get("blocked_by_flat_probability")],
        ["Blocked by trend danger", costed.get("blocked_by_trend_danger")],
        ["No direction signal", costed.get("no_direction_signal")],
    ]
    summary_rows = [
        ["Locked run", phase8.get("run") or wfa_manifest.get("run")],
        ["Promoted", phase8.get("promoted")],
        ["Research alpha ready", metrics.get("research_alpha_ready")],
        ["Model promotion allowed", metrics.get("model_promotion_allowed")],
        ["Selection status", model_selection.get("selection_status")],
        ["Feasibility verdict", inventory.get("feasibility_verdict")],
    ]
    cost_rows = [
        ["Rows", costed.get("row_count")],
        ["Trades", costed.get("trade_count")],
        ["Gross dollars", costed.get("gross_return_dollars")],
        ["Costs", costed.get("cost_dollars")],
        ["Net dollars", costed.get("net_return_dollars")],
        ["Net Sharpe-like", costed.get("net_sharpe_like")],
        ["Cost drag to abs gross", costed.get("cost_drag_to_abs_gross")],
    ]
    market_rows = [
        [
            row.get("market"),
            row.get("trade_count"),
            row.get("gross_return_dollars"),
            row.get("cost_dollars"),
            row.get("net_return_dollars"),
            row.get("cost_drag_to_abs_gross"),
        ]
        for row in markets
        if isinstance(row, Mapping)
    ]
    blocker_rows = [[idx + 1, blocker] for idx, blocker in enumerate(blockers)]
    provenance_rows = [[key, value] for key, value in readiness.items()]
    skipped_rows = [[row["name"], row["reason"]] for row in skipped]

    html_doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>Intraday Futures Research Dashboard</title>",
            "<style>",
            "body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1c2430}",
            "main{max-width:1180px;margin:0 auto;padding:24px}",
            "section{background:white;border:1px solid #d9dee7;border-radius:6px;margin:0 0 18px;padding:18px}",
            "h1,h2,h3{margin-top:0} .source{font-size:12px;color:#596575;margin:6px 0 10px}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}",
            ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:10px 0 16px}",
            ".metric-card{border:1px solid #dfe4ec;border-radius:6px;padding:10px;background:#fbfcfe}",
            ".metric-label{font-size:12px;color:#596575}.metric-value{font-size:22px;font-weight:700;margin:4px 0}",
            ".pill{display:inline-block;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700}.ok{background:#e6f4ea;color:#17663a}.fail{background:#fde8e8;color:#9b1c1c}.watch{background:#eef2f7;color:#42526b}",
            ".callout{background:#eef5ff;border-left:4px solid #2f6fbb;padding:10px 12px;margin:10px 0 14px}.callout p{margin:6px 0 0}",
            ".explain{font-size:13px;color:#42526b}",
            ".chart img{max-width:100%;border:1px solid #e2e6ee;background:white}",
            "table{border-collapse:collapse;width:100%;font-size:13px} th,td{border:1px solid #dfe4ec;padding:6px;text-align:left;vertical-align:top}",
            "th{background:#eef2f7}.warn{background:#fff7e6;border-color:#f0cf8a}.bad{color:#9b1c1c;font-weight:600}",
            "</style>",
            "</head>",
            "<body><main>",
            "<h1>Intraday Futures Research Dashboard</h1>",
            "<p>This static dashboard is diagnostic only. It does not change the model, labels, features, WFA, data generation, configs, or trading assumptions.</p>",
            "<section><h2>Executive Summary</h2>"
            + callout(
                "Read this top down",
                "Start with alpha scorecard, then costs, then market/policy behavior, then gates and provenance. A chart is research-useful only if its source file is shown and the matching table has the exact values.",
            )
            + html_table(["Item", "Value"], summary_rows, ["reports/report_inventory.json", *phase8_sources])
            + "</section>",
            "<section><h2>Alpha Research Scorecard</h2>"
            + callout(
                "Decision use",
                "These are research diagnostics from locked reports. They help decide whether to stop, inspect a failure mode, or design a new pre-registered hypothesis; they are not permission to tune the failed run.",
            )
            + metric_cards(["Metric", "Value", "Status", "Use"], alpha_score_rows, [*phase8_sources, *provenance_sources])
            + "</section>",
            "<section><h2>Performance / Costs</h2><div class=\"grid\">"
            + chart_block(
                "Locked Tier 1 Costed OOS Summary",
                performance_chart,
                phase8_sources,
                "Gross, costs, and net show whether the signal exists before costs and whether costs destroy it after execution assumptions.",
            )
            + chart_block(
                "Net Return By Market",
                market_chart,
                market_sources,
                "Market net return shows whether one contract is subsidizing the rest or every market fails independently.",
            )
            + chart_block(
                "Cost Components",
                cost_component_chart,
                phase8_sources,
                "Slippage versus commission separates execution realism problems from fee assumptions.",
            )
            + "</div>"
            + html_table(["Metric", "Value"], cost_rows, phase8_sources)
            + html_table(["Market", "Trades", "Gross", "Costs", "Net", "Cost drag"], market_rows, market_sources)
            + "</section>",
            "<section><h2>Trading Behavior / Policy Effects</h2><div class=\"grid\">"
            + chart_block(
                "Trade Activity / Directional Balance",
                trade_activity_chart,
                phase8_sources,
                "Trade count plus long/short rows highlights directional imbalance and whether the policy mostly acts on one side.",
            )
            + chart_block(
                "Policy Blocker Counts",
                policy_blocker_chart,
                phase8_sources,
                "Policy blockers show whether most rows are filtered by flat probability, trend danger, fade checks, or lack of signal.",
            )
            + "</div>"
            + html_table(["Metric", "Value"], behavior_rows, phase8_sources)
            + "</section>",
            "<section><h2>Promotion Gates</h2>"
            + chart_block(
                "Promotion Gate Blockers",
                gate_chart,
                gate_sources,
                "Blocker categories summarize why the locked run cannot advance. The table below keeps exact blocker text.",
            )
            + html_table(["#", "Blocker"], blocker_rows, gate_sources)
            + "</section>",
            "<section><h2>Provenance / Readiness</h2>"
            + chart_block(
                "Artifact Provenance / Readiness",
                provenance_chart,
                provenance_sources,
                "Readiness checks prevent stale, partial, or final-holdout-contaminated artifacts from being treated as evidence.",
            )
            + html_table(["Check", "Value"], provenance_rows, provenance_sources)
            + "</section>",
            "<section><h2>Hypotheses</h2>"
            + chart_block(
                "Feature / Target Hypothesis Statuses",
                hypothesis_chart,
                [*feature_sources, *target_sources],
                "Registry statuses show which ideas are candidates, frozen, or rejected before another WFA is allowed.",
            )
            + "<h3>Feature Hypotheses</h3>"
            + html_table(["ID", "Status", "WFA allowed", "Family"], feature_rows, feature_sources)
            + "<h3>Target Hypotheses</h3>"
            + html_table(["ID", "Status", "WFA allowed", "Family"], target_rows, target_sources)
            + "</section>",
            "<section><h2>Phase 9 Decisions</h2>"
            + chart_block(
                "Phase 9 Stopped / Rejected Decisions",
                phase9_chart,
                phase9_sources,
                "Stopped or rejected branches should become research constraints, not near-neighbor tuning inputs.",
            )
            + html_table(["Branch", "Decision", "Evidence type"], phase9_rows, phase9_sources)
            + "</section>",
            "<section><h2>How To Use This For Research</h2>"
            + html_table(["Observed condition", "Research/code response"], research_use_rows, [*phase8_sources, *gate_sources, *phase9_sources])
            + "</section>",
            "<section><h2>Skipped Charts</h2>"
            + html_table(["Chart", "Reason"], skipped_rows, ["reports/report_inventory.json"])
            + "<h3>Unavailable But Important Metrics</h3>"
            + html_table(["Metric", "Current status", "Why it matters"], MISSING_METRIC_ROWS, ["reports/report_inventory.json"])
            + "</section>",
            "<section class=\"warn\"><h2>Warnings</h2><ul>"
            + "".join(f"<li>{html.escape(warning)}</li>" for warning in ctx.warnings)
            + "</ul></section>",
            "</main></body></html>",
        ]
    )
    return {"inventory": inventory, "html": html_doc}


def build_dashboard_v2(ctx: BuildContext) -> dict[str, Any]:
    if not ctx.inventory_path.exists():
        raise FileNotFoundError(f"inventory missing: {ctx.inventory_path}")
    inventory = load_json(ctx.inventory_path)
    validate_inventory_sources(ctx, inventory)

    phase8_sources = chart_sources(inventory, "Locked Tier 1 costed OOS summary cards")
    market_sources = chart_sources(inventory, "net/gross/cost by market")
    gate_sources = chart_sources(inventory, "promotion gate blockers")
    provenance_sources = chart_sources(inventory, "artifact provenance/readiness summary")
    feature_sources = chart_sources(inventory, "feature hypothesis statuses")
    target_sources = chart_sources(inventory, "target hypothesis statuses")
    phase9_sources = chart_sources(inventory, "Phase 9 stopped/rejected branch summary")

    phase8 = read_json_source(ctx, "reports/phase8/alpha_promotion_decision.json", required=ctx.strict)
    metrics = read_json_source(ctx, "reports/metrics/tier1_locked_baseline_20260616_metrics.json", required=ctx.strict)
    wfa_manifest = read_json_source(ctx, "reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json", required=ctx.strict)
    model_selection = read_json_source(ctx, "reports/model_selection/model_selection_report.json", required=ctx.strict)
    feature_registry = read_json_source(ctx, "manifests/feature_hypotheses/registry.json", required=ctx.strict)
    target_registry = read_json_source(ctx, "manifests/target_hypotheses/registry.json", required=ctx.strict)
    cost_clear_text = read_text_source(ctx, "reports/pipeline_audit/phase9_cost_clearability_harness_audit_20260617.md", required=ctx.strict)
    balanced_text = read_text_source(ctx, "reports/pipeline_audit/phase9_market_balanced_cost_clearability_harness_audit_20260617.md", required=ctx.strict)
    liquidity = read_json_source(ctx, "reports/pipeline_audit/liquidity_cost_state_features_v1_smoke_20260617T045008Z.json", required=ctx.strict)
    directional = read_json_source(ctx, "reports/pipeline_audit/directional_path_quality_target_v1_smoke_20260617T095912Z.json", required=ctx.strict)

    run = str(phase8.get("run") or wfa_manifest.get("run") or metrics.get("run") or "unknown")
    ctx.metric_contract = init_contract(run)
    ctx.metric_contract["source_files"] = sorted(set(ctx.source_files_read))

    if ctx.errors:
        return {"inventory": inventory, "html": ""}

    costed = phase8.get("costed_oos", {})
    if not isinstance(costed, Mapping):
        ctx.warnings.append("phase8 costed_oos missing or invalid")
        costed = {}
    markets = phase8.get("markets", [])
    if not isinstance(markets, list):
        ctx.warnings.append("phase8 markets missing or invalid")
        markets = []
    folds = phase8.get("folds", [])
    if not isinstance(folds, list):
        folds = []
    blockers = phase8.get("blockers", [])
    if not isinstance(blockers, list):
        blockers = []

    predictions, policy_frame = derive_policy_frame(ctx, metrics, wfa_manifest)
    lifecycle = lifecycle_metrics(policy_frame)
    derived = derived_tables(policy_frame)
    lift = blocker_lift(policy_frame)
    label_stats = label_integrity(predictions, policy_frame)

    gross = safe_float(costed.get("gross_return_dollars"))
    total_costs = safe_float(costed.get("cost_dollars"))
    net = safe_float(costed.get("net_return_dollars"))
    slippage = safe_float(costed.get("slippage_cost_dollars"))
    commission = safe_float(costed.get("commission_cost_dollars"))
    active_rows = safe_float(costed.get("trade_count"))
    long_rows = safe_float(costed.get("long_count"))
    short_rows = safe_float(costed.get("short_count"))
    row_count = safe_float(costed.get("row_count"))
    cost_drag = safe_float(costed.get("cost_drag_to_abs_gross"))
    breakeven_cost_multiple = abs(gross) / total_costs if gross is not None and total_costs not in {None, 0.0} else None
    active_net_expectancy = net / active_rows if net is not None and active_rows else None
    active_gross_expectancy = gross / active_rows if gross is not None and active_rows else None
    lifecycle_count = safe_float(lifecycle.get("lifecycle_trade_count"))
    lifecycle_net_expectancy = net / lifecycle_count if net is not None and lifecycle_count else None
    lifecycle_gross_expectancy = gross / lifecycle_count if gross is not None and lifecycle_count else None

    daily_net = pd.Series(dtype=float)
    daily_gross = pd.Series(dtype=float)
    daily_cost = pd.Series(dtype=float)
    month_net = pd.Series(dtype=float)
    if not policy_frame.empty and "timestamp" in policy_frame:
        tmp = policy_frame.copy()
        tmp["timestamp"] = pd.to_datetime(tmp["timestamp"], errors="coerce", utc=True).dt.tz_convert(None)
        tmp["date"] = tmp["timestamp"].dt.date
        tmp["month"] = tmp["timestamp"].dt.to_period("M").astype(str)
        daily = tmp.groupby("date", dropna=False).agg(
            gross=("gross_dollars", "sum"),
            costs=("cost_dollars", "sum"),
            net=("net_dollars", "sum"),
        )
        daily_net = daily["net"]
        daily_gross = daily["gross"]
        daily_cost = daily["costs"]
        month_net = tmp.groupby("month", dropna=False)["net_dollars"].sum()

    daily_sharpe = sharpe(daily_net, periods_per_year=252)
    daily_sortino = sortino(daily_net, periods_per_year=252)
    daily_mdd = max_drawdown(daily_net)
    annualized_daily_net = float(daily_net.mean() * 252) if not daily_net.empty else None
    calmar = annualized_daily_net / abs(daily_mdd) if annualized_daily_net is not None and daily_mdd not in {None, 0.0} else None
    net_positive_days_pct = float(daily_net.gt(0.0).mean()) if not daily_net.empty else None
    net_positive_months_pct = float(month_net.gt(0.0).mean()) if not month_net.empty else None
    fold_net = pd.Series([safe_float(row.get("net_return_dollars")) for row in folds], dtype="float64").dropna()
    market_net = pd.Series([safe_float(row.get("net_return_dollars")) for row in markets if isinstance(row, Mapping)], dtype="float64").dropna()
    net_positive_folds_pct = float(fold_net.gt(0.0).mean()) if not fold_net.empty else None
    net_positive_markets_pct = float(market_net.gt(0.0).mean()) if not market_net.empty else None
    worst_day_net = float(daily_net.min()) if not daily_net.empty else None
    worst_fold_net = float(fold_net.min()) if not fold_net.empty else None
    worst_market_net = float(market_net.min()) if not market_net.empty else None

    active_signal_net = policy_frame.loc[policy_frame["trade_count"].eq(1), "net_dollars"] if not policy_frame.empty and "trade_count" in policy_frame else pd.Series(dtype=float)
    active_signal_gross = policy_frame.loc[policy_frame["trade_count"].eq(1), "gross_dollars"] if not policy_frame.empty and "trade_count" in policy_frame else pd.Series(dtype=float)
    gross_pf = profit_factor(active_signal_gross)
    net_pf = profit_factor(active_signal_net)
    avg_win, avg_loss, payoff = average_win_loss(active_signal_net)

    def add(
        metric_id: str,
        name: str,
        display_name: str,
        section: str,
        value: Any,
        definition: str,
        formula: str,
        source_file: str,
        source_key: str,
        aggregation: str,
        *,
        promotion: bool = False,
        diagnostic: bool = True,
        required: bool = False,
        pass_threshold: str | None = None,
        warning_threshold: str | None = None,
        interpretation: str = "",
        failure_modes: Sequence[str] = (),
        next_action: str = "",
        display: bool = True,
        leakage_safe: bool = True,
    ) -> dict[str, Any]:
        return add_metric(
            ctx,
            metric_id=metric_id,
            name=name,
            display_name=display_name,
            dashboard_section=section,
            value=value,
            definition=definition,
            formula=formula,
            source_file=source_file,
            source_key=source_key,
            aggregation_level=aggregation,
            oos_only=True,
            causal_leakage_safe=leakage_safe,
            promotion_metric=promotion,
            diagnostic_metric=diagnostic,
            required=required,
            pass_threshold=pass_threshold,
            warning_threshold=warning_threshold,
            interpretation=interpretation,
            failure_modes=failure_modes,
            recommended_next_action_when_bad=next_action,
            display=display,
        )

    add("portfolio.gross_pnl", "gross_pnl", "Gross PnL", "Alpha evidence", gross, "Locked OOS gross dollars before costs.", "sum(gross_dollars)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.gross_return_dollars", "portfolio", promotion=True, required=True, pass_threshold="> 0", interpretation="Gross alpha must be positive before cost work matters.", failure_modes=["no predictive signal", "wrong target direction"], next_action="Do not tune costs; gross is negative.")
    add("portfolio.total_costs", "total_costs", "Total costs", "Risk/cost realism", total_costs, "Estimated round-turn costs on positioned OOS rows.", "sum(cost_dollars)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.cost_dollars", "portfolio", promotion=True, required=True, interpretation="Costs must be explained before trusting net.", failure_modes=["overtrading", "cost model dominates signal"], next_action="Inspect turnover and active signal density.")
    add("portfolio.net_pnl", "net_pnl", "Net PnL", "Alpha evidence", net, "Locked OOS gross dollars minus total estimated costs.", "sum(gross_dollars) - sum(cost_dollars)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.net_return_dollars", "portfolio", promotion=True, required=True, pass_threshold="> 0", interpretation="Primary proof-of-alpha metric after costs.", failure_modes=["negative gross", "cost drag", "overtrading"], next_action="Do not promote or tune thresholds; diagnose gross and costs first.")
    add("portfolio.commission", "commission", "Commission", "Risk/cost realism", commission, "Commission component of total estimated cost.", "sum(commission_cost_dollars)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.commission_cost_dollars", "portfolio", interpretation="Separates fees from slippage assumptions.")
    add("portfolio.slippage", "slippage", "Slippage", "Risk/cost realism", slippage, "Slippage component of total estimated cost.", "sum(slippage_cost_dollars)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.slippage_cost_dollars", "portfolio", interpretation="Highlights execution-cost sensitivity.")
    add("portfolio.cost_drag_over_abs_gross", "cost_drag_over_abs_gross", "Cost drag / abs gross", "Risk/cost realism", cost_drag, "Total costs divided by absolute gross dollars.", "sum(costs) / abs(sum(gross))", "reports/phase8/alpha_promotion_decision.json", "costed_oos.cost_drag_to_abs_gross", "portfolio", promotion=True, required=True, pass_threshold="< 1", interpretation="Costs should not exceed gross edge.", failure_modes=["churn", "too-small target"], next_action="Study lower-turnover target or event selection.")
    add("portfolio.breakeven_cost_multiple", "breakeven_cost_multiple", "Breakeven cost multiple", "Risk/cost realism", breakeven_cost_multiple, "Absolute gross dollars divided by total estimated costs.", "abs(gross_pnl) / total_costs", "derived", "costed_oos.gross_return_dollars,costed_oos.cost_dollars", "portfolio", pass_threshold="> 0", interpretation="Values below 1 mean gross edge cannot clear current costs.")
    add("portfolio.active_signal_rows", "active_signal_rows", "Active signal rows", "Alpha evidence", active_rows, "Rows where deterministic policy position is nonzero; not lifecycle trades.", "sum(position != 0)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.trade_count", "active signal", promotion=True, required=True, interpretation="Sample-size and churn context; this is not true trade count.", failure_modes=["underpowered", "churn"], next_action="If too low, mark inconclusive; if too high with cost drag, reduce turnover.")
    add("portfolio.long_positioned_rows", "long_positioned_rows", "Long positioned rows", "Signal quality", long_rows, "Rows where policy position is long.", "sum(position == 1)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.long_count", "active signal", interpretation="Directional participation on long side.")
    add("portfolio.short_positioned_rows", "short_positioned_rows", "Short positioned rows", "Signal quality", short_rows, "Rows where policy position is short.", "sum(position == -1)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.short_count", "active signal", interpretation="Directional participation on short side.")
    add("portfolio.flat_rows", "flat_rows", "Flat rows", "Signal quality", costed.get("flat_count"), "Rows where policy is flat.", "sum(position == 0)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.flat_count", "row", display=False)
    add("portfolio.active_signal_net_win_rate", "active_signal_net_win_rate", "Active-signal net win rate", "Signal quality", costed.get("win_rate_net_positive"), "Share of positioned rows with positive net dollars.", "mean(net_dollars > 0 for position != 0)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.win_rate_net_positive", "active signal", pass_threshold="> 0", interpretation="Row-level hit rate after costs; not lifecycle trade win rate.")
    add("portfolio.gross_expectancy_per_active_signal", "gross_expectancy_per_active_signal", "Gross expectancy / active signal", "Alpha evidence", active_gross_expectancy, "Gross dollars divided by active signal rows.", "gross_pnl / active_signal_rows", "derived", "costed_oos.gross_return_dollars,costed_oos.trade_count", "active signal", pass_threshold="> 0", interpretation="Undiluted row-level gross expectancy.")
    add("portfolio.net_expectancy_per_active_signal", "net_expectancy_per_active_signal", "Net expectancy / active signal", "Alpha evidence", active_net_expectancy, "Net dollars divided by active signal rows.", "net_pnl / active_signal_rows", "derived", "costed_oos.net_return_dollars,costed_oos.trade_count", "active signal", pass_threshold="> 0", interpretation="Undiluted row-level net expectancy.")
    add("portfolio.gross_expectancy_per_trade", "gross_expectancy_per_trade", "Gross expectancy / lifecycle trade", "Trade lifecycle", lifecycle_gross_expectancy, "Gross dollars divided by reconstructed entries plus flips.", "gross_pnl / lifecycle_trade_count", "derived", "policy_frame.lifecycle_trade_count", "trade", pass_threshold="> 0", interpretation="Lifecycle estimate only; current costs are still row-based.")
    add("portfolio.net_expectancy_per_trade", "net_expectancy_per_trade", "Net expectancy / lifecycle trade", "Trade lifecycle", lifecycle_net_expectancy, "Net dollars divided by reconstructed entries plus flips.", "net_pnl / lifecycle_trade_count", "derived", "policy_frame.lifecycle_trade_count", "trade", pass_threshold="> 0", interpretation="Lifecycle estimate only; current costs are still row-based.")
    add("portfolio.daily_expectancy", "daily_expectancy", "Daily expectancy", "Alpha evidence", float(daily_net.mean()) if not daily_net.empty else None, "Mean daily net dollars.", "mean(daily net)", "derived", "policy_frame.timestamp,net_dollars", "day", pass_threshold="> 0", interpretation="Daily OOS expectancy.")
    add("portfolio.daily_sharpe", "daily_sharpe", "Daily Sharpe annualized", "Alpha evidence", daily_sharpe, "Annualized Sharpe from daily net dollars.", "mean(daily_net)/std(daily_net)*sqrt(252)", "derived", "policy_frame.timestamp,net_dollars", "day", promotion=True, pass_threshold="> 0", interpretation="Preferred Sharpe-style metric for OOS alpha proof.")
    add("portfolio.daily_sortino", "daily_sortino", "Daily Sortino annualized", "Risk/cost realism", daily_sortino, "Annualized Sortino from daily net dollars.", "mean(daily_net)/std(negative_daily_net)*sqrt(252)", "derived", "policy_frame.timestamp,net_dollars", "day", pass_threshold="> 0", interpretation="Downside-risk adjusted daily expectancy.")
    add("portfolio.calmar_ratio", "calmar_ratio", "Calmar ratio", "Risk/cost realism", calmar, "Annualized daily net divided by absolute daily max drawdown.", "annualized_daily_net / abs(max_daily_drawdown)", "derived", "policy_frame.timestamp,net_dollars", "day", pass_threshold="> 0", interpretation="Path-risk metric for prop-style review.")
    add("portfolio.max_drawdown", "max_drawdown", "Max drawdown dollars", "Risk/cost realism", costed.get("max_drawdown_dollars"), "Row-cumulative max drawdown from locked OOS policy net dollars.", "min(cumsum(net)-cummax(cumsum(net)))", "reports/phase8/alpha_promotion_decision.json", "costed_oos.max_drawdown_dollars", "row", diagnostic=True, interpretation="Useful risk context; needs equity curve for timing.")
    add("portfolio.net_positive_days_pct", "net_positive_days_pct", "Net-positive days pct", "Attribution", net_positive_days_pct, "Share of OOS days with positive net dollars.", "mean(daily_net > 0)", "derived", "policy_frame.timestamp,net_dollars", "day", pass_threshold="> 0", interpretation="Day-level persistence check.")
    add("portfolio.net_positive_folds_pct", "net_positive_folds_pct", "Net-positive folds pct", "Attribution", net_positive_folds_pct, "Share of folds with positive net dollars.", "mean(fold_net > 0)", "reports/phase8/alpha_promotion_decision.json", "folds[].net_return_dollars", "fold", pass_threshold="> 0", interpretation="Fold robustness check.")
    add("portfolio.net_positive_months_pct", "net_positive_months_pct", "Net-positive months pct", "Attribution", net_positive_months_pct, "Share of months with positive net dollars.", "mean(month_net > 0)", "derived", "policy_frame.timestamp,net_dollars", "month", pass_threshold="> 0", interpretation="Monthly persistence check.")
    add("portfolio.net_positive_markets_pct", "net_positive_markets_pct", "Net-positive markets pct", "Attribution", net_positive_markets_pct, "Share of markets with positive net dollars.", "mean(market_net > 0)", "reports/phase8/alpha_promotion_decision.json", "markets[].net_return_dollars", "market", pass_threshold="> 0", interpretation="Cross-market robustness check.")
    add("portfolio.worst_day_net", "worst_day_net", "Worst day net", "Risk/cost realism", worst_day_net, "Worst daily net dollars.", "min(daily_net)", "derived", "policy_frame.timestamp,net_dollars", "day", interpretation="Daily loss-tail screen.")
    add("portfolio.worst_fold_net", "worst_fold_net", "Worst fold net", "Attribution", worst_fold_net, "Worst fold net dollars.", "min(fold_net)", "reports/phase8/alpha_promotion_decision.json", "folds[].net_return_dollars", "fold", interpretation="Fold loss-tail screen.")
    add("portfolio.worst_market_net", "worst_market_net", "Worst market net", "Attribution", worst_market_net, "Worst market net dollars.", "min(market_net)", "reports/phase8/alpha_promotion_decision.json", "markets[].net_return_dollars", "market", interpretation="Market loss-tail screen.")
    add("portfolio.profit_factor_gross", "profit_factor_gross", "Gross profit factor", "Alpha evidence", gross_pf, "Positive gross active-signal dollars divided by absolute negative gross active-signal dollars.", "sum(gross>0)/abs(sum(gross<0))", "derived", "policy_frame.gross_dollars", "active signal", pass_threshold="> 0", interpretation="Distribution quality before costs.")
    add("portfolio.profit_factor_net", "profit_factor_net", "Net profit factor", "Alpha evidence", net_pf, "Positive net active-signal dollars divided by absolute negative net active-signal dollars.", "sum(net>0)/abs(sum(net<0))", "derived", "policy_frame.net_dollars", "active signal", pass_threshold="> 0", interpretation="Distribution quality after costs.")
    add("portfolio.average_win", "average_win", "Average active-signal win", "Signal quality", avg_win, "Mean positive active-signal net dollars.", "mean(net_dollars > 0)", "derived", "policy_frame.net_dollars", "active signal", interpretation="Payoff distribution context.")
    add("portfolio.average_loss", "average_loss", "Average active-signal loss", "Signal quality", avg_loss, "Mean negative active-signal net dollars.", "mean(net_dollars < 0)", "derived", "policy_frame.net_dollars", "active signal", interpretation="Payoff distribution context.")
    add("portfolio.payoff_ratio", "payoff_ratio", "Payoff ratio", "Signal quality", payoff, "Average active-signal win divided by absolute average active-signal loss.", "avg_win / abs(avg_loss)", "derived", "policy_frame.net_dollars", "active signal", pass_threshold="> 0", interpretation="Win/loss asymmetry.")
    add("portfolio.bar_sharpe_like_sample_scaled", "bar_sharpe_like_sample_scaled", "Bar Sharpe-like sample-scaled", "Risk/cost realism", costed.get("net_sharpe_like"), "Mean row net divided by row std and scaled by sqrt(row count).", "mean(row_net)/std(row_net)*sqrt(n_rows)", "reports/phase8/alpha_promotion_decision.json", "costed_oos.net_sharpe_like", "row", promotion=False, diagnostic=True, interpretation="Diagnostic only; not annualized daily Sharpe.")

    for key, display, source_key in [
        ("entries", "Entries", "policy_frame.position transitions 0 to nonzero"),
        ("exits", "Exits", "policy_frame.position transitions nonzero to 0"),
        ("flips", "Flips", "policy_frame.position sign changes"),
        ("lifecycle_trade_count", "Lifecycle trade count estimate", "entries + flips"),
        ("position_change_sum", "Position change sum", "sum(abs(position change))"),
        ("round_turn_estimate", "Round-turn estimate", "position_change_sum / 2"),
        ("average_holding_period_bars", "Average holding period bars", "position runs"),
        ("median_holding_period_bars", "Median holding period bars", "position runs"),
        ("max_holding_period_bars", "Max holding period bars", "position runs"),
        ("trades_per_day", "Lifecycle trades per day", "lifecycle_trade_count / days"),
        ("overnight_exposure_count", "Overnight/session-boundary exposure count", "session segment final position != 0"),
    ]:
        add(f"lifecycle.{key}", key, display, "Trade lifecycle", lifecycle.get(key), "Reconstructed from locked OOS policy positions.", source_key, "derived", source_key, "trade", diagnostic=True, pass_threshold="zero" if key == "overnight_exposure_count" else None, interpretation="Lifecycle diagnostic derived from policy positions.")

    add("policy.blocker_counts_are_exclusive", "blocker_counts_are_exclusive", "Non-exclusive blocker counts are exclusive?", "Policy/blocker diagnostics", False, "Current raw blocker counts can overlap.", "constant false", "scripts/phase8_model_selection/evaluate_predictions.py", "blocked_by_*", "row", diagnostic=True, required=True, pass_threshold="true", interpretation="False means raw blocker counts cannot be summed.")

    blocker_nonexclusive_rows = [
        ["fade_filter_block", costed.get("blocked_by_fade_filter")],
        ["flat_probability_block", costed.get("blocked_by_flat_probability")],
        ["trend_danger_block", costed.get("blocked_by_trend_danger")],
        ["no_direction_signal", costed.get("no_direction_signal")],
    ]
    exclusive_counts = exclusive_blocker_counts(policy_frame)
    exclusive_rows = [[key, value] for key, value in exclusive_counts.items()]
    exclusive_total = sum(exclusive_counts.values()) if exclusive_counts else None
    add("policy.exclusive_blocker_total_rows", "exclusive_blocker_total_rows", "Exclusive blocker total rows", "Policy/blocker diagnostics", exclusive_total, "Rows assigned to one blocker category using priority no_direction, flat_probability, trend_danger, fade_filter, active.", "sum(exclusive_blocker_counts)", "derived", "policy_frame.blocker booleans", "row", diagnostic=True, pass_threshold="> 0", interpretation="Must reconcile to total policy rows.")

    for key, value in lift.items():
        add(f"policy.{key}", key, key.replace("_", " ").title(), "Policy/blocker diagnostics", value, "Blocker lift diagnostic from base-position counterfactual.", "base_position counterfactual", "derived", f"policy_frame.{key}", "row", diagnostic=True, interpretation="Shows whether blockers saved losses or missed profits.")

    for key, value in label_stats.items():
        add(f"data.{key}", key, key.replace("_", " ").title(), "Label/data integrity", value, "Locked prediction data integrity diagnostic.", "derived from predictions", "data/predictions/tier1_locked_baseline_20260616/oos_predictions.parquet", key, "row", diagnostic=True, required=key in {"target_valid_rows", "causal_valid_rows"}, interpretation="Data/label validity context for interpreting OOS metrics.")

    readiness = {
        "artifact_evidence_ready": bool(wfa_manifest.get("artifact_evidence_ready")),
        "manifest_failures_zero": int(wfa_manifest.get("failure_count", 1) or 0) == 0,
        "metrics_failures_zero": int(metrics.get("failure_count", 1) or 0) == 0,
        "model_selection_failures_zero": int(model_selection.get("failure_count", 1) or 0) == 0,
        "promotion_allowed": bool(model_selection.get("model_promotion_allowed")),
        "final_holdout_excluded": bool(model_selection.get("final_holdout_excluded_from_selection")),
    }
    add("promotion.research_alpha_ready", "research_alpha_ready", "Research alpha ready", "Promotion verdict", metrics.get("research_alpha_ready"), "Phase 8 promotion gate research-alpha readiness.", "reported gate boolean", "reports/metrics/tier1_locked_baseline_20260616_metrics.json", "research_alpha_ready", "portfolio", promotion=True, required=True, pass_threshold="true", interpretation="Hard gate result.")
    add("promotion.model_promotion_allowed", "model_promotion_allowed", "Model promotion allowed", "Promotion verdict", model_selection.get("model_promotion_allowed"), "Model-selection promotion permission.", "reported gate boolean", "reports/model_selection/model_selection_report.json", "model_promotion_allowed", "portfolio", promotion=True, required=True, pass_threshold="true", interpretation="Hard gate result.")
    add("provenance.artifacts_ready", "artifacts_ready", "Artifacts ready", "Run identity/provenance", all(readiness.values()), "Combined readiness over manifest, metrics, model selection, promotion, and holdout exclusion checks.", "all(readiness checks)", "reports/wfa/tier1_locked_baseline_20260616_predictions_manifest.json", "artifact_evidence_ready", "portfolio", promotion=True, required=True, pass_threshold="true", interpretation="Do not trust metrics if provenance fails.")

    for metric_id, reason, required_for, stage, current_research_blocker in [
        ("live.fills_latency_capacity", "Deferred while project is research-stage: no live execution/fill/latency/capacity source-of-truth artifact is expected yet.", ["execution readiness", "prop risk"], "future_live", False),
        ("holdout.final_performance", "Deferred while project is research-stage: final holdout is intentionally excluded until a branch passes pre-registered research gates.", ["final validation"], "future_holdout", False),
        ("benchmark.random_sign_same_frequency", "No current deterministic random-sign same-frequency benchmark-control artifact exists.", ["alpha proof", "overfit rejection"], "research", True),
        ("benchmark.naive_momentum", "No current naive momentum benchmark artifact exists.", ["alpha proof", "overfit rejection"], "research", True),
        ("benchmark.naive_mean_reversion", "No current naive mean-reversion benchmark artifact exists.", ["alpha proof", "overfit rejection"], "research", True),
        ("bootstrap.daily_net_expectancy_ci", "Bootstrap confidence interval not generated; daily samples may be insufficient.", ["alpha proof"], "research", True),
        ("prop_firm.full_execution_realism", "Deferred while project is research-stage: full prop-firm execution realism needs fills, latency, queue position, capacity, loss limits, and trailing drawdown rules.", ["prop-firm execution realism", "risk review"], "future_live", False),
        ("research.feature_label_wfa_readiness", "No current artifact proves any new feature or label has passed pre-registered gates that justify a new WFA.", ["feature research", "target research", "WFA readiness"], "research", True),
        ("validation.purge_embargo_leakage_dashboard_evidence", "No dashboard source currently exposes an explicit purge/embargo/leakage-check summary tied to the visualized locked run.", ["data integrity", "alpha proof"], "research", True),
        ("risk.loss_limit_stress", "Research-stage risk proxy missing: no daily loss limit, trailing drawdown, losing-streak, or worst-N-day stress artifact feeds the dashboard.", ["prop risk", "promotion gate"], "research", True),
    ]:
        add_missing_evidence(
            ctx,
            metric_id,
            reason,
            required_for,
            stage=stage,
            current_research_blocker=current_research_blocker,
        )

    if policy_frame.empty:
        for metric_id in [
            "equity_curve",
            "drawdown_curve",
            "score_bucket_expectancy",
            "side_diagnostics",
            "trade_lifecycle",
            "blocker_lift",
            "label_integrity",
            "prop_firm_risk",
        ]:
            add_missing_evidence(ctx, f"derived.{metric_id}", "Could not derive locked OOS policy frame.", ["diagnosis"])

    ctx.metric_contract["missing_evidence"] = ctx.missing_evidence

    performance_chart = write_bar_chart(
        ctx,
        "locked_tier1_cost_summary.png",
        ["gross", "costs", "net"],
        [gross or 0.0, -(total_costs or 0.0), net or 0.0],
        title="Locked Tier 1 Costed OOS Summary",
        ylabel="Dollars",
        source_files=phase8_sources,
    )
    market_frame = pd.DataFrame(markets)
    market_chart = None
    if not market_frame.empty and {"market", "net_return_dollars"}.issubset(market_frame.columns):
        market_chart = write_bar_chart(
            ctx,
            "net_by_market.png",
            market_frame["market"].astype(str).tolist(),
            pd.to_numeric(market_frame["net_return_dollars"], errors="coerce").fillna(0.0).tolist(),
            title="Net Return By Market",
            ylabel="Dollars",
            source_files=market_sources,
        )
    else:
        ctx.warnings.append("market net chart skipped: phase8 markets are missing required fields")
    cost_component_chart = write_bar_chart(ctx, "cost_components.png", ["slippage", "commission"], [slippage or 0.0, commission or 0.0], title="Cost Components", ylabel="Dollars", source_files=phase8_sources)
    signal_activity_chart = write_bar_chart(ctx, "trade_activity.png", ["active rows", "long rows", "short rows"], [active_rows or 0.0, long_rows or 0.0, short_rows or 0.0], title="Active Signal / Directional Balance", ylabel="Rows", source_files=phase8_sources)
    policy_blocker_chart = write_bar_chart(ctx, "policy_blocker_counts.png", [row[0] for row in blocker_nonexclusive_rows], [safe_float(row[1]) or 0.0 for row in blocker_nonexclusive_rows], title="Non-Exclusive Policy Blocker Counts", ylabel="Rows", source_files=phase8_sources)
    prediction_source = str(metrics.get("prediction_path") or wfa_manifest.get("prediction_path") or "derived")
    daily_chart = write_bar_chart(ctx, "daily_net_summary.png", ["worst day", "mean day", "best day"], [float(daily_net.min()) if not daily_net.empty else 0.0, float(daily_net.mean()) if not daily_net.empty else 0.0, float(daily_net.max()) if not daily_net.empty else 0.0], title="Daily Net Distribution Summary", ylabel="Dollars", source_files=[prediction_source])
    side_chart = write_bar_chart(ctx, "side_net.png", [str(row[0]) for row in derived.get("side", [])], [safe_float(row[4]) or 0.0 for row in derived.get("side", [])], title="Net By Side", ylabel="Dollars", source_files=[prediction_source])
    score_chart = write_bar_chart(ctx, "score_bucket_expectancy.png", [str(idx + 1) for idx, _ in enumerate(derived.get("score", []))], [safe_float(row[3]) or 0.0 for row in derived.get("score", [])], title="Score Bucket Net Expectancy", ylabel="Dollars / Active Row", source_files=[prediction_source])

    blocker_categories = {"net_return": 0, "sharpe": 0, "cost_drag": 0, "market": 0, "fold": 0, "other": 0}
    for blocker in blockers:
        text = str(blocker)
        if "net_return" in text and "folds" not in text and "markets" not in text:
            blocker_categories["net_return"] += 1
        elif "sharpe" in text.lower():
            blocker_categories["sharpe"] += 1
        elif "cost_drag" in text:
            blocker_categories["cost_drag"] += 1
        elif "markets" in text:
            blocker_categories["market"] += 1
        elif "folds" in text:
            blocker_categories["fold"] += 1
        else:
            blocker_categories["other"] += 1
    gate_chart = write_bar_chart(ctx, "promotion_gate_blockers.png", list(blocker_categories.keys()), list(blocker_categories.values()), title="Promotion Gate Blockers", ylabel="Count", source_files=gate_sources)
    provenance_chart = write_bar_chart(ctx, "artifact_readiness.png", list(readiness.keys()), [1.0 if value else 0.0 for value in readiness.values()], title="Artifact Provenance / Readiness", ylabel="True=1 / False=0", source_files=provenance_sources)

    feature_rows = [[row.get("hypothesis_id"), row.get("status"), row.get("wfa_allowed"), row.get("feature_family")] for row in feature_registry.get("hypotheses", []) if isinstance(row, Mapping)]
    target_rows = [[row.get("target_hypothesis_id"), row.get("status"), row.get("wfa_allowed"), row.get("target_family")] for row in target_registry.get("hypotheses", []) if isinstance(row, Mapping)]
    status_counts: dict[str, int] = {}
    for row in feature_rows + target_rows:
        status_counts[str(row[1])] = status_counts.get(str(row[1]), 0) + 1
    hypothesis_chart = write_bar_chart(ctx, "hypothesis_statuses.png", list(status_counts.keys()), list(status_counts.values()), title="Feature / Target Hypothesis Statuses", ylabel="Count", source_files=list(dict.fromkeys([*feature_sources, *target_sources])))

    def md_decision(text: str) -> str:
        match = re.search(r"Decision:\s*`?([A-Z0-9_]+)`?", text)
        return match.group(1) if match else "MISSING"

    phase9_rows = [
        ["cost_clearability", md_decision(cost_clear_text), "Phase 9 audit markdown"],
        ["market_balanced_cost_clearability", md_decision(balanced_text), "Phase 9 audit markdown"],
        ["liquidity_cost_state_features_v1", liquidity.get("decision"), "Smoke JSON"],
        ["directional_path_quality_target_v1", directional.get("decision"), "Smoke JSON"],
    ]
    phase9_status_counts: dict[str, int] = {}
    for row in phase9_rows:
        phase9_status_counts[str(row[1])] = phase9_status_counts.get(str(row[1]), 0) + 1
    phase9_chart = write_bar_chart(ctx, "phase9_decisions.png", list(phase9_status_counts.keys()), list(phase9_status_counts.values()), title="Phase 9 Stopped / Rejected Decisions", ylabel="Count", source_files=phase9_sources)

    skipped = skipped_charts_from_inventory(inventory)
    ctx.charts_skipped.extend(skipped)

    market_status_rows = classify_markets([row for row in markets if isinstance(row, Mapping)])
    blocker_rows = [[idx + 1, blocker] for idx, blocker in enumerate(blockers)]
    provenance_rows = [[key, value] for key, value in readiness.items()]
    lifecycle_rows = metric_table_rows(ctx, [f"lifecycle.{key}" for key in ["entries", "exits", "flips", "lifecycle_trade_count", "position_change_sum", "round_turn_estimate", "average_holding_period_bars", "median_holding_period_bars", "max_holding_period_bars", "trades_per_day", "overnight_exposure_count"]])
    label_rows = metric_table_rows(ctx, [row["id"] for row in ctx.metric_contract["metrics"] if str(row["id"]).startswith("data.")])
    missing_rows = [
        [
            row["metric_id"],
            row.get("stage"),
            row.get("current_research_blocker"),
            row["reason"],
            ", ".join(row["required_for"]),
        ]
        for row in ctx.missing_evidence
    ]
    skipped_rows = [[row["name"], row["reason"]] for row in skipped]

    next_actions: list[list[Any]] = []
    if gross is not None and gross < 0:
        next_actions.append(["Do not tune costs; gross is negative.", "Signal/target failure before execution assumptions."])
    if net is not None and net < 0:
        next_actions.append(["Do not promote or rerun WFA variants from this branch.", "Locked OOS net is negative."])
    if cost_drag is not None and cost_drag > 1:
        next_actions.append(["Investigate turnover or smaller target economics.", "Costs exceed absolute gross edge."])
    if any(row[1] == "zero_trade_market" for row in market_status_rows):
        next_actions.append(["Separate zero-participation markets from losing markets.", "A market with zero active rows is coverage/policy selectivity, not loss attribution."])
    if derived.get("score") and len([row for row in derived["score"] if safe_float(row[3]) is not None]) >= 2:
        score_values = [safe_float(row[3]) for row in derived["score"] if safe_float(row[3]) is not None]
        if score_values != sorted(score_values):
            next_actions.append(["Do not trust score threshold tuning.", "Score bucket net expectancy is not monotonic."])
    if lift.get("missed_profit") is not None and lift.get("saved_loss") is not None and float(lift["missed_profit"]) > float(lift["saved_loss"]):
        next_actions.append(["Inspect blocker lift before changing model features.", "Blockers appear to miss more profit than they save."])
    if label_stats.get("cost_clearable_future_move_pct") is not None and float(label_stats["cost_clearable_future_move_pct"]) < 0.5:
        next_actions.append(["Redesign label or horizon before policy tuning.", "Less than half of future moves clear estimated round-turn cost."])
    if not next_actions:
        next_actions.append(["No promote action.", "Use missing-evidence table before making research changes."])

    ctx.tables_generated.extend(
        [
            {"name": "Run identity/provenance", "source_files": ["reports/report_inventory.json", *provenance_sources]},
            {"name": "Promotion verdict", "source_files": [*phase8_sources, *gate_sources]},
            {"name": "Alpha evidence", "source_files": phase8_sources},
            {"name": "Risk/cost realism", "source_files": phase8_sources},
            {"name": "Attribution", "source_files": [*phase8_sources, str(wfa_manifest.get("prediction_path", ""))]},
            {"name": "Signal quality", "source_files": [str(wfa_manifest.get("prediction_path", ""))]},
            {"name": "Policy/blocker diagnostics", "source_files": [*phase8_sources, str(wfa_manifest.get("prediction_path", ""))]},
            {"name": "Trade lifecycle", "source_files": [str(wfa_manifest.get("prediction_path", ""))]},
            {"name": "Label/data integrity", "source_files": [str(wfa_manifest.get("prediction_path", ""))]},
            {"name": "Deterministic next-action recommendations", "source_files": ["dashboard metric contract"]},
        ]
    )

    ctx.metric_contract["displayed_metric_ids"] = list(dict.fromkeys(ctx.displayed_metric_ids))
    ctx.metric_contract["missing_evidence"] = ctx.missing_evidence
    ctx.metric_audit_markdown = build_metric_audit_markdown(ctx)

    run_identity_rows = [
        ["Locked run", run],
        ["Profile", wfa_manifest.get("profile")],
        ["Resolved profile", wfa_manifest.get("resolved_profile")],
        ["Markets", ", ".join(str(x) for x in wfa_manifest.get("markets", []))],
        ["Years", ", ".join(str(x) for x in wfa_manifest.get("years", []))],
        ["Fold count", wfa_manifest.get("fold_count")],
        ["Prediction path", wfa_manifest.get("prediction_path")],
        ["Git commit", wfa_manifest.get("git_commit") or metrics.get("git_commit")],
    ]

    html_doc = "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            "<title>Intraday Futures Research Dashboard</title>",
            "<style>",
            "body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f6f7f9;color:#1c2430}",
            "main{max-width:1220px;margin:0 auto;padding:24px}",
            "section{background:white;border:1px solid #d9dee7;border-radius:6px;margin:0 0 18px;padding:18px}",
            "h1,h2,h3{margin-top:0}.source{font-size:12px;color:#596575;margin:6px 0 10px}",
            ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}",
            ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:10px 0 16px}",
            ".metric-card{border:1px solid #dfe4ec;border-radius:6px;padding:10px;background:#fbfcfe}.metric-label{font-size:12px;color:#596575}.metric-value{font-size:22px;font-weight:700;margin:4px 0}",
            ".pill{display:inline-block;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:700}.ok{background:#e6f4ea;color:#17663a}.fail{background:#fde8e8;color:#9b1c1c}.watch{background:#eef2f7;color:#42526b}",
            ".callout{background:#eef5ff;border-left:4px solid #2f6fbb;padding:10px 12px;margin:10px 0 14px}.callout p{margin:6px 0 0}.explain{font-size:13px;color:#42526b}",
            ".chart img{max-width:100%;border:1px solid #e2e6ee;background:white}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #dfe4ec;padding:6px;text-align:left;vertical-align:top}th{background:#eef2f7}.warn{background:#fff7e6;border-color:#f0cf8a}",
            "</style>",
            "</head>",
            "<body><main>",
            "<h1>Intraday Futures Research Dashboard</h1>",
            "<p>This dashboard is an evidence display. It does not change model logic, labels, features, WFA, data generation, configs, or trading assumptions.</p>",
            "<section><h2>1. Run identity/provenance</h2>" + html_table(["Item", "Value"], run_identity_rows, ["reports/report_inventory.json", *provenance_sources]) + chart_block("Artifact Provenance / Readiness", provenance_chart, provenance_sources, "Hard readiness checks before using any metrics.") + html_table(["Check", "Value"], provenance_rows, provenance_sources) + "</section>",
            "<section><h2>2. Promotion verdict</h2>" + metric_cards(["Metric", "Value", "Status", "Use"], metric_card_rows(ctx, ["promotion.research_alpha_ready", "promotion.model_promotion_allowed", "provenance.artifacts_ready"]), [*phase8_sources, *gate_sources]) + chart_block("Promotion Gate Blockers", gate_chart, gate_sources, "Exact blocker text remains below; this chart only groups blocker types.") + html_table(["#", "Blocker"], blocker_rows, gate_sources) + "</section>",
            "<section><h2>3. Alpha evidence</h2>" + metric_cards(["Metric", "Value", "Status", "Use"], metric_card_rows(ctx, ["portfolio.gross_pnl", "portfolio.net_pnl", "portfolio.daily_sharpe", "portfolio.net_positive_folds_pct", "portfolio.net_positive_markets_pct", "portfolio.active_signal_rows"]), phase8_sources) + '<div class="grid">' + chart_block("Locked Tier 1 Costed OOS Summary", performance_chart, phase8_sources, "Gross, costs, and net after locked OOS policy.") + chart_block("Daily Net Distribution Summary", daily_chart, [str(wfa_manifest.get("prediction_path", ""))], "Daily path summary derived from locked OOS predictions.") + "</div>" + html_table(["Metric", "Value", "Aggregation", "Status", "Interpretation"], metric_table_rows(ctx, ["portfolio.gross_expectancy_per_active_signal", "portfolio.net_expectancy_per_active_signal", "portfolio.gross_expectancy_per_trade", "portfolio.net_expectancy_per_trade", "portfolio.daily_expectancy", "portfolio.profit_factor_gross", "portfolio.profit_factor_net"]), phase8_sources) + "</section>",
            "<section><h2>4. Risk/cost realism</h2>" + '<div class="grid">' + chart_block("Cost Components", cost_component_chart, phase8_sources, "Slippage versus commission components from locked OOS report.") + chart_block("Active Signal / Directional Balance", signal_activity_chart, phase8_sources, "Active signal rows are not lifecycle trades.") + "</div>" + html_table(["Metric", "Value", "Aggregation", "Status", "Interpretation"], metric_table_rows(ctx, ["portfolio.total_costs", "portfolio.commission", "portfolio.slippage", "portfolio.cost_drag_over_abs_gross", "portfolio.breakeven_cost_multiple", "portfolio.daily_sortino", "portfolio.calmar_ratio", "portfolio.max_drawdown", "portfolio.worst_day_net", "portfolio.bar_sharpe_like_sample_scaled"]), phase8_sources) + "</section>",
            "<section><h2>5. Attribution</h2>" + chart_block("Net Return By Market", market_chart, market_sources, "Zero-trade markets are classified separately below.") + html_table(["Market", "Status", "Active signal rows", "Net"], market_status_rows, market_sources) + "<h3>By fold</h3>" + html_table(["Fold", "Active rows", "Gross", "Costs", "Net"], derived.get("fold", [])[:60], [str(wfa_manifest.get("prediction_path", ""))]) + "<h3>By month</h3>" + html_table(["Month", "Active rows", "Gross", "Costs", "Net"], derived.get("month", []), [str(wfa_manifest.get("prediction_path", ""))]) + "<h3>By hour UTC</h3>" + html_table(["Hour", "Active rows", "Gross", "Costs", "Net"], derived.get("hour", []), [str(wfa_manifest.get("prediction_path", ""))]) + "</section>",
            "<section><h2>6. Signal quality</h2>" + '<div class="grid">' + chart_block("Net By Side", side_chart, [str(wfa_manifest.get("prediction_path", ""))], "Long/short contribution after policy.") + chart_block("Score Bucket Net Expectancy", score_chart, [str(wfa_manifest.get("prediction_path", ""))], "Bucket monotonicity must hold before threshold research.") + "</div>" + html_table(["Side", "Active rows", "Gross", "Costs", "Net", "Net expectancy", "Win rate", "Cost drag"], derived.get("side", []), [str(wfa_manifest.get("prediction_path", ""))]) + html_table(["Score bucket", "Rows", "Active rows", "Net expectancy", "Net win rate"], derived.get("score", []), [str(wfa_manifest.get("prediction_path", ""))]) + "</section>",
            "<section><h2>7. Policy/blocker diagnostics</h2>" + chart_block("Non-Exclusive Policy Blocker Counts", policy_blocker_chart, phase8_sources, "Raw blocker counts overlap and cannot be summed.") + html_table(["Blocker", "Rows"], blocker_nonexclusive_rows, phase8_sources) + "<h3>Exclusive blocker counts</h3>" + html_table(["Exclusive category", "Rows"], exclusive_rows, [str(wfa_manifest.get("prediction_path", ""))]) + "<h3>Blocker lift</h3>" + html_table(["Metric", "Value", "Aggregation", "Status", "Interpretation"], metric_table_rows(ctx, [f"policy.{key}" for key in lift.keys()]), [str(wfa_manifest.get("prediction_path", ""))]) + "</section>",
            "<section><h2>8. Trade lifecycle</h2>" + callout("Cost warning", "Current Phase 8 costs assume one independent round-turn per active signal row. Lifecycle metrics below are reconstructed diagnostics and must not be treated as executable fill PnL.") + html_table(["Metric", "Value", "Aggregation", "Status", "Interpretation"], lifecycle_rows, [str(wfa_manifest.get("prediction_path", ""))]) + "</section>",
            "<section><h2>9. Label/data integrity</h2>" + html_table(["Metric", "Value", "Aggregation", "Status", "Interpretation"], label_rows, [str(wfa_manifest.get("prediction_path", ""))]) + "<h3>Missing evidence</h3>" + html_table(["Metric", "Stage", "Current research blocker", "Reason", "Required for"], missing_rows, ["dashboard_metric_contract.json"]) + "</section>",
            "<section><h2>10. Deterministic next-action recommendations</h2>" + html_table(["Recommendation", "Evidence trigger"], next_actions, ["dashboard_metric_contract.json"]) + "</section>",
            "<section><h2>Hypothesis / Phase 9 context</h2>" + chart_block("Feature / Target Hypothesis Statuses", hypothesis_chart, [*feature_sources, *target_sources], "Registry status prevents retesting rejected branches as if new.") + html_table(["ID", "Status", "WFA allowed", "Family"], feature_rows, feature_sources) + html_table(["ID", "Status", "WFA allowed", "Family"], target_rows, target_sources) + chart_block("Phase 9 Stopped / Rejected Decisions", phase9_chart, phase9_sources, "Stopped branches are constraints, not rescue inputs.") + html_table(["Branch", "Decision", "Evidence type"], phase9_rows, phase9_sources) + "</section>",
            "<section><h2>Skipped charts</h2>" + html_table(["Chart", "Reason"], skipped_rows, ["reports/report_inventory.json"]) + "</section>",
            "<section class=\"warn\"><h2>Warnings</h2><ul>" + "".join(f"<li>{html.escape(warning)}</li>" for warning in ctx.warnings) + "</ul></section>",
            "</main></body></html>",
        ]
    )
    return {"inventory": inventory, "html": html_doc}


def write_outputs(ctx: BuildContext, html_doc: str) -> dict[str, Any]:
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    ctx.charts_dir.mkdir(parents=True, exist_ok=True)
    dashboard = ctx.out_dir / "dashboard.html"
    dashboard.write_text(html_doc, encoding="utf-8")
    contract_path = ctx.out_dir / "dashboard_metric_contract.json"
    audit_path = ctx.out_dir / "dashboard_metric_audit.md"
    if ctx.metric_contract:
        contract_path.write_text(
            json.dumps(ctx.metric_contract, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if ctx.metric_audit_markdown:
        audit_path.write_text(ctx.metric_audit_markdown, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "inventory": ctx.rel(ctx.inventory_path),
        "dashboard": ctx.rel(dashboard),
        "metric_contract": ctx.rel(contract_path),
        "metric_audit": ctx.rel(audit_path),
        "source_files_read": sorted(set(ctx.source_files_read)),
        "source_files_missing": sorted(set(ctx.source_files_missing)),
        "charts_generated": ctx.charts_generated,
        "tables_generated": ctx.tables_generated,
        "charts_skipped": ctx.charts_skipped,
        "displayed_metric_ids": sorted(set(ctx.displayed_metric_ids)),
        "missing_evidence": ctx.missing_evidence,
        "warnings": ctx.warnings,
    }
    manifest_path = ctx.out_dir / "visualization_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def run(
    *,
    reports_dir: Path,
    out_dir: Path,
    inventory: Path,
    strict: bool = False,
    derive_predictions: bool = True,
) -> tuple[int, dict[str, Any]]:
    ctx = BuildContext(
        reports_dir=reports_dir,
        out_dir=out_dir,
        inventory_path=inventory,
        strict=strict,
        derive_predictions=derive_predictions,
    )
    try:
        result = build_dashboard_v2(ctx)
    except Exception as exc:
        ctx.errors.append(str(exc))
        result = {"html": ""}
    if ctx.errors:
        manifest = {
            "schema_version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit(),
            "inventory": ctx.rel(inventory) if inventory.exists() else str(inventory),
            "source_files_read": sorted(set(ctx.source_files_read)),
            "source_files_missing": sorted(set(ctx.source_files_missing)),
            "charts_generated": ctx.charts_generated,
            "tables_generated": ctx.tables_generated,
            "charts_skipped": ctx.charts_skipped,
            "displayed_metric_ids": sorted(set(ctx.displayed_metric_ids)),
            "missing_evidence": ctx.missing_evidence,
            "warnings": ctx.warnings,
            "errors": ctx.errors,
        }
        if out_dir.exists() or not strict:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "visualization_manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return 1, manifest
    manifest = write_outputs(ctx, str(result["html"]))
    return 0, manifest


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--out-dir", default="reports/visualizations")
    parser.add_argument("--inventory", default="reports/report_inventory.json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip heavy locked prediction parquet derivations for quick dashboard launch.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    code, manifest = run(
        reports_dir=Path(args.reports_dir),
        out_dir=Path(args.out_dir),
        inventory=Path(args.inventory),
        strict=bool(args.strict),
        derive_predictions=not bool(args.fast),
    )
    print(
        json.dumps(
            {
                "dashboard": manifest.get("dashboard"),
                "manifest": str(Path(args.out_dir) / "visualization_manifest.json"),
                "metric_audit": manifest.get("metric_audit"),
                "metric_contract": manifest.get("metric_contract"),
                "charts_generated": len(manifest.get("charts_generated", [])),
                "charts_skipped": len(manifest.get("charts_skipped", [])),
                "missing_evidence": len(manifest.get("missing_evidence", [])),
                "warnings": manifest.get("warnings", []),
                "errors": manifest.get("errors", []),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
