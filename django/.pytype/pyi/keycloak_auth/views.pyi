# (generated with --quick)

from typing import Any

auth: module
clients: module
django: module
logger: logging.Logger
logging: module
models: module

class Login(Any):
    def get_redirect_url(self, *args, **kwargs) -> Any: ...

class LoginComplete(Any):
    def get(self, *args, **kwargs) -> Any: ...

class Logout(Any):
    def get_redirect_url(self, *args, **kwargs) -> Any: ...
