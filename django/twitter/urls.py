from django.urls import path
from . import views

app_name = "twitter"
urlpatterns = [
    path("webhook/", views.webhook),
    path("authorise/", views.authorise, name="authorise"),
    path("oauth/", views.oauth, name="oauth"),
    path("deauth/", views.deauthorise, name="deauthorise"),
    path("account_linking/", views.account_linking, name="account_linking"),
]
