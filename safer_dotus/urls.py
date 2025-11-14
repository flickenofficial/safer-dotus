from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('safer_app_listing.urls')),  # safer app
    path('scraper/', include('safer_scraper.urls')),  # scraper app ✅
]
