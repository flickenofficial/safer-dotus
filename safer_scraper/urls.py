from django.urls import path
from . import views


urlpatterns = [
    path("start/", views.start_scraper_view, name="start_scraper"),
    path("status/", views.scraper_status_view, name="scraper_status"),
]