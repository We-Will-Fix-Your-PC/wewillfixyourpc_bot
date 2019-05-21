from django.http import HttpResponse, HttpResponseServerError
from django.shortcuts import redirect, reverse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import json
import hashlib
import hmac
import base64
import requests
import requests_oauthlib
import urllib.parse
from . import models
from . import tasks


def get_creds():
    config = models.Config.objects.first()
    if config is None:
        return None
    if config.auth is None:
        return None
    try:
        auth = json.loads(config.auth)
    except json.JSONDecodeError:
        return None
    if auth.get("access_token") is None:
        return None
    if auth.get("access_token_secret") is None:
        return None
    auth = requests_oauthlib.OAuth1(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET,
                                    auth["access_token"], auth["access_token_secret"])
    return auth


def authorise(request):
    uri = request.build_absolute_uri(reverse('twitter:oauth'))
    if not settings.DEBUG:
        uri = uri.replace("http://", "https://")

    auth = requests_oauthlib.OAuth1(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET, callback_uri=uri)
    r = requests.post("https://api.twitter.com/oauth/request_token", auth=auth)
    r.raise_for_status()
    r = urllib.parse.parse_qs(r.text)

    if not r["oauth_callback_confirmed"][0]:
        return HttpResponseServerError()

    request.session['redirect'] = request.META.get('HTTP_REFERER')

    authorization_url = f"https://api.twitter.com/oauth/authorize?oauth_token={r['oauth_token'][0]}"

    return redirect(authorization_url)


def oauth(request):
    oauth_token = request.GET.get("oauth_token")
    oauth_verifier = request.GET.get("oauth_verifier")

    r = requests.post("https://api.twitter.com/oauth/access_token", data={
        "oauth_consumer_key": settings.TWITTER_CONSUMER_KEY,
        "oauth_token": oauth_token,
        "oauth_verifier": oauth_verifier,
    })
    r.raise_for_status()
    r = urllib.parse.parse_qs(r.text)

    config = models.Config.objects.first()
    config.auth = json.dumps({
        "access_token": r["oauth_token"][0],
        "access_token_secret": r["oauth_token_secret"][0]
    })
    config.save()

    creds = get_creds()
    r = requests.get(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}"
                     f"/subscriptions.json",
                     auth=creds)
    if r.status_code != 204:
        r = requests.post(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}"
                          f"/subscriptions.json", auth=creds)
        r.raise_for_status()

    return redirect(request.session['redirect'])


def deauthorise(request):
    credentials = get_creds()

    if credentials is not None:
        requests.delete(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}"
                        f"/subscriptions.json", auth=credentials)
        requests.post('https://api.twitter.com/oauth/invalidate_token', params={
            "access_token": credentials.client.resource_owner_key,
            "access_token_secret": credentials.client.resource_owner_secret
        }, auth=credentials)

        config = models.Config.objects.first()
        config.auth = ""
        config.save()

    return redirect(request.META.get('HTTP_REFERER'))


def webhook(request):
    print(request.body)
    return HttpResponse("")
