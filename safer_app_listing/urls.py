from django.urls import path
from . import views

urlpatterns = [
    path('safer/', views.safer_data_view, name='safer_data'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('download_csv/', views.download_csv, name='download_csv'),
]