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
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('fulfillment/', include('fulfillment.urls', namespace='fulfillment')),
    path('twitter/', include('twitter.urls', namespace='twitter')),
    path('facebook/', include('facebook.urls', namespace='facebook')),
    path('payment/', include('payment.urls', namespace='payment')),
    path('', include('operator_interface.urls', namespace='operator')),
]

if settings.DEBUG:
    urlpatterns += static('static/operator_interface',
                          document_root=os.path.join(settings.BASE_DIR,
                                                     'operator_interface/templates/operator_interface/build'))
    urlpatterns += static('static/', document_root=settings.STATIC_ROOT)
    urlpatterns += static('media/', document_root=settings.MEDIA_ROOT)
