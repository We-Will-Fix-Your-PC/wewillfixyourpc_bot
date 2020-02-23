from django.urls import path
from . import views

app_name = "api"
urlpatterns = [
    path("send_message/<customer_id>/", views.send_message),
]
