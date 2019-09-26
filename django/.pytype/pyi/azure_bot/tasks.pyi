# (generated with --quick)

import operator_interface.models
from typing import Any, Mapping, Type

Conversation: Type[operator_interface.models.Conversation]
Message: Type[operator_interface.models.Message]
datetime: module
dateutil: module
handle_azure_contact_relation_update: Any
handle_azure_conversation_update: Any
handle_azure_message: Any
json: module
logging: module
models: module
operator_interface: module
requests: module
send_azure_message: Any
settings: Any
shared_task: Any
timezone: module

def event_to_conversation(msg: Mapping[str, Mapping]) -> Any: ...
def get_access_token() -> Any: ...
