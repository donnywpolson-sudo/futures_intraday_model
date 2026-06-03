import polars as pl

from pipeline.common.config import RootConfig
from pipeline.walkforward.walkforward import apply_walkforward_contract
from pipeline.walkforward.split_plan import write_wfa_split_plan


def test_walkforward_train_test_no_overlap():
    df = pl.DataFrame({"ts_event": list(range(10)), "y": list(range(10))})
    train, test = apply_walkforward_contract(df, 0, 5, 5, 10, target_horizon_bars=0, entry_lag_bars=0)
    assert train["ts_event"].max() < test["ts_event"].min()


def test_target_horizon_purge_near_test_end():
    df = pl.DataFrame({"ts_event": list(range(10)), "y": list(range(10))})
    _, test = apply_walkforward_contract(df, 0, 5, 5, 10, target_horizon_bars=2, entry_lag_bars=1)
    assert test["ts_event"].max() == 6


def test_embargo_removes_boundary_train_rows():
    df = pl.DataFrame({"ts_event": list(range(10)), "y": list(range(10))})
    train, _ = apply_walkforward_contract(df, 0, 5, 5, 10, embargo_bars=2, target_horizon_bars=0, entry_lag_bars=0)
    assert train["ts_event"].to_list() == [0, 1, 2]


def test_walkforward_accepts_date_strings_for_utc_datetime():
    df = pl.DataFrame(
        {
            "ts_event": pl.datetime_range(
                pl.datetime(2023, 1, 1, time_zone="UTC"),
                pl.datetime(2023, 1, 10, time_zone="UTC"),
                "1d",
                eager=True,
            ),
            "y": list(range(10)),
        }
    )
    train, test = apply_walkforward_contract(
        df,
        "2023-01-02",
        "2023-01-05",
        "2023-01-05",
        "2023-01-08",
        target_horizon_bars=0,
        entry_lag_bars=0,
    )
    assert train["ts_event"].min().date().isoformat() == "2023-01-02"
    assert train["ts_event"].max().date().isoformat() == "2023-01-04"
    assert test["ts_event"].min().date().isoformat() == "2023-01-05"


def test_wfa_split_plan_writes_contract_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    files = []
    for year in [2024, 2025]:
        p = tmp_path / "data" / "ES" / f"{year}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
        files.append(p)
    cfg = RootConfig(symbols=["ES"])
    report = write_wfa_split_plan(
        [([2024], [2025], "2024-01-01", "2024-07-01", "2024-07-01", "2024-08-01")],
        files,
        cfg,
    )
    assert report["status"] == "PASS"
    assert report["split_count"] == 1
    assert (tmp_path / "reports" / "wfa" / "wfa_split_plan.json").exists()
    assert (tmp_path / "reports" / "wfa" / "wfa_split_plan_summary.csv").exists()
