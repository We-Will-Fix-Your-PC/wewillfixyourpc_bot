# (generated with --quick)

from typing import Any

HttpResponse: Any
HttpResponseBadRequest: Any
HttpResponseServerError: Any
base64: module
csrf_exempt: Any
hashlib: module
hmac: module
json: module
logger: logging.Logger
logging: module
models: module
redirect: Any
requests: module
requests_oauthlib: module
reverse: Any
sentry_sdk: module
settings: Any
tasks: module
urllib: module
webhook: Any

def authorise(request) -> Any: ...
def deauthorise(request) -> Any: ...
def get_creds() -> Any: ...
def oauth(request) -> Any: ...
