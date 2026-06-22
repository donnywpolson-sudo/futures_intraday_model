"""Model readiness and signal state for live paper operations."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Mapping

from .schemas import (
    DataQualityResult,
    LiveBar,
    ModelReadinessResult,
    SignalState,
    utc_datetime,
)


class ModelReadinessGate:
    def __init__(
        self,
        *,
        expected_features: tuple[str, ...] = (),
        model_path: str | Path | None = None,
        supported_symbols: tuple[str, ...] = (),
        requires_scaler: bool = False,
        scaler_available: bool = True,
        warmup_bars_required: int = 0,
        model_version: str | None = None,
        config_version: str | None = None,
        feature_version: str | None = None,
    ) -> None:
        self.expected_features = expected_features
        self.model_path = Path(model_path) if model_path is not None else None
        self.supported_symbols = supported_symbols
        self.requires_scaler = requires_scaler
        self.scaler_available = scaler_available
        self.warmup_bars_required = warmup_bars_required
        self.model_version = model_version
        self.config_version = config_version
        self.feature_version = feature_version

    def evaluate(
        self,
        *,
        symbol: str,
        features: Mapping[str, float] | None,
        warmup_bars_available: int = 0,
        model_available: bool = True,
    ) -> ModelReadinessResult:
        if not model_available:
            return self._result("UNAVAILABLE", "MODEL_UNAVAILABLE", features)
        if self.model_path is not None and not self.model_path.exists():
            return self._result("UNAVAILABLE", "MODEL_FILE_MISSING", features)
        if self.supported_symbols and symbol not in self.supported_symbols:
            return self._result("BLOCKED", "SYMBOL_UNSUPPORTED", features)
        if self.requires_scaler and not self.scaler_available:
            return self._result("BLOCKED", "SCALER_UNAVAILABLE", features)
        if warmup_bars_available < self.warmup_bars_required:
            return self._result("UNAVAILABLE", "WARMUP_INCOMPLETE", features)
        if features is None:
            return self._result("UNAVAILABLE", "FEATURES_MISSING", features)

        actual = tuple(features.keys())
        if self.expected_features:
            missing = tuple(feature for feature in self.expected_features if feature not in features)
            extra = tuple(feature for feature in actual if feature not in self.expected_features)
            if missing:
                return self._result("BLOCKED", "FEATURES_MISSING", features)
            if extra:
                return self._result("BLOCKED", "FEATURES_EXTRA", features)
            if actual != self.expected_features:
                return self._result("BLOCKED", "FEATURE_ORDER_MISMATCH", features)

        for value in features.values():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return self._result("BLOCKED", "FEATURE_NOT_NUMERIC", features)
            if not isfinite(numeric):
                return self._result("BLOCKED", "FEATURE_NOT_FINITE", features)

        return self._result("READY", "OK", features)

    def _result(
        self,
        status: str,
        reason_code: str,
        features: Mapping[str, float] | None,
    ) -> ModelReadinessResult:
        actual = tuple(features.keys()) if features is not None else ()
        missing = tuple(feature for feature in self.expected_features if feature not in actual)
        extra = tuple(feature for feature in actual if feature not in self.expected_features) if self.expected_features else ()
        return ModelReadinessResult(
            status=status,
            reason_code=reason_code,
            expected_features=self.expected_features,
            missing_features=missing,
            extra_features=extra,
            model_version=self.model_version,
            config_version=self.config_version,
            feature_version=self.feature_version,
        )


def build_signal_state(
    *,
    bar: LiveBar,
    data_quality: DataQualityResult,
    model_status: ModelReadinessResult,
    now: datetime | None = None,
    prediction: float | None = None,
    score: float | None = None,
    signal: str | None = None,
    confidence: float | None = None,
    allow_partial_preview: bool = False,
) -> SignalState:
    timestamp = utc_datetime(now or datetime.now(timezone.utc))
    if not data_quality.passed or data_quality.severity == "BLOCK":
        return _no_signal(bar, data_quality, model_status, timestamp, f"DATA_QUALITY_{data_quality.reason_code}")
    if model_status.status != "READY":
        return _no_signal(bar, data_quality, model_status, timestamp, f"MODEL_{model_status.reason_code}")
    if not bar.bar_is_final and not allow_partial_preview:
        return _no_signal(bar, data_quality, model_status, timestamp, "PARTIAL_BAR_NON_TRADABLE")
    normalized_signal = (signal or "NO_SIGNAL").upper()
    if normalized_signal not in {"LONG", "SHORT", "FLAT", "NO_SIGNAL"}:
        normalized_signal = "NO_SIGNAL"
    tradable = normalized_signal in {"LONG", "SHORT", "FLAT"} and bar.bar_is_final
    if normalized_signal == "NO_SIGNAL":
        tradable = False
    return SignalState(
        symbol=bar.symbol,
        contract=bar.contract,
        timestamp_utc=timestamp,
        bar_timestamp_utc=utc_datetime(bar.timestamp_utc),
        timeframe=bar.timeframe,
        features_ready=True,
        model_available=True,
        model_version=model_status.model_version,
        config_version=model_status.config_version,
        feature_version=model_status.feature_version,
        prediction=prediction,
        score=score,
        signal=normalized_signal,
        confidence=confidence,
        tradable=tradable,
        skip_reason=None if tradable else "NO_TRADABLE_SIGNAL",
        data_quality_status=data_quality.severity,
        source_schema=bar.source_schema,
        bar_is_final=bar.bar_is_final,
    )


def _no_signal(
    bar: LiveBar,
    data_quality: DataQualityResult,
    model_status: ModelReadinessResult,
    timestamp: datetime,
    reason: str,
) -> SignalState:
    return SignalState(
        symbol=bar.symbol,
        contract=bar.contract,
        timestamp_utc=timestamp,
        bar_timestamp_utc=utc_datetime(bar.timestamp_utc),
        timeframe=bar.timeframe,
        features_ready=model_status.status == "READY",
        model_available=model_status.status == "READY",
        model_version=model_status.model_version,
        config_version=model_status.config_version,
        feature_version=model_status.feature_version,
        prediction=None,
        score=None,
        signal="NO_SIGNAL",
        confidence=None,
        tradable=False,
        skip_reason=reason,
        data_quality_status=data_quality.severity,
        source_schema=bar.source_schema,
        bar_is_final=bar.bar_is_final,
    )
