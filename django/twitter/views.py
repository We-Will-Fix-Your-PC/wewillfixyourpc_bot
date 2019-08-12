from django.http import HttpResponse, HttpResponseServerError, HttpResponseBadRequest
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
import logging
from . import models
from . import tasks

logger = logging.getLogger(__name__)


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


@csrf_exempt
def webhook(request):
    if request.method == "GET":
        crc_token = request.GET.get('crc_token')

        if not crc_token:
            return HttpResponseBadRequest()

        sha256_hash_digest = hmac.new(settings.TWITTER_CONSUMER_SECRET.encode(),
                                      msg=crc_token.encode(),
                                      digestmod=hashlib.sha256).digest()

        # construct response data with base64 encoded hash
        return HttpResponse(json.dumps({
            'response_token': 'sha256=' + base64.b64encode(sha256_hash_digest).decode()
        }))

    r = json.loads(request.body)

    logger.debug(f"Got event from twitter webhook: {r}")

    for_user = r.get("for_user_id")
    if for_user is None:
        return HttpResponseBadRequest()

    if r.get("direct_message_events") is not None:
        users = r["users"]
        messages = r["direct_message_events"]
        for message in messages:
            if message["type"] == "message_create":
                mid = message["id"]
                message = message["message_create"]
                psid = message["sender_id"]
                if psid != for_user:
                    message = message["message_data"]
                    user = users[psid]
                    tasks.handle_twitter_message.delay(mid, psid, message, user)
    if r.get("direct_message_mark_read_events") is not None:
        events = r["direct_message_mark_read_events"]
        for event in events:
            psid = event["sender_id"]
            last_read = event["last_read_event_id"]
            tasks.handle_twitter_read.delay(psid, last_read)

    return HttpResponse("")
