# Live Trading Readiness

Current status: paper/smoke scaffold only. There is no real broker execution path, no broker SDK import, and no live orders.

Run the deterministic smoke check:

```powershell
python scripts/smoke_live_trading.py
```

Kill switch controls only the paper/sim layer:

```powershell
python scripts/kill_switch_on.py
python scripts/kill_switch_off.py
```

Paper safety scripts:

```powershell
python scripts/paper_cancel_all.py
python scripts/paper_flatten_all.py
```

Before live orders are considered, prove:

* model output is available live
* live-derived bars match the historical feature contract
* data quality gate passes
* model readiness gate passes
* paper broker passes smoke tests
* kill switch works
* cancel all works
* flatten all works
* reconciliation works
* stale-data shutoff works
* session guard works
* contract rollover guard works
* audit logging works
* at least 2 weeks of paper/shadow logs are reviewed
* first live test is one symbol and one contract max
* manual broker-side limits are configured
* real order types are manually tested in the broker UI before API use
* live broker implementation remains disabled until explicitly approved

Known limitations:

* The scaffold uses synthetic records and deterministic paper fills.
* System clock drift and low disk space checks are not implemented here.
* Contract rollover calendars are represented by explicit active contract checks; no exchange calendar automation is included.
* The chart displays status and must not submit orders.
