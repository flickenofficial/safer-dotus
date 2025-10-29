from django.urls import path
from . import views

urlpatterns = [
    path('safer/', views.safer_data_view, name='safer_data'),
]