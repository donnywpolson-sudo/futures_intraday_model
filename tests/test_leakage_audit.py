import polars as pl

from pipeline.audit.leakage import run_leakage_audit


def test_leakage_audit_catches_future_and_target_columns():
    df = pl.DataFrame({"future_x": [1.0, 2.0], "target_y": [1.0, 2.0], "target": [1.0, 2.0]})
    report = run_leakage_audit(df, ["future_x", "target_y"], "target")
    assert report["status"] == "FAIL"


def test_leakage_audit_catches_availability_after_prediction():
    df = pl.DataFrame(
        {
            "x": [1.0, 2.0],
            "target": [2.0, 4.0],
            "prediction_time": [1, 1],
            "x_available_at": [0, 2],
        }
    )
    report = run_leakage_audit(df, ["x"], "target")
    assert report["status"] == "FAIL"
    assert "availability after prediction_time" in report["failures"][0]


def test_leakage_audit_catches_near_perfect_corr():
    df = pl.DataFrame({"x": [1.0, 2.0, 3.0], "target": [1.0, 2.0, 3.0]})
    report = run_leakage_audit(df, ["x"], "target")
    assert report["status"] == "FAIL"


def test_valid_feature_matrix_passes():
    df = pl.DataFrame({"x": [1.0, 2.0, 4.0, 8.0], "target": [1.0, -1.0, 1.0, -1.0]})
    report = run_leakage_audit(df, ["x"], "target")
    assert report["status"] == "PASS"


def test_causal_roll_features_are_not_metadata_leakage():
    df = pl.DataFrame(
        {
            "roll_vol_5": [1.0, 2.0, 1.5, 2.5],
            "roll_volume_5": [10.0, 20.0, 15.0, 25.0],
            "roll_range_1": [0.1, 0.2, 0.1, 0.3],
            "target": [1.0, -1.0, 1.0, -1.0],
        }
    )
    report = run_leakage_audit(df, ["roll_vol_5", "roll_volume_5", "roll_range_1"], "target")
    assert report["status"] == "PASS"


def test_roll_metadata_still_fails():
    df = pl.DataFrame({"roll_flag": [0.0, 1.0, 0.0, 1.0], "target": [1.0, -1.0, 1.0, -1.0]})
    report = run_leakage_audit(df, ["roll_flag"], "target")
    assert report["status"] == "FAIL"
