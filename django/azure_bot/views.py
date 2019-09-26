import json
import logging
import sentry_sdk

import jwt
import jwt.algorithms
import jwt.exceptions
import requests
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from . import tasks

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        sentry_sdk.capture_exception(e)
        return HttpResponseBadRequest()

    authorization = request.META.get("HTTP_AUTHORIZATION")  # type: str
    if not authorization or not authorization.startswith("Bearer "):
        return HttpResponseForbidden()
    authorization = authorization[len("Bearer ") :]

    openid_config_r = requests.get(
        "https://login.botframework.com/v1/.well-known/openidconfiguration"
    )
    openid_config_r.raise_for_status()
    openid_config = openid_config_r.json()
    openid_algs = openid_config["id_token_signing_alg_values_supported"]

    jwks_r = requests.get(openid_config["jwks_uri"])
    jwks_r.raise_for_status()
    jwks = jwks_r.json()

    channel_id = data["channelId"]
    jwks = [k for k in jwks["keys"] if channel_id in k["endorsements"]]

    public_keys = {}
    for jwk in jwks:
        kid = jwk["kid"]
        public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    authorized = False

    kid = jwt.get_unverified_header(authorization)["kid"]
    key = public_keys.get(kid)

    if key:
        try:
            jwt_msg = jwt.decode(
                authorization,
                key=key,
                algorithms=openid_algs,
                audience=settings.AZURE_APP_ID,
                issuer="https://api.botframework.com",
            )
            if jwt_msg["serviceUrl"] == data["serviceUrl"]:
                authorized = True
        except jwt.exceptions.InvalidTokenError as e:
            sentry_sdk.capture_exception(e)
            pass

    if not authorized:
        openid_config_r = requests.get(
            "https://login.microsoftonline.com/botframework.com/v2.0/.well-known/openid-configuration"
        )
        openid_config_r.raise_for_status()
        openid_config = openid_config_r.json()
        openid_algs = openid_config["id_token_signing_alg_values_supported"]

        jwks_r = requests.get(openid_config["jwks_uri"])
        jwks_r.raise_for_status()
        jwks = jwks_r.json()["keys"]

        public_keys = {}
        for jwk in jwks:
            kid = jwk["kid"]
            public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

            kid = jwt.get_unverified_header(authorization)["kid"]
            key = public_keys.get(kid)

            if key:
                try:
                    jwt_msg = jwt.decode(
                        authorization,
                        key=key,
                        algorithms=openid_algs,
                        audience=settings.AZURE_APP_ID,
                        options={"verify_iss": False},
                    )
                    if (
                        jwt_msg["iss"]
                        == "https://login.microsoftonline.com/d6d49420-f39b-4df7-a1dc-d59a935871db/v2.0"
                        or jwt_msg["iss"]
                        == "https://login.microsoftonline.comf8cdef31-a31e-4b4a-93e4-5f571e91255a/v2.0"
                    ):
                        authorized = True
                except jwt.exceptions.InvalidTokenError as e:
                    sentry_sdk.capture_exception(e)
                    continue

        if not authorized:
            return HttpResponseForbidden()

    logger.debug(f"Got event from azure webhook: {data}")

    event_type = data["type"]

    if event_type == "contactRelationUpdate":
        tasks.handle_azure_contact_relation_update.delay(data)
    elif event_type == "conversationUpdate":
        tasks.handle_azure_conversation_update(data)
    elif event_type == "message":
        tasks.handle_azure_message.delay(data)

    return HttpResponse("")
