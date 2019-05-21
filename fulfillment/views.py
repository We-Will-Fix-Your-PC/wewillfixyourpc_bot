from django.http import HttpResponse, HttpResponseBadRequest
import json
from django.views.decorators.csrf import csrf_exempt
from . import actions


@csrf_exempt
def webhook(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    query = data.get('queryResult')
    if query is None:
        return HttpResponseBadRequest()
    action = query.get('action')
    if action is None:
        return HttpResponseBadRequest()
    params = query.get("parameters")
    if params is None:
        return HttpResponseBadRequest()

    text = query.get("fulfillmentText")
    if text is None:
        text = ""

    action = actions.ACTIONS.get(action)
    if action is None:
        return HttpResponseBadRequest()

    out_data = action(params, text, data)
    out_data = json.dumps(out_data)

    return HttpResponse(out_data)
