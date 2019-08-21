import decimal
import json
import uuid
import hmac

import requests
from django.conf import settings
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render, reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

import operator_interface.models
import operator_interface.tasks
from . import gpay, models, tasks


@receiver(post_save, sender=models.Payment)
def payment_saved(sender, instance: models.Payment, **kwargs):
    if instance.state == models.Payment.STATE_PAID:
        try:
            message = operator_interface.models.Message.objects.get(payment_request=instance.id)
            conversation = message.conversation
            conversation.customer_phone = instance.customer.phone if instance.customer.phone \
                else conversation.customer_phone
            conversation.customer_email = instance.customer.email if instance.customer.email \
                else conversation.customer_email
            conversation.save()

            message = operator_interface.models.Message(
                conversation=conversation, direction=operator_interface.models.Message.TO_CUSTOMER,
                message_id=uuid.uuid4(), text="Payment complete 💸, thanks!")
            message.save()
            operator_interface.tasks.process_message.delay(message.id)
        except operator_interface.models.Message.DoesNotExist:
            pass
        tasks.process_payment.delay(instance.id)


def apple_mechantid(request):
    return render(request, "payment/apple-developer-merchantid-domain-association")


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def render_payment(request, payment_id, template):
    if not request.session.get("sess_id"):
        request.session["sess_id"] = str(uuid.uuid4())
        request.session.save()

    payment_o = get_object_or_404(models.Payment, id=payment_id)

    return render(request, template,
                  {"payment_id": payment_id, "accepts_header": request.META.get('HTTP_ACCEPT'),
                   "is_open_payment": payment_o.state == models.Payment.STATE_OPEN})


@xframe_options_exempt
def fb_payment(request, payment_id):
    return render_payment(request, payment_id, "payment/fb_payment.html")


@xframe_options_exempt
def twitter_payment(request, payment_id):
    return render_payment(request, payment_id, "payment/twitter_payment.html")


@xframe_options_exempt
def receipt(request, payment_id):
    payment_o = get_object_or_404(models.Payment, id=payment_id)
    return render(request, "payment/receipt.html", {
        "payment": payment_o,
        "subtotal": (payment_o.total / decimal.Decimal('1.2'))
                  .quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_DOWN),
        "tax": (payment_o.total * decimal.Decimal('0.2'))
                        .quantize(decimal.Decimal('.01'), rounding=decimal.ROUND_DOWN)
    })


def payment(request, payment_id):
    payment_o = get_object_or_404(models.Payment, id=payment_id)

    return HttpResponse(json.dumps({
        "id": payment_o.id,
        "timestamp": payment_o.timestamp.isoformat(),
        "state": payment_o.state,
        "environment": payment_o.environment,
        "customer": payment_o.customer if not payment_o.customer else {
            "id": payment_o.customer.id,
            "name": payment_o.customer.name,
            "email": payment_o.customer.email,
            "phone": payment_o.customer.phone.as_e164
        },
        "items": list(map(lambda i: {
            "id": i.id,
            "type": i.item_type,
            "data": i.item_data,
            "title": i.title,
            "price": float(i.price),
        }, payment_o.paymentitem_set.all()))
    }))


@csrf_exempt
def complete_payment(request):
    if request.method != "POST":
        raise SuspiciousOperation()

    token = request.META.get('HTTP_AUTHORIZATION')

    try:
        models.PaymentToken.objects.get(token=token)
    except models.PaymentToken.DoesNotExist:
        raise PermissionDenied()

    payment_id = request.POST.get("order_id")
    payment_o = get_object_or_404(models.Payment, id=payment_id)

    if payment_o.state != payment_o.STATE_PAID:
        raise Http404()

    payment_o.state = models.Payment.STATE_COMPLETE
    payment_o.save()

    return HttpResponse(json.dumps({
        "status": "OK"
    }))


@csrf_exempt
def take_worldpay_payment(request, payment_id):
    if not request.session.get("sess_id"):
        request.session["sess_id"] = str(uuid.uuid4())
        request.session.save()

    if request.method != "POST":
        raise SuspiciousOperation()

    try:
        payment_o = models.Payment.objects.get(id=payment_id)
    except models.Payment.DoesNotExist:
        payment_o = None

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        raise SuspiciousOperation()

    if payment_o is not None:
        if payment_o.state != payment_o.STATE_OPEN:
            raise Http404()
    else:
        if body.get("payment") is not None:
            payment = body["payment"]
            items = payment["items"]
            payment_o = models.Payment()
            payment_o.environment = payment["environment"]
            payment_o.state = models.Payment.STATE_OPEN
            payment_o.id = payment["id"]
            if payment.get("customer"):
                customer = payment["customer"]
                email = customer.get("email")
                phone = customer.get("phone")
                name = customer.get("name")
                payment_o.customer = models.Customer.find_customer(email=email, phone=phone, name=name)
            payment_o.save()

            for item in items:
                verified = False
                tokens = models.PaymentToken.objects.all()
                for token in tokens:
                    hmac_data = f"{item['type']}{item['data']}{item['title']}{item['price']}"
                    sig = hmac.new(key=token.token.encode(), digestmod='sha512')
                    sig.update(hmac_data.encode())
                    digest = sig.hexdigest()
                    if hmac.compare_digest(digest, item["sig"]):
                        verified = True

                if verified:
                    item_o = models.PaymentItem()
                    item_o.payment = payment_o
                    item_o.item_type = item["type"]
                    item_o.item_data = item["data"]
                    item_o.title = item["title"]
                    item_o.price = item["price"]
                    item_o.save()
                else:
                    raise SuspiciousOperation()
        else:
            raise Http404()

    token = settings.WORLDPAY_LIVE_KEY if payment_o.environment == models.Payment.ENVIRONMENT_LIVE \
        else settings.WORLDPAY_TEST_KEY

    description = payment_o.description
    total = int(payment_o.total * 100)

    if payment_o.customer is None:
        email = body.get("email")
        phone = body.get("phone")
        name = body.get("payerName")
        payment_o.customer = models.Customer.find_customer(email=email, phone=phone, name=name)
        payment_o.save()

    billingAddress = {}
    if body.get("billingAddress"):
        if len(body["billingAddress"]["addressLine"]) >= 1:
            billingAddress["address1"] = body["billingAddress"]["addressLine"][0]
        if len(body["billingAddress"]["addressLine"]) >= 2:
            billingAddress["address2"] = body["billingAddress"]["addressLine"][1]
        if len(body["billingAddress"]["addressLine"]) >= 3:
            billingAddress["address3"] = body["billingAddress"]["addressLine"][2]
        billingAddress["postalCode"] = body["billingAddress"]["postalCode"]
        billingAddress["city"] = body["billingAddress"]["city"]
        billingAddress["countryCode"] = body["billingAddress"]["country"]
        billingAddress["state"] = body["billingAddress"]["region"]
        billingAddress["telephoneNumber"] = body["billingAddress"]["phone"]

    order_data = {
        "orderType": "ECOM",
        "orderDescription": description,
        "customerOrderCode": payment_o.id,
        "amount": total,
        "currencyCode": "GBP",
        "name": body.get("name"),
        "shopperEmailAddress": payment_o.customer.email,
        "billingAddress": billingAddress,
        "shopperIpAddress": get_client_ip(request),
        "shopperUserAgent": request.META["HTTP_USER_AGENT"],
        "shopperAcceptHeader": body.get("accepts"),
        "shopperSessionId": request.session.get("sess_id", ""),
        "is3DSOrder": True,
        "authorizeOnly": total == 0,
    }

    if body.get("token"):
        order_data = dict(token=body["token"], **order_data)
    elif body.get("googleData"):
        try:
            message = gpay.unseal_google_token(body["googleData"],
                                               test=payment_o.environment != models.Payment.ENVIRONMENT_LIVE)
        except gpay.GPayError:
            raise SuspiciousOperation()

        if message["paymentMethod"] != "CARD":
            raise SuspiciousOperation()

        card_details = message["paymentMethodDetails"]
        if card_details["authMethod"] != "PAN_ONLY":
            raise SuspiciousOperation()

        order_data = dict(paymentMethod={
            "name": body.get("name"),
            "expiryMonth": card_details["expirationMonth"],
            "expiryYear": card_details["expirationYear"],
            "cardNumber": card_details["pan"],
            "type": "Card"
        }, **order_data)

    else:
        raise SuspiciousOperation()

    r = requests.post("https://api.worldpay.com/v1/orders", headers={
        "Authorization": token
    }, json=order_data)
    data = r.json()
    print(data)

    if data.get("paymentStatus") is None:
        return HttpResponse(json.dumps({
            "state": "FAILED"
        }))
    elif data["paymentStatus"] in ["SUCCESS", "AUTHORIZED"]:
        payment_o.state = models.Payment.STATE_PAID
        payment_o.payment_method = \
            f"{data['paymentResponse']['cardIssuer']} {data['paymentResponse']['maskedCardNumber']}"
        payment_o.save()
        return HttpResponse(json.dumps({
            "state": "SUCCESS"
        }))
    elif data["paymentStatus"] == "PRE_AUTHORIZED":
        models.ThreeDSData.objects.filter(payment_id=payment_id).delete()

        threedsData = models.ThreeDSData()
        threedsData.orderId = data["orderCode"]
        threedsData.redirectURL = data["redirectURL"]
        threedsData.oneTime3DsToken = data["oneTime3DsToken"]
        threedsData.sessionId = request.session.get("sess_id", "")
        threedsData.payment = payment_o
        threedsData.save()

        path = reverse("payment:3ds_form", kwargs={"payment_id": payment_o.id})
        return HttpResponse(json.dumps({
            "state": "3DS",
            "frame": f"https://{request.get_host()}{path}"
        }))
    elif data["paymentStatus"] == "FAILED":
        return HttpResponse(json.dumps({
            "state": "FAILED"
        }))
    else:
        return HttpResponse(json.dumps({
            "state": "UNKNOWN"
        }))


@xframe_options_exempt
def threeds_form(request, payment_id):
    threedsData = get_object_or_404(models.ThreeDSData, payment_id=payment_id)
    path = reverse("payment:3ds_complete", kwargs={
        "payment_id": threedsData.payment.id
    })
    base_url = f"https://{request.get_host()}{path}"
    return render(request, "payment/3ds_form.html", {
        "threeds": threedsData,
        "redirect": f'{base_url}?sess_id={threedsData.sessionId}'
    })


@csrf_exempt
@xframe_options_exempt
def threeds_complete(request, payment_id):
    payment_o = get_object_or_404(models.Payment, id=payment_id)
    if payment_o.state != payment_o.STATE_OPEN:
        raise Http404()

    if request.method != "POST":
        raise SuspiciousOperation()

    payment_o.threedsdata_set.all().delete()

    order_id = request.POST["MD"]
    resp_3ds = request.POST["PaRes"]
    session_id = request.GET["sess_id"]
    token = settings.WORLDPAY_LIVE_KEY if payment_o.environment == models.Payment.ENVIRONMENT_LIVE \
        else settings.WORLDPAY_TEST_KEY

    r = requests.put(f"https://api.worldpay.com/v1/orders/{order_id}", headers={
        "Authorization": token
    }, json={
        "threeDSResponseCode": resp_3ds,
        "shopperIpAddress": get_client_ip(request),
        "shopperUserAgent": request.META["HTTP_USER_AGENT"],
        "shopperAcceptHeader": request.META.get('HTTP_ACCEPT'),
        "shopperSessionId": session_id,
    })
    data = r.json()
    if data.get("paymentStatus") is None:
        return render(request, "payment/3ds_complete.html", {"payment_id": payment_id, "3ds_approved": False})

    if data["paymentStatus"] in ["SUCCESS", "AUTHORIZED"]:
        payment_o.state = models.Payment.STATE_PAID
        payment_o.payment_method = \
            f"{data['paymentResponse']['cardIssuer']} {data['paymentResponse']['maskedCardNumber']}"
        payment_o.save()
        return render(request, "payment/3ds_complete.html", {"payment_id": payment_id, "3ds_approved": True})
    else:
        return render(request, "payment/3ds_complete.html", {"payment_id": payment_id, "3ds_approved": False})
