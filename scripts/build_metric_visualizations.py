#!/usr/bin/env python3
"""Build a static diagnostic dashboard from the Phase 0 report inventory."""

from __future__ import annotations

import argparse
import html
import json
import re
import struct
import subprocess
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
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_files_read: list[str] = field(default_factory=list)
    source_files_missing: list[str] = field(default_factory=list)
    charts_generated: list[dict[str, Any]] = field(default_factory=list)
    tables_generated: list[dict[str, Any]] = field(default_factory=list)
    charts_skipped: list[dict[str, Any]] = field(default_factory=list)

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


def chart_sources(inventory: Mapping[str, Any], chart_name: str) -> list[str]:
    sources: list[str] = []
    for row in inventory.get("charts", []):
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("chart", ""))
        if name == chart_name or (chart_name in {"feature hypothesis statuses", "target hypothesis statuses"} and name == COMBINED_HYPOTHESIS_CHART):
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


def write_outputs(ctx: BuildContext, html_doc: str) -> dict[str, Any]:
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    ctx.charts_dir.mkdir(parents=True, exist_ok=True)
    dashboard = ctx.out_dir / "dashboard.html"
    dashboard.write_text(html_doc, encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "inventory": ctx.rel(ctx.inventory_path),
        "dashboard": ctx.rel(dashboard),
        "source_files_read": sorted(set(ctx.source_files_read)),
        "source_files_missing": sorted(set(ctx.source_files_missing)),
        "charts_generated": ctx.charts_generated,
        "tables_generated": ctx.tables_generated,
        "charts_skipped": ctx.charts_skipped,
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
) -> tuple[int, dict[str, Any]]:
    ctx = BuildContext(
        reports_dir=reports_dir,
        out_dir=out_dir,
        inventory_path=inventory,
        strict=strict,
    )
    try:
        result = build_dashboard(ctx)
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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    code, manifest = run(
        reports_dir=Path(args.reports_dir),
        out_dir=Path(args.out_dir),
        inventory=Path(args.inventory),
        strict=bool(args.strict),
    )
    print(
        json.dumps(
            {
                "dashboard": manifest.get("dashboard"),
                "manifest": str(Path(args.out_dir) / "visualization_manifest.json"),
                "charts_generated": len(manifest.get("charts_generated", [])),
                "charts_skipped": len(manifest.get("charts_skipped", [])),
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
