import requests_oauthlib
import requests
import os
import sys
import django
from django.conf import settings

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wewillfixyourpc_bot.settings_dev')
django.setup()

import twitter.views

WEBHOOK_URL = 'https://ef530566.ngrok.io/twitter/webhook/'

auth = requests_oauthlib.OAuth1(settings.TWITTER_CONSUMER_KEY, settings.TWITTER_CONSUMER_SECRET,
                                settings.TWITTER_ACCESS_TOKEN, settings.TWITTER_ACCESS_TOKEN_SECRET)

r = requests.get(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}/webhooks.json",
                 auth=auth)
print(r.text)
hooks = r.json()
for hook in hooks:
    r = requests.delete(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}"
                        f"/webhooks/{hook['id']}.json", auth=auth)
    print(r.text)

r = requests.post(f'https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}/webhooks.json',
                  params={"url": WEBHOOK_URL}, auth=auth)
print(r.text)

creds = twitter.views.get_creds()
if creds is not None:
    r = requests.get(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}"
                     f"/subscriptions.json",
                     auth=creds)
    if r.status_code != 204:
        r = requests.post(f"https://api.twitter.com/1.1/account_activity/all/{settings.TWITTER_ENVNAME}"
                          f"/subscriptions.json", auth=creds)
        print(r.text)
