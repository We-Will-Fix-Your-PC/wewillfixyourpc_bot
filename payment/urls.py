from django.urls import path
from . import views

app_name = 'payment'
urlpatterns = [
    path('fb/<payment_id>/', views.fb_payment, name='fb_payment'),
    path('fb/<payment_id>/3ds', views.fb_payment_3ds),
    path('<payment_id>/', views.payment),
    path('worldpay/<payment_id>/', views.take_worldpay_payment),
]
