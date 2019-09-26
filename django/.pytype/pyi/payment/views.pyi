# (generated with --quick)

from typing import Any, Iterable, Union

Http404: Any
HttpResponse: Any
SuspiciousOperation: Any
base64: module
csrf_exempt: Any
datetime: module
decimal: module
fb_payment: Any
get_object_or_404: Any
gpay: module
hmac: module
json: module
mastercard: module
models: module
operator_interface: module
payment_saved: Any
post_save: Any
receipt: Any
receiver: Any
redirect: Any
render: Any
requests: module
reverse: Any
sentry_sdk: module
settings: Any
take_worldpay_payment: Any
tasks: module
threeds_complete: Any
threeds_form: Any
twitter_payment: Any
uuid: module
xframe_options_exempt: Any

def apple_mechantid(request) -> Any: ...
def get_client_ip(request) -> Any: ...
def payment(request, payment_id) -> Any: ...
def payment_state_form(request) -> Any: ...
def render_payment(request, payment_id, template) -> Any: ...
def take_masterpass_payment(request, payment_id: Union[bytes, float, str, Iterable[Union[bytes, float, str]]], redirect_url_b64: Union[bytes, str], base_url, auth) -> Any: ...
def take_masterpass_payment_live(request, payment_id: Union[bytes, float, str, Iterable[Union[bytes, float, str]]], redirect_url: Union[bytes, str]) -> Any: ...
def take_masterpass_payment_test(request, payment_id: Union[bytes, float, str, Iterable[Union[bytes, float, str]]], redirect_url: Union[bytes, str]) -> Any: ...
