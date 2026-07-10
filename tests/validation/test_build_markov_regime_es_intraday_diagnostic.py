from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.validation import build_markov_regime_es_intraday_diagnostic as diag


def _session_frame(
    *,
    session_id: str,
    start: str,
    closes: list[float],
    market: str = "ES",
    year: int = 2023,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range(start=start, periods=len(closes), freq="min", tz="UTC"),
            "market": market,
            "year": year,
            "session_segment_id": session_id,
            "close": closes,
            "feature_row_valid": True,
            "training_row_valid": True,
        }
    )


def _state_observations(states: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2023-01-01", periods=len(states), freq="30min", tz="UTC"),
            "session_segment_id": ["s1"] * len(states),
            "state": states,
        }
    )


def test_required_input_path_and_column_validation(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.json"
    with pytest.raises(diag.DiagnosticStop) as missing_exc:
        diag.validate_input_paths({"split_plan": missing_path})

    assert missing_exc.value.status == diag.STOP_INPUT_FAILURE
    assert "missing required input split_plan" in str(missing_exc.value)

    frame = pd.DataFrame({"ts": pd.date_range("2023-01-01", periods=1, tz="UTC")})
    with pytest.raises(diag.DiagnosticStop) as column_exc:
        diag.validate_required_columns(frame)

    assert column_exc.value.status == diag.STOP_INPUT_FAILURE
    assert "missing required feature columns" in str(column_exc.value)


def test_observation_grid_uses_30_minute_same_session_rows() -> None:
    frame = pd.concat(
        [
            _session_frame(
                session_id="s1",
                start="2023-01-01T14:30:00Z",
                closes=(100 + np.sin(np.arange(120) / 5.0)).tolist(),
            ),
            _session_frame(
                session_id="s2",
                start="2023-01-02T14:30:00Z",
                closes=(200 + np.cos(np.arange(120) / 7.0)).tolist(),
            ),
        ],
        ignore_index=True,
    )

    observations = diag.build_observation_grid(frame)
    transitions = diag.build_state_transitions(
        observations.assign(state=["bull_up", "bear_down", "sideways", "bull_up"])
    )

    assert observations["session_segment_id"].tolist() == ["s1", "s1", "s2", "s2"]
    assert observations["valid_row_counter"].tolist() == [90, 120, 90, 120]
    assert len(transitions) == 2
    assert transitions["session_segment_id"].tolist() == ["s1", "s2"]


def test_cross_session_transition_rejection() -> None:
    transitions = pd.DataFrame(
        {
            "session_segment_id": ["s1"],
            "next_session_segment_id": ["s2"],
            "state": ["bull_up"],
            "next_state": ["bear_down"],
        }
    )

    with pytest.raises(diag.DiagnosticStop) as exc:
        diag.validate_no_cross_session_transitions(transitions)

    assert exc.value.status == diag.STOP_INPUT_FAILURE
    assert "cross-session transitions detected" in str(exc.value)


def test_state_inputs_do_not_use_future_rows() -> None:
    base_closes = (100 + np.sin(np.arange(130) / 4.0)).tolist()
    frame = _session_frame(
        session_id="s1",
        start="2023-01-01T14:30:00Z",
        closes=base_closes,
    )
    mutated = frame.copy()
    mutated.loc[100:, "close"] = mutated.loc[100:, "close"] + 50.0

    base = diag.build_observation_grid(frame)
    changed = diag.build_observation_grid(mutated)

    base_row_90 = base.loc[base["valid_row_counter"] == 90].iloc[0]
    changed_row_90 = changed.loc[changed["valid_row_counter"] == 90].iloc[0]
    assert changed_row_90["return_60m_ticks"] == pytest.approx(base_row_90["return_60m_ticks"])
    assert changed_row_90["prior_vol_60m_ticks"] == pytest.approx(base_row_90["prior_vol_60m_ticks"])


def test_train_only_vol_floor_and_state_thresholds_ignore_test_extremes() -> None:
    observations = pd.DataFrame(
        {
            "return_60m_ticks": [3.0, -3.0, 0.1, 1000.0],
            "prior_vol_60m_ticks": [1.0, 2.0, 1.0, 0.0001],
        }
    )
    train_mask = pd.Series([True, True, True, False])

    floor = diag.fit_train_vol_floor(observations, train_mask)
    stated = diag.assign_states(
        observations,
        train_vol_floor_ticks=floor,
        threshold=1.0,
    )

    assert floor == pytest.approx(1.0)
    assert stated["state"].tolist() == ["bull_up", "bear_down", "sideways", "bull_up"]


def test_transition_count_and_row_normalization_math() -> None:
    transitions = pd.DataFrame(
        {
            "state": ["bull_up", "bull_up", "bear_down", "sideways"],
            "next_state": ["bull_up", "bear_down", "sideways", "bear_down"],
        }
    )

    counts = diag.transition_count_matrix(transitions)
    probs = diag.normalize_transition_counts(counts)

    assert counts.loc["bull_up", "bull_up"] == 1
    assert counts.loc["bull_up", "bear_down"] == 1
    assert counts.loc["bear_down", "sideways"] == 1
    assert probs.loc["bull_up", "bull_up"] == pytest.approx(0.5)
    assert probs.loc["bull_up", "bear_down"] == pytest.approx(0.5)
    assert probs.loc["sideways", "bear_down"] == pytest.approx(1.0)


def test_sparse_state_blockers_are_fail_closed() -> None:
    train_observations = _state_observations(["bull_up", "bull_up", "sideways"])
    train_transitions = diag.build_state_transitions(train_observations)
    test_observations = _state_observations(["bull_up", "sideways"])
    rules = diag.StateCountRules(
        min_train_observations=3,
        min_test_observations=2,
        min_train_state_observations=1,
        min_train_state_transitions=1,
        min_test_state_observations=1,
    )

    blockers = diag.sparse_state_blockers(
        train_observations,
        train_transitions,
        test_observations,
        rules=rules,
    )

    assert any("train state bear_down observations 0 < 1" in item for item in blockers)
    assert any("test state bear_down observations 0 < 1" in item for item in blockers)


def test_baseline_and_null_scores_are_constructed_deterministically() -> None:
    train = diag.build_state_transitions(
        _state_observations(["bull_up", "bull_up", "bear_down", "sideways", "sideways"])
    )
    test = diag.build_state_transitions(
        _state_observations(["bull_up", "bear_down", "sideways", "bull_up", "sideways"])
    )
    probs = diag.normalize_transition_counts(diag.transition_count_matrix(train))

    first = diag.build_baseline_null_scores(train, test, probs)
    second = diag.build_baseline_null_scores(train, test, probs)

    assert [row["forecast_id"] for row in first] == [
        "markov_transition",
        "train_unconditional_next_state",
        "same_state_persistence",
        "shuffled_label_null",
        "timing_shift_null",
    ]
    assert first == second
    assert first[3]["row_count"] == len(test)


def test_existing_output_root_and_unexpected_paths_fail_closed(tmp_path: Path) -> None:
    output_root = tmp_path / "reports" / "model_trust_audit" / "markov_regime_es_intraday_v1"
    output_root.mkdir(parents=True)

    diag.validate_output_root_is_expected(tmp_path, output_root)
    with pytest.raises(diag.DiagnosticStop) as root_exc:
        diag.validate_output_root_is_expected(tmp_path, tmp_path / "reports" / "wrong_root")

    assert root_exc.value.status == diag.STOP_INPUT_FAILURE
    assert "unexpected output root" in str(root_exc.value)

    with pytest.raises(diag.DiagnosticStop) as existing_exc:
        diag.validate_output_root_available(output_root)

    assert existing_exc.value.status == diag.STOP_INPUT_FAILURE
    assert "output root already exists" in str(existing_exc.value)

    unexpected_paths = diag.expected_output_paths(output_root) | {output_root / "extra.csv"}
    with pytest.raises(diag.DiagnosticStop) as path_exc:
        diag.validate_expected_output_paths(output_root, unexpected_paths)

    assert path_exc.value.status == diag.STOP_INPUT_FAILURE
    assert "unexpected output paths" in str(path_exc.value)


def test_es_fold_parser_requires_all_12_non_holdout_research_folds() -> None:
    folds = []
    for index, fold_id in enumerate(diag.EXPECTED_FOLD_IDS, start=1):
        folds.append(
            {
                "market": "ES",
                "fold_id": fold_id,
                "fold_number": index,
                "split_group": "research",
                "train_start": "2023-01-01T00:00:00+00:00",
                "purged_train_end": "2023-12-31T23:00:00+00:00",
                "test_start": "2024-01-01T00:00:00+00:00",
                "test_end": "2024-01-31T23:00:00+00:00",
                "final_holdout": False,
                "is_final_holdout": False,
                "selection_allowed": True,
            }
        )

    parsed = diag.extract_es_research_folds({"folds": folds})
    assert [fold.fold_id for fold in parsed] == list(diag.EXPECTED_FOLD_IDS)

    folds[-1]["final_holdout"] = True
    with pytest.raises(diag.DiagnosticStop) as exc:
        diag.extract_es_research_folds({"folds": folds})

    assert exc.value.status == diag.STOP_INPUT_FAILURE
    assert "final holdout fold is forbidden" in str(exc.value)
