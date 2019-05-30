from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.auth.models import User
from PIL import Image
import datetime
import json
import jwt
from . import models


@login_required
def index(request):
    return render(request, "operator_interface/build/index.html")


@login_required
def token(request):
    key = jwt.jwk.OctetJWK(settings.SECRET_KEY.encode())
    jwt_i = jwt.JWT()
    compact_jws = jwt_i.encode({
        'sub': request.user.id,
        'iat': datetime.datetime.now().timestamp(),
    }, key, 'HS256')
    return HttpResponse(compact_jws)


@csrf_exempt
@login_required
def push_subscription(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return HttpResponseBadRequest()
        subscription = body.get('subscription_info')
        if subscription is None:
            return HttpResponseBadRequest()
        try:
            subscription_m = models.NotificationSubscription.objects.get(subscription_info=subscription)
        except models.NotificationSubscription.DoesNotExist:
            subscription_m = models.NotificationSubscription()
            subscription_m.subscription_info = subscription
        subscription_m.user = request.user
        subscription_m.save()
        return HttpResponse(json.dumps({
            "id": subscription_m.id
        }))
    elif request.method == "DELETE":
        subscription_id = request.GET.get("subscription_id")
        if subscription_id is None:
            return HttpResponseBadRequest()
        try:
            subscription_m = models.NotificationSubscription.objects.get(id=subscription_id)
        except models.NotificationSubscription.DoesNotExist:
            return HttpResponseBadRequest()

        if subscription_m.user != request.user:
            return HttpResponseBadRequest()

        subscription_m.delete()

        return HttpResponse()

    return HttpResponseBadRequest()


def profile_picture(request, user_id):
    user = get_object_or_404(User, id=user_id)
    image = user.userprofile.picture
    i = Image.open(image)
    i.thumbnail((64, 64))
    response = HttpResponse(content_type='image/jpg')
    i.save(response, "JPEG")
    return response


def privacy_policy(request):
    return render(request, "operator_interface/Privacy Policy.html")
