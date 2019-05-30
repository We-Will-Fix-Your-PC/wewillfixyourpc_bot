from django.urls import path
from . import views

app_name = 'operator'
urlpatterns = [
    path('', views.index),
    path('privacy/', views.privacy_policy),
    path('token/', views.token),
    path('push_subscription/', views.push_subscription),
    path('profile_pic/<int:user_id>/', views.profile_picture, name='profile_pic'),
]
