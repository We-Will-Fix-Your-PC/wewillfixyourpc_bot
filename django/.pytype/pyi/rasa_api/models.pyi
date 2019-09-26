# (generated with --quick)

from typing import Any

models: module
operator_interface: module

class EnvironmentModel(Any):
    name: Any
    rasa_model: Any
    def __str__(self) -> Any: ...

class TestingUser(Any):
    platform: Any
    platform_id: Any
    rasa_url: Any
    def __str__(self) -> str: ...

class Utterance(Any):
    name: Any
    def __str__(self) -> Any: ...

class UtteranceButton(Any):
    payload: Any
    title: Any
    utterance: Any

class UtteranceResponse(Any):
    custom_json: Any
    image: Any
    text: Any
    utterance: Any
    def __str__(self) -> str: ...
