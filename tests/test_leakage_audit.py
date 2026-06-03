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
