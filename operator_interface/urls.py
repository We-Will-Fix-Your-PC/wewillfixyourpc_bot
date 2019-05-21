from django.urls import path
from . import views

app_name = 'operator'
urlpatterns = [
    path('', views.index),
    path('privacy/', views.privacy_policy)
]
