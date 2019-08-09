from django.urls import path
from . import views

app_name = 'operator'
urlpatterns = [
    path('', views.index),
    path('privacy/', views.privacy_policy),
    path('push_subscription/', views.push_subscription),
    path('profile_pic/<int:user_id>/', views.profile_picture, name='profile_pic'),
    path('data/networks/', views.get_networks),
    path('data/brands/', views.get_brands),
    path('data/models/<brand>/', views.get_models),
    path('data/unlocks/<brand>/<network>/', views.get_unlocks),
]
