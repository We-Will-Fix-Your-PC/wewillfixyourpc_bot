# (generated with --quick)

import requests.auth
from typing import Any

crypto: module
json: module
oauth1: module
requests: module

class MastercardAuth(requests.auth.AuthBase):
    consumer_key: Any
    private_key: Any
    def __init__(self, consumer_key, key_store, password) -> None: ...
