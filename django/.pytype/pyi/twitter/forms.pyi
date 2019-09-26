# (generated with --quick)

from typing import Any

forms: module
mark_safe: Any
models: module
render_to_string: Any
requests: module
settings: Any
views: module

class AuthWidget(Any):
    template_name: str
    def render(self, name, value, attrs = ..., **kwargs) -> Any: ...

class TwitterAuthForm(Any):
    Meta: type
    login: Any
    def save(self, commit = ...) -> Any: ...
