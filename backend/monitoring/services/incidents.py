"""Transactional CriticalIncident lifecycle."""

from datetime import timedelta
import uuid

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from backend.monitoring.enums import IncidentState, Severity
from backend.monitoring.models import CriticalIncident, EventLogEntry
from backend.monitoring.services.risk import RiskPolicy, RiskResult


class CriticalIncidentEngine:
    def __init__(self, publisher=None, policy: RiskPolicy | None = None):
        self.publisher = publisher
        self.policy = policy or RiskPolicy.from_settings()

    def _publish(self, event_type: str, incident: CriticalIncident, reason: str,
                 metrics: dict, sequence: int | None = None):
        if not self.publisher:
            return
        payload = {
            "incident_id": str(incident.incident_id),
            "feed_id": str(incident.feed_id),
            "zone_id": str(incident.zone_id) if incident.zone_id else None,
            "state": incident.state,
            "severity": incident.severity,
            "acknowledged": incident.acknowledged,
            "acknowledged_at": incident.acknowledged_at.isoformat() if incident.acknowledged_at else None,
            "acknowledged_by": incident.acknowledged_by,
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "reason": reason,
            "latest_metrics": metrics,
            "state_version": self._state_version(incident),
        }
        transaction.on_commit(
            lambda: self.publisher.publish(
                event_type, payload, feed_id=str(incident.feed_id)
            )
        )

    @staticmethod
    def _state_version(incident: CriticalIncident) -> int:
        if isinstance(incident.latest_metrics, dict):
            return int(incident.latest_metrics.get("state_version", 1))
        return 1

    def _audit(self, incident: CriticalIncident, event_type: str, reason: str,
               metrics: dict, severity: Severity = Severity.CRITICAL):
        next_sequence = (EventLogEntry.objects.aggregate(Max("sequence"))["sequence__max"] or 0) + 1
        EventLogEntry.objects.create(
            feed=incident.feed,
            feed_name=incident.feed.name,
            category="crowd",
            severity=severity.value,
            event_type=event_type,
            message=reason,
            delta_percent=None,
            density_people_per_m2=metrics.get("density"),
            people_count=metrics.get("people_count"),
            incident_id=incident.incident_id,
            state=incident.state,
            sequence=next_sequence,
        )
        return next_sequence

    def _metrics(self, risk: RiskResult, people_count: int | None,
                 sequence: int, state_version: int) -> dict:
        return {
            "density": risk.smoothed_density,
            "people_count": people_count,
            "growth_rate": risk.growth_rate,
            "density_trend": risk.density_trend.value,
            "predicted_threshold_time": (
                risk.predicted_threshold_time.isoformat()
                if risk.predicted_threshold_time else None
            ),
            "sequence": sequence,
            "state_version": state_version,
            "policy_version": self.policy.policy_version,
        }

    @transaction.atomic
    def process_observation(self, *, feed, zone=None, captured_at,
                            risk: RiskResult, people_count=None, sequence=0):
        feed = type(feed).objects.select_for_update().get(pk=feed.pk)
        active = (
            CriticalIncident.objects.select_for_update()
            .filter(feed=feed, state=IncidentState.ACTIVE.value)
            .order_by("started_at", "incident_id")
            .first()
        )

        if risk.severity != Severity.CRITICAL:
            if active:
                active.feed = feed
                active.last_updated_at = timezone.now()
                active.latest_metrics = self._metrics(
                    risk, people_count, sequence,
                    int((active.latest_metrics or {}).get("state_version", 1)) + 1,
                )
                active.save(update_fields=["last_updated_at", "latest_metrics"])

            # A non-critical observation is safe only below the critical exit threshold.
            if risk.smoothed_density >= self.policy.critical_exit:
                if active and active.recovery_started_at:
                    active.recovery_started_at = None
                    active.save(update_fields=["recovery_started_at"])
                return {"active_incident": active, "resolved": False, "recovery_started": False}

            if active:
                if active.recovery_started_at is None:
                    active.recovery_started_at = captured_at
                    active.save(update_fields=["recovery_started_at", "last_updated_at"])
                    metrics = active.latest_metrics or {}
                    metrics["recovery_started_at"] = captured_at.isoformat()
                    active.latest_metrics = metrics
                    active.save(update_fields=["latest_metrics"])
                    self._publish(
                        "incident.updated", active,
                        "valid recovery window started",
                        active.latest_metrics or {}, sequence,
                    )
                    return {"active_incident": active, "resolved": False, "recovery_started": True}

                recovery_elapsed = (captured_at - active.recovery_started_at).total_seconds()
                metrics = active.latest_metrics or {}
                sample_count = int(metrics.get("recovery_sample_count", 1)) + 1
                metrics["recovery_sample_count"] = sample_count
                active.latest_metrics = metrics
                active.save(update_fields=["latest_metrics", "last_updated_at"])

                if (
                    recovery_elapsed >= self.policy.recovery_seconds
                    and sample_count >= self.policy.recovery_min_samples
                ):
                    active.state = IncidentState.RESOLVED.value
                    active.resolved_at = captured_at
                    active.recovery_started_at = None
                    active.last_updated_at = timezone.now()
                    active.latest_metrics = self._metrics(
                        risk, people_count, sequence,
                        int((active.latest_metrics or {}).get("state_version", 1)) + 1,
                    )
                    active.latest_metrics["recovery_sample_count"] = sample_count
                    active.save(update_fields=[
                        "state", "resolved_at", "recovery_started_at",
                        "last_updated_at", "latest_metrics",
                    ])
                    active.feed.severity = Severity.NORMAL.value
                    active.feed.risk_score = 0.0
                    active.feed.save(update_fields=["severity", "risk_score", "updated_at"])
                    reason = "sustained calibrated observations remained below critical exit threshold"
                    self._audit(active, "returned_to_normal", reason,
                                active.latest_metrics, Severity.NORMAL)
                    self._publish("incident.resolved", active, reason,
                                  active.latest_metrics, sequence)
                    return {"active_incident": active, "resolved": True, "recovery_started": False}
                return {"active_incident": active, "resolved": False, "recovery_started": True}

        if risk.severity == Severity.CRITICAL:
            if active:
                previous_metrics = active.latest_metrics if isinstance(active.latest_metrics, dict) else {}
                previous_warning = previous_metrics.get("last_warning_at")
                now = timezone.now()
                should_warn = True
                if previous_warning:
                    try:
                        from datetime import datetime
                        parsed = datetime.fromisoformat(str(previous_warning).replace("Z", "+00:00"))
                        should_warn = (now - parsed).total_seconds() >= self.policy.warning_cooldown_seconds
                    except (TypeError, ValueError):
                        should_warn = True

                next_version = int(previous_metrics.get("state_version", 1)) + 1
                metrics = self._metrics(risk, people_count, sequence, next_version)
                if should_warn:
                    metrics["last_warning_at"] = now.isoformat()
                elif previous_metrics:
                    metrics["last_warning_at"] = previous_metrics.get("last_warning_at")
                active.recovery_started_at = None
                active.latest_metrics = metrics
                active.severity = Severity.CRITICAL.value
                active.reason = risk.reason
                active.last_updated_at = now
                active.save(update_fields=[
                    "recovery_started_at", "latest_metrics", "severity",
                    "reason", "last_updated_at",
                ])
                if should_warn:
                    self._audit(active, "threshold_crossed", risk.reason, metrics)
                    self._publish("incident.updated", active, risk.reason, metrics, sequence)
                return {"active_incident": active, "resolved": False, "created": False}

            incident = CriticalIncident.objects.create(
                feed=feed,
                zone=zone,
                state=IncidentState.ACTIVE.value,
                severity=Severity.CRITICAL.value,
                acknowledged=False,
                reason=risk.reason,
                latest_metrics=self._metrics(risk, people_count, sequence, 1),
                recovery_started_at=None,
                policy_version=self.policy.policy_version,
            )
            incident.latest_metrics["last_warning_at"] = timezone.now().isoformat()
            incident.save(update_fields=["latest_metrics"])
            self._audit(incident, "threshold_crossed", risk.reason,
                        incident.latest_metrics)
            self._publish("incident.created", incident, risk.reason,
                          incident.latest_metrics, sequence)
            return {"active_incident": incident, "resolved": False, "created": True}

        return {"active_incident": active, "resolved": False, "created": False}

    def mark_recovery_unavailable(self, feed):
        """Reset a recovery window for feed failure; never resolve."""
        updated = 0
        with transaction.atomic():
            for incident in CriticalIncident.objects.select_for_update().filter(
                feed=feed, state=IncidentState.ACTIVE.value,
            ):
                if incident.recovery_started_at is not None:
                    incident.recovery_started_at = None
                    incident.save(update_fields=["recovery_started_at"])
                    updated += 1
        return updated

    @transaction.atomic
    def acknowledge(self, incident_id: str, actor=None):
        if not incident_id:
            raise ValueError("incident_id is required")
        try:
            incident = CriticalIncident.objects.select_for_update().get(
                incident_id=incident_id,
            )
        except (CriticalIncident.DoesNotExist, ValueError, TypeError):
            raise LookupError("incident not found")

        if incident.state != IncidentState.ACTIVE.value:
            return incident

        if incident.acknowledged:
            return incident

        if hasattr(actor, "get_username"):
            actor_name = actor.get_username()
        elif isinstance(actor, str):
            actor_name = actor
        elif actor is not None:
            actor_name = str(actor)
        else:
            actor_name = "operator"

        now = timezone.now()
        previous = incident.latest_metrics if isinstance(incident.latest_metrics, dict) else {}
        next_version = int(previous.get("state_version", 1)) + 1
        incident.acknowledged = True
        incident.acknowledged_at = now
        incident.acknowledged_by = actor_name[:150]
        incident.last_updated_at = now
        incident.latest_metrics = dict(previous)
        incident.latest_metrics["state_version"] = next_version
        incident.save(update_fields=[
            "acknowledged", "acknowledged_at", "acknowledged_by",
            "last_updated_at", "latest_metrics",
        ])
        incident.feed.state_version += 1
        incident.feed.save(update_fields=["state_version", "updated_at"])

        reason = f"incident acknowledged by {actor_name}; alarm silenced"
        self._audit(incident, "incident.acknowledged", reason,
                    incident.latest_metrics)
        self._publish("incident.acknowledged", incident, reason,
                      incident.latest_metrics)
        return incident

    acknowledge_incident = acknowledge

    def can_navigate(self, feed_id=None) -> bool:
        qs = CriticalIncident.objects.filter(
            state=IncidentState.ACTIVE.value,
            acknowledged=False,
        )
        if feed_id:
            qs = qs.filter(feed_id=feed_id)
        return not qs.exists()
