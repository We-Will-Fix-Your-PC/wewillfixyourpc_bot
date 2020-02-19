from django.urls import path
from . import views

app_name = "customer_chat"
urlpatterns = [
    path("", views.index),
    path("config/", views.config),
]
