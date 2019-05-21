import logging
import uuid
import tornado.websocket
import tornado.web
import tornado.ioloop
import pika
import os
import sys
import django
import json
import threading
from django.contrib.staticfiles.templatetags.staticfiles import static
from tornado.platform.asyncio import AsyncIOMainLoop

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wewillfixyourpc_bot.settings_dev')
django.setup()

import operator_interface.models
import operator_interface.tasks

message_handlers = set()


class OperatorWebSocket(tornado.websocket.WebSocketHandler):
    loop: AsyncIOMainLoop

    def open(self):
        self.loop = tornado.ioloop.IOLoop.current()
        message_handlers.add(self.handle_message)
        print("WebSocket opened")

    def on_message(self, message):
        message = json.loads(message)
        if message["type"] == "resyncReq":
            last_message = message["lastMessage"]
            for conversation in operator_interface.models.Conversation.objects.all():
                for message in conversation.message_set.all():
                    if int(message.timestamp.strftime("%s")) > last_message:
                        self.send_message(message)
        elif message["type"] == "msg":
            text = message["text"]
            cid = message["cid"]
            conversation = operator_interface.models.Conversation.objects.get(id=cid)
            message = operator_interface.models.Message(conversation=conversation, text=text,
                                                        direction=operator_interface.models.Message.TO_CUSTOMER,
                                                        message_id=uuid.uuid4())
            message.save()
            operator_interface.tasks.process_message.delay(message.id)

    def send_message(self, message: operator_interface.models.Message):
        pic = static("operator_interface/img/default_profile_normal.png")
        if message.conversation.customer_pic:
            pic = message.conversation.customer_pic.url
        message = {
            "id": message.id,
            "direction": message.direction,
            "timestamp": int(message.timestamp.strftime("%s")),
            "text": message.text,
            "conversation": {
                "id": message.conversation.id,
                "agent_responding": message.conversation.agent_responding,
                "platform": message.conversation.platform,
                "customer_name": message.conversation.customer_name,
                "customer_username": message.conversation.customer_username,
                "customer_pic": pic,
            }
        }
        self.write_message(json.dumps(message))

    def handle_message(self, message):
        self.loop.add_callback(self.send_message, message)

    def on_close(self):
        message_handlers.remove(self.handle_message)
        print("WebSocket closed")

    def check_origin(self, origin):
        return True


def rmq_callback(ch, method, properties, body):
    data = json.loads(body)
    mid = data.get("mid")
    if mid is not None:
        try:
            message = operator_interface.models.Message.objects.get(id=mid)
        except operator_interface.models.Message.DoesNotExist:
            return
        for h in message_handlers:
            h(message)


rmq = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost'))
channel = rmq.channel()
channel.exchange_declare(exchange='bot_messages', exchange_type='fanout')

result = channel.queue_declare('', exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange='bot_messages', queue=queue_name)
channel.basic_consume(queue=queue_name, on_message_callback=rmq_callback, auto_ack=True)

application = tornado.web.Application([
    (r"/", OperatorWebSocket),
])
application.listen(8001)

logging.basicConfig(level=logging.INFO)

rmq_t = threading.Thread(target=channel.start_consuming, daemon=True)
rmq_t.start()

tornado.ioloop.IOLoop.current().start()
