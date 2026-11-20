from django.urls import path

from .views import (
    acknowledge_incident, active_incidents, dashboard, events, feed_calibration,
    feed_detail, feed_upload, feeds, incident_detail,
)


urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("feeds/", feeds, name="feeds"),
    path("feeds/upload/", feed_upload, name="feed-upload"),
    path("feeds/<uuid:feed_id>/", feed_detail, name="feed-detail"),
    path("feeds/<uuid:feed_id>/calibration/", feed_calibration, name="feed-calibration"),
    path("events/", events, name="events"),
    path("incidents/active/", active_incidents, name="active-incidents"),
    path("incidents/<uuid:incident_id>/", incident_detail, name="incident-detail"),
    path("incidents/<uuid:incident_id>/acknowledge/", acknowledge_incident, name="incident-acknowledge"),
]

