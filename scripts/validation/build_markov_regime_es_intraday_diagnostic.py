#!/usr/bin/env python3
"""Build a guarded Markov regime diagnostic for ES intraday research.

This module is intentionally report-only. It does not define a tradable signal,
position sizing policy, promotion gate, paper-trading gate, or HMM workflow.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


STOP_INPUT_FAILURE = "STOP_INPUT_FAILURE"
STOP_SPARSE_STATE_COVERAGE = "STOP_SPARSE_STATE_COVERAGE"
PASS_DIAGNOSTIC_REPORT_ONLY = "PASS_DIAGNOSTIC_REPORT_ONLY"

MARKET = "ES"
YEARS = (2023, 2024)
EXPECTED_FOLD_IDS = tuple(f"ES_research_{index:04d}" for index in range(1, 13))
STATE_ORDER = ("bull_up", "bear_down", "sideways")
DEFAULT_TICK_SIZE = 0.25
DEFAULT_LOOKBACK_ROWS = 60
DEFAULT_OBSERVATION_STEP_ROWS = 30
DEFAULT_MIN_COUNTER = 90
DEFAULT_THRESHOLD = 1.0
SHUFFLE_SEED = 20260709
MAX_RUNTIME_SECONDS = 600

DEFAULT_OUTPUT_ROOT = (
    Path("reports") / "model_trust_audit" / "markov_regime_es_intraday_v1"
)
EXPECTED_OUTPUT_FILENAMES = (
    "input_manifest.json",
    "markov_regime_es_intraday_v1_report.json",
    "markov_regime_es_intraday_v1_report.md",
    "fold_state_counts.csv",
    "fold_transition_matrices.csv",
    "fold_forecast_scores.csv",
    "baseline_null_scores.csv",
    "stress_grid_results.csv",
    "trial_accounting.json",
)

DEFAULT_INPUT_PATHS = {
    "predeclaration_packet": Path("docs")
    / "markov_regime_es_intraday_v1_predecl_packet_20260709.md",
    "project_outline": Path("PROJECT_OUTLINE.md"),
    "codex_handoff": Path("CODEX_HANDOFF.md"),
    "feature_2023": Path("data") / "feature_matrices" / "ES" / "2023.parquet",
    "feature_2024": Path("data") / "feature_matrices" / "ES" / "2024.parquet",
    "split_plan": Path("reports")
    / "wfa"
    / "tier1_core_phase5_split_plan_20260706"
    / "split_plan.json",
    "active_feature_set": Path("reports")
    / "wfa"
    / "tier1_core_phase6_wfa_runner_preflight_20260706"
    / "tier1_core_active_feature_set.json",
    "alpha_evidence_gap_matrix": Path("reports")
    / "model_trust_audit"
    / "alpha_evidence_gap_matrix_20260709T034313Z"
    / "alpha_evidence_gap_matrix.json",
    "alpha_evidence_closeout": Path("reports")
    / "model_trust_audit"
    / "alpha_evidence_completion_closeout_20260709T035929Z"
    / "alpha_evidence_completion_closeout.json",
}

REQUIRED_FEATURE_COLUMNS = (
    "ts",
    "market",
    "year",
    "session_segment_id",
    "close",
    "feature_row_valid",
    "training_row_valid",
)

STRESS_GRID = tuple(
    {"lookback_rows": lookback, "threshold": threshold, "horizon_steps": 1}
    for lookback in (30, 60, 120)
    for threshold in (0.75, 1.0, 1.25)
)
MATRIX_POWER_DIAGNOSTICS = (2, 4, 8)


class DiagnosticStop(RuntimeError):
    """Fail-closed exception for predeclared diagnostic stop conditions."""

    def __init__(self, status: str, failures: Sequence[str]):
        self.status = status
        self.failures = list(failures)
        super().__init__(f"{status}: {'; '.join(self.failures)}")


@dataclass(frozen=True)
class FoldWindow:
    fold_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True)
class StateCountRules:
    min_train_observations: int = 1000
    min_test_observations: int = 100
    min_train_state_observations: int = 50
    min_train_state_transitions: int = 30
    min_test_state_observations: int = 10


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def resolve_path(repo_root: Path, path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else repo_root / candidate


def repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_commit(repo_root: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DiagnosticStop(STOP_INPUT_FAILURE, [f"{path.as_posix()}: JSON root is not an object"])
    return payload


def expected_output_paths(output_root: Path) -> set[Path]:
    return {output_root / name for name in EXPECTED_OUTPUT_FILENAMES}


def validate_output_root_is_expected(repo_root: Path, output_root: Path) -> None:
    expected = resolve_path(repo_root, DEFAULT_OUTPUT_ROOT).resolve()
    if output_root.resolve() != expected:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            [
                "unexpected output root: "
                f"{output_root.as_posix()} != {expected.as_posix()}"
            ],
        )


def validate_expected_output_paths(output_root: Path, paths: Iterable[Path]) -> None:
    expected = {path.resolve() for path in expected_output_paths(output_root)}
    actual = {path.resolve() for path in paths}
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    failures: list[str] = []
    if unexpected:
        failures.append(
            "unexpected output paths: "
            + ", ".join(path.as_posix() for path in unexpected)
        )
    if missing:
        failures.append(
            "missing expected output paths: "
            + ", ".join(path.as_posix() for path in missing)
        )
    if failures:
        raise DiagnosticStop(STOP_INPUT_FAILURE, failures)


def validate_output_root_available(output_root: Path) -> None:
    if output_root.exists():
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            [f"output root already exists: {output_root.as_posix()}"],
        )


def validate_input_paths(paths: Mapping[str, Path]) -> None:
    missing = [
        f"{name}: {path.as_posix()}"
        for name, path in sorted(paths.items())
        if not path.exists()
    ]
    if missing:
        raise DiagnosticStop(STOP_INPUT_FAILURE, [f"missing required input {item}" for item in missing])


def validate_required_columns(frame: pd.DataFrame, required: Sequence[str] = REQUIRED_FEATURE_COLUMNS) -> None:
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            ["missing required feature columns: " + ", ".join(missing)],
        )


def load_feature_frame(path: Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path, columns=list(REQUIRED_FEATURE_COLUMNS))
    except Exception as exc:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            [f"failed to read required feature columns from {path.as_posix()}: {exc}"],
        ) from exc


def filter_scope(
    frame: pd.DataFrame,
    *,
    market: str = MARKET,
    years: Sequence[int] = YEARS,
) -> pd.DataFrame:
    validate_required_columns(frame)
    work = frame.copy()
    work["ts"] = pd.to_datetime(work["ts"], utc=True)
    scoped = work[
        (work["market"] == market)
        & (work["year"].isin(years))
        & (work["feature_row_valid"].astype(bool))
        & (work["training_row_valid"].astype(bool))
    ].copy()
    scoped = scoped.sort_values(["session_segment_id", "ts"], kind="mergesort").reset_index(drop=True)
    scoped["close"] = pd.to_numeric(scoped["close"], errors="coerce")
    return scoped.dropna(subset=["ts", "session_segment_id", "close"])


def build_observation_grid(
    frame: pd.DataFrame,
    *,
    tick_size: float = DEFAULT_TICK_SIZE,
    lookback_rows: int = DEFAULT_LOOKBACK_ROWS,
    step_rows: int = DEFAULT_OBSERVATION_STEP_ROWS,
    min_counter: int = DEFAULT_MIN_COUNTER,
) -> pd.DataFrame:
    scoped = filter_scope(frame)
    if scoped.empty:
        return scoped.assign(
            valid_row_counter=pd.Series(dtype="int64"),
            return_60m_ticks=pd.Series(dtype="float64"),
            prior_vol_60m_ticks=pd.Series(dtype="float64"),
            observation_id=pd.Series(dtype="int64"),
        )

    grouped_close = scoped.groupby("session_segment_id", sort=False)["close"]
    scoped["valid_row_counter"] = grouped_close.cumcount() + 1
    scoped["close_lag"] = grouped_close.shift(lookback_rows)
    scoped["return_60m_ticks"] = (scoped["close"] - scoped["close_lag"]) / tick_size
    scoped["close_diff_ticks"] = grouped_close.diff() / tick_size
    scoped["prior_vol_60m_ticks"] = (
        scoped.groupby("session_segment_id", sort=False)["close_diff_ticks"]
        .rolling(window=lookback_rows, min_periods=lookback_rows)
        .std()
        .reset_index(level=0, drop=True)
    )

    observation_mask = (
        (scoped["valid_row_counter"] % step_rows == 0)
        & (scoped["valid_row_counter"] >= min_counter)
        & scoped["return_60m_ticks"].notna()
        & scoped["prior_vol_60m_ticks"].notna()
    )
    observations = scoped.loc[observation_mask].copy()
    observations = observations.sort_values(["session_segment_id", "ts"], kind="mergesort")
    observations["observation_id"] = np.arange(len(observations), dtype=np.int64)
    return observations.reset_index(drop=True)


def fit_train_vol_floor(
    observations: pd.DataFrame,
    train_mask: pd.Series | np.ndarray | Sequence[bool],
    *,
    quantile: float = 0.10,
) -> float:
    train = observations.loc[pd.Series(train_mask, index=observations.index)]
    positive = pd.to_numeric(train["prior_vol_60m_ticks"], errors="coerce")
    positive = positive[(positive > 0) & positive.notna()]
    if positive.empty:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            ["train fold has no positive prior_vol_60m_ticks values for volatility floor"],
        )
    return float(positive.quantile(quantile))


def assign_states(
    observations: pd.DataFrame,
    *,
    train_vol_floor_ticks: float,
    threshold: float = DEFAULT_THRESHOLD,
) -> pd.DataFrame:
    if train_vol_floor_ticks <= 0 or not math.isfinite(train_vol_floor_ticks):
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            [f"invalid train_vol_floor_ticks: {train_vol_floor_ticks}"],
        )
    out = observations.copy()
    denominator = np.maximum(
        pd.to_numeric(out["prior_vol_60m_ticks"], errors="coerce").to_numpy(dtype=float),
        train_vol_floor_ticks,
    )
    out["normalized_return"] = pd.to_numeric(
        out["return_60m_ticks"],
        errors="coerce",
    ).to_numpy(dtype=float) / denominator
    out["state"] = "sideways"
    out.loc[out["normalized_return"] >= threshold, "state"] = "bull_up"
    out.loc[out["normalized_return"] <= -threshold, "state"] = "bear_down"
    return out


def build_state_transitions(observations: pd.DataFrame) -> pd.DataFrame:
    required = {"session_segment_id", "ts", "state"}
    missing = sorted(required - set(observations.columns))
    if missing:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            ["missing transition columns: " + ", ".join(missing)],
        )
    work = observations.sort_values(["session_segment_id", "ts"], kind="mergesort").copy()
    grouped = work.groupby("session_segment_id", sort=False)
    work["next_state"] = grouped["state"].shift(-1)
    work["next_ts"] = grouped["ts"].shift(-1)
    work["next_session_segment_id"] = grouped["session_segment_id"].shift(-1)
    transitions = work[work["next_state"].notna()].copy()
    validate_no_cross_session_transitions(transitions)
    return transitions.reset_index(drop=True)


def validate_no_cross_session_transitions(transitions: pd.DataFrame) -> None:
    if "next_session_segment_id" not in transitions.columns:
        return
    bad = transitions[
        transitions["session_segment_id"].astype(str)
        != transitions["next_session_segment_id"].astype(str)
    ]
    if not bad.empty:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            [f"cross-session transitions detected: {len(bad)}"],
        )


def transition_count_matrix(transitions: pd.DataFrame) -> pd.DataFrame:
    counts = pd.DataFrame(0, index=STATE_ORDER, columns=STATE_ORDER, dtype=int)
    if transitions.empty:
        return counts
    for row in transitions[["state", "next_state"]].itertuples(index=False):
        state = str(row.state)
        next_state = str(row.next_state)
        if state in counts.index and next_state in counts.columns:
            counts.loc[state, next_state] += 1
    return counts


def normalize_transition_counts(counts: pd.DataFrame) -> pd.DataFrame:
    probs = counts.astype(float).copy()
    row_sums = probs.sum(axis=1)
    for state in probs.index:
        if row_sums.loc[state] > 0:
            probs.loc[state] = probs.loc[state] / row_sums.loc[state]
        else:
            probs.loc[state] = 0.0
    return probs


def laplace_transition_probs(counts: pd.DataFrame, *, alpha: float = 1.0) -> pd.DataFrame:
    smoothed = counts.astype(float) + alpha
    return smoothed.div(smoothed.sum(axis=1), axis=0)


def state_count_summary(
    train_observations: pd.DataFrame,
    train_transitions: pd.DataFrame,
    test_observations: pd.DataFrame,
) -> dict[str, int]:
    summary: dict[str, int] = {
        "train_observations": int(len(train_observations)),
        "test_observations": int(len(test_observations)),
    }
    train_counts = train_observations["state"].value_counts()
    test_counts = test_observations["state"].value_counts()
    outgoing_counts = train_transitions["state"].value_counts()
    for state in STATE_ORDER:
        summary[f"train_state_{state}"] = int(train_counts.get(state, 0))
        summary[f"test_state_{state}"] = int(test_counts.get(state, 0))
        summary[f"train_outgoing_{state}"] = int(outgoing_counts.get(state, 0))
    return summary


def sparse_state_blockers(
    train_observations: pd.DataFrame,
    train_transitions: pd.DataFrame,
    test_observations: pd.DataFrame,
    *,
    rules: StateCountRules = StateCountRules(),
) -> list[str]:
    summary = state_count_summary(train_observations, train_transitions, test_observations)
    blockers: list[str] = []
    if summary["train_observations"] < rules.min_train_observations:
        blockers.append(
            f"train observations {summary['train_observations']} < {rules.min_train_observations}"
        )
    if summary["test_observations"] < rules.min_test_observations:
        blockers.append(
            f"test observations {summary['test_observations']} < {rules.min_test_observations}"
        )
    for state in STATE_ORDER:
        if summary[f"train_state_{state}"] < rules.min_train_state_observations:
            blockers.append(
                f"train state {state} observations {summary[f'train_state_{state}']} "
                f"< {rules.min_train_state_observations}"
            )
        if summary[f"train_outgoing_{state}"] < rules.min_train_state_transitions:
            blockers.append(
                f"train state {state} outgoing transitions {summary[f'train_outgoing_{state}']} "
                f"< {rules.min_train_state_transitions}"
            )
        if summary[f"test_state_{state}"] < rules.min_test_state_observations:
            blockers.append(
                f"test state {state} observations {summary[f'test_state_{state}']} "
                f"< {rules.min_test_state_observations}"
            )
    return blockers


def probability_vector_from_state(
    transition_probs: pd.DataFrame,
    state: str,
    *,
    fallback: Mapping[str, float] | None = None,
) -> dict[str, float]:
    if state in transition_probs.index and float(transition_probs.loc[state].sum()) > 0:
        return {target: float(transition_probs.loc[state, target]) for target in STATE_ORDER}
    if fallback is not None:
        return {target: float(fallback.get(target, 0.0)) for target in STATE_ORDER}
    return {target: 1.0 / len(STATE_ORDER) for target in STATE_ORDER}


def next_state_base_rates(train_transitions: pd.DataFrame) -> dict[str, float]:
    counts = train_transitions["next_state"].value_counts()
    total = sum(int(counts.get(state, 0)) for state in STATE_ORDER)
    if total <= 0:
        return {state: 1.0 / len(STATE_ORDER) for state in STATE_ORDER}
    return {state: float(counts.get(state, 0) / total) for state in STATE_ORDER}


def log_loss_for_rows(probability_rows: Sequence[Mapping[str, float]], actual_states: Sequence[str]) -> float:
    losses: list[float] = []
    epsilon = 1e-15
    for probs, actual in zip(probability_rows, actual_states):
        probability = min(max(float(probs.get(actual, 0.0)), epsilon), 1.0)
        losses.append(-math.log(probability))
    return float(np.mean(losses)) if losses else math.nan


def brier_score_for_rows(probability_rows: Sequence[Mapping[str, float]], actual_states: Sequence[str]) -> float:
    scores: list[float] = []
    for probs, actual in zip(probability_rows, actual_states):
        total = 0.0
        for state in STATE_ORDER:
            observed = 1.0 if state == actual else 0.0
            total += (float(probs.get(state, 0.0)) - observed) ** 2
        scores.append(total)
    return float(np.mean(scores)) if scores else math.nan


def score_probability_rows(
    probability_rows: Sequence[Mapping[str, float]],
    actual_states: Sequence[str],
) -> dict[str, float]:
    return {
        "row_count": int(len(actual_states)),
        "log_loss": log_loss_for_rows(probability_rows, actual_states),
        "brier": brier_score_for_rows(probability_rows, actual_states),
    }


def markov_probability_rows(
    transitions: pd.DataFrame,
    transition_probs: pd.DataFrame,
    *,
    fallback: Mapping[str, float] | None = None,
) -> list[dict[str, float]]:
    return [
        probability_vector_from_state(transition_probs, str(state), fallback=fallback)
        for state in transitions["state"].tolist()
    ]


def persistence_probability_rows(transitions: pd.DataFrame) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for state in transitions["state"].tolist():
        rows.append({target: 1.0 if target == state else 0.0 for target in STATE_ORDER})
    return rows


def constant_probability_rows(
    transitions: pd.DataFrame,
    probabilities: Mapping[str, float],
) -> list[dict[str, float]]:
    row = {state: float(probabilities.get(state, 0.0)) for state in STATE_ORDER}
    return [dict(row) for _ in range(len(transitions))]


def shuffled_actual_states(
    transitions: pd.DataFrame,
    *,
    seed: int = SHUFFLE_SEED,
) -> list[str]:
    actual = transitions["next_state"].astype(str).to_numpy(copy=True)
    rng = np.random.default_rng(seed)
    rng.shuffle(actual)
    return actual.tolist()


def timing_shift_actual_states(transitions: pd.DataFrame) -> list[str]:
    if transitions.empty:
        return []
    work = transitions.sort_values(["session_segment_id", "ts"], kind="mergesort").copy()
    shifted = work.groupby("session_segment_id", sort=False)["next_state"].shift(1)
    return shifted.dropna().astype(str).tolist()


def build_baseline_null_scores(
    train_transitions: pd.DataFrame,
    test_transitions: pd.DataFrame,
    transition_probs: pd.DataFrame,
    *,
    seed: int = SHUFFLE_SEED,
) -> list[dict[str, Any]]:
    actual = test_transitions["next_state"].astype(str).tolist()
    base_rates = next_state_base_rates(train_transitions)
    markov_rows = markov_probability_rows(test_transitions, transition_probs, fallback=base_rates)

    rows: list[dict[str, Any]] = []
    for forecast_id, probability_rows, actual_states in (
        ("markov_transition", markov_rows, actual),
        ("train_unconditional_next_state", constant_probability_rows(test_transitions, base_rates), actual),
        ("same_state_persistence", persistence_probability_rows(test_transitions), actual),
        ("shuffled_label_null", markov_rows, shuffled_actual_states(test_transitions, seed=seed)),
    ):
        score = score_probability_rows(probability_rows, actual_states)
        rows.append({"forecast_id": forecast_id, **score})

    shifted_actual = timing_shift_actual_states(test_transitions)
    if shifted_actual:
        markov_rows_by_index = pd.Series(markov_rows, index=test_transitions.index)
        shifted_work = test_transitions.sort_values(
            ["session_segment_id", "ts"],
            kind="mergesort",
        ).copy()
        shifted_work["_shifted_next_state"] = shifted_work.groupby(
            "session_segment_id",
            sort=False,
        )["next_state"].shift(1)
        shifted_probability_rows = [
            markov_rows_by_index.loc[index]
            for index in shifted_work[shifted_work["_shifted_next_state"].notna()].index
        ]
        rows.append(
            {
                "forecast_id": "timing_shift_null",
                **score_probability_rows(shifted_probability_rows, shifted_actual),
            }
        )
    else:
        rows.append(
            {
                "forecast_id": "timing_shift_null",
                "row_count": 0,
                "log_loss": math.nan,
                "brier": math.nan,
            }
        )
    return rows


def parse_utc_timestamp(value: object, *, field_name: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(value).tz_convert("UTC")
    except TypeError:
        try:
            return pd.Timestamp(value).tz_localize("UTC")
        except Exception as exc:
            raise DiagnosticStop(
                STOP_INPUT_FAILURE,
                [f"invalid timestamp for {field_name}: {value}"],
            ) from exc
    except Exception as exc:
        raise DiagnosticStop(
            STOP_INPUT_FAILURE,
            [f"invalid timestamp for {field_name}: {value}"],
        ) from exc


def extract_es_research_folds(split_plan: Mapping[str, Any]) -> list[FoldWindow]:
    raw_folds = split_plan.get("folds")
    if not isinstance(raw_folds, list):
        raise DiagnosticStop(STOP_INPUT_FAILURE, ["split_plan folds is missing or not a list"])

    folds_by_id: dict[str, Mapping[str, Any]] = {}
    for raw in raw_folds:
        if not isinstance(raw, Mapping):
            continue
        fold_id = str(raw.get("fold_id", ""))
        if raw.get("market") == MARKET and fold_id in EXPECTED_FOLD_IDS:
            folds_by_id[fold_id] = raw

    missing = [fold_id for fold_id in EXPECTED_FOLD_IDS if fold_id not in folds_by_id]
    if missing:
        raise DiagnosticStop(STOP_INPUT_FAILURE, ["missing ES research folds: " + ", ".join(missing)])

    fold_windows: list[FoldWindow] = []
    failures: list[str] = []
    for fold_id in EXPECTED_FOLD_IDS:
        raw = folds_by_id[fold_id]
        if str(raw.get("split_group")) != "research":
            failures.append(f"{fold_id}: split_group is not research")
        if bool(raw.get("final_holdout")) or bool(raw.get("is_final_holdout")):
            failures.append(f"{fold_id}: final holdout fold is forbidden")
        if raw.get("selection_allowed") is False:
            failures.append(f"{fold_id}: selection_allowed is false")
        train_end_value = raw.get("purged_train_end") or raw.get("train_end")
        fold_windows.append(
            FoldWindow(
                fold_id=fold_id,
                train_start=parse_utc_timestamp(raw.get("train_start"), field_name=f"{fold_id}.train_start"),
                train_end=parse_utc_timestamp(train_end_value, field_name=f"{fold_id}.train_end"),
                test_start=parse_utc_timestamp(raw.get("test_start"), field_name=f"{fold_id}.test_start"),
                test_end=parse_utc_timestamp(raw.get("test_end"), field_name=f"{fold_id}.test_end"),
            )
        )
    if failures:
        raise DiagnosticStop(STOP_INPUT_FAILURE, failures)
    return fold_windows


def fold_masks(observations: pd.DataFrame, fold: FoldWindow) -> tuple[pd.Series, pd.Series]:
    ts = pd.to_datetime(observations["ts"], utc=True)
    train_mask = (ts >= fold.train_start) & (ts <= fold.train_end)
    test_mask = (ts >= fold.test_start) & (ts <= fold.test_end)
    return train_mask, test_mask


def fold_diagnostic(
    observations: pd.DataFrame,
    fold: FoldWindow,
    *,
    rules: StateCountRules = StateCountRules(),
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    train_mask, test_mask = fold_masks(observations, fold)
    train_vol_floor = fit_train_vol_floor(observations, train_mask)
    stated = assign_states(
        observations,
        train_vol_floor_ticks=train_vol_floor,
        threshold=threshold,
    )
    train_observations = stated.loc[train_mask].copy()
    test_observations = stated.loc[test_mask].copy()
    train_transitions = build_state_transitions(train_observations)
    test_transitions = build_state_transitions(test_observations)
    counts = transition_count_matrix(train_transitions)
    probs = normalize_transition_counts(counts)
    blockers = sparse_state_blockers(
        train_observations,
        train_transitions,
        test_observations,
        rules=rules,
    )
    baseline_scores: list[dict[str, Any]] = []
    if not blockers:
        baseline_scores = build_baseline_null_scores(train_transitions, test_transitions, probs)
    return {
        "fold_id": fold.fold_id,
        "train_vol_floor_ticks": train_vol_floor,
        "state_count_summary": state_count_summary(
            train_observations,
            train_transitions,
            test_observations,
        ),
        "sparse_state_blockers": blockers,
        "transition_counts": counts,
        "transition_probs": probs,
        "laplace_transition_probs": laplace_transition_probs(counts),
        "baseline_scores": baseline_scores,
    }


def matrix_to_rows(fold_id: str, matrix: pd.DataFrame, *, matrix_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for state in STATE_ORDER:
        for next_state in STATE_ORDER:
            rows.append(
                {
                    "fold_id": fold_id,
                    "matrix_type": matrix_type,
                    "state": state,
                    "next_state": next_state,
                    "value": float(matrix.loc[state, next_state]),
                }
            )
    return rows


def build_stress_grid_rows(*, executed: bool = False) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, combo in enumerate(STRESS_GRID, start=1):
        rows.append(
            {
                "trial_id": f"stress_grid_{index:02d}",
                "lookback_rows": combo["lookback_rows"],
                "threshold": combo["threshold"],
                "horizon_steps": combo["horizon_steps"],
                "matrix_power_diagnostics": list(MATRIX_POWER_DIAGNOSTICS),
                "status": "NOT_RUN_SEPARATE_APPROVAL_REQUIRED" if not executed else "RUN",
                "winner_selection_allowed": False,
            }
        )
    return rows


def build_input_manifest(repo_root: Path, input_paths: Mapping[str, Path], *, generated_at_utc: str) -> dict[str, Any]:
    return {
        "diagnostic_id": "markov_regime_es_intraday_v1",
        "generated_at_utc": generated_at_utc,
        "git_commit": git_commit(repo_root),
        "market": MARKET,
        "years": list(YEARS),
        "fold_ids": list(EXPECTED_FOLD_IDS),
        "max_runtime_seconds": MAX_RUNTIME_SECONDS,
        "provider_network_calls_allowed": 0,
        "non_approval_statement": (
            "Report-only regime diagnostic; not alpha evidence, not sizing, not promotion, "
            "not paper/live readiness, and not HMM approval."
        ),
        "inputs": {
            name: {
                "path": repo_relative(repo_root, path),
                "sha256": file_sha256(path),
            }
            for name, path in sorted(input_paths.items())
        },
        "required_feature_columns": list(REQUIRED_FEATURE_COLUMNS),
    }


def run_diagnostic(
    *,
    repo_root: Path,
    input_paths: Mapping[str, Path],
    generated_at_utc: str | None = None,
    rules: StateCountRules = StateCountRules(),
) -> dict[str, Any]:
    generated_at_utc = generated_at_utc or utc_now()
    validate_input_paths(input_paths)

    split_plan = read_json_object(input_paths["split_plan"])
    folds = extract_es_research_folds(split_plan)
    feature_frames = [
        load_feature_frame(input_paths["feature_2023"]),
        load_feature_frame(input_paths["feature_2024"]),
    ]
    feature_frame = pd.concat(feature_frames, ignore_index=True)
    observations = build_observation_grid(feature_frame)

    fold_results = [
        fold_diagnostic(observations, fold, rules=rules)
        for fold in folds
    ]
    sparse_blockers = [
        f"{result['fold_id']}: {blocker}"
        for result in fold_results
        for blocker in result["sparse_state_blockers"]
    ]
    status = STOP_SPARSE_STATE_COVERAGE if sparse_blockers else PASS_DIAGNOSTIC_REPORT_ONLY

    fold_state_counts = [
        {"fold_id": result["fold_id"], **result["state_count_summary"]}
        for result in fold_results
    ]
    fold_transition_matrices: list[dict[str, Any]] = []
    baseline_null_scores: list[dict[str, Any]] = []
    fold_forecast_scores: list[dict[str, Any]] = []
    for result in fold_results:
        fold_id = str(result["fold_id"])
        fold_transition_matrices.extend(
            matrix_to_rows(fold_id, result["transition_counts"], matrix_type="raw_count")
        )
        fold_transition_matrices.extend(
            matrix_to_rows(fold_id, result["transition_probs"], matrix_type="primary_probability")
        )
        fold_transition_matrices.extend(
            matrix_to_rows(
                fold_id,
                result["laplace_transition_probs"],
                matrix_type="laplace_alpha_1_probability_diagnostic",
            )
        )
        for score in result["baseline_scores"]:
            score_row = {"fold_id": fold_id, **score}
            baseline_null_scores.append(score_row)
            if score["forecast_id"] == "markov_transition":
                fold_forecast_scores.append(score_row)

    input_manifest = build_input_manifest(
        repo_root,
        input_paths,
        generated_at_utc=generated_at_utc,
    )
    stress_grid_rows = build_stress_grid_rows(executed=False)
    report = {
        "diagnostic_id": "markov_regime_es_intraday_v1",
        "generated_at_utc": generated_at_utc,
        "status": status,
        "model_trust_readiness": False,
        "sparse_state_blockers": sparse_blockers,
        "fold_count": len(fold_results),
        "observation_count": int(len(observations)),
        "fold_ids": [result["fold_id"] for result in fold_results],
        "baseline_null_status": "NOT_SCORED_SPARSE_STATE_COVERAGE"
        if sparse_blockers
        else "SCORED_REPORT_ONLY",
        "non_approval_statement": input_manifest["non_approval_statement"],
    }
    trial_accounting = {
        "diagnostic_id": "markov_regime_es_intraday_v1",
        "winner_selection_allowed": False,
        "stress_grid_execution_approved": False,
        "stress_grid_rows": stress_grid_rows,
    }
    return {
        "input_manifest": input_manifest,
        "report": report,
        "fold_state_counts": fold_state_counts,
        "fold_transition_matrices": fold_transition_matrices,
        "fold_forecast_scores": fold_forecast_scores,
        "baseline_null_scores": baseline_null_scores,
        "stress_grid_results": stress_grid_rows,
        "trial_accounting": trial_accounting,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def write_markdown_report(path: Path, report: Mapping[str, Any]) -> None:
    lines = [
        "# Markov Regime ES Intraday V1 Diagnostic",
        "",
        f"- Status: `{report['status']}`",
        f"- Model-trust readiness: `{report['model_trust_readiness']}`",
        f"- Fold count: `{report['fold_count']}`",
        f"- Observation count: `{report['observation_count']}`",
        f"- Baseline/null status: `{report['baseline_null_status']}`",
        f"- Non-approval: {report['non_approval_statement']}",
        "",
        "## Sparse State Blockers",
        "",
    ]
    blockers = report.get("sparse_state_blockers") or []
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_outputs(output_root: Path, payload: Mapping[str, Any]) -> None:
    intended_paths = expected_output_paths(output_root)
    validate_output_root_available(output_root)
    validate_expected_output_paths(output_root, intended_paths)
    output_root.mkdir(parents=True, exist_ok=False)

    write_json(output_root / "input_manifest.json", payload["input_manifest"])
    write_json(output_root / "markov_regime_es_intraday_v1_report.json", payload["report"])
    write_markdown_report(
        output_root / "markov_regime_es_intraday_v1_report.md",
        payload["report"],
    )
    write_csv(output_root / "fold_state_counts.csv", payload["fold_state_counts"])
    write_csv(output_root / "fold_transition_matrices.csv", payload["fold_transition_matrices"])
    write_csv(output_root / "fold_forecast_scores.csv", payload["fold_forecast_scores"])
    write_csv(output_root / "baseline_null_scores.csv", payload["baseline_null_scores"])
    write_csv(output_root / "stress_grid_results.csv", payload["stress_grid_results"])
    write_json(output_root / "trial_accounting.json", payload["trial_accounting"])

    actual_files = {path for path in output_root.iterdir() if path.is_file()}
    validate_expected_output_paths(output_root, actual_files)


def build_default_input_paths(repo_root: Path) -> dict[str, Path]:
    return {name: resolve_path(repo_root, path) for name, path in DEFAULT_INPUT_PATHS.items()}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the guarded ES Markov regime diagnostic report."
    )
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--approve-diagnostic-run", action="store_true")
    parser.add_argument("--approval-token", default="")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_root = resolve_path(repo_root, args.output_root)
    validate_output_root_is_expected(repo_root, output_root)
    if not args.approve_diagnostic_run or args.approval_token != "RUN_MARKOV_REGIME_DIAGNOSTIC_V1":
        raise SystemExit(
            "Diagnostic execution is not approved. Re-run only with "
            "--approve-diagnostic-run --approval-token RUN_MARKOV_REGIME_DIAGNOSTIC_V1 "
            "after separate explicit approval."
        )

    payload = run_diagnostic(
        repo_root=repo_root,
        input_paths=build_default_input_paths(repo_root),
    )
    write_outputs(output_root, payload)
    print(json.dumps({"status": payload["report"]["status"], "output_root": output_root.as_posix()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
