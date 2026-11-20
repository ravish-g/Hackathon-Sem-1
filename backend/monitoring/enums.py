from enum import StrEnum


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    ELEVATED = "elevated"
    NORMAL = "normal"
    UNKNOWN = "unknown"


class IncidentState(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class StreamState(StrEnum):
    CONNECTING = "connecting"
    LIVE = "live"
    REPLAY = "replay"
    STALE = "stale"
    OFFLINE = "offline"
    ERROR = "error"


class AnalysisState(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    CALIBRATING = "calibrating"
    PAUSED = "paused"
    FAILED = "failed"


class SourceType(StrEnum):
    UPLOAD = "upload"
    WEBCAM = "webcam"
    NETWORK = "network"


class DensityTrend(StrEnum):
    RISING = "rising"
    STABLE = "stable"
    FALLING = "falling"
    UNKNOWN = "unknown"

