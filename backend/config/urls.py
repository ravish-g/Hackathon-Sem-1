from django.urls import include, path

from backend.monitoring.health import health

urlpatterns = [
    path("health/", health, name="health"),
    path("api/", include("backend.monitoring.urls")),
    path("internal/", include("backend.worker_api.urls")),
]

