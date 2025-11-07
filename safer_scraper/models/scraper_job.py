from django.db import models
from django.utils import timezone


class ScraperJob(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('stopped', 'Stopped'),
    ]

    id = models.AutoField(primary_key=True)
    start_id = models.IntegerField()
    hours_to_run = models.IntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_id_processed = models.IntegerField(default=0)
    total_processed = models.IntegerField(default=0)
    error_message = models.TextField(blank=True, null=True)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'scraper_job'
        verbose_name = 'Scraper Job'
        verbose_name_plural = 'Scraper Jobs'
        ordering = ['-id']

    def __str__(self):
        return f"Job {self.id}: {self.start_id} - {self.status}"

    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None

    def mark_as_running(self, task_id=None):
        self.status = 'running'
        self.started_at = timezone.now()
        if task_id:
            self.celery_task_id = task_id
        self.save()

    def mark_as_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def mark_as_failed(self, error_message):
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save()

    def mark_as_stopped(self):
        self.status = 'stopped'
        self.completed_at = timezone.now()
        self.save()