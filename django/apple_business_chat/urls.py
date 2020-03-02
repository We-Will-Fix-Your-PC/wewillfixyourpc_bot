from django.urls import path
from . import views

app_name = "apple_business_chat"
urlpatterns = [
    path("webhook/", views.webhook),
    path("notification/", views.notif_webhook),
]
