# (generated with --quick)

import io
import operator_interface.models
from typing import Any, Dict, Iterable, List, Pattern, Tuple, Type, Union

BytesIO: Type[io.BytesIO]
Conversation: Type[operator_interface.models.Conversation]
HttpResponse: Any
HttpResponseBadRequest: Any
HttpResponseForbidden: Any
InMemoryUploadedFile: Any
Message: Type[operator_interface.models.Message]
csrf_exempt: Any
emoji_pattern: Pattern[str]
google: module
json: module
keycloak_auth: module
logger: logging.Logger
logging: module
operator_interface: module
os: module
re: module
requests: module
settings: Any
urllib: module
uuid: module
webhook: Any

def process_inputs(inputs: Iterable, conversation) -> list: ...
def process_outputs(outputs_l: Iterable, is_guest_user, user_id_token, conversation) -> Tuple[List[Dict[str, Union[str, Dict[str, str]]]], List[Dict[str, Dict[str, Any]]], Any]: ...
