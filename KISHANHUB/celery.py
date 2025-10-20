import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "KISHANHUB.settings")

app = Celery("KISHANHUB")

# Read config from Django settings, using a namespace prefix CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

# Autodiscover tasks from installed apps
app.autodiscover_tasks()

# Add your periodic task schedule here
app.conf.beat_schedule = {
    "notify-upcoming-bookings-every-minute": {
        "task": "yourapp.tasks.notify_upcoming_bookings",
        "schedule": crontab(minute="*"),  # Run every minute
    },
}
