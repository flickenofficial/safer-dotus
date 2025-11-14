from django.contrib import admin
from .models.safer_data import SaferData
from .models.scraper_job import ScraperJob

@admin.register(SaferData)
class SaferDataAdmin(admin.ModelAdmin):
    list_display = ('dot_number', 'legal_name', 'zipcode', 'fetched_at')
    search_fields = ('dot_number', 'legal_name', 'zipcode', 'phone')

@admin.register(ScraperJob)
class ScraperJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'start_id', 'hours_to_run', 'status', 'started_at', 'completed_at')
    search_fields = ('start_id', 'status')
