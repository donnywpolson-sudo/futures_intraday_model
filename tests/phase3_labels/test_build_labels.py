from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pipeline_gates import file_sha256
from scripts.phase3_labels import build_labels as labels_mod
from scripts.phase3_labels.build_labels import (
    LABEL_COLUMNS,
    LABEL_SEMANTICS_ID,
    add_labels,
    load_market_config,
    process_file,
    resolve_profile_inputs,
    select_profile_inputs,
    write_reports,
)


def _write_profile_config(path: Path, *, profile: str = "research") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""
profiles:
  {profile}:
    markets: ["ES"]
    years: [2024]
""".strip(),
        encoding="utf-8",
    )
    return path


def _write_upstream_manifest(
    path: Path,
    *,
    stage: str,
    profile: str,
    output_root: Path,
    output_path: Path,
    status: str = "PASS",
    warning_count: int = 0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "status": status,
        "profile": profile,
        "resolved_profile": profile,
        "output_root": output_root.as_posix(),
        "warning_count": warning_count,
        "failure_count": 0,
        "failures": [],
        "summary": {"fail_count": 0, "warn_count": warning_count},
        "output_file_hashes": {output_path.as_posix(): file_sha256(output_path)},
        "outputs": [
            {
                "market": "ES",
                "year": 2024,
                "status": status,
                "warning_count": warning_count,
                "failure_count": 0,
                "failures": [],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_multi_upstream_manifest(
    path: Path,
    *,
    profile: str,
    output_root: Path,
    market_years: list[tuple[str, int]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_hashes = {}
    outputs = []
    for market, year in market_years:
        output_path = output_root / market / f"{year}.parquet"
        output_hashes[output_path.as_posix()] = file_sha256(output_path)
        outputs.append(
            {
                "market": market,
                "year": year,
                "status": "PASS",
                "warning_count": 0,
                "failure_count": 0,
                "failures": [],
            }
        )
    payload = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": profile,
        "resolved_profile": profile,
        "output_root": output_root.as_posix(),
        "warning_count": 0,
        "failure_count": 0,
        "failures": [],
        "summary": {"fail_count": 0, "warn_count": 0},
        "output_file_hashes": output_hashes,
        "outputs": outputs,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_tier1_profile_config(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_1_research:",
                "    markets: [6E]",
                "    years: [2023, 2024]",
                "aliases:",
                "  tier_1: tier_1_research",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _tier1_warning(year: int) -> str:
    return str(labels_mod.APPROVED_TIER1_ACCEPTED_EXCEPTIONS[("6E", year)]["warning"])


def _write_tier1_candidate_inputs(root: Path) -> None:
    for year in (2023, 2024):
        path = root / "6E" / f"{year}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"6E {year}".encode("utf-8"))


def _write_tier1_candidate_manifest(
    path: Path,
    root: Path,
    *,
    extra_warning: str | None = None,
    failure: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    outputs = []
    output_hashes = {}
    for year in (2023, 2024):
        output_path = root / "6E" / f"{year}.parquet"
        warnings = [_tier1_warning(year)]
        if extra_warning is not None and year == 2024:
            warnings.append(extra_warning)
        failures = ["failed"] if failure and year == 2024 else []
        output_hashes[output_path.as_posix()] = file_sha256(output_path)
        outputs.append(
            {
                "market": "6E",
                "year": year,
                "status": "PASS",
                "warning_count": len(warnings),
                "warnings": warnings,
                "failure_count": len(failures),
                "failures": failures,
            }
        )
    payload = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "output_root": root.as_posix(),
        "warning_count": 0,
        "failure_count": 0,
        "failures": [],
        "summary": {"fail_count": 0, "warn_count": 0},
        "output_file_hashes": output_hashes,
        "outputs": outputs,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _approved_exception_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for market, year in sorted(labels_mod.APPROVED_TIER1_ACCEPTED_EXCEPTIONS):
        approved = labels_mod.APPROVED_TIER1_ACCEPTED_EXCEPTIONS[(market, year)]
        rows.append(
            {
                "category": approved["category"],
                "market": market,
                "year": year,
                "metric": approved["metric"],
                "observed": approved["observed"],
                "approved_limit": approved["approved_limit"],
                "warning_prefixes": [approved["warning"]],
            }
        )
    return rows


def _write_accepted_exceptions(
    path: Path,
    *,
    rows: list[dict[str, object]] | None = None,
    global_threshold: float = 2.0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "tier1_candidate_accepted_readiness_exceptions",
        "status": "APPROVED_REPORT_ONLY",
        "profile": "tier_1",
        "resolved_profile": "tier_1_research",
        "global_threshold": global_threshold,
        "exceptions": rows if rows is not None else _approved_exception_rows(),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _patch_tier1_approval_paths(
    monkeypatch: pytest.MonkeyPatch,
    *,
    candidate_root: Path,
    exceptions_path: Path,
) -> None:
    monkeypatch.setattr(labels_mod, "APPROVED_TIER1_CANDIDATE_ROOT", candidate_root)
    monkeypatch.setattr(
        labels_mod,
        "APPROVED_TIER1_ACCEPTED_EXCEPTIONS_PATH",
        exceptions_path,
    )


def _write_es2026_profile_config(
    path: Path,
    *,
    warning: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    expected = labels_mod.APPROVED_ES2026_ACCEPTED_EXCEPTION
    warning_value = warning if warning is not None else str(expected["warning"])
    evidence_paths = expected["evidence_paths"]
    path.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_3_forward:",
                "    markets: [ES]",
                "    years: [2026]",
                "    accepted_readiness_exceptions:",
                "      - category: statistics_enrichment_sparse",
                "        market: ES",
                "        year: 2026",
                "        reason: bounded_es2026_statistics_enrichment_sparse_accepted_warning_packet_20260703",
                "        evidence_paths:",
                f"          - {evidence_paths[0]}",
                f"          - {evidence_paths[1]}",
                "        warning_prefixes:",
                f"          - '{warning_value}'",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _write_es2026_candidate_input(root: Path) -> None:
    path = root / "ES" / "2026.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"ES 2026")


def _write_es2026_candidate_manifest(path: Path, root: Path) -> Path:
    output_path = root / "ES" / "2026.parquet"
    warning = str(labels_mod.APPROVED_ES2026_ACCEPTED_EXCEPTION["warning"])
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": "causal_base",
        "status": "PASS",
        "profile": "tier_3_forward",
        "resolved_profile": "tier_3_forward",
        "output_root": root.as_posix(),
        "warning_count": 0,
        "failure_count": 0,
        "failures": [],
        "summary": {"fail_count": 0, "warn_count": 0},
        "output_file_hashes": {output_path.as_posix(): file_sha256(output_path)},
        "outputs": [
            {
                "market": "ES",
                "year": 2026,
                "status": "PASS",
                "warning_count": 1,
                "warnings": [warning],
                "failure_count": 0,
                "failures": [],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _run_es2026_candidate_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    input_root: Path,
    manifest_path: Path,
    profile_config: Path,
) -> dict[str, object]:
    captured: dict[str, object] = {}

    def fake_process(
        input_path: Path,
        output_path: Path,
        *,
        profile: str,
        costs_config: Path,
    ) -> labels_mod.LabelResult:
        return labels_mod.LabelResult(
            profile=profile,
            market=input_path.parent.name,
            year=int(input_path.stem),
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
        )

    def fake_write_reports(*args: object, **kwargs: object) -> None:
        captured["gate"] = kwargs["causal_base_gate"]

    monkeypatch.setattr(labels_mod, "process_file", fake_process)
    monkeypatch.setattr(labels_mod, "write_reports", fake_write_reports)
    monkeypatch.setattr(labels_mod, "APPROVED_ES2026_CANDIDATE_ROOT", input_root)
    monkeypatch.setattr(labels_mod, "APPROVED_ES2026_ACCEPTED_EXCEPTIONS_PATH", profile_config)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_labels.py",
            "--profile",
            "tier_3_forward",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "labeled").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "labels").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--causal-base-manifest",
            manifest_path.as_posix(),
            "--accepted-readiness-exceptions",
            profile_config.as_posix(),
            "--markets",
            "ES",
            "--years",
            "2026",
        ],
    )

    assert labels_mod.main() == 0
    return captured


def _run_tier1_candidate_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    input_root: Path,
    manifest_path: Path,
    exceptions_path: Path | None,
) -> dict[str, object]:
    profile_config = _write_tier1_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    captured: dict[str, object] = {}

    def fake_process(
        input_path: Path,
        output_path: Path,
        *,
        profile: str,
        costs_config: Path,
    ) -> labels_mod.LabelResult:
        return labels_mod.LabelResult(
            profile=profile,
            market=input_path.parent.name,
            year=int(input_path.stem),
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
        )

    def fake_write_reports(*args: object, **kwargs: object) -> None:
        captured["gate"] = kwargs["causal_base_gate"]

    argv = [
        "build_labels.py",
        "--profile",
        "tier_1",
        "--input-root",
        input_root.as_posix(),
        "--output-root",
        (tmp_path / "data" / "labeled").as_posix(),
        "--reports-root",
        (tmp_path / "reports" / "labels").as_posix(),
        "--profile-config",
        profile_config.as_posix(),
        "--costs-config",
        (tmp_path / "configs" / "costs.yaml").as_posix(),
        "--causal-base-manifest",
        manifest_path.as_posix(),
    ]
    if exceptions_path is not None:
        argv.extend(["--accepted-readiness-exceptions", exceptions_path.as_posix()])

    monkeypatch.setattr(labels_mod, "process_file", fake_process)
    monkeypatch.setattr(labels_mod, "write_reports", fake_write_reports)
    monkeypatch.setattr(sys, "argv", argv)

    assert labels_mod.main() == 0
    return captured


def test_phase3_main_requires_explicit_input_root(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["build_labels.py"])

    with pytest.raises(SystemExit) as exc_info:
        labels_mod.main()

    assert exc_info.value.code == 2
    assert "--input-root is required; pass an explicit causal root" in capsys.readouterr().err


def test_phase3_cli_accepts_explicit_causal_roots(tmp_path: Path) -> None:
    approved_root = Path("data/causally_gated_normalized")
    report_root = tmp_path / "reports" / "phase3" / "causal_base_fixture"

    approved_args = labels_mod.build_arg_parser().parse_args(
        ["--input-root", approved_root.as_posix()]
    )
    report_args = labels_mod.build_arg_parser().parse_args(
        ["--input-root", report_root.as_posix()]
    )

    assert Path(approved_args.input_root).as_posix() == approved_root.as_posix()
    assert Path(report_args.input_root).as_posix() == report_root.as_posix()


def _base_rows(count: int = 40, market: str = "ES") -> list[dict[str, object]]:
    start = pd.Timestamp("2024-01-02T15:00:00Z")
    rows: list[dict[str, object]] = []
    for i in range(count):
        open_price = 100.0 + (i * 0.25)
        rows.append(
            {
                "ts": start + pd.Timedelta(minutes=i),
                "market": market,
                "year": 2024,
                "symbol": f"{market}.v.0",
                "open": open_price,
                "high": open_price + 0.25,
                "low": open_price - 0.25,
                "close": open_price,
                "volume": 10,
                "causal_valid": True,
                "phase2_ready": True,
                "phase2_not_ready_reason": "",
                "session_segment_id": "session_2024-01-02_seg0",
                "is_synthetic": False,
                "valid_ohlcv": True,
                "boundary_session_flag": False,
                "roll_boundary_flag": False,
                "roll_window_flag": False,
                "roll_detection_available": True,
                "minutes_until_session_close": 120,
            }
        )
    return rows


def _write_causal(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path, index=False)


def _write_costs(path: Path, markets_blob: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "markets:",
                markets_blob,
            ]
        ),
        encoding="utf-8",
    )


def _write_es_costs(path: Path) -> None:
    _write_costs(
        path,
        "\n".join(
            [
                "  ES:",
                "    tick_size: 0.25",
                "    tick_value: 12.5",
                "    point_value: 50.0",
                "    min_profit_ticks: 2.0",
                "    min_stop_ticks: 4.0",
                "    round_turn_cost_ticks: 2.0",
                "    cost_source: test_costs",
                "    provisional: false",
            ]
        ),
    )


def test_phase3_main_rejects_warn_causal_base_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    input_path = input_root / "ES" / "2024.parquet"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"causal")
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    manifest = _write_upstream_manifest(
        tmp_path / "reports" / "causal_base" / "causal_base_manifest.json",
        stage="causal_base",
        profile="research",
        output_root=input_root,
        output_path=input_path,
        status="WARN",
        warning_count=1,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_labels.py",
            "--profile",
            "research",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "labeled").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "labels").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--causal-base-manifest",
            manifest.as_posix(),
        ],
    )

    with pytest.raises(SystemExit) as exc:
        labels_mod.main()

    assert "causal_base_manifest_gate failed" in str(exc.value)


def test_phase3_main_accepts_passed_causal_base_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    input_path = input_root / "ES" / "2024.parquet"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"causal")
    profile_config = _write_profile_config(tmp_path / "configs" / "alpha_tiered.yaml")
    manifest = _write_upstream_manifest(
        tmp_path / "reports" / "causal_base" / "causal_base_manifest.json",
        stage="causal_base",
        profile="research",
        output_root=input_root,
        output_path=input_path,
    )
    captured: dict[str, object] = {}

    def fake_process(
        input_path: Path,
        output_path: Path,
        *,
        profile: str,
        costs_config: Path,
    ) -> labels_mod.LabelResult:
        return labels_mod.LabelResult(
            profile=profile,
            market=input_path.parent.name,
            year=int(input_path.stem),
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
        )

    def fake_write_reports(*args: object, **kwargs: object) -> None:
        captured["gate"] = kwargs["causal_base_gate"]

    monkeypatch.setattr(labels_mod, "process_file", fake_process)
    monkeypatch.setattr(labels_mod, "write_reports", fake_write_reports)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_labels.py",
            "--profile",
            "research",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "labeled").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "labels").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--causal-base-manifest",
            manifest.as_posix(),
        ],
    )

    assert labels_mod.main() == 0
    assert captured["gate"]["status"] == "PASS"  # type: ignore[index]


def test_phase3_main_without_exception_flag_rejects_candidate_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(manifest, input_root)
    _write_accepted_exceptions(exceptions)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=exceptions,
    )

    with pytest.raises(SystemExit, match="warnings are not accepted"):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            exceptions_path=None,
        )


def test_phase3_main_accepts_exact_tier1_candidate_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(manifest, input_root)
    _write_accepted_exceptions(exceptions)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=exceptions,
    )

    captured = _run_tier1_candidate_main(
        tmp_path,
        monkeypatch,
        input_root=input_root,
        manifest_path=manifest,
        exceptions_path=exceptions,
    )

    gate = captured["gate"]
    assert gate["status"] == "PASS"  # type: ignore[index]
    assert gate["accepted_warning_count"] == 2  # type: ignore[index]
    assert gate["accepted_readiness_exception_count"] == 2  # type: ignore[index]
    assert gate["accepted_readiness_exceptions_path"] == exceptions.as_posix()  # type: ignore[index]


def test_phase3_main_accepts_exact_es2026_profile_config_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = (
        tmp_path
        / "data"
        / "causally_gated_normalized"
        / "local_trade_es2026_p1_candidate"
    )
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_es2026_candidate_input(input_root)
    _write_es2026_candidate_manifest(manifest, input_root)
    _write_es2026_profile_config(profile_config)

    captured = _run_es2026_candidate_main(
        tmp_path,
        monkeypatch,
        input_root=input_root,
        manifest_path=manifest,
        profile_config=profile_config,
    )

    gate = captured["gate"]
    assert gate["status"] == "PASS"  # type: ignore[index]
    assert gate["accepted_warning_count"] == 1  # type: ignore[index]
    assert gate["accepted_readiness_exception_count"] == 1  # type: ignore[index]
    assert gate["accepted_readiness_exceptions_path"] == profile_config.as_posix()  # type: ignore[index]
    accepted = gate["accepted_readiness_exceptions"][0]  # type: ignore[index]
    assert accepted["market"] == "ES"
    assert accepted["year"] == 2026
    assert accepted["category"] == "statistics_enrichment_sparse"


def test_phase3_main_rejects_mutated_es2026_profile_config_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = (
        tmp_path
        / "data"
        / "causally_gated_normalized"
        / "local_trade_es2026_p1_candidate"
    )
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    _write_es2026_candidate_input(input_root)
    _write_es2026_candidate_manifest(manifest, input_root)
    _write_es2026_profile_config(profile_config, warning="statistics enrichment sparse: missing_rows=7")

    with pytest.raises(SystemExit, match="wrong warning_prefixes"):
        _run_es2026_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            profile_config=profile_config,
        )


def test_phase3_main_rejects_wrong_exception_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    approved_exceptions = tmp_path / "reports" / "candidate" / "approved.json"
    wrong_exceptions = tmp_path / "reports" / "candidate" / "wrong.json"
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(manifest, input_root)
    _write_accepted_exceptions(approved_exceptions)
    _write_accepted_exceptions(wrong_exceptions)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=approved_exceptions,
    )

    with pytest.raises(SystemExit, match="path is not approved"):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            exceptions_path=wrong_exceptions,
        )


@pytest.mark.parametrize(
    ("field_name", "bad_value", "match"),
    [
        ("market", "ES", "market/year"),
        ("year", 2025, "market/year"),
        ("metric", "other_metric", "wrong metric"),
        ("observed", 999.0, "wrong observed"),
        ("approved_limit", 999.0, "wrong approved_limit"),
    ],
)
def test_phase3_main_rejects_mutated_exception_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field_name: str,
    bad_value: object,
    match: str,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    rows = _approved_exception_rows()
    rows[0][field_name] = bad_value
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(manifest, input_root)
    _write_accepted_exceptions(exceptions, rows=rows)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=exceptions,
    )

    with pytest.raises(SystemExit, match=match):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            exceptions_path=exceptions,
        )


def test_phase3_main_rejects_new_candidate_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(
        manifest,
        input_root,
        extra_warning="new candidate warning",
    )
    _write_accepted_exceptions(exceptions)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=exceptions,
    )

    with pytest.raises(SystemExit, match="warnings are not accepted"):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            exceptions_path=exceptions,
        )


def test_phase3_main_rejects_candidate_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(manifest, input_root, failure=True)
    _write_accepted_exceptions(exceptions)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=exceptions,
    )

    with pytest.raises(SystemExit, match="failure_count"):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            exceptions_path=exceptions,
        )


def test_phase3_main_rejects_stale_input_root_with_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved_root = tmp_path / "data" / "causally_gated_normalized"
    stale_root = tmp_path / "data" / "archive" / "tier1_rebuild_v1"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    _write_tier1_candidate_inputs(stale_root)
    _write_tier1_candidate_manifest(manifest, stale_root)
    _write_accepted_exceptions(exceptions)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=approved_root,
        exceptions_path=exceptions,
    )

    with pytest.raises(SystemExit, match="require input-root"):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=stale_root,
            manifest_path=manifest,
            exceptions_path=exceptions,
        )


def test_phase3_main_rejects_changed_global_threshold(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    manifest = tmp_path / "reports" / "candidate" / "causal_base_manifest.json"
    exceptions = tmp_path / "reports" / "candidate" / "accepted_readiness_exceptions.json"
    _write_tier1_candidate_inputs(input_root)
    _write_tier1_candidate_manifest(manifest, input_root)
    _write_accepted_exceptions(exceptions, global_threshold=2.5)
    _patch_tier1_approval_paths(
        monkeypatch,
        candidate_root=input_root,
        exceptions_path=exceptions,
    )

    with pytest.raises(SystemExit, match="global_threshold changed"):
        _run_tier1_candidate_main(
            tmp_path,
            monkeypatch,
            input_root=input_root,
            manifest_path=manifest,
            exceptions_path=exceptions,
        )


def _rows_with_gross_ticks(gross_ticks: float) -> list[dict[str, object]]:
    rows = _base_rows()
    entry_price = 100.0
    exit_price = entry_price + (gross_ticks * 0.25)
    for row in rows:
        row["open"] = entry_price
        row["high"] = entry_price + 0.25
        row["low"] = entry_price - 0.25
        row["close"] = entry_price
    rows[1]["open"] = entry_price
    rows[31]["open"] = exit_price
    rows[31]["high"] = max(exit_price, entry_price) + 0.25
    rows[31]["low"] = min(exit_price, entry_price) - 0.25
    return rows


def test_entry_exit_alignment_uses_next_bar_open_not_close_t(tmp_path: Path) -> None:
    rows = _base_rows()
    rows[0]["close"] = 999.0
    input_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    output_path = tmp_path / "data" / "labeled" / "ES" / "2024.parquet"
    costs_path = tmp_path / "configs" / "costs.yaml"
    _write_causal(input_path, rows)
    _write_es_costs(costs_path)

    result = process_file(
        input_path,
        output_path,
        profile="tier_1",
        costs_config=costs_path,
    )

    assert result.failures == []
    output = pd.read_parquet(output_path)
    row = output.iloc[0]
    assert row["target_entry_ts"] == rows[1]["ts"]
    assert row["target_exit_ts"] == rows[31]["ts"]
    assert row["target_entry_price"] == rows[1]["open"]
    assert row["target_exit_price"] == rows[31]["open"]
    assert row["target_horizon_bars"] == 30
    assert row["target_entry_price"] != rows[0]["close"]


def test_profile_resolution_uses_alpha_tier_aliases(tmp_path: Path) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    config_path = tmp_path / "configs" / "alpha_tiered.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "profiles:",
                "  tier_1:",
                "    markets: [CL, ES, ZN]",
                "    years: [2023, 2024, 2025]",
                "aliases:",
                "  tier_1_core: tier_1",
            ]
        ),
        encoding="utf-8",
    )

    resolved = resolve_profile_inputs("tier_1", input_root, config_path)

    assert resolved[0] == ("CL", 2023, input_root / "CL" / "2023.parquet")
    assert resolved[-1] == ("ZN", 2025, input_root / "ZN" / "2025.parquet")
    assert len(resolved) == 9


def test_phase3_input_filters_are_deterministic(tmp_path: Path) -> None:
    inputs = [
        ("ES", 2025, tmp_path / "ES" / "2025.parquet"),
        ("ES", 2026, tmp_path / "ES" / "2026.parquet"),
        ("NG", 2025, tmp_path / "NG" / "2025.parquet"),
        ("NG", 2026, tmp_path / "NG" / "2026.parquet"),
    ]

    selected, selection = select_profile_inputs(
        inputs,
        markets={"NG", "ES"},
        years={2026},
    )

    assert [(market, year) for market, year, _ in selected] == [("ES", 2026), ("NG", 2026)]
    assert selection["profile_input_count"] == 4
    assert selection["selected_input_count"] == 2
    assert selection["requested_markets"] == ["ES", "NG"]
    assert selection["requested_years"] == [2026]
    assert selection["selected_markets"] == ["ES", "NG"]
    assert selection["selected_years"] == [2026]


def test_phase3_input_filters_fail_when_scope_is_empty(tmp_path: Path) -> None:
    inputs = [("ES", 2025, tmp_path / "ES" / "2025.parquet")]

    with pytest.raises(SystemExit, match="No Phase 3 inputs selected after filters"):
        select_profile_inputs(inputs, markets={"NG"})


def test_phase3_main_applies_market_year_filters_to_gate_and_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_root = tmp_path / "data" / "causally_gated_normalized"
    market_years = [("ES", 2025), ("ES", 2026), ("NG", 2025), ("NG", 2026)]
    for market, year in market_years:
        path = input_root / market / f"{year}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"{market} {year}".encode("utf-8"))

    profile_config = tmp_path / "configs" / "alpha_tiered.yaml"
    profile_config.parent.mkdir(parents=True, exist_ok=True)
    profile_config.write_text(
        "\n".join(
            [
                "profiles:",
                "  local_trade:",
                "    markets: [ES, NG]",
                "    years: [2025, 2026]",
            ]
        ),
        encoding="utf-8",
    )
    manifest = _write_multi_upstream_manifest(
        tmp_path / "reports" / "causal_base" / "causal_base_manifest.json",
        profile="local_trade",
        output_root=input_root,
        market_years=market_years,
    )
    captured: dict[str, object] = {"processed": []}

    def fake_process(
        input_path: Path,
        output_path: Path,
        *,
        profile: str,
        costs_config: Path,
    ) -> labels_mod.LabelResult:
        processed = captured["processed"]
        assert isinstance(processed, list)
        processed.append((input_path.parent.name, int(input_path.stem), output_path))
        return labels_mod.LabelResult(
            profile=profile,
            market=input_path.parent.name,
            year=int(input_path.stem),
            input_path=input_path.as_posix(),
            output_path=output_path.as_posix(),
        )

    def fake_write_reports(*args: object, **kwargs: object) -> None:
        captured["input_selection"] = kwargs["input_selection"]
        captured["causal_base_gate"] = kwargs["causal_base_gate"]

    monkeypatch.setattr(labels_mod, "process_file", fake_process)
    monkeypatch.setattr(labels_mod, "write_reports", fake_write_reports)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_labels.py",
            "--profile",
            "local_trade",
            "--input-root",
            input_root.as_posix(),
            "--output-root",
            (tmp_path / "data" / "labeled").as_posix(),
            "--reports-root",
            (tmp_path / "reports" / "labels").as_posix(),
            "--profile-config",
            profile_config.as_posix(),
            "--costs-config",
            (tmp_path / "configs" / "costs.yaml").as_posix(),
            "--causal-base-manifest",
            manifest.as_posix(),
            "--markets",
            "NG",
            "--years",
            "2026",
        ],
    )

    assert labels_mod.main() == 0
    assert [(market, year) for market, year, _ in captured["processed"]] == [("NG", 2026)]  # type: ignore[index]
    selection = captured["input_selection"]
    assert selection["profile_input_count"] == 4  # type: ignore[index]
    assert selection["selected_input_count"] == 1  # type: ignore[index]
    assert selection["requested_markets"] == ["NG"]  # type: ignore[index]
    assert selection["requested_years"] == [2026]  # type: ignore[index]
    gate = captured["causal_base_gate"]
    assert gate["status"] == "PASS"  # type: ignore[index]
    assert gate["expected_market_year_count"] == 1  # type: ignore[index]


def test_invalid_reasons_for_current_and_future_path_flags(tmp_path: Path) -> None:
    cases = [
        ("current_causal_valid_false", 0, "causal_valid", False),
        ("session_segment_cross", 5, "session_segment_id", "session_2024-01-02_seg1"),
        ("synthetic_path", 5, "is_synthetic", True),
        ("invalid_ohlcv_path", 5, "valid_ohlcv", False),
        ("phase2_not_ready_path", 5, "phase2_ready", False),
        ("boundary_session_path", 5, "boundary_session_flag", True),
        ("roll_path", 5, "roll_window_flag", True),
    ]

    for reason, row_index, column, value in cases:
        rows = _base_rows()
        rows[row_index][column] = value
        labeled = add_labels(pd.DataFrame(rows), load_market_config("ES", tmp_path / "missing.yaml"))

        assert labeled.loc[0, "target_valid"] == False
        assert labeled.loc[0, "target_invalid_reason"] == reason


def test_causal_valid_false_is_hard_label_exclusion(tmp_path: Path) -> None:
    rows = _base_rows()
    rows[0]["causal_valid"] = False

    labeled = add_labels(pd.DataFrame(rows), load_market_config("ES", tmp_path / "missing.yaml"))

    assert labeled.loc[0, "target_valid"] == False
    assert labeled.loc[0, "target_invalid_reason"] == "current_causal_valid_false"


def test_tick_dollar_cost_and_deadzone_conversion() -> None:
    rows = _base_rows()
    for i, row in enumerate(rows):
        row["open"] = 100.0
        row["high"] = 100.25
        row["low"] = 99.75
        row["close"] = 100.0
    rows[1]["open"] = 100.0
    rows[31]["open"] = 101.0
    labeled = add_labels(
        pd.DataFrame(rows),
        load_market_config("ES", Path("missing.yaml")),
    )

    row = labeled.iloc[0]
    assert row["target_ret_ticks_30m"] == 4.0
    assert row["target_gross_dollars_30m"] == 50.0
    assert row["target_estimated_cost_ticks"] == 2.0
    assert row["target_estimated_cost_dollars"] == 25.0
    assert row["target_net_ticks_after_est_cost"] == 2.0
    assert row["target_net_dollars_after_est_cost"] == 25.0
    assert row["target_sign_30m"] == 1
    assert row["target_sign_with_deadzone"] == 0
    assert row["target_tradeable_after_cost"] == True
    assert row["target_favorable_after_cost_30m"] == False
    assert row["target_fillable_after_slippage_30m"] == False
    assert "target_ret_ticks_15m" not in labeled.columns


def test_explicit_cost_config_is_loaded_and_reported(tmp_path: Path) -> None:
    costs_path = tmp_path / "configs" / "costs.yaml"
    _write_costs(
        costs_path,
        "\n".join(
            [
                "  ES:",
                "    tick_size: 0.25",
                "    tick_value: 12.5",
                "    point_value: 50.0",
                "    min_profit_ticks: 2.0",
                "    min_stop_ticks: 4.0",
                "    commission_per_contract_dollars: 0.0",
                "    slippage_ticks_per_side: 1.5",
                "    round_turn_cost_ticks: 3.0",
                "    round_turn_cost_dollars: 37.5",
                "    cost_source: test_provisional_costs",
                "    provisional: true",
            ]
        ),
    )

    config = load_market_config("ES", costs_path)

    assert config.estimated_cost_ticks == 3.0
    assert config.estimated_cost_dollars == 37.5
    assert config.cost_source == "test_provisional_costs"
    assert config.provisional == True
    assert config.defaults_used == []


def test_present_cost_config_missing_market_fails_without_output(tmp_path: Path) -> None:
    input_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    output_path = tmp_path / "data" / "labeled" / "ES" / "2024.parquet"
    costs_path = tmp_path / "configs" / "costs.yaml"
    _write_causal(input_path, _base_rows())
    _write_costs(
        costs_path,
        "\n".join(
            [
                "  CL:",
                "    tick_size: 0.01",
                "    tick_value: 10.0",
                "    point_value: 1000.0",
                "    min_profit_ticks: 2.0",
                "    min_stop_ticks: 4.0",
                "    round_turn_cost_ticks: 3.0",
                "    cost_source: cl_only_costs",
                "    provisional: true",
            ]
        ),
    )

    result = process_file(
        input_path,
        output_path,
        profile="tier_1",
        costs_config=costs_path,
    )

    assert result.status == "FAIL"
    assert "market_cost_missing" in result.config["defaults_used"]
    assert any("market config defaults used" in warning for warning in result.warnings)
    assert "placeholder costs used" in result.warnings
    assert any("placeholder/default costs unavailable" in failure for failure in result.failures)
    assert not output_path.exists()


def test_net_ticks_after_cost_semantics() -> None:
    cases = [
        (4.0, 2.0, True),
        (1.0, 0.0, False),
        (-4.0, -2.0, True),
        (-1.0, -0.0, False),
        (0.0, 0.0, False),
        (2.0, 0.0, False),
        (-2.0, -0.0, False),
    ]

    for gross_ticks, expected_net_ticks, expected_tradeable in cases:
        labeled = add_labels(
            pd.DataFrame(_rows_with_gross_ticks(gross_ticks)),
            load_market_config("ES", Path("missing.yaml")),
        )
        row = labeled.iloc[0]
        gross = row["target_ret_ticks_30m"]
        net = row["target_net_ticks_after_est_cost"]

        assert gross == gross_ticks
        assert net == expected_net_ticks
        assert row["target_net_dollars_after_est_cost"] == expected_net_ticks * 12.5
        assert row["target_tradeable_after_cost"] == expected_tradeable
        assert abs(net) <= abs(gross)
        assert net == 0 or gross * net > 0


def test_primary_30m_and_robustness_60m_labels_are_independent() -> None:
    rows = _base_rows(count=80)
    for row in rows:
        row["open"] = 100.0
        row["high"] = 100.25
        row["low"] = 99.75
        row["close"] = 100.0
    rows[31]["open"] = 102.0
    rows[31]["high"] = 102.25
    rows[61]["open"] = 103.0
    rows[61]["high"] = 103.25

    labeled = add_labels(
        pd.DataFrame(rows),
        load_market_config("ES", Path("missing.yaml")),
    )

    row = labeled.iloc[0]
    assert row["target_valid"] == True
    assert row["target_30m_valid"] == True
    assert row["target_60m_valid"] == True
    assert row["target_ret_ticks_30m"] == 8.0
    assert row["target_ret_ticks_60m"] == 12.0
    assert row["target_mfe_long_ticks_30m"] == 9.0
    assert row["target_mae_long_ticks_30m"] == -1.0
    assert row["target_favorable_after_cost_long_30m"] == True
    assert row["target_fillable_after_slippage_long_30m"] == True
    assert row["target_accept_long_30m"] == True
    assert row["target_accept_long_60m"] == True
    assert row["target_apex_confirmed_long_30m_60m"] == True
    assert row["diagnostic_valid_15m"] == True
    assert "target_ret_15m" not in labeled.columns


def test_apex_mae_threat_rejects_otherwise_accepted_primary_path() -> None:
    rows = _base_rows(count=80)
    for row in rows:
        row["open"] = 100.0
        row["high"] = 100.25
        row["low"] = 99.75
        row["close"] = 100.0
    rows[10]["low"] = 94.75
    rows[31]["open"] = 102.0
    rows[31]["high"] = 102.25

    labeled = add_labels(
        pd.DataFrame(rows),
        load_market_config("ES", Path("missing.yaml")),
    )

    row = labeled.iloc[0]
    assert row["target_valid"] == True
    assert row["target_favorable_after_cost_long_30m"] == True
    assert row["target_fillable_after_slippage_long_30m"] == True
    assert row["target_mae_long_dollars_30m"] == -262.5
    assert row["target_apex_dll_eod_threat_long_30m"] == True
    assert row["target_accept_long_30m"] == False


def test_apex_eod_close_buffer_invalidates_primary_path() -> None:
    rows = _base_rows(count=80)
    start = pd.Timestamp("2024-01-02T21:30:00Z")
    for i, row in enumerate(rows):
        row["ts"] = start + pd.Timedelta(minutes=i)
        row["open"] = 100.0
        row["high"] = 100.25
        row["low"] = 99.75
        row["close"] = 100.0

    labeled = add_labels(
        pd.DataFrame(rows),
        load_market_config("ES", Path("missing.yaml")),
    )

    row = labeled.iloc[0]
    assert row["target_valid"] == False
    assert row["target_invalid_reason"] == "apex_eod_close_buffer"
    assert row["target_no_hold_into_close_30m"] == False
    assert row["target_accept_any_30m"] == False


def test_60m_robustness_can_fail_independently_of_primary_30m() -> None:
    rows = _base_rows(count=80)
    for row in rows:
        row["open"] = 100.0
        row["high"] = 100.25
        row["low"] = 99.75
        row["close"] = 100.0
    rows[31]["open"] = 102.0
    rows[31]["high"] = 102.25
    rows[31]["low"] = 101.75
    rows[45]["session_segment_id"] = "session_2024-01-02_seg1"

    labeled = add_labels(
        pd.DataFrame(rows),
        load_market_config("ES", Path("missing.yaml")),
    )

    row = labeled.iloc[0]
    assert row["target_30m_valid"] == True
    assert row["target_60m_valid"] == False
    assert row["target_60m_invalid_reason"] == "session_segment_cross"
    assert row["target_accept_long_30m"] == True
    assert row["target_apex_confirmed_any_30m_60m"] == False


def test_output_schema_and_reports(tmp_path: Path) -> None:
    input_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    output_path = tmp_path / "data" / "labeled" / "ES" / "2024.parquet"
    reports_root = tmp_path / "reports" / "labels"
    costs_path = tmp_path / "configs" / "costs.yaml"
    input_df = pd.DataFrame(_base_rows())
    _write_causal(input_path, input_df.to_dict("records"))
    _write_es_costs(costs_path)

    result = process_file(
        input_path,
        output_path,
        profile="tier_1",
        costs_config=costs_path,
    )
    write_reports([result], reports_root, "tier_1")

    output = pd.read_parquet(output_path)
    assert list(output.columns) == list(input_df.columns) + LABEL_COLUMNS
    assert output["label_semantics"].eq(LABEL_SEMANTICS_ID).all()
    assert output["cost_source"].eq("test_costs").all()
    assert output["cost_provisional"].eq(False).all()
    for column in (
        "target_ret_ticks_30m",
        "target_ret_ticks_60m",
        "target_favorable_after_cost_30m",
        "target_fillable_after_slippage_30m",
        "target_apex_dll_eod_threat_30m",
        "target_no_hold_into_close_30m",
        "target_accept_any_30m",
        "target_accept_any_60m",
        "target_apex_confirmed_any_30m_60m",
        "diagnostic_ret_ticks_15m",
    ):
        assert column in output.columns
    manifest = json.loads((reports_root / "label_manifest.json").read_text())
    report = json.loads((reports_root / "label_report.json").read_text())
    provenance_keys = {
        "generated_at",
        "git_commit",
        "script_path",
        "script_hash",
        "config_hash",
        "input_root",
        "output_root",
        "reports_root",
        "input_file_hashes",
        "output_file_hashes",
        "profile",
        "markets",
        "years",
        "warning_count",
        "failure_count",
        "failures",
    }
    assert provenance_keys <= set(manifest)
    assert provenance_keys <= set(report)
    assert manifest["input_root"] == (
        tmp_path / "data" / "causally_gated_normalized"
    ).as_posix()
    assert manifest["output_root"] == (tmp_path / "data" / "labeled").as_posix()
    assert manifest["reports_root"] == reports_root.as_posix()
    assert report["input_root"] == manifest["input_root"]
    assert report["output_root"] == manifest["output_root"]
    assert report["reports_root"] == manifest["reports_root"]
    assert isinstance(manifest["output_file_hashes"][result.output_path], str)
    assert len(manifest["output_file_hashes"][result.output_path]) == 64
    assert manifest["input_file_hashes"][result.input_path] is not None
    assert manifest["profile"] == "tier_1"
    assert manifest["markets"] == ["ES"]
    assert manifest["years"] == [2024]
    for payload in (manifest, report):
        assert payload["partial_scope"] is True
        assert payload["authoritative"] is False
        assert payload["expected_input_count"] == 8
        assert payload["actual_input_count"] == 1
        assert len(payload["missing_market_years"]) == 7
    assert manifest["warning_count"] == len(result.warnings)
    assert manifest["failure_count"] == len(result.failures)
    assert manifest["failures"] == []
    assert manifest["stage"] == "labels"
    assert report["summary"]["target_valid_rows"] == result.target_valid_rows
    assert manifest["outputs"][0]["config"]["tick_size"] == 0.25
    assert manifest["outputs"][0]["warning_count"] == len(result.warnings)
    assert manifest["outputs"][0]["failure_count"] == len(result.failures)
    assert manifest["outputs"][0]["failures"] == result.failures
    assert manifest["label_semantics"]["label_semantics_id"] == LABEL_SEMANTICS_ID
    assert "primary 30m" in manifest["label_semantics"]["target_ret_ticks_30m"]


def test_mixed_roll_detection_availability_is_reported(tmp_path: Path) -> None:
    input_path = tmp_path / "data" / "causally_gated_normalized" / "ES" / "2024.parquet"
    output_path = tmp_path / "data" / "labeled" / "ES" / "2024.parquet"
    reports_root = tmp_path / "reports" / "labels"
    costs_path = tmp_path / "configs" / "costs.yaml"
    rows = _base_rows()
    rows[3]["roll_detection_available"] = False
    rows[4]["roll_detection_available"] = False
    _write_causal(input_path, rows)
    _write_es_costs(costs_path)

    result = process_file(
        input_path,
        output_path,
        profile="tier_1",
        costs_config=costs_path,
    )
    write_reports([result], reports_root, "tier_1")

    manifest = json.loads((reports_root / "label_manifest.json").read_text())
    report = json.loads((reports_root / "label_report.json").read_text())
    output_row = manifest["outputs"][0]

    assert result.roll_detection_available == False
    assert result.roll_detection_available_rows == len(rows) - 2
    assert result.roll_detection_unavailable_rows == 2
    assert result.roll_protection_unavailable == True
    assert "roll protection unavailable for 2 rows" in result.warnings[-1]
    assert result.status == "FAIL"
    assert "roll protection unavailable for 2 rows" in result.failures[-1]
    assert not output_path.exists()
    assert output_row["roll_detection_available"] == False
    assert output_row["roll_detection_available_rows"] == len(rows) - 2
    assert output_row["roll_detection_unavailable_rows"] == 2
    assert report["summary"]["roll_detection_unavailable_rows"] == 2

