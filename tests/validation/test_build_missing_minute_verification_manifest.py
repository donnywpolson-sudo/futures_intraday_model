from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.validation.build_missing_minute_verification_manifest import (
    REQUIRED_THIRD_PARTY_SOURCE_TYPE,
    build_manifest,
    main,
)


def _write_session_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "session_templates:",
                "  cme_globex_17_16_ct:",
                "    timezone: America/Chicago",
                '    regular_open: "17:00"',
                '    regular_close: "16:00"',
                "    holidays: []",
                "    closed_dates: []",
                "    early_closes: {}",
                "markets:",
                "  default:",
                "    session_template: cme_globex_17_16_ct",
                "  ZN:",
                "    session_template: cme_globex_17_16_ct",
            ]
        ),
        encoding="utf-8",
    )


def _write_config(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_3_research:",
                "    markets: [ZN]",
                "    years: [2024]",
                "aliases:",
                "  tier_3: tier_3_research",
            ]
        ),
        encoding="utf-8",
    )


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_inputs(tmp_path: Path, *, ambiguous_contract: bool = False, with_gap_id: bool = True) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_session_config(tmp_path / "configs" / "market_sessions.yaml")
    after_symbol = "ZNH4" if not ambiguous_contract else "ZNM4"
    after_id = 123 if not ambiguous_contract else 456
    _write_parquet(
        tmp_path / "data" / "raw" / "ZN" / "2024.parquet",
        [
            {
                "ts_event": "2024-01-03T14:59:00Z",
                "raw_symbol": "ZNH4",
                "instrument_id": 123,
                "source_file": "raw.dbn.zst",
                "source_sha256": "abc",
            },
            {
                "ts_event": "2024-01-03T15:03:00Z",
                "raw_symbol": after_symbol,
                "instrument_id": after_id,
                "source_file": "raw.dbn.zst",
                "source_sha256": "abc",
            },
        ],
    )
    synthetic_one = {
        "ts": "2024-01-03T15:00:00Z",
        "is_synthetic": True,
        "roll_window_flag": False,
    }
    synthetic_two = {
        "ts": "2024-01-03T15:01:00Z",
        "is_synthetic": True,
        "roll_window_flag": True,
    }
    if with_gap_id:
        synthetic_one["synthetic_gap_id"] = 7
        synthetic_two["synthetic_gap_id"] = 7
    _write_parquet(
        tmp_path / "data" / "causally_gated_normalized" / "ZN" / "2024.parquet",
        [
            {"ts": "2024-01-03T14:59:00Z", "is_synthetic": False},
            synthetic_one,
            synthetic_two,
            {"ts": "2024-01-03T15:03:00Z", "is_synthetic": False},
        ],
    )


def _args(tmp_path: Path) -> object:
    return type(
        "Args",
        (),
        {
            "profile": "tier_3",
            "config": str(tmp_path / "configs" / "alpha_tiered.yaml"),
            "markets": None,
            "years": None,
            "raw_root": str(tmp_path / "data" / "raw"),
            "causal_root": str(tmp_path / "data" / "causally_gated_normalized"),
            "session_config": str(tmp_path / "configs" / "market_sessions.yaml"),
            "json_out": str(tmp_path / "reports" / "manifest.json"),
            "md_out": str(tmp_path / "reports" / "manifest.md"),
            "buffer_minutes": 2,
            "allow_unresolved_contracts": False,
        },
    )()


def test_groups_contiguous_synthetic_rows_into_windows(tmp_path: Path) -> None:
    _write_inputs(tmp_path, with_gap_id=False)

    manifest = build_manifest(_args(tmp_path))
    window = manifest["windows"][0]

    assert manifest["status"] == "PASS"
    assert manifest["resolved_profile"] == "tier_3_research"
    assert manifest["summary"]["window_count"] == 1
    assert window["synthetic_gap_id"] == "generated_gap_000001"
    assert window["missing_minute_count"] == 2
    assert window["first_missing_ts_utc"] == "2024-01-03T15:00:00Z"
    assert window["last_missing_ts_utc"] == "2024-01-03T15:01:00Z"


def test_resolves_adjacent_contract(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    window = build_manifest(_args(tmp_path))["windows"][0]

    assert window["contract_resolution_status"] == "resolved"
    assert window["raw_symbol"] == "ZNH4"
    assert window["instrument_id"] == 123
    assert window["raw_ohlcv_source_files"] == ["raw.dbn.zst"]
    assert window["raw_ohlcv_source_hashes"] == ["abc"]


def test_missing_inputs_fail_closed_after_writing_manifest(tmp_path: Path) -> None:
    _write_config(tmp_path / "configs" / "alpha_tiered.yaml")
    _write_session_config(tmp_path / "configs" / "market_sessions.yaml")
    json_out = tmp_path / "reports" / "manifest.json"
    md_out = tmp_path / "reports" / "manifest.md"

    code = main(
        [
            "--profile",
            "tier_3",
            "--config",
            str(tmp_path / "configs" / "alpha_tiered.yaml"),
            "--raw-root",
            str(tmp_path / "data" / "raw"),
            "--causal-root",
            str(tmp_path / "data" / "causally_gated_normalized"),
            "--session-config",
            str(tmp_path / "configs" / "market_sessions.yaml"),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    manifest = json.loads(json_out.read_text(encoding="utf-8"))
    assert code == 1
    assert manifest["status"] == "FAIL"
    assert "missing input" in " ".join(manifest["failures"])
    assert md_out.exists()


def test_unresolved_contract_fails_unless_allowed(tmp_path: Path) -> None:
    _write_inputs(tmp_path, ambiguous_contract=True)
    args = _args(tmp_path)

    blocked = build_manifest(args)
    args.allow_unresolved_contracts = True
    allowed = build_manifest(args)

    assert blocked["status"] == "FAIL"
    assert blocked["windows"] == []
    assert "adjacent contract unresolved" in " ".join(blocked["failures"])
    assert allowed["status"] == "PASS"
    assert allowed["windows"][0]["contract_resolution_status"] == "ambiguous_or_missing"
    assert allowed["windows"][0]["decision"] == "pending_trade_source_verification"


def test_writes_valid_json_and_md_manifest(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    json_out = tmp_path / "reports" / "manifest.json"
    md_out = tmp_path / "reports" / "manifest.md"

    code = main(
        [
            "--profile",
            "tier_3",
            "--config",
            str(tmp_path / "configs" / "alpha_tiered.yaml"),
            "--raw-root",
            str(tmp_path / "data" / "raw"),
            "--causal-root",
            str(tmp_path / "data" / "causally_gated_normalized"),
            "--session-config",
            str(tmp_path / "configs" / "market_sessions.yaml"),
            "--json-out",
            str(json_out),
            "--md-out",
            str(md_out),
        ]
    )

    manifest = json.loads(json_out.read_text(encoding="utf-8"))
    assert code == 0
    assert manifest["status"] == "PASS"
    assert manifest["windows"][0]["decision"] == "pending_trade_source_verification"
    assert md_out.read_text(encoding="utf-8").startswith("# Missing-Minute")


def test_accepted_external_trade_schema_is_documented(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    manifest = build_manifest(_args(tmp_path))
    schema = manifest["accepted_external_trade_schema"]

    assert manifest["required_third_party_source_type"] == REQUIRED_THIRD_PARTY_SOURCE_TYPE
    assert schema["required_columns"] == ["timestamp_utc"]
    assert "OHLCV bars" in schema["not_accepted_as_proof"]
    assert manifest["windows"][0]["accepted_external_schema"] == schema
