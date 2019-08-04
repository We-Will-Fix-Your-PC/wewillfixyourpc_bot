from django.urls import path
from . import views

app_name = 'rasa_api'
urlpatterns = [
    path('webhook/', views.webhook),
    path('nlg/', views.nlg),
    path('model/<environment_id>', views.model),
]
