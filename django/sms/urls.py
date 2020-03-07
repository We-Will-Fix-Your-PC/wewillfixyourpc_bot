from django.urls import path
from . import views

app_name = "sms"
urlpatterns = [
    path("webhook/", views.webhook),
    path("status/", views.notif_webhook),
    path("account_linking/", views.account_linking, name="account_linking"),
]
