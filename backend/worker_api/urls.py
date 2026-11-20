from django.urls import path

from backend.monitoring.urls import foundation_not_implemented

urlpatterns = [
    path("telemetry/", foundation_not_implemented, name="worker-telemetry"),
    path("worker-heartbeat/", foundation_not_implemented, name="worker-heartbeat"),
]
