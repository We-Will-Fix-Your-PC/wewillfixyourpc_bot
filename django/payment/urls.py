from django.urls import path
from . import views

app_name = 'payment'
urlpatterns = [
    path('fb/<payment_id>/', views.fb_payment, name='fb_payment'),
    path('complete/', views.complete_payment),
    path('<payment_id>/', views.payment),
    path('worldpay/<payment_id>/', views.take_worldpay_payment),
    path('3ds/<payment_id>/', views.threeds_form, name='3ds_form'),
    path('3ds-complete/<payment_id>/', views.threeds_complete, name='3ds_complete'),
]
