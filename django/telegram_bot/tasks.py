import datetime
import logging
from io import BytesIO

import requests
from celery import shared_task
from django.conf import settings
from django.core.files.storage import DefaultStorage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.shortcuts import reverse

import operator_interface.consumers
import operator_interface.tasks
from operator_interface.models import Conversation, Message


@shared_task
def handle_telegram_message(message):
    text = message.get("text")
    contact = message.get("contact")
    photo = message.get("photo")
    sticker = message.get("sticker")
    document = message.get("document")
    entities = message.get('entities')
    caption = message.get("caption")
    mid = message["message_id"]
    chat_id = message["chat"]["id"]
    timestamp = message["date"]
    conversation = Conversation.get_or_create_conversation(Conversation.TELEGRAM, chat_id)
    update_telegram_profile(chat_id, conversation.id)
    if not Message.message_exits(conversation, mid):
        message_m = Message(
            conversation=conversation, message_id=mid, direction=Message.FROM_CUSTOMER,
            timestamp=datetime.datetime.fromtimestamp(timestamp))
        if text:
            if entities:
                for entity in entities:
                    if entity["type"] == "bot_command":
                        command = text[entity["offset"] + 1:entity["offset"] + entity["length"]]
                        if command == "start":
                            operator_interface.tasks.process_event.delay(conversation.id, "WELCOME")
                        else:
                            operator_interface.tasks.process_event.delay(conversation.id, command)
                    else:
                        message_m.text = text
            else:
                message_m.text = text
        elif photo or sticker:
            if photo:
                photo = photo[-1]
            else:
                photo = sticker
            file = requests.get(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/getFile", json={
                "file_id": photo["file_id"]
            })
            file.raise_for_status()
            fs = DefaultStorage()
            file_name = fs.save(photo["file_id"], BytesIO(file.content))

            message_m.image = fs.base_url + file_name
            if caption:
                message.text = caption
        elif document:
            file_name = document["file_name"] if document.get("file_name") else "File"
            file = requests.get(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/getFile", json={
                "file_id": document["file_id"]
            })
            file.raise_for_status()
            fs = DefaultStorage()
            file_url = fs.save(photo["file_id"], BytesIO(file.content))
            message_m.text = f"<a href=\"{fs.base_url + file_url}\" target=\"_blank\">{file_name}</a>"
            if caption:
                message.text = caption
        elif contact:
            message_m.text = contact["phone_number"]
        else:
            return
        message_m.save()
        operator_interface.tasks.process_message.delay(message_m.id)


@shared_task
def handle_telegram_message_typing_on(cid):
    conversation = Conversation.objects.get(id=cid)
    r = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendChatAction", json={
        "chat_id": conversation.platform_id,
        "action": "typing"
    })
    r.raise_for_status()


@shared_task
def update_telegram_profile(chat_id, cid):
    conversation = Conversation.objects.get(id=cid)
    r = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/getChat", json={
        "chat_id": chat_id
    })
    r.raise_for_status()
    r = r.json()
    if r["ok"]:
        r = r["result"]
        if r.get('title'):
            name = r['title']
        else:
            first_name = r.get('first_name')
            last_name = r.get('last_name')
            name = []
            if first_name:
                name.append(first_name)
            if last_name:
                name.append(last_name)
            name = " ".join(name)
        username = r.get('username')
        profile_pic = r.get("photo")

        if profile_pic:
            file = requests.get(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/getFile", json={
                "file_id": profile_pic["small_file_id"]
            })
            file.raise_for_status()
            file = file.json()
            if file["ok"]:
                file = file["result"]
                file = requests.get(f"https://api.telegram.org/file/bot{settings.TELEGRAM_TOKEN}/{file['file_path']}")
                if file.status_code == 200:
                    conversation.customer_pic = InMemoryUploadedFile(
                        file=BytesIO(file.content), size=len(file.content), charset=file.encoding,
                        content_type=file.headers.get('content-type'), field_name=profile_pic["small_file_id"],
                        name=profile_pic["small_file_id"])
        conversation.customer_name = name
        conversation.customer_username = username
        conversation.save()
        operator_interface.consumers.conversation_saved(None, conversation)


@shared_task
def send_telegram_message(mid):
    message = Message.objects.get(id=mid)

    def send(data, method):
        quick_replies = []
        for suggestion in message.messagesuggestion_set.all():
            quick_replies.append([{
                "text": suggestion.suggested_response
            }])

        if message.request_phone:
            quick_replies.append([{
                "text": "Send my phone number",
                "request_contact": True
            }])

        if len(quick_replies) > 0:
            data["reply_markup"] = {
                "keyboard": quick_replies,
                "resize_keyboard": True,
                "one_time_keyboard": True,
                "selective": True,
            }
        else:
            data["reply_markup"] = {
                "remove_keyboard": True,
                "selective": True,
            }

        if message.payment_request:
            data["reply_markup"] = {
                "inline_keyboard": [
                    [{
                        "text": "Pay",
                        "url": settings.EXTERNAL_URL_BASE + reverse(
                            "payment:telegram_payment", kwargs={"payment_id": message.payment_request.id}
                        ),
                        "pay": True
                    }]
                ]
            }
        elif message.payment_confirm:
            data["text"] = "You can view your receipt using the link below"
            data["reply_markup"] = {
                "inline_keyboard": [
                    [{
                        "text": "View receipt",
                        "url": settings.EXTERNAL_URL_BASE + reverse(
                            "payment:receipt", kwargs={"payment_id": message.payment_confirm.id}
                        ),
                    }]
                ]
            }

        r = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/{method}", json=data)
        if r.status_code != 200 or not r.json()["ok"]:
            logging.error(f"Error sending telegram message: {r.status_code} {r.text}")
            requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_TOKEN}/sendMessage", json={
                "chat_id": message.conversation.platform_id,
                "text": "Sorry, I'm having some difficulty processing your request. Please try again later"
            }).raise_for_status()
        else:
            r = r.json()
            mid = r["result"]["message_id"]
            message.message_id = mid
            message.delivered = True
            message.save()
            operator_interface.consumers.message_saved(None, message)

    if not message.image:
        data = {
            "chat_id": message.conversation.platform_id,
            "text": message.text
        }
        send(data, "sendMessage")
    else:
        data = {
            "chat_id": message.conversation.platform_id,
            "photo": message.image
        }
        if message.text:
            data["caption"] = message.text

        send(data, "sendPhoto")
