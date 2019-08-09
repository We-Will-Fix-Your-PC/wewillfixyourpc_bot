from django.urls import path
from . import views

app_name = 'facebook'
urlpatterns = [
    path('webhook/', views.webhook),
]
