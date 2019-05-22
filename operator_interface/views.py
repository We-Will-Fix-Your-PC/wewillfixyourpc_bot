from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib.auth.models import User
from PIL import Image
import datetime
import jwt


@login_required
def index(request):
    return render(request, "operator_interface/index.html")


@login_required
def token(request):
    key = jwt.jwk.OctetJWK(settings.SECRET_KEY.encode())
    jwt_i = jwt.JWT()
    compact_jws = jwt_i.encode({
        'sub': request.user.id,
        'iat': datetime.datetime.now().timestamp(),
    }, key, 'HS256')
    return HttpResponse(compact_jws)


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
