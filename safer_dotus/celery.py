import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'safer_dotus.settings')

app = Celery('safer_dotus')

# Load settings from Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks in apps
app.autodiscover_tasks()


# CELERY_BEAT_SCHEDULE = {
#     'run_test_scraper': {
#         'task': 'safer_scraper.tasks.run_daily_scraper',  # your task name
#         'schedule': crontab(minute='*'),  # 1:05 AM Mountain Time
#         'args': (),  # optional, if your task requires arguments
#     },
# }


