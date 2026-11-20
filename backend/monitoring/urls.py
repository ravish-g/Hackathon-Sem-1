from django.http import JsonResponse
from django.urls import path


def foundation_not_implemented(request):
    return JsonResponse(
        {"error": {"code": "NOT_IMPLEMENTED", "message": "This endpoint belongs to a feature workstream."}},
        status=501,
    )


urlpatterns = [
    path("dashboard/", foundation_not_implemented, name="dashboard"),
    path("feeds/", foundation_not_implemented, name="feeds"),
    path("feeds/upload/", foundation_not_implemented, name="feed-upload"),
    path("feeds/<uuid:feed_id>/", foundation_not_implemented, name="feed-detail"),
    path("feeds/<uuid:feed_id>/calibration/", foundation_not_implemented, name="feed-calibration"),
    path("events/", foundation_not_implemented, name="events"),
    path("incidents/active/", foundation_not_implemented, name="active-incidents"),
    path("incidents/<uuid:incident_id>/", foundation_not_implemented, name="incident-detail"),
    path("incidents/<uuid:incident_id>/acknowledge/", foundation_not_implemented, name="incident-acknowledge"),
    path("worker-heartbeat/", foundation_not_implemented, name="worker-heartbeat"),
]

