from django.urls import path
from . import views

app_name = 'payment'
urlpatterns = [
    path('fb/<payment_id>/', views.fb_payment),
    path('<payment_id>/', views.payment),
]
