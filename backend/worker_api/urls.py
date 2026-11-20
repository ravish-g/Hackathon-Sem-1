from django.urls import path

from .views import telemetry, worker_heartbeat

urlpatterns = [
    path("telemetry/", telemetry, name="worker-telemetry"),
    path("worker-heartbeat/", worker_heartbeat, name="worker-heartbeat"),
]
