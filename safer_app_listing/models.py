from django.db import models


class SaferData(models.Model):
    dot_number = models.TextField(null=True, blank=True)
    legal_name = models.TextField(null=True, blank=True)
    physical_address = models.TextField(null=True, blank=True)
    zipcode = models.TextField(null=True, blank=True)
    mailing_code = models.TextField(null=True, blank=True)
    phone = models.TextField(null=True, blank=True)
    operating_status = models.TextField(null=True, blank=True)
    power_units = models.TextField(null=True, blank=True)
    drivers = models.TextField(null=True, blank=True)
    date_filed = models.TextField(null=True, blank=True)
    email = models.TextField(null=True, blank=True)
    fetched_at = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "safer_data"
        managed = False
