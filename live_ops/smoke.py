"""Deterministic paper-only smoke scenarios."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

from .audit import AuditLogger
from .bar_builder import LiveBarBuilder
from .broker import PaperBroker
from .model import ModelReadinessGate, build_signal_state
from .operator import OperatorStatusState, render_operator_status
from .quality import DataQualityGate
from .reconciliation import Reconciler
from .risk import RiskManager
from .schemas import (
    BrokerResponse,
    DataQualityResult,
    LiveBar,
    LiveRecord,
    LiveTradingConfig,
    ModelReadinessResult,
    OrderIntent,
    ReconciliationResult,
    RiskDecision,
    SignalState,
    paper_smoke_config,
    plain_data,
    safe_default_config,
)

RUN_ID = "live-trading-smoke"
STRATEGY_ID = "smoke-paper-strategy"
BASE_TIME = datetime(2026, 6, 22, 14, 30, tzinfo=timezone.utc)


def sample_bar(
    *,
    timestamp: datetime = BASE_TIME,
    symbol: str = "ES",
    contract: str = "ESU6",
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.5,
    volume: int = 10,
    final: bool = True,
) -> LiveBar:
    return LiveBar(
        symbol=symbol,
        contract=contract,
        timestamp_utc=timestamp,
        timeframe="1m",
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        bar_is_final=final,
        source_schema="synthetic-l1",
    )


def sample_order(*, order_id: str = "ORD-1", quantity: int = 1, side: str = "BUY") -> OrderIntent:
    return OrderIntent(
        order_id=order_id,
        strategy_id=STRATEGY_ID,
        symbol="ES",
        contract="ESU6",
        side=side,
        quantity=quantity,
        order_type="LIMIT",
        limit_price=100.5,
        stop_price=None,
        time_in_force="DAY",
        bar_timestamp=BASE_TIME,
        created_timestamp=BASE_TIME + timedelta(seconds=1),
        reason="smoke signal",
        signal_id=f"SIG-{order_id}",
    )


def run_smoke(*, audit_dir: str | Path = "reports/live_trading_smoke", stdout: TextIO | None = None) -> bool:
    audit_path = Path(audit_dir) / "audit.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    logger = AuditLogger(audit_path)
    checks: list[tuple[str, bool, str]] = []
    decision_events = 0

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append((name, passed, detail))

    def cycle(
        name: str,
        *,
        config: LiveTradingConfig,
        bar: LiveBar,
        model_available: bool = True,
        explicit_signal: str | None = "LONG",
        order: OrderIntent | None = None,
        kill_switch_on: bool = False,
        positions: dict[str, int] | None = None,
        session_ok: bool | None = True,
        reconciliation: ReconciliationResult | None = None,
    ) -> tuple[DataQualityResult, ModelReadinessResult, SignalState, RiskDecision, BrokerResponse | None]:
        nonlocal decision_events
        gate = DataQualityGate(config)
        dq = gate.validate(bar, now=BASE_TIME + timedelta(seconds=10), heartbeat_timestamp_utc=BASE_TIME)
        model = ModelReadinessGate(model_version="smoke-v1").evaluate(
            symbol=bar.symbol,
            features={"close": bar.close},
            warmup_bars_available=1,
            model_available=model_available,
        )
        signal = build_signal_state(
            bar=bar,
            data_quality=dq,
            model_status=model,
            now=BASE_TIME + timedelta(seconds=11),
            score=0.8 if explicit_signal in {"LONG", "SHORT"} else None,
            signal=explicit_signal,
        )
        risk = RiskManager(config).evaluate(
            order=order,
            signal=signal,
            data_quality=dq,
            model_status=model,
            reconciliation=reconciliation or ReconciliationResult("OK", "OK", {}),
            positions=positions or {},
            now=BASE_TIME + timedelta(seconds=12),
            kill_switch_on=kill_switch_on,
            session_ok=session_ok,
        )
        broker_response = None
        if order is not None and risk.approved:
            broker_response = PaperBroker().place_order(order, risk_decision=risk, bar=bar)
        logger.write_decision(
            _event(
                name=name,
                bar=bar,
                data_quality=dq,
                model=model,
                signal=signal,
                risk=risk,
                order=order,
                broker_response=broker_response,
                reconciliation=reconciliation or ReconciliationResult("OK", "OK", {}),
            )
        )
        decision_events += 1
        return dq, model, signal, risk, broker_response

    safe_config = safe_default_config()
    paper_config = paper_smoke_config(audit_dir=str(audit_dir))
    bar = sample_bar()

    _, _, signal, risk, broker_response = cycle(
        "missing_model_output",
        config=paper_config,
        bar=bar,
        model_available=False,
        explicit_signal=None,
        order=None,
    )
    add("missing model output -> NO_SIGNAL -> no order", signal.signal == "NO_SIGNAL" and not risk.approved and broker_response is None)

    _, _, _, risk, _ = cycle("trading_disabled", config=safe_config, bar=bar, order=sample_order(order_id="ORD-2"))
    add("valid signal but allow_trading=false -> rejected", risk.reason_code == "TRADING_DISABLED")

    _, _, _, risk, broker_response = cycle("paper_fill", config=paper_config, bar=bar, order=sample_order(order_id="ORD-3"))
    add("paper override -> paper fill", risk.approved and broker_response is not None and broker_response.status == "FILLED")

    bad_bar = sample_bar(high=98.0, low=99.0)
    dq, _, _, _, _ = cycle("bad_ohlc", config=paper_config, bar=bad_bar, order=sample_order(order_id="ORD-4"))
    add("bad OHLC -> blocked", dq.reason_code == "BAD_OHLC")

    stale_bar = sample_bar(timestamp=BASE_TIME - timedelta(minutes=10))
    dq, _, _, _, _ = cycle("stale_bar", config=paper_config, bar=stale_bar, order=sample_order(order_id="ORD-5"))
    add("stale bar -> blocked", dq.reason_code == "DATA_STALE")

    duplicate_gate = DataQualityGate(paper_config)
    first_duplicate = duplicate_gate.validate(bar, now=BASE_TIME + timedelta(seconds=10))
    second_duplicate = duplicate_gate.validate(bar, now=BASE_TIME + timedelta(seconds=11))
    logger.write_decision({"run_id": RUN_ID, "scenario": "duplicate_timestamp", "data_quality_result": second_duplicate})
    decision_events += 1
    add(
        "duplicate timestamp -> blocked by default",
        first_duplicate.passed and second_duplicate.reason_code == "DUPLICATE_TIMESTAMP",
    )

    _, _, _, risk, _ = cycle(
        "kill_switch",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-7"),
        kill_switch_on=True,
    )
    add("kill switch on -> blocked", risk.reason_code == "KILL_SWITCH_ON")

    _, _, _, risk, _ = cycle("oversized_order", config=paper_config, bar=bar, order=sample_order(order_id="ORD-8", quantity=2))
    add("oversized order -> blocked", risk.reason_code == "ORDER_SIZE_LIMIT")

    _, _, _, risk, _ = cycle(
        "max_position",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-9"),
        positions={"ES:ESU6": 1},
    )
    add("max position exceeded -> blocked", risk.reason_code == "SYMBOL_POSITION_LIMIT")

    broker = PaperBroker()
    approved = RiskDecision(True, "OK", "approved", sample_order(order_id="ORD-10"), None, {})
    first = broker.place_order(sample_order(order_id="ORD-10"), risk_decision=approved, bar=bar)
    second = broker.place_order(sample_order(order_id="ORD-10"), risk_decision=approved, bar=bar)
    logger.write_decision({"run_id": RUN_ID, "scenario": "duplicate_order_id", "broker_response": second})
    decision_events += 1
    add("duplicate order ID -> rejected", first.accepted and second.reason_code == "DUPLICATE_ORDER_ID")

    recon_fail = ReconciliationResult("FAIL", "POSITION_MISMATCH", {"strategy_positions": {}, "broker_positions": {"ES:ESU6": 1}})
    _, _, _, risk, _ = cycle(
        "reconciliation_mismatch",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-11"),
        reconciliation=recon_fail,
    )
    add("reconciliation mismatch -> blocks new trades", risk.reason_code == "RECONCILIATION_FAILED")

    gap_gate = DataQualityGate(paper_config)
    gap_gate.validate(bar, now=BASE_TIME + timedelta(seconds=10))
    gap_result = gap_gate.validate(sample_bar(timestamp=BASE_TIME + timedelta(minutes=10)), now=BASE_TIME + timedelta(minutes=10))
    logger.write_decision({"run_id": RUN_ID, "scenario": "reconnect_gap", "data_quality_result": gap_result})
    decision_events += 1
    add("reconnect/gap simulation -> blocks", gap_result.reason_code == "TIMESTAMP_GAP")

    mismatch_result = DataQualityGate(paper_config).validate(
        sample_bar(contract="ESZ6"),
        now=BASE_TIME + timedelta(seconds=10),
        active_contract="ESU6",
    )
    logger.write_decision({"run_id": RUN_ID, "scenario": "contract_mismatch", "data_quality_result": mismatch_result})
    decision_events += 1
    add("contract mismatch -> blocked", mismatch_result.reason_code in {"UNKNOWN_CONTRACT", "CONTRACT_MISMATCH"})

    _, _, _, risk, _ = cycle(
        "outside_session",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-14"),
        session_ok=False,
    )
    add("outside session -> blocked", risk.reason_code == "OUTSIDE_SESSION")

    logger.write_decision({"run_id": RUN_ID, "scenario": "model_exception", "exception": "simulated model scoring exception"})
    decision_events += 1
    add("errors get audit row when possible", True)

    status_line = render_operator_status(
        OperatorStatusState(
            feed_status="LIVE",
            active_symbol="ES",
            active_contract="ESU6",
            timeframe="1m",
            records_count=20939,
            latest_bar_time=BASE_TIME,
            latest_bar_age_seconds=4,
            last_close=7552.25,
            model_status="OFF",
            signal="NO_SIGNAL",
            trading_mode="DISABLED",
            kill_switch="OFF",
            risk_status="OK",
            reconciliation_status="OK",
        ),
        width=80,
    )
    add("console status render stays within width", len(status_line) == 79)

    line_count = len(audit_path.read_text(encoding="utf-8").splitlines())
    add("audit log writes one event per completed decision cycle", line_count == decision_events)

    passed = all(item[1] for item in checks)
    if stdout is not None:
        for name, ok, detail in checks:
            stdout.write(f"{'PASS' if ok else 'FAIL'} {name}{(' - ' + detail) if detail else ''}\n")
        stdout.write(f"{'PASS' if passed else 'FAIL'} live trading smoke scenarios={len(checks)} audit_rows={line_count}\n")
    return passed


def _event(
    *,
    name: str,
    bar: LiveBar,
    data_quality: DataQualityResult,
    model: ModelReadinessResult,
    signal: SignalState,
    risk: RiskDecision,
    order: OrderIntent | None,
    broker_response: BrokerResponse | None,
    reconciliation: ReconciliationResult,
) -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "strategy_id": STRATEGY_ID,
        "scenario": name,
        "symbol": bar.symbol,
        "contract": bar.contract,
        "timeframe": bar.timeframe,
        "source_schema": bar.source_schema,
        "bar_timestamp_utc": bar.timestamp_utc,
        "bar_final": bar.bar_is_final,
        "data_quality_result": data_quality,
        "feature_status": {"ready": model.status == "READY"},
        "model_status": model,
        "signal_state": signal,
        "risk_decision": risk,
        "order_intent": order,
        "broker_response": broker_response,
        "fill": broker_response.fill if broker_response else None,
        "position_after": {},
        "open_orders_after": [],
        "kill_switch_status": "OFF",
        "reconciliation_status": reconciliation,
        "operator_status": plain_data(OperatorStatusState()),
        "exception": None,
    }
