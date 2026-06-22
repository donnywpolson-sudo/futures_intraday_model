"""Deterministic paper-only decision-loop smoke scenarios."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, TextIO

from .audit import AuditLogger
from .broker import PaperBroker
from .model import ModelReadinessGate, build_signal_state
from .operator import (
    OperatorControlDecision,
    OperatorControlState,
    OperatorStatusState,
    evaluate_operator_controls,
    load_operator_control_state,
    render_operator_status,
)
from .quality import DataQualityGate
from .reconciliation import Reconciler
from .risk import RiskManager, SessionGuard
from .schemas import (
    BrokerResponse,
    DataQualityResult,
    LiveBar,
    LiveTradingConfig,
    ModelReadinessResult,
    OrderIntent,
    ReconciliationResult,
    RiskDecision,
    SignalState,
    paper_smoke_config,
    position_key,
    safe_default_config,
    utc_datetime,
)

RUN_ID = "live-trading-smoke"
STRATEGY_ID = "smoke-paper-strategy"
BASE_TIME = datetime(2026, 6, 22, 14, 30, tzinfo=timezone.utc)


@dataclass(frozen=True)
class DecisionCycleResult:
    name: str
    data_quality: DataQualityResult
    model: ModelReadinessResult
    signal: SignalState
    risk: RiskDecision
    operator_control: OperatorControlState
    operator_control_decision: OperatorControlDecision
    broker_response: BrokerResponse | None
    reconciliation: ReconciliationResult
    operator_status: OperatorStatusState
    status_line: str
    exception: str | None


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


def sample_order(
    *,
    order_id: str = "ORD-1",
    quantity: int = 1,
    side: str = "BUY",
    symbol: str = "ES",
    contract: str = "ESU6",
    bar_timestamp: datetime = BASE_TIME,
) -> OrderIntent:
    return OrderIntent(
        order_id=order_id,
        strategy_id=STRATEGY_ID,
        symbol=symbol,
        contract=contract,
        side=side,
        quantity=quantity,
        order_type="LIMIT",
        limit_price=100.5,
        stop_price=None,
        time_in_force="DAY",
        bar_timestamp=bar_timestamp,
        created_timestamp=BASE_TIME + timedelta(seconds=1),
        reason="smoke signal",
        signal_id=f"SIG-{order_id}",
    )


def run_smoke(
    *,
    audit_dir: str | Path = "reports/live_trading_smoke",
    stdout: TextIO | None = None,
    force_failure: bool = False,
) -> bool:
    audit_path = Path(audit_dir) / "audit.jsonl"
    if audit_path.exists():
        audit_path.unlink()
    logger = AuditLogger(audit_path)
    checks: list[tuple[str, bool, str]] = []
    results: list[DecisionCycleResult] = []

    def add(name: str, passed: bool, detail: str = "") -> None:
        checks.append((name, passed, detail))

    def cycle(name: str, **kwargs: Any) -> DecisionCycleResult:
        result = _run_decision_cycle(name=name, logger=logger, cycle_number=len(results) + 1, **kwargs)
        results.append(result)
        return result

    safe_config = safe_default_config()
    paper_config = paper_smoke_config(audit_dir=str(audit_dir))
    bar = sample_bar()

    result = cycle(
        "missing_model_output",
        config=paper_config,
        bar=bar,
        model_available=False,
        explicit_signal=None,
        order=None,
    )
    add(
        "missing model output -> NO_SIGNAL -> no order",
        result.signal.signal == "NO_SIGNAL" and not result.risk.approved and result.broker_response is None,
    )

    missing_features = cycle(
        "missing_features",
        config=paper_config,
        bar=bar,
        model_gate=ModelReadinessGate(expected_features=("close", "volume"), model_version="smoke-v1"),
        features={"close": bar.close},
        explicit_signal="LONG",
        order=sample_order(order_id="ORD-MISSING-FEATURES"),
    )
    add(
        "missing features -> NO_SIGNAL -> no order",
        missing_features.signal.signal == "NO_SIGNAL"
        and missing_features.risk.reason_code == "MODEL_FEATURES_MISSING"
        and missing_features.broker_response is None,
    )

    result = cycle("trading_disabled", config=safe_config, bar=bar, order=sample_order(order_id="ORD-SAFE"))
    add("valid signal but allow_trading=false -> rejected", result.risk.reason_code == "TRADING_DISABLED")

    result = cycle("paper_fill", config=paper_config, bar=bar, order=sample_order(order_id="ORD-FILL"))
    add(
        "paper override -> paper fill",
        result.risk.approved and result.broker_response is not None and result.broker_response.status == "FILLED",
    )

    result = cycle(
        "operator_kill_switch",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-OP-KILL"),
        operator_control=OperatorControlState(
            kill_switch_active=True,
            reason="operator kill switch",
            message="operator kill switch blocks new orders",
        ),
    )
    add(
        "operator kill switch -> no broker submit",
        result.risk.reason_code == "OPERATOR_KILL_SWITCH"
        and result.broker_response is None
        and result.operator_status.kill_switch == "ON",
    )

    result = cycle(
        "operator_trading_disabled",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-OP-DISABLED"),
        operator_control=OperatorControlState(
            trading_enabled=False,
            reason="operator disabled trading",
            message="operator disabled trading",
        ),
    )
    add(
        "operator trading disabled -> no broker submit",
        result.risk.reason_code == "OPERATOR_TRADING_DISABLED" and result.broker_response is None,
    )

    result = cycle(
        "operator_pause_new_entries",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-OP-PAUSE"),
        operator_control=OperatorControlState(
            pause_new_entries=True,
            reason="operator paused new entries",
            message="operator paused new entries",
        ),
    )
    add(
        "operator pause new entries -> no broker submit",
        result.risk.reason_code == "OPERATOR_PAUSE_NEW_ENTRIES" and result.broker_response is None,
    )

    bad_bar = sample_bar(high=98.0, low=99.0)
    result = cycle("bad_ohlc", config=paper_config, bar=bad_bar, order=sample_order(order_id="ORD-BAD-OHLC"))
    add("bad OHLC -> blocked", result.data_quality.reason_code == "BAD_OHLC")

    stale_bar = sample_bar(timestamp=BASE_TIME - timedelta(minutes=10))
    result = cycle("stale_bar", config=paper_config, bar=stale_bar, order=sample_order(order_id="ORD-STALE"))
    add("stale bar -> blocked", result.data_quality.reason_code == "DATA_STALE")

    result = cycle(
        "stale_heartbeat",
        config=paper_config,
        bar=bar,
        heartbeat_timestamp_utc=BASE_TIME - timedelta(minutes=2),
        order=sample_order(order_id="ORD-HEARTBEAT"),
    )
    add("stale feed heartbeat -> blocked", result.data_quality.reason_code == "HEARTBEAT_STALE")

    result = cycle(
        "feed_disconnected",
        config=paper_config,
        bar=bar,
        feed_connected=False,
        order=sample_order(order_id="ORD-DISCONNECT"),
    )
    add("market data disconnect -> blocked", result.data_quality.reason_code == "FEED_DISCONNECTED")

    result = cycle(
        "no_heartbeat",
        config=paper_config,
        bar=bar,
        heartbeat_required=True,
        heartbeat_timestamp_utc=None,
        order=sample_order(order_id="ORD-NO-HEARTBEAT"),
    )
    add("missing heartbeat -> blocked", result.data_quality.reason_code == "NO_HEARTBEAT")

    duplicate_gate = DataQualityGate(paper_config)
    first_duplicate = cycle(
        "duplicate_timestamp_seed",
        config=paper_config,
        bar=bar,
        data_gate=duplicate_gate,
        order=None,
        explicit_signal=None,
    )
    duplicate_result = cycle(
        "duplicate_timestamp",
        config=paper_config,
        bar=bar,
        data_gate=duplicate_gate,
        order=sample_order(order_id="ORD-DUP-TS"),
    )
    add(
        "duplicate timestamp -> blocked by default",
        first_duplicate.data_quality.passed
        and duplicate_result.data_quality.reason_code == "DUPLICATE_TIMESTAMP"
        and duplicate_result.data_quality.duplicate_timestamp_policy == "block",
    )

    result = cycle(
        "kill_switch",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-KILL"),
        kill_switch_on=True,
    )
    add("kill switch on -> blocked", result.risk.reason_code == "KILL_SWITCH_ON")

    result = cycle("oversized_order", config=paper_config, bar=bar, order=sample_order(order_id="ORD-BIG", quantity=2))
    add("oversized order -> blocked", result.risk.reason_code == "ORDER_SIZE_LIMIT")

    duplicate_broker = PaperBroker()
    first_order = sample_order(order_id="ORD-DUP")
    first_duplicate_order = cycle(
        "duplicate_order_id_seed",
        config=paper_config,
        bar=bar,
        order=first_order,
        broker=duplicate_broker,
    )
    duplicate_order = cycle(
        "duplicate_order_id",
        config=paper_config,
        bar=bar,
        order=first_order,
        broker=duplicate_broker,
        pre_reconciliation=ReconciliationResult("OK", "OK", {}),
    )
    add(
        "duplicate order ID -> rejected",
        first_duplicate_order.broker_response is not None
        and first_duplicate_order.broker_response.accepted
        and duplicate_order.broker_response is not None
        and duplicate_order.broker_response.reason_code == "DUPLICATE_ORDER_ID",
    )

    recon_broker = PaperBroker()
    recon_broker.positions[position_key("ES", "ESU6")] = 1
    recon_fail = Reconciler().reconcile(strategy_positions={}, broker=recon_broker, now=BASE_TIME)
    result = cycle(
        "reconciliation_mismatch",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-RECON"),
        pre_reconciliation=recon_fail,
    )
    add("reconciliation mismatch -> blocks new trades", result.risk.reason_code == "RECONCILIATION_FAILED")

    gap_gate = DataQualityGate(paper_config)
    cycle("reconnect_gap_seed", config=paper_config, bar=bar, data_gate=gap_gate, order=None, explicit_signal=None)
    gap_bar = sample_bar(timestamp=BASE_TIME + timedelta(minutes=10))
    result = cycle(
        "reconnect_gap",
        config=paper_config,
        bar=gap_bar,
        data_gate=gap_gate,
        order=sample_order(order_id="ORD-GAP", bar_timestamp=gap_bar.timestamp_utc),
    )
    add("reconnect/gap simulation -> blocks", result.data_quality.reason_code == "TIMESTAMP_GAP")

    result = cycle(
        "reconnect_backfill_required",
        config=paper_config,
        bar=bar,
        reconnect_backfill_required=True,
        order=sample_order(order_id="ORD-BACKFILL"),
    )
    add("reconnect backfill required -> blocked", result.data_quality.reason_code == "RECONNECT_BACKFILL_REQUIRED")

    pending_reconnect = cycle(
        "reconnect_pending",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-RECONNECT-PENDING"),
        heartbeat_timestamp_utc=BASE_TIME + timedelta(seconds=20),
        reconnect_reconciled=False,
    )
    cleared_reconnect = cycle(
        "reconnect_cleared",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-RECONNECT-CLEARED"),
        heartbeat_timestamp_utc=BASE_TIME + timedelta(seconds=20),
        reconnect_reconciled=True,
    )
    add(
        "reconnect state -> blocked until reconciled",
        pending_reconnect.risk.reason_code == "RECONNECT_RECONCILIATION_PENDING" and cleared_reconnect.risk.approved,
    )

    mismatch_config = replace(paper_config, allowed_contracts=("ESU6", "ESZ6"))
    mismatch_bar = sample_bar(contract="ESZ6")
    result = cycle(
        "contract_mismatch",
        config=mismatch_config,
        bar=mismatch_bar,
        active_contract="ESU6",
        order=sample_order(order_id="ORD-CONTRACT", contract="ESZ6"),
    )
    add("contract mismatch -> blocked", result.data_quality.reason_code == "CONTRACT_MISMATCH")

    result = cycle(
        "root_symbol_mismatch",
        config=paper_config,
        bar=bar,
        active_symbol="NQ",
        order=sample_order(order_id="ORD-ROOT"),
    )
    add("root symbol mismatch -> blocked", result.data_quality.reason_code == "ROOT_SYMBOL_MISMATCH")

    result = cycle(
        "outside_session",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-SESSION"),
        session_ok=False,
    )
    add("outside session -> blocked", result.risk.reason_code == "OUTSIDE_SESSION")

    missing_session_guard = SessionGuard.from_strings({"NQ": ("00:00", "23:59", "UTC")})
    result = cycle(
        "missing_session_config",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-MISSING-SESSION"),
        session_ok=None,
        session_guard=missing_session_guard,
    )
    add("missing session config -> blocked", result.risk.reason_code == "OUTSIDE_SESSION")

    closed_session_guard = SessionGuard.from_strings({"ES": ("15:00", "16:00", "UTC")})
    result = cycle(
        "known_closed_period",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-CLOSED-SESSION"),
        session_ok=None,
        session_guard=closed_session_guard,
    )
    add("known closed session period -> blocked", result.data_quality.reason_code == "SESSION_CLOSED")

    result = cycle(
        "monitor_only_outside_session",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-MONITOR-ONLY"),
        session_ok=False,
        monitor_only=True,
    )
    add(
        "monitor-only outside session -> non-tradable",
        result.risk.reason_code == "MONITOR_ONLY" and not result.signal.tradable and result.broker_response is None,
    )

    result = cycle(
        "unsafe_live_mode",
        config=replace(paper_config, mode="live"),
        bar=bar,
        order=sample_order(order_id="ORD-LIVE"),
    )
    add("unsafe live mode -> blocked", result.risk.reason_code == "LIVE_BROKER_BLOCKED")

    result = cycle(
        "forced_exception",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-EXCEPTION"),
        raise_model_exception=True,
    )
    add(
        "exception during decision cycle -> audit row and fail closed",
        result.exception is not None and result.risk.reason_code == "EXCEPTION" and not result.risk.approved,
    )

    result = cycle(
        "feature_exception",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-FEATURE-EXCEPTION"),
        raise_feature_exception=True,
    )
    add(
        "feature exception -> no signal and no broker submit",
        result.exception is not None and result.signal.signal == "NO_SIGNAL" and result.broker_response is None,
    )

    result = cycle(
        "broker_exception",
        config=paper_config,
        bar=bar,
        order=sample_order(order_id="ORD-BROKER-EXCEPTION"),
        raise_broker_exception=True,
    )
    add(
        "broker sim exception -> blocked and audited",
        result.exception is not None and result.risk.reason_code == "EXCEPTION" and result.broker_response is None,
    )

    add(
        "operator status render stays within width",
        all(len(result.status_line) == 119 and "\n" not in result.status_line for result in results),
    )

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    add("audit log writes one event per completed decision cycle", len(lines) == len(results))
    add("audit rows include nullable exception field", all('"exception":' in line for line in lines))
    add(
        "operator status comes from decision-loop state",
        any(
            result.name == "paper_fill"
            and result.operator_status.signal == "LONG"
            and result.operator_status.risk_status == "OK"
            and result.operator_status.paper_position == "ES:ESU6=1"
            for result in results
        ),
    )

    if force_failure:
        add("forced failure requested", False, "force_failure=True")

    passed = all(item[1] for item in checks)
    if stdout is not None:
        for name, ok, detail in checks:
            stdout.write(f"{'PASS' if ok else 'FAIL'} {name}{(' - ' + detail) if detail else ''}\n")
        stdout.write(
            f"{'PASS' if passed else 'FAIL'} live trading smoke scenarios={len(checks)} "
            f"decision_cycles={len(results)} audit_rows={len(lines)}\n"
        )
    return passed


def _run_decision_cycle(
    *,
    name: str,
    logger: AuditLogger,
    cycle_number: int,
    config: LiveTradingConfig,
    bar: LiveBar,
    model_gate: ModelReadinessGate | None = None,
    data_gate: DataQualityGate | None = None,
    broker: PaperBroker | None = None,
    features: Mapping[str, float] | None = None,
    model_available: bool = True,
    explicit_signal: str | None = "LONG",
    order: OrderIntent | None = None,
    kill_switch_on: bool = False,
    operator_control: OperatorControlState | None = None,
    operator_control_path: str | Path | None = None,
    positions: dict[str, int] | None = None,
    session_ok: bool | None = True,
    session_guard: SessionGuard | None = None,
    pre_reconciliation: ReconciliationResult | None = None,
    reconnect_reconciled: bool = True,
    heartbeat_timestamp_utc: datetime | None = None,
    heartbeat_required: bool = False,
    feed_connected: bool = True,
    reconnect_backfill_required: bool = False,
    active_symbol: str | None = None,
    active_contract: str | None = None,
    monitor_only: bool = False,
    raise_feature_exception: bool = False,
    raise_model_exception: bool = False,
    raise_broker_exception: bool = False,
) -> DecisionCycleResult:
    now = BASE_TIME + timedelta(seconds=10 + cycle_number)
    broker = broker or PaperBroker()
    data_gate = data_gate or DataQualityGate(config, session_guard=session_guard)
    model_gate = model_gate or ModelReadinessGate(model_version="smoke-v1")
    positions = positions or {}
    operator_control_state = operator_control or load_operator_control_state(operator_control_path, now=now)
    operator_control_decision = evaluate_operator_controls(operator_control_state, is_new_entry=order is not None)
    data_quality = _exception_data_quality(bar, config, "NOT_RUN", "data quality not evaluated")
    model = ModelReadinessResult("UNAVAILABLE", "NOT_RUN")
    signal = build_signal_state(bar=bar, data_quality=data_quality, model_status=model, now=now, signal=None)
    risk = RiskDecision(False, "NOT_RUN", "risk not evaluated", None, order, {})
    reconciliation = pre_reconciliation or ReconciliationResult("OK", "OK", {})
    broker_response = None
    exception: str | None = None

    try:
        data_quality = data_gate.validate(
            bar,
            now=now,
            heartbeat_timestamp_utc=heartbeat_timestamp_utc,
            heartbeat_required=heartbeat_required,
            feed_connected=feed_connected,
            reconnect_backfill_required=reconnect_backfill_required,
            active_symbol=active_symbol,
            active_contract=active_contract,
        )
        if raise_feature_exception:
            raise RuntimeError("forced smoke feature exception")
        if raise_model_exception:
            raise RuntimeError("forced smoke model exception")
        model = model_gate.evaluate(
            symbol=bar.symbol,
            features={"close": bar.close} if features is None else features,
            warmup_bars_available=1,
            model_available=model_available,
        )
        signal = build_signal_state(
            bar=bar,
            data_quality=data_quality,
            model_status=model,
            now=now + timedelta(seconds=1),
            score=0.8 if explicit_signal in {"LONG", "SHORT"} else None,
            signal=explicit_signal,
        )
        if monitor_only:
            signal = replace(signal, tradable=False, skip_reason="MONITOR_ONLY")
        if pre_reconciliation is None:
            reconciliation = Reconciler().reconcile(strategy_positions=positions, broker=broker, now=now)
        risk = RiskManager(config, session_guard=session_guard).evaluate(
            order=order,
            signal=signal,
            data_quality=data_quality,
            model_status=model,
            reconciliation=reconciliation,
            positions=positions,
            now=now + timedelta(seconds=2),
            kill_switch_on=kill_switch_on,
            session_ok=session_ok,
            reconnect_reconciled=reconnect_reconciled,
            active_symbol=active_symbol,
            active_contract=active_contract,
            monitor_only=monitor_only,
        )
        if order is not None and risk.approved:
            operator_control_decision = evaluate_operator_controls(operator_control_state, is_new_entry=True)
            if not operator_control_decision.allowed:
                risk = _operator_blocked_risk(risk, order, operator_control_decision)
        if order is not None and risk.approved:
            try:
                logger.ensure_writable()
            except OSError as exc:
                raise RuntimeError(f"audit log write preflight failed: {exc}") from exc
            if raise_broker_exception:
                raise RuntimeError("forced smoke broker exception")
            broker_response = broker.place_order(order, risk_decision=risk, bar=bar)
            if broker_response.accepted:
                reconciliation = Reconciler().reconcile(strategy_positions=dict(broker.positions), broker=broker, now=now)
    except Exception as exc:  # noqa: BLE001 - smoke runner must log and fail closed.
        exception = f"{type(exc).__name__}: {exc}"
        data_quality = _exception_data_quality(bar, config, "EXCEPTION", exception)
        model = ModelReadinessResult("UNAVAILABLE", "EXCEPTION")
        signal = build_signal_state(bar=bar, data_quality=data_quality, model_status=model, now=now, signal=None)
        risk = RiskDecision(
            False,
            "EXCEPTION",
            "decision cycle exception; no order can be submitted",
            None,
            order,
            {"mode": config.mode, "allow_trading": config.allow_trading},
        )
        reconciliation = ReconciliationResult("FAIL", "EXCEPTION", {"exception": exception})
        broker_response = None

    operator_status = _operator_status(
        config=config,
        bar=bar,
        data_quality=data_quality,
        model=model,
        signal=signal,
        risk=risk,
        broker=broker,
        reconciliation=reconciliation,
        kill_switch_on=kill_switch_on,
        operator_control=operator_control_state,
        exception=exception,
        cycle_number=cycle_number,
    )
    status_line = render_operator_status(operator_status, width=120)
    result = DecisionCycleResult(
        name=name,
        data_quality=data_quality,
        model=model,
        signal=signal,
        risk=risk,
        operator_control=operator_control_state,
        operator_control_decision=operator_control_decision,
        broker_response=broker_response,
        reconciliation=reconciliation,
        operator_status=operator_status,
        status_line=status_line,
        exception=exception,
    )
    logger.write_decision(
        _event(
            name=name,
            bar=bar,
            data_quality=data_quality,
            model=model,
            signal=signal,
            risk=risk,
            operator_control=operator_control_state,
            operator_control_decision=operator_control_decision,
            order=order,
            broker_response=broker_response,
            reconciliation=reconciliation,
            operator_status=operator_status,
            status_line=status_line,
            broker=broker,
            exception=exception,
        )
    )
    return result


def _event(
    *,
    name: str,
    bar: LiveBar,
    data_quality: DataQualityResult,
    model: ModelReadinessResult,
    signal: SignalState,
    risk: RiskDecision,
    operator_control: OperatorControlState,
    operator_control_decision: OperatorControlDecision,
    order: OrderIntent | None,
    broker_response: BrokerResponse | None,
    reconciliation: ReconciliationResult,
    operator_status: OperatorStatusState,
    status_line: str,
    broker: PaperBroker,
    exception: str | None,
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
        "operator_control": operator_control,
        "operator_control_decision": operator_control_decision,
        "order_intent": order,
        "broker_response": broker_response,
        "fill": broker_response.fill if broker_response else None,
        "position_after": dict(broker.positions),
        "open_orders_after": sorted(broker.open_orders),
        "kill_switch_status": operator_status.kill_switch,
        "reconciliation_status": reconciliation,
        "operator_status": operator_status,
        "operator_status_line": status_line,
        "exception": exception,
    }


def _operator_status(
    *,
    config: LiveTradingConfig,
    bar: LiveBar,
    data_quality: DataQualityResult,
    model: ModelReadinessResult,
    signal: SignalState,
    risk: RiskDecision,
    broker: PaperBroker,
    reconciliation: ReconciliationResult,
    kill_switch_on: bool,
    operator_control: OperatorControlState,
    exception: str | None,
    cycle_number: int,
) -> OperatorStatusState:
    if exception is not None:
        feed_status = "ERROR"
    elif data_quality.reason_code in {"DATA_STALE", "HEARTBEAT_STALE"}:
        feed_status = "STALE"
    elif data_quality.passed:
        feed_status = "LIVE"
    else:
        feed_status = "BLOCKED"
    error_code = _last_error_code(data_quality, model, risk, broker, exception)
    return OperatorStatusState(
        feed_status=feed_status,
        active_symbol=bar.symbol,
        active_contract=bar.contract,
        timeframe=bar.timeframe,
        records_count=cycle_number,
        latest_bar_time=bar.timestamp_utc,
        latest_bar_age_seconds=data_quality.latest_bar_age_seconds,
        last_close=bar.close,
        model_status=model.reason_code,
        signal=signal.signal,
        trading_mode=config.mode.upper(),
        kill_switch="ON" if kill_switch_on or operator_control.kill_switch_active else "OFF",
        risk_status=risk.reason_code,
        reconciliation_status=reconciliation.reason_code,
        paper_position=_format_positions(broker.positions),
        last_error_code=error_code,
    )


def _operator_blocked_risk(
    risk: RiskDecision,
    order: OrderIntent,
    decision: OperatorControlDecision,
) -> RiskDecision:
    snapshot = dict(risk.risk_snapshot)
    snapshot["operator_control"] = decision.state
    snapshot["operator_control_decision"] = decision
    return RiskDecision(False, decision.reason_code, decision.reason, None, order, snapshot)


def _last_error_code(
    data_quality: DataQualityResult,
    model: ModelReadinessResult,
    risk: RiskDecision,
    broker: PaperBroker,
    exception: str | None,
) -> str | None:
    if exception is not None:
        return "EXCEPTION"
    if not data_quality.passed:
        return data_quality.reason_code
    if model.status != "READY":
        return model.reason_code
    if not risk.approved:
        return risk.reason_code
    if risk.adjusted_order is not None and broker.fills and broker.fills[-1].order_id == risk.adjusted_order.order_id:
        return None
    return None


def _format_positions(positions: Mapping[str, int]) -> str | None:
    active = [f"{key}={quantity}" for key, quantity in sorted(positions.items()) if quantity != 0]
    return ",".join(active) if active else None


def _exception_data_quality(
    bar: LiveBar,
    config: LiveTradingConfig,
    reason_code: str,
    message: str,
) -> DataQualityResult:
    try:
        timestamp = utc_datetime(bar.timestamp_utc)
    except ValueError:
        timestamp = None
    return DataQualityResult(
        False,
        "BLOCK",
        reason_code,
        message,
        bar.symbol,
        timestamp,
        None,
        config.duplicate_timestamp_policy,
    )
