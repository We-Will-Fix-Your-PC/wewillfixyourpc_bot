from django.urls import path
from . import views

app_name = "sendgrid"
urlpatterns = [
    path("webhook/", views.webhook),
    path("account_linking/", views.account_linking, name="account_linking"),
]
