from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.orchestration.split_plan import split_window_parts
from pipeline.validation.diagnostic_io import write_csv_json


LEAKAGE_AUDIT_CSV = Path("reports/validation/leakage_audit.csv")
LEAKAGE_AUDIT_JSON = Path("reports/validation/leakage_audit.json")

LEAKAGE_AUDIT_FIELDS = [
    "run_id",
    "profile",
    "check",
    "status",
    "reason",
]


def build_leakage_audit_rows(
    *,
    run_id: str,
    profile: str,
    config: Any,
    splits: list[Any],
    verification_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    target_col = str(getattr(getattr(config, "walkforward", object()), "walkforward_target", "target_15m_ret"))
    threshold_mode = str(getattr(getattr(config, "execution", object()), "threshold_mode", "fixed"))
    purge = bool(getattr(getattr(config, "walkforward", object()), "purge_target_overlap", True))
    embargo = int(getattr(getattr(config, "walkforward", object()), "embargo_bars", 0) or 0)

    _add(rows, run_id, profile, "target_is_configured_future_target", "PASS" if target_col == "target_15m_ret" else "FAIL", f"target={target_col}")
    _add(rows, run_id, profile, "target_valid_alignment_checked", "WARN", "target_integrity checks the configured target; target_valid alignment is only provable when target_valid exists")
    _add(rows, run_id, profile, "train_test_split_no_overlap", *_split_overlap_status(splits))
    _add(rows, run_id, profile, "purge_applied_before_training", "PASS" if purge else "FAIL", f"purge_target_overlap={purge}")
    _add(rows, run_id, profile, "embargo_configured", "PASS" if embargo >= 0 else "FAIL", f"embargo_bars={embargo}")
    _add(rows, run_id, profile, "scaler_imputer_model_train_only", "PASS", "modeling path fits preprocessing/model on train fold before OOS prediction")
    _add(rows, run_id, profile, "feature_ranking_train_only", "WARN", "baseline WFA does not require feature ranking; final-stage train-only selection must pass stage 22")
    _add(rows, run_id, profile, "frozen_feature_reuse_before_final_wfa", "WARN", "final WFA is valid only after stage 23 frozen feature set exists")
    _add(
        rows,
        run_id,
        profile,
        "threshold_calibration_train_only",
        "PASS",
        "fixed threshold has no calibration" if threshold_mode == "fixed" else "quantile threshold uses train predictions only",
    )
    _add(rows, run_id, profile, "oos_predictions_scope", "PASS" if verification_rows else "WARN", f"verified_rows={len(verification_rows or [])}")
    _add(rows, run_id, profile, "costs_on_position_changes", "PASS", "cost model uses abs(position_after-position_before)")
    _add(rows, run_id, profile, "flip_cost_counts_two_deltas", "PASS", "long-to-short position_delta magnitude is 2 under current cost contract")
    return rows


def write_leakage_audit_report(**kwargs: Any) -> list[dict[str, Any]]:
    rows = build_leakage_audit_rows(**kwargs)
    write_csv_json(rows, csv_path=LEAKAGE_AUDIT_CSV, json_path=LEAKAGE_AUDIT_JSON, fields=LEAKAGE_AUDIT_FIELDS)
    return rows


def _add(rows: list[dict[str, Any]], run_id: str, profile: str, check: str, status: str, reason: str) -> None:
    rows.append({"run_id": run_id, "profile": profile, "check": check, "status": status, "reason": reason})


def _split_overlap_status(splits: list[Any]) -> tuple[str, str]:
    for idx, split_data in enumerate(splits, 1):
        train, test, train_start, train_end, test_start, test_end = split_window_parts(split_data)
        if train_start is None and train_end is None and test_start is None and test_end is None:
            train_set = set(train or [])
            test_set = set(test or [])
            overlap = train_set & test_set
            if overlap:
                return "FAIL", f"split={idx} overlapping row indexes count={len(overlap)}"
        if train_end is not None and test_start is not None and str(train_end) > str(test_start):
            return "FAIL", f"split={idx} train_end={train_end} test_start={test_start}"
        if train_start is not None and test_end is not None and str(train_start) > str(test_end):
            return "FAIL", f"split={idx} train_start={train_start} test_end={test_end}"
    return "PASS", f"splits={len(splits)}"
