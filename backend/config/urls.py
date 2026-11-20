from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.static import serve

from backend.monitoring.health import health


FRONTEND_ROOT = Path(settings.BASE_DIR) / "frontend" / "dist"


def frontend(request, path=""):
    if path and Path(path).name:
        requested = (FRONTEND_ROOT / path).resolve()
        if FRONTEND_ROOT.resolve() in requested.parents and requested.is_file():
            return FileResponse(requested.open("rb"))
    index = FRONTEND_ROOT / "index.html"
    if not index.is_file():
        raise Http404("Frontend build was not found.")
    return FileResponse(index.open("rb"), content_type="text/html")

urlpatterns = [
    path("health/", health, name="health"),
    path("api/", include("backend.monitoring.urls")),
    path("internal/", include("backend.worker_api.urls")),
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    re_path(r"^(?P<path>.*)$", frontend),
]

