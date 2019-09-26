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
import django.views.generic
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
import os
import payment.views

urlpatterns = [
    # path('admin/login/', django.views.generic.RedirectView.as_view(
    #     pattern_name=settings.LOGIN_URL, permanent=True, query_string=True)),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("auth/", include("keycloak_auth.urls")),
    path("fulfillment/", include("fulfillment.urls", namespace="fulfillment")),
    path("rasa/", include("rasa_api.urls", namespace="rasa")),
    path("twitter/", include("twitter.urls", namespace="twitter")),
    path("facebook/", include("facebook.urls", namespace="facebook")),
    path("telegram/", include("telegram_bot.urls", namespace="telegram")),
    path("azure/", include("azure_bot.urls", namespace="azure")),
    path("gactions/", include("gactions.urls", namespace="gactions")),
    path("payment/", include("payment.urls", namespace="payment")),
    path(
        ".well-known/apple-developer-merchantid-domain-association",
        payment.views.apple_mechantid,
    ),
    path("", include("operator_interface.urls", namespace="operator")),
]

if settings.DEBUG:
    urlpatterns += static(
        "static/operator_interface",
        document_root=os.path.join(
            settings.BASE_DIR, "operator_interface/templates/operator_interface/build"
        ),
    )
    urlpatterns += static("static/", document_root=settings.STATIC_ROOT)
    urlpatterns += static("media/", document_root=settings.MEDIA_ROOT)
