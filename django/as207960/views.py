from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from . import tasks
import json
import logging
import hmac

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    sig: str = request.META.get("HTTP_X_AS207960_SIGNATURE_SHA512", "")
    digest = hmac.new(key=settings.AS207960_SIG_KEY.encode(), msg=request.body, digestmod='sha512')
    if not hmac.compare_digest(sig, digest.hexdigest()):
        return HttpResponseForbidden()

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    logger.debug(f"Got event from AS207960 webhook: {data}")

    msg_direction = data.get("direction")
    msg_platform = data.get("platform")
    msg_conv_id = data.get("platform_conversation_id")
    msg_id = data.get("id")
    msg_type = data.get("media_type")
    msg_content = data.get("content")
    msg_metadata = data.get("metadata")

    if msg_direction == "incoming":
        if msg_type == "text":
            tasks.handle_as207960_text.delay(msg_id, msg_platform, msg_conv_id, msg_metadata, msg_content)
        elif msg_type == "chat_state":
            tasks.handle_as207960_chatstate.delay(msg_id, msg_platform, msg_conv_id, msg_metadata, msg_content)
        elif msg_type == "file":
            tasks.handle_as207960_file.delay(msg_id, msg_platform, msg_conv_id, msg_metadata, msg_content)

    return HttpResponse("")
