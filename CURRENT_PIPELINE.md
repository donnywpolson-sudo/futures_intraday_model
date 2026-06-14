Phases In Simple Terms
Phase 1A: download Databento DBN archives.
Phase 1B: convert DBN archives into raw yearly parquet files.
Phase 2: clean and normalize bars into causal session-aware data.
Phase 3: create future-looking labels/targets, including cost-aware targets.
Phase 4: build model features while excluding target/leakage columns.
Phase 5: build walk-forward train/test splits with purge/embargo.
Phase 6: no separate implemented phase in this repo.
Phase 7: train baseline models and save out-of-sample predictions.
Phase 8: score predictions with a deterministic policy, costs, and promotion gates.