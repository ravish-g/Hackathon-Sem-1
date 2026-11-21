from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Calibration, EventLogEntry, Feed, FeedActivity


@receiver(post_save, sender=Feed)
def record_registration(sender, instance, created, raw, **kwargs):
    if created and not raw:
        FeedActivity.objects.create(feed_id=instance.pk, feed_name=instance.name,
                                    event_type="feed.added", message=f"{instance.source_type.capitalize()} source registered.")


@receiver(post_save, sender=Calibration)
def record_calibration(sender, instance, created, raw, **kwargs):
    if created and not raw:
        feed = instance.zone.feed
        FeedActivity.objects.create(feed_id=feed.pk, feed_name=feed.name,
                                    event_type="feed.calibration_changed",
                                    message=f"Zone calibration version {instance.version} saved.")


@receiver(post_delete, sender=Feed)
def record_removal(sender, instance, **kwargs):
    FeedActivity.objects.create(feed_id=instance.pk, feed_name=instance.name,
                                event_type="feed.removed", message="Camera feed removed.")


def recent_activity(kind, feed_id=None):
    actions = FeedActivity.objects.all()
    alerts = EventLogEntry.objects.filter(category__in=["crowd", "alert", "prediction"])
    if feed_id:
        actions = actions.filter(feed_id=feed_id)
        alerts = alerts.filter(feed_id=feed_id)
    rows = []
    if kind != "Alerts":
        for row in actions.order_by("-timestamp", "-event_id").values()[:250]:
            row.update(category="system", severity="info")
            rows.append(row)
    if kind != "System":
        rows.extend(alerts.order_by("-timestamp", "-sequence").values(
            "event_id", "timestamp", "feed_id", "feed_name", "event_type", "category",
            "message", "severity", "incident_id", "state"
        )[:250])
    return sorted(rows, key=lambda row: row["timestamp"], reverse=True)[:250]
