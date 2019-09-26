# (generated with --quick)

from typing import Any, Iterable, List, Mapping, Sized, Union

Cipher: Any
algorithms: module
backend: Any
base64: module
cryptography: module
default_backend: Any
ec: module
hashes: module
hkdf: module
hmac: module
json: module
load_der_public_key: Any
load_pem_private_key: Any
modes: module
requests: module
settings: Any
struct: module
time: module

class GPayError(Exception):
    def __init__(self, message) -> None: ...

def get_google_root_keys(test = ...) -> List[nothing]: ...
def unseal_google_token(token: Union[bytearray, bytes, str], merchant_id = ..., test = ...) -> Any: ...
def verify_encrypted_message(message: Mapping[str, Any], ephemeral_public_key_bytes, priv_keys: Iterable) -> Any: ...
def verify_intermediate_signing_key(intermediate_signing_key: Mapping[str, Iterable], root_keys: Iterable) -> None: ...
def verify_signed_message(msg: Sized, sig: Union[bytes, str], intermediate_key, merchant_id) -> None: ...
