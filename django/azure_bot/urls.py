from django.urls import path
from . import views

app_name = "azure_bot"
urlpatterns = [path("webhook/", views.webhook)]
