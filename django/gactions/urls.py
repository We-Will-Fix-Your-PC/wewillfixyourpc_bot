from django.urls import path
from . import views

app_name = 'gactions'
urlpatterns = [
    path('webhook/', views.webhook),
]
