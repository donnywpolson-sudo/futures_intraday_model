import copy
from pathlib import Path

from scripts.validation import validate_hardened_wfa_split_plan as validator


MARKETS = list(validator.DEFAULT_MARKETS)
YEARS = list(validator.DEFAULT_YEARS)


def _input_hashes() -> dict[str, str]:
    return {
        f"data/feature_matrices/{market}/{year}.parquet": f"{market}{year}".encode().hex().ljust(64, "0")[:64]
        for market in MARKETS
        for year in YEARS
    }


def _fold(market: str) -> dict[str, object]:
    return {
        "market": market,
        "fold_id": f"{market}_hardened_0001",
        "fold_number": 1,
        "year": 2024,
        "split_group": "hardened_research",
        "train_start": "2023-01-02T00:00:00+00:00",
        "train_end": "2023-12-29T23:59:00+00:00",
        "purged_train_end": "2023-12-29T22:58:00+00:00",
        "validation_start": "2024-01-02T00:00:00+00:00",
        "validation_end": "2024-06-28T20:58:00+00:00",
        "validation_embargo_end": "2024-06-28T21:59:00+00:00",
        "test_start": "2024-07-01T00:00:00+00:00",
        "test_end": "2024-12-27T20:58:00+00:00",
        "test_embargo_end": "2024-12-27T21:59:00+00:00",
        "train_rows_before_purge": 100,
        "train_rows_after_purge": 90,
        "purged_train_rows": 10,
        "validation_rows": 70,
        "validation_embargo_rows": 10,
        "test_rows": 70,
        "test_embargo_rows": 10,
        "purge_bars": 10,
        "resolved_purge_bars": 10,
        "embargo_bars": 10,
        "hardened_split_type": "fixed_train_validation_test",
        "independent_test_claim_allowed": True,
        "selection_source": "validation_only",
        "is_final_holdout": False,
        "final_holdout": False,
    }


def _split_plan() -> dict[str, object]:
    return {
        "status": "PASS_HARDENED_PHASE5_SPLIT_PLAN_BUILT_NO_MODELING",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "input_root": "data/feature_matrices",
        "markets": MARKETS,
        "years": YEARS,
        "fold_count": 4,
        "failure_count": 0,
        "purge_policy": {"purge_bars": 10, "resolved_purge_bars": 10, "embargo_bars": 10},
        "input_file_hashes": _input_hashes(),
        "folds": [_fold(market) for market in MARKETS],
    }


def _report(split_plan: dict[str, object]) -> dict[str, object]:
    return validator.build_acceptance_report(
        split_plan=split_plan,
        split_plan_path=Path("reports/wfa/hardened/split_plan.json"),
        reports_root=Path("reports/wfa/hardened"),
        min_train_rows=50,
        min_validation_rows=50,
        min_test_rows=50,
        minimum_required_bars=10,
        generated_at_utc="2026-07-09T00:00:00Z",
    )


def test_accepts_hardened_split_plan() -> None:
    report = _report(_split_plan())

    assert report["status"] == validator.PASS_STATUS
    assert report["summary"]["failure_count"] == 0
    assert report["summary"]["independent_test_claim_allowed"] is True
    assert report["summary"]["modeling_allowed"] is False


def test_rejects_missing_validation_window() -> None:
    plan = _split_plan()
    del plan["folds"][0]["validation_start"]

    report = _report(plan)

    assert report["status"] == validator.FAIL_STATUS
    assert any("missing fields" in failure for failure in report["failures"])


def test_rejects_overlapping_boundaries() -> None:
    plan = _split_plan()
    plan["folds"][0]["validation_end"] = "2024-07-02T00:00:00+00:00"

    report = _report(plan)

    assert report["status"] == validator.FAIL_STATUS
    assert any("overlap" in failure or "unordered" in failure for failure in report["failures"])


def test_rejects_short_purge_or_embargo() -> None:
    plan = _split_plan()
    plan["folds"][0]["validation_embargo_rows"] = 9

    report = _report(plan)

    assert report["status"] == validator.FAIL_STATUS
    assert any("validation_embargo_rows" in failure for failure in report["failures"])


def test_rejects_forward_or_final_holdout_scope() -> None:
    plan = _split_plan()
    plan["years"] = [2023, 2024, 2025]

    report = _report(plan)

    assert report["status"] == validator.FAIL_STATUS
    assert any("forbidden forward" in failure or "years mismatch" in failure for failure in report["failures"])


def test_rejects_later_fold_training_through_prior_oos_block() -> None:
    plan = _split_plan()
    extra = copy.deepcopy(plan["folds"][0])
    extra["fold_id"] = "6E_hardened_0002"
    extra["purged_train_end"] = "2024-12-27T22:00:00+00:00"
    plan["folds"].append(extra)

    report = _report(plan)

    assert report["status"] == validator.FAIL_STATUS
    assert any("prior OOS" in failure for failure in report["failures"])
