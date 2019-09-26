import requests.auth
from OpenSSL import crypto
import oauth1.oauth
import json


class MastercardAuth(requests.auth.AuthBase):
    def __init__(self, consumer_key, key_store, password):
        self.consumer_key = consumer_key
        self.private_key = crypto.load_pkcs12(
            key_store, password.encode("utf-8")
        ).get_privatekey()

    def __call__(self, r: requests.PreparedRequest):
        signer = oauth1.oauth.OAuth()
        payload = r.body
        payload_str = (
            json.dumps(payload)
            if type(payload) is dict
            else (
                (payload.decode() if isinstance(payload, bytes) else payload)
                if payload is not None
                else None
            )
        )
        h = signer.get_authorization_header(
            r.url, r.method, payload_str, self.consumer_key, self.private_key
        )
        r.headers["Authorization"] = h
        r.body = payload_str
        return r
