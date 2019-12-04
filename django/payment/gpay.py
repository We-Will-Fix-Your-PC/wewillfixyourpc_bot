import requests
import json
import time
import struct
import base64
from django.conf import settings
import cryptography.exceptions
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.serialization import (
    load_der_public_key,
    load_pem_private_key,
)
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf import hkdf

backend = default_backend()


class GPayError(Exception):
    def __init__(self, message):
        super().__init__(message)


def get_google_root_keys(test=True):
    google_keys_url = (
        "https://payments.developers.google.com/paymentmethodtoken/test/keys.json"
        if test
        else "https://payments.developers.google.com/paymentmethodtoken/keys.json"
    )

    google_keys = requests.get(google_keys_url)
    try:
        google_keys.raise_for_status()
    except requests.exceptions.BaseHTTPError:
        raise GPayError("Unable to get root keys")
    google_keys = google_keys.json()["keys"]

    now = time.time()

    google_keys = filter(lambda k: k["protocolVersion"] == "ECv2", google_keys)
    google_keys = filter(
        lambda k: float(k["keyExpiration"]) > now if k.get("keyExpiration") else True,
        google_keys,
    )
    google_keys = list(
        map(
            lambda k: load_der_public_key(base64.b64decode(k["keyValue"]), backend),
            google_keys,
        )
    )

    return google_keys


def verify_intermediate_signing_key(intermediate_signing_key, root_keys):
    key = intermediate_signing_key["signedKey"].encode("UTF-8")
    signedBytes = struct.pack(
        f"<L6sL4sL{len(key)}s", 6, b"Google", 4, b"ECv2", len(key), key
    )

    verified = False
    for k in root_keys:
        for s in intermediate_signing_key["signatures"]:
            try:
                k.verify(base64.b64decode(s), signedBytes, ec.ECDSA(hashes.SHA256()))
                verified = True
            except cryptography.exceptions.InvalidSignature:
                pass
    if not verified:
        raise cryptography.exceptions.InvalidSignature()


def verify_signed_message(msg, sig, intermediate_key, merchant_id):
    merchant_id = f"merchant:{merchant_id}"
    signedBytes = struct.pack(
        f"<L6sL{len(merchant_id)}sL4sL{len(msg)}s",
        6,
        b"Google",
        len(merchant_id),
        merchant_id.encode("UTF-8"),
        4,
        b"ECv2",
        len(msg),
        msg.encode("UTF-8"),
    )
    intermediate_key.verify(
        base64.b64decode(sig), signedBytes, ec.ECDSA(hashes.SHA256())
    )


def verify_encrypted_message(message, ephemeral_public_key_bytes, priv_keys):
    ephemeral_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        ec.SECP256R1(), ephemeral_public_key_bytes
    )
    for k in priv_keys:
        sharedKey = k.exchange(ec.ECDH(), ephemeral_public_key)

        kdf = hkdf.HKDF(
            algorithm=hashes.SHA256(),
            length=512 // 8,
            salt=b"\0",
            info=b"Google",
            backend=backend,
        )
        sharedKey = kdf.derive(ephemeral_public_key_bytes + sharedKey)

        symmetricEncryptionKey = sharedKey[: 256 // 8]
        macKey = sharedKey[256 // 8 :]
        encryptedMessage = base64.b64decode(message["encryptedMessage"])

        h = hmac.HMAC(macKey, hashes.SHA256(), backend)
        h.update(encryptedMessage)
        try:
            h.verify(base64.b64decode(message["tag"]))
        except cryptography.exceptions.InvalidSignature:
            continue

        cipher = Cipher(
            algorithms.AES(symmetricEncryptionKey), modes.CTR(b"\0" * 16), backend
        )
        decryptor = cipher.decryptor()
        message = decryptor.update(encryptedMessage) + decryptor.finalize()
        return json.loads(message)
    raise GPayError("no private key worked")


def unseal_google_token(token, merchant_id="12345678901234567890", test=True):
    try:
        google_token = json.loads(token)
    except json.JSONDecodeError:
        raise GPayError("Invalid GPay token")
    if google_token["protocolVersion"] != "ECv2":
        raise GPayError("Unsupported protocol")

    root_keys = get_google_root_keys(test)

    intermediate_signing_key = google_token["intermediateSigningKey"]
    try:
        verify_intermediate_signing_key(intermediate_signing_key, root_keys)
    except cryptography.exceptions.InvalidSignature:
        raise GPayError("Invalid intermediate key")
    try:
        intermediate_signing_key = json.loads(intermediate_signing_key["signedKey"])
    except json.JSONDecodeError:
        raise GPayError("Invalid intermediate signing key")
    if float(intermediate_signing_key["keyExpiration"]) <= time.time():
        raise GPayError("Expired intermediate key")
    intermediate_key = load_der_public_key(
        base64.b64decode(intermediate_signing_key["keyValue"]), backend
    )

    try:
        verify_signed_message(
            google_token["signedMessage"],
            google_token["signature"],
            intermediate_key,
            merchant_id,
        )
    except cryptography.exceptions.InvalidSignature:
        raise GPayError("Invalid message signature")
    signed_message = json.loads(google_token["signedMessage"])

    ephemeral_public_key_bytes = base64.b64decode(signed_message["ephemeralPublicKey"])

    private_keys = (
        settings.GPAY_TEST_PRIVATE_KEYS if test else settings.GPAY_LIVE_PRIVATE_KEYS
    )
    private_keys = list(
        map(lambda k: load_pem_private_key(k, None, backend), private_keys)
    )

    message = verify_encrypted_message(
        signed_message, ephemeral_public_key_bytes, private_keys
    )
    if float(message["messageExpiration"]) <= time.time():
        raise GPayError("Expired message")

    return message
