"""Dependency-injection protocols shared by risk, API, worker and realtime code."""

from typing import Any, Protocol


class IncidentEngine(Protocol):
    def process_observation(self, observation: Any) -> Any:
        ...

    def acknowledge(self, incident_id: str, actor: Any) -> Any:
        ...


class EventPublisher(Protocol):
    def publish(self, event_type: str, payload: dict, feed_id: str | None = None) -> dict:
        ...


class ObservationProcessor(Protocol):
    def accept(self, payload: dict) -> Any:
        ...

