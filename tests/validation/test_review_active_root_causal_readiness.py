from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.validation import review_active_root_causal_readiness as review


def _write_exclusions(path: Path, *, data_mutation_performed: bool = False) -> None:
    payload = {
        "summary": {
            "status": "PASS_APPROVED_ACTIVE_CAUSAL_SCOPE_EXCLUSIONS_NO_RAW_DELETE",
            "provider_network_calls": False,
            "data_mutation_performed": data_mutation_performed,
            "raw_deletion_approved": False,
            "raw_deletion_performed": False,
            "causal_rebuild_approved": False,
            "causal_parquet_writes": False,
            "labels_features_wfa_predictions_modeling_approved": False,
            "commit_push_paper_live_approved": False,
        },
        "rows": [
            {
                "pair": "6M:2012",
                "market": "6M",
                "year": 2012,
                "disposition": "exclude_from_active_causal_scope_no_raw_delete",
                "reason": "historical_scope_exclusion",
            },
            {
                "pair": "TN:2010",
                "market": "TN",
                "year": 2010,
                "disposition": "exclude_from_active_causal_scope_no_raw_delete",
                "reason": "historical_scope_exclusion",
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_approved_scope_exclusions_return_exact_pairs(tmp_path: Path) -> None:
    path = tmp_path / "approved_exclusions.json"
    _write_exclusions(path)

    rows = review.approved_scope_exclusions(path)

    assert set(rows) == {("6M", 2012), ("TN", 2010)}


def test_approved_scope_exclusions_reject_mutating_report(tmp_path: Path) -> None:
    path = tmp_path / "approved_exclusions.json"
    _write_exclusions(path, data_mutation_performed=True)

    with pytest.raises(ValueError, match="data_mutation_performed"):
        review.approved_scope_exclusions(path)
