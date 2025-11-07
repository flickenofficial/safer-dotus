from django.db import models


class SaferState(models.Model):
    STATUS_CHOICES = [
        ('no_data', 'No Data'),
        ('fetched', 'Fetched'),
        ('pending', 'Pending'),
        ('processing', 'Processing'),
    ]

    id = models.IntegerField(primary_key=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    last_checked = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'safer_state'
        verbose_name = 'SAFER State'
        verbose_name_plural = 'SAFER States'
        managed = False

    def __str__(self):
        return f"ID: {self.id}, Status: {self.status}"