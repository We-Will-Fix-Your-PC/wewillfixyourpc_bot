from django.views.decorators.csrf import csrf_exempt
import json
import logging
import datetime
import os.path
from . import tasks
from . import models
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest

logger = logging.getLogger(__name__)


@csrf_exempt
def webhook(request):
    msg_headers = request.POST.get("headers")
    msg_text = request.POST.get("text")
    msg_html = request.POST.get("html")
    msg_num_attachments = request.POST.get("attachments")
    msg_attachment_info = request.POST.get("attachment-info")

    if request.POST.get("to") != "hello@wewillfixyourpc.co.uk":
        return HttpResponse()

    try:
        msg_num_attachments = int(msg_num_attachments)
    except TypeError:
        return HttpResponseBadRequest()
    if msg_num_attachments:
        try:
            msg_attachment_info = json.loads(msg_attachment_info)
        except json.JSONDecodeError:
            return HttpResponseBadRequest()
    else:
        msg_attachment_info = None

    logger.debug(
        f"Got sendgrid webhook; from: {request.POST.get('from')}, text: {msg_text}, html: {msg_html},"
        f" attachments: {msg_attachment_info}"
    )

    attachments_img = []
    attachments_other = []
    for i in range(msg_num_attachments):
        attachment_name = f"attachment{i+1}"
        attachment_file = request.FILES[attachment_name]
        attachment_info = msg_attachment_info[attachment_name]
        path = default_storage.save(
            attachment_info["filename"], ContentFile(attachment_file.read())
        )
        path = os.path.join(settings.MEDIA_ROOT, path)
        if attachment_info["type"].startswith("image/"):
            attachments_img.append(path)
        else:
            attachments_other.append((path, attachment_info["name"]))

    tasks.handle_email.delay(
        msg_headers,
        msg_text,
        msg_html,
        attachments_img,
        attachments_other,
    )

    return HttpResponse()


@login_required
def account_linking(request):
    state = request.GET.get("state")

    try:
        state = models.AccountLinkingState.objects.get(id=state)
    except models.AccountLinkingState.DoesNotExist:
        return HttpResponseBadRequest()

    if state.timestamp + datetime.timedelta(minutes=5) < timezone.now():
        return HttpResponseBadRequest()
    state.conversation.conversation.update_user_id(request.user.username)
    state.delete()

    return HttpResponse(
        '<script type="text/javascript">window.close();</script><h1>You can now close this window</h1>'
    )
