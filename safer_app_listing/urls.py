from django.urls import path
from . import views

urlpatterns = [
    path('safer/', views.safer_data_view, name='safer_data'),
    path('download_csv/', views.download_csv, name='download_csv'),
    path("scraper/start/", views.start_scraper_view, name="start_scraper"),
    path("scraper/status/", views.scraper_status_view, name="scraper_status"),
]