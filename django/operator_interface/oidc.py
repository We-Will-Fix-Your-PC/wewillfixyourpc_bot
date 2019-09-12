from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import get_user_model
import requests


class OIDCAB(OIDCAuthenticationBackend):
    def verify_claims(self, claims):
        print(claims)
        return super().verify_claims(claims)
