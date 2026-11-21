from django.db.models import Max

from .models import CriticalIncident, EventLogEntry, Feed, FeedMetric
from .enums import IncidentState


def latest_metric_for_feed(feed):
    return feed.metrics.order_by("-sequence").first()


def feed_queryset():
    return Feed.objects.prefetch_related(
        "zones__calibrations",
    )


def active_incidents_queryset():
    return CriticalIncident.objects.filter(state=IncidentState.ACTIVE.value).select_related("feed", "zone")


def event_cursor():
    return EventLogEntry.objects.aggregate(cursor=Max("sequence"))["cursor"] or 0

