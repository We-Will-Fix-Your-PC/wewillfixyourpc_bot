from django.urls import path
from . import views

app_name = 'twitter'
urlpatterns = [
    path('webhook/', views.webhook),
]
