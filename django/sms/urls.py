from django.urls import path
from . import views

app_name = "sms"
urlpatterns = [
    path("webhook/", views.webhook),
    path("status/", views.notif_webhook),
]
