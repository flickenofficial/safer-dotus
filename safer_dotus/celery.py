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
