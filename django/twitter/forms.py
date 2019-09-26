from django import forms
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from django.conf import settings
import requests
from . import models
from . import views


class AuthWidget(forms.Widget):
    template_name = "twitter/auth_button_widget.html"

    def render(self, name, value, attrs=None, **kwargs):
        is_signed_in = False

        creds = views.get_creds()
        if creds is not None:
            is_signed_in = True

        context = {"is_signed_in": is_signed_in}
        return mark_safe(render_to_string(self.template_name, context))


class TwitterAuthForm(forms.ModelForm):
    login = forms.Field(widget=AuthWidget, required=False)

    def save(self, commit=True):
        m = super().save(commit=False)

        r = requests.post(
            "https://api.twitter.com/oauth2/token",
            auth=(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET),
            data={"grant_type": "client_credentials"},
        )
        r.raise_for_status()
        r = r.json()
        m.bearer_token = r["access_token"]
        if commit:
            m.save()
        return m

    class Meta:
        fields = "__all__"
        model = models.Config
