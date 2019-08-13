from django.http import HttpResponse, HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import SuspiciousOperation
import json
import logging
import random
import pprint
from . import models
from django.views.decorators.csrf import csrf_exempt
from rasa_sdk.executor import ActionExecutor
from rasa_sdk.interfaces import ActionExecutionRejection

logger = logging.getLogger(__name__)
executor = ActionExecutor()
executor.register_package("rasa_api.actions")


@csrf_exempt
def webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        raise SuspiciousOperation()

    # logger.debug(f"Got event from rasa webhook: {pprint.pformat(data)}")

    try:
        out_data = json.dumps(executor.run(data))
    except ActionExecutionRejection as e:
        logger.error(str(e))
        result = {"error": str(e), "action_name": e.action_name}
        return HttpResponseBadRequest(json.dumps(result))

    return HttpResponse(out_data, content_type='application/json')


@csrf_exempt
def nlg(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        raise SuspiciousOperation()

    template = data.get("template")
    try:
        utterance = models.Utterance.objects.get(name=template)
    except models.Utterance.DoesNotExist:
        logging.warn(f"Utterance {template} not found")
        raise Http404()

    responses = utterance.utteranceresponse_set.all()
    response = random.choice(responses)

    out = {}

    if response.text:
        out["text"] = response.text
    if response.custom_json:
        out["custom"] = json.loads(response.custom_json)
    if response.image:
        out["image"] = response.image.url

    buttons = utterance.utterancebutton_set.all()
    if len(buttons) >= 1:
        out["buttons"] = [{
            "title": b.title,
            "payload": b.payload
        } for b in buttons]

    return HttpResponse(json.dumps(out), content_type='application/json')


def model(request, environment_id):
    environment = get_object_or_404(models.EnvironmentModel, name=environment_id)

    file = environment.rasa_model.open()
    return HttpResponse(file, content_type='application/gzip')
