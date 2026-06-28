from __future__ import annotations


SIDE_AWARE_TREND_TARGETS = {
    "trend_adverse_long": ("target_trend_adverse_long_30m", "p_trend_adverse_long_30m"),
    "trend_favorable_long": ("target_trend_favorable_long_30m", "p_trend_favorable_long_30m"),
    "trend_adverse_short": ("target_trend_adverse_short_30m", "p_trend_adverse_short_30m"),
    "trend_favorable_short": ("target_trend_favorable_short_30m", "p_trend_favorable_short_30m"),
}


def add_side_aware_trend_rows(
    rows: list[dict[str, object]],
    base: dict[str, object],
    item: dict[str, object],
) -> None:
    long_adverse = float(item.get("p_trend_adverse_long", item.get("p_trend", 0.10)))
    short_adverse = float(item.get("p_trend_adverse_short", item.get("p_trend", 0.10)))
    scores = {
        "target_trend_adverse_long_30m": long_adverse,
        "target_trend_favorable_long_30m": float(
            item.get("p_trend_favorable_long", max(0.0, 1.0 - long_adverse))
        ),
        "target_trend_adverse_short_30m": short_adverse,
        "target_trend_favorable_short_30m": float(
            item.get("p_trend_favorable_short", max(0.0, 1.0 - short_adverse))
        ),
    }
    for side_key, (target_name, probability_column) in SIDE_AWARE_TREND_TARGETS.items():
        score = scores[target_name]
        rows.append(
            {
                **base,
                "model_id": f"logistic_{side_key}_v1",
                "model_family": "logistic_regression",
                "target_name": target_name,
                "y_true": int(score >= 0.5),
                "y_pred_raw": score,
                "y_pred_calibrated": score,
                "p_long": None,
                "p_short": None,
                "p_flat": None,
                "p_fade_success": None,
                probability_column: score,
                "p_trend_danger": None,
            }
        )
