from __future__ import annotations

from pathlib import Path

from scripts.phase2_causal_base.build_causal_base_data import (
    STATISTICS_ENRICHMENT_SPARSE_EXCEPTION_CATEGORY,
    load_causal_base_config,
)


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_WARNING = "statistics enrichment sparse: missing_rows=6 stale_rows=6"
EXPECTED_EVIDENCE_PATHS = (
    "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.json",
    "reports/pipeline_audit/local_trade_es2026_p1_repair_plan_v2/readiness_warning_evidence/ES_2026_readiness_warning_evidence.md",
)


def test_tier3_forward_es2026_statistics_sparse_packet_is_exact() -> None:
    config = load_causal_base_config(
        ROOT / "configs" / "alpha_tiered.yaml",
        "tier_3_forward",
    )

    matching = [
        exception
        for exception in config.accepted_readiness_exceptions
        if (
            exception.market == "ES"
            and exception.year == 2026
            and exception.category == STATISTICS_ENRICHMENT_SPARSE_EXCEPTION_CATEGORY
        )
    ]

    assert len(matching) == 1
    exception = matching[0]
    assert exception.reason == (
        "bounded_es2026_statistics_enrichment_sparse_accepted_warning_packet_20260703"
    )
    assert exception.evidence_paths == EXPECTED_EVIDENCE_PATHS
    assert exception.warning_prefixes == (EXPECTED_WARNING,)
