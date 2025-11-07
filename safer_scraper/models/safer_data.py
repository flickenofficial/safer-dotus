from django.db import models


class SaferData(models.Model):
    dot_number = models.IntegerField(primary_key=True)
    legal_name = models.TextField(blank=True, null=True)
    physical_address = models.TextField(blank=True, null=True)
    zipcode = models.CharField(max_length=20, blank=True, null=True)
    mailing_code = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    operating_status = models.CharField(max_length=100, blank=True, null=True)
    power_units = models.CharField(max_length=50, blank=True, null=True)
    drivers = models.CharField(max_length=50, blank=True, null=True)
    date_filed = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    fetched_at = models.DateTimeField()

    class Meta:
        db_table = 'safer_data'
        verbose_name = 'SAFER Data'
        verbose_name_plural = 'SAFER Data'
        managed = False

    def __str__(self):
        return f"DOT: {self.dot_number}, Name: {self.legal_name}"