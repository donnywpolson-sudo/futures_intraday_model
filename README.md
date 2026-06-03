python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Active config
$env:CONFIG_ENV="tier_0_smoke_pipeline"
# config file: configs/alpha_tiered.yaml
# Current modeling mode: minimal_compatible
# This validates pipeline wiring/safety gates only. It is not strategy evidence
# and deployment readiness remains NOT_READY.

# Phase 1 data/report workflow
python scripts/validate_databento_continuous.py --audit-only
python scripts/validate_databento_continuous.py --write-validated --clean-policy drop-invalid
python -m pipeline.audit.data_quality --root data/validated --out reports/validation/data_quality_report.json
python -m pipeline.audit.session_roll
python scripts/session_normalize.py
python scripts/causal_gate_normalized.py
python scripts/build_data_manifests.py --stages raw validated session_normalized causally_gated_normalized

# Research run
python run.py

# CLI help
python -m pipeline.cli --help
python -m pipeline.cli discover --help
python -m pipeline.cli run --help
python -m pipeline.cli aggregate --help

# Hard gate
Downstream research refuses to run from data/validated if parquet files are
missing or manifests are missing. Remediation:
python scripts/validate_databento_continuous.py --write-validated --clean-policy drop-invalid

# Review
reports/leakage/
reports/metrics/
reports/stress/
reports/acceptance/
artifacts/run_manifests/

# Artifact layout
data/raw -> data/validated -> data/session_normalized -> data/causally_gated_normalized
reports/validation -> reports/session_normalization -> reports/causal_gating -> reports/wfa -> reports/metrics
artifacts/models -> artifacts/scalers -> artifacts/selectors -> artifacts/run_manifests -> artifacts/backtests
