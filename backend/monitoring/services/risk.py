"""Risk assessment, elapsed-time trends and severity hysteresis."""

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
import os

from django.conf import settings

from backend.monitoring.enums import DensityTrend, Severity


@dataclass(frozen=True)
class RiskPolicy:
    elevated_enter: float = 1.0
    elevated_exit: float = 0.8
    high_enter: float = 1.5
    high_exit: float = 1.2
    critical_enter: float = 2.0
    critical_exit: float = 1.6
    ewma_tau_seconds: float = 30.0
    prediction_horizon_minutes: float = 10.0
    stale_seconds: float = 15.0
    recovery_seconds: float = 30.0
    recovery_min_samples: int = 2
    warning_cooldown_seconds: float = 10.0
    policy_version: str = "v1-demo"

    @classmethod
    def from_settings(cls) -> "RiskPolicy":
        stale = getattr(settings, "METRIC_STALE_SECONDS", 15)
        recovery = getattr(settings, "CRITICAL_RECOVERY_SECONDS", 30)
        read = lambda name, default: float(os.getenv(name, default))
        return cls(
            elevated_enter=read("RISK_ELEVATED_ENTER", 1.0),
            elevated_exit=read("RISK_ELEVATED_EXIT", 0.8),
            high_enter=read("RISK_HIGH_ENTER", 1.5),
            high_exit=read("RISK_HIGH_EXIT", 1.2),
            critical_enter=read("RISK_CRITICAL_ENTER", 2.0),
            critical_exit=read("RISK_CRITICAL_EXIT", 1.6),
            ewma_tau_seconds=read("RISK_EWMA_TAU_SECONDS", 30.0),
            prediction_horizon_minutes=read("RISK_PREDICTION_HORIZON_MINUTES", 10.0),
            stale_seconds=float(stale),
            recovery_seconds=float(recovery),
            recovery_min_samples=max(2, int(os.getenv("RISK_RECOVERY_MIN_SAMPLES", "2"))),
            warning_cooldown_seconds=read("RISK_WARNING_COOLDOWN_SECONDS", 10.0),
        )

    def validate(self) -> None:
        pairs = (
            ("elevated", self.elevated_exit, self.elevated_enter),
            ("high", self.high_exit, self.high_enter),
            ("critical", self.critical_exit, self.critical_enter),
        )
        for name, exit_value, enter_value in pairs:
            if exit_value < 0 or enter_value < exit_value:
                raise ValueError(f"invalid {name} threshold hysteresis")
        if not (0 < self.ewma_tau_seconds and 0 < self.recovery_seconds):
            raise ValueError("EWMA and recovery durations must be positive")


@dataclass(frozen=True)
class RiskResult:
    severity: Severity
    risk_score: float
    smoothed_density: float
    growth_rate: float
    density_trend: DensityTrend
    predicted_threshold_time: datetime | None
    forecast_density: float
    reason: str


class RiskAssessor:
    def __init__(self, policy: RiskPolicy | None = None):
        self.policy = policy or RiskPolicy.from_settings()
        self.policy.validate()

    def _severity_raw(self, density: float) -> Severity:
        if density >= self.policy.critical_enter:
            return Severity.CRITICAL
        if density >= self.policy.high_enter:
            return Severity.HIGH
        if density >= self.policy.elevated_enter:
            return Severity.ELEVATED
        return Severity.NORMAL

    def apply_hysteresis(self, density: float, current: Severity | str | None) -> Severity:
        raw = self._severity_raw(density)
        try:
            current = Severity(current)
        except (TypeError, ValueError):
            current = Severity.NORMAL

        if raw == Severity.CRITICAL:
            return Severity.CRITICAL
        if current == Severity.CRITICAL:
            return Severity.CRITICAL if density >= self.policy.critical_exit else (
                Severity.HIGH if density >= self.policy.high_exit else (
                    Severity.ELEVATED if density >= self.policy.elevated_exit else Severity.NORMAL
                )
            )
        if current == Severity.HIGH:
            if density >= self.policy.high_enter:
                return Severity.HIGH
            return Severity.ELEVATED if density >= self.policy.elevated_exit else Severity.NORMAL
        if current == Severity.ELEVATED:
            if density >= self.policy.elevated_enter:
                return Severity.ELEVATED
            return Severity.NORMAL
        return raw

    def assess(
        self,
        density: float,
        captured_at: datetime,
        prior_density: float | None = None,
        prior_captured_at: datetime | None = None,
        current_severity: Severity | str | None = None,
    ) -> RiskResult:
        if not math.isfinite(density) or density < 0:
            raise ValueError("density must be finite and nonnegative")

        elapsed_seconds = 0.0
        smoothed = density
        if prior_density is not None and prior_captured_at is not None:
            elapsed_seconds = max(0.0, (captured_at - prior_captured_at).total_seconds())
            if elapsed_seconds > 0:
                alpha = 1.0 - math.exp(-elapsed_seconds / self.policy.ewma_tau_seconds)
                smoothed = (alpha * density) + ((1.0 - alpha) * prior_density)

        growth = 0.0
        if elapsed_seconds > 0 and prior_density is not None:
            growth = (smoothed - prior_density) * 60.0 / elapsed_seconds

        if abs(growth) < 1e-6:
            trend = DensityTrend.STABLE
        elif growth > 0:
            trend = DensityTrend.RISING
        else:
            trend = DensityTrend.FALLING

        severity = self.apply_hysteresis(smoothed, current_severity)
        horizon = timedelta(minutes=self.policy.prediction_horizon_minutes)
        forecast = smoothed + growth * self.policy.prediction_horizon_minutes
        predicted_at = None
        if growth > 0:
            threshold = self.policy.critical_enter
            if smoothed < threshold:
                minutes = (threshold - smoothed) * 60.0 / growth
                predicted_at = captured_at + timedelta(minutes=minutes)

        severity_rank = {
            Severity.NORMAL: 20,
            Severity.ELEVATED: 45,
            Severity.HIGH: 70,
            Severity.CRITICAL: 100,
            Severity.UNKNOWN: 0,
        }
        threshold_ratio = smoothed / max(self.policy.critical_enter, 1e-9)
        risk_score = round(
            min(100.0, max(severity_rank[severity] * 0.55, threshold_ratio * 100.0) * 1.0),
            2,
        )
        reason = f"density={smoothed:.3f} people/m2; trend={trend.value}; policy={self.policy.policy_version}"
        return RiskResult(severity, risk_score, smoothed, round(growth, 6),
                          trend, predicted_at, max(0.0, forecast), reason)
