from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.urls import reverse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import operator_interface.models
import json
import secrets


channel_layer = get_channel_layer()


def index(request):
    return render(request, "customer_chat/index.html")


@csrf_exempt
def config(request):
    if request.method == "GET":
        token = None
        user_profile = None
        if request.user.is_authenticated:
            try:
                conversation = operator_interface.models.Conversation.objects.get(
                    conversation_user_id=request.user.username
                )
            except operator_interface.models.Conversation.DoesNotExist:
                conversation = operator_interface.models.Conversation(
                    conversation_user_id=request.user.username
                )
                conversation.save()

            try:
                platform = conversation.conversationplatform_set.get(
                    platform=operator_interface.models.ConversationPlatform.CHAT
                )
            except operator_interface.models.ConversationPlatform.DoesNotExist:
                platform = operator_interface.models.ConversationPlatform(
                    conversation=conversation,
                    platform=operator_interface.models.ConversationPlatform.CHAT,
                    platform_id=secrets.token_urlsafe(64)
                )
                platform.save()

            token = platform.platform_id
            user_profile = {
                "name": request.user.first_name,
                "is_authenticated": True
            }

            if request.session.get("chat_session_token"):
                old_token = request.session["chat_session_token"]
                if old_token != token:
                    del request.session["chat_session_token"]
                    try:
                        old_platform = operator_interface.models.ConversationPlatform.objects.get(
                            platform=operator_interface.models.ConversationPlatform.CHAT,
                            platform_id=old_token
                        )

                        async_to_sync(channel_layer.group_send)(
                            "operator_interface", {
                                "type": "conversation_merge",
                                "ncid": platform.conversation.id,
                                "cid": old_platform.conversation.id
                            }
                        )
                        msgs = old_platform.messages.all()
                        msgs.update(platform=platform)
                        old_platform.conversation.conversationplatform_set.all().update(conversation=conversation)
                        old_platform.conversation.delete()
                        old_platform.delete()
                    except operator_interface.models.ConversationPlatform.DoesNotExist:
                        pass

        else:
            if request.session.get("chat_session_token"):
                token = request.session["chat_session_token"]
                try:
                    platform = operator_interface.models.ConversationPlatform.objects.get(
                        platform=operator_interface.models.ConversationPlatform.CHAT,
                        platform_id=token
                    )
                    user_profile = {
                        "name": platform.conversation.conversation_name,
                        "is_authenticated": False
                    }
                except operator_interface.models.ConversationPlatform.DoesNotExist:
                    pass

        return HttpResponse(json.dumps({
            "token": token,
            "profile": user_profile,
            "login_url": reverse("oidc_login"),
            "logout_url": reverse("oidc_logout")
        }), content_type='application/json')
    elif request.method == "POST":
        if request.user.is_authenticated:
            return HttpResponseBadRequest()

        conversation = operator_interface.models.Conversation(
            conversation_name=request.POST.get("name", "Unknown")
        )
        conversation.save()
        platform = operator_interface.models.ConversationPlatform(
            conversation=conversation,
            platform=operator_interface.models.ConversationPlatform.CHAT,
            platform_id=secrets.token_urlsafe(64)
        )
        platform.save()
        request.session["chat_session_token"] = platform.platform_id

        return HttpResponse(json.dumps({
            "token": platform.platform_id,
        }), content_type='application/json')
    else:
        return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])
