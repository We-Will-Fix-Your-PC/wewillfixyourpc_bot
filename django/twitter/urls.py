from django.urls import path
from . import views

app_name = "twitter"
urlpatterns = [
    path("webhook/", views.webhook),
    path("authorise/", views.authorise, name="authorise"),
    path("oauth/", views.oauth, name="oauth"),
    path("deauth/", views.deauthorise, name="deauthorise"),
]
