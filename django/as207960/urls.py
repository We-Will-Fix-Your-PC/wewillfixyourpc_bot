from django.urls import path
from . import views

app_name = "as207969"
urlpatterns = [
    path("webhook/", views.webhook),
]
