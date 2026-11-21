import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitoring", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="VisionJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("state", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("error", "Error")], default="pending", max_length=20)),
                ("worker_id", models.CharField(blank=True, max_length=120)),
                ("source_path", models.CharField(blank=True, max_length=500)),
                ("error_message", models.CharField(blank=True, max_length=1000)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("last_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("configuration_version", models.PositiveIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("feed", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="vision_job", to="monitoring.feed")),
            ],
        ),
    ]
