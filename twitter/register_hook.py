from TwitterAPI import TwitterAPI
import requests_oauthlib
import requests

CONSUMER_KEY = '40QHIgq0t2MJRQztYK9v5msce'
CONSUMER_SECRET = 'V81hszJdGpvY6uWFcfcNHKrm3yi0nqeQPkDuTCVXCn1W9VfntB'

ACCESS_TOKEN = '4898627980-LlyTpDcnjPQHFoMXmDbSc7xNLcBuuPo4XaMNupd'
ACCESS_TOKEN_SECRET = 'P7wjJCRUKXHO1ABZwf4otFkq7Kek15isuTtQRBGCPS9Bf'

ENVNAME = 'main'
WEBHOOK_URL = ' https://93085331.ngrok.io/twitter/webhook'

auth = requests_oauthlib.OAuth1(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

r = requests.get("https://api.twitter.com/1.1/account_activity/all/webhooks.json", auth=auth)
print(r.request.headers)
print(r.text)

r = requests.post('https://api.twitter.com/1.1/account_activity/all/env-beta/webhooks.json', params={'url': WEBHOOK_URL}, auth=auth)

print(r.request.headers)
print(r.status_code)
print(r.text)