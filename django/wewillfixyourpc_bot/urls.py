"""wewillfixyourpc_bot URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
import os

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("auth/", include("django_keycloak_auth.urls")),
    path("api/", include("api.urls", namespace="api")),
    path("fulfillment/", include("fulfillment.urls", namespace="fulfillment")),
    path("rasa/", include("rasa_api.urls", namespace="rasa")),
    path("twitter/", include("twitter.urls", namespace="twitter")),
    path("facebook/", include("facebook.urls", namespace="facebook")),
    path("telegram/", include("telegram_bot.urls", namespace="telegram")),
    path("azure/", include("azure_bot.urls", namespace="azure")),
    path("gactions/", include("gactions.urls", namespace="gactions")),
    path("chat/", include("customer_chat.urls", namespace="customer_chat")),
    path("abc/", include("apple_business_chat.urls", namespace="apple_business_chat")),
    path("", include("operator_interface.urls", namespace="operator")),
]

if settings.DEBUG:
    urlpatterns += static("static/", document_root=settings.STATIC_ROOT)
    urlpatterns += static("media/", document_root=settings.MEDIA_ROOT)
