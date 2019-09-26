from django.urls import path
from . import views

app_name = "fulfillment"
urlpatterns = [path("form/<form_type>/<form_id>/", views.form, name="form")]
