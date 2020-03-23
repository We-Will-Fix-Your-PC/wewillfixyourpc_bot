from django.urls import path
from . import views

app_name = "apple_business_chat"
urlpatterns = [
    path("webhook/", views.webhook),
    path("message", views.message),
    path("notification", views.notification),
    path("notification/", views.notif_webhook),
    path("account_linking/", views.account_linking, name="account_linking"),
]
