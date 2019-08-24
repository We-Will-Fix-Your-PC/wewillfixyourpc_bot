import base64
import decimal
import hmac
import json
import uuid
import datetime

import requests
import sentry_sdk
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt

import operator_interface.models
import operator_interface.tasks
from . import gpay, mastercard, models, tasks


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


def payment_state_form(request):
    return render(request, "payment/payment_state.html", {
        "redirect_url": base64.b64decode(request.GET.get("redirect_url")).decode(),
        "payment_state": request.GET.get("state"),
        "payment_id": request.GET.get("payment_id")
    })


def render_payment(request, payment_id, template):
    if not request.session.get("sess_id"):
        request.session["sess_id"] = str(uuid.uuid4())
        request.session.save()

    payment_o = get_object_or_404(models.Payment, id=payment_id)

    return render(request, template, {
        "payment_id": payment_id,
        "accepts_header": request.META.get('HTTP_ACCEPT'),
        "is_open_payment": payment_o.state == models.Payment.STATE_OPEN or
        request.POST.get("payment_state") == "success",
        "test": payment_o.state != models.Payment.ENVIRONMENT_LIVE,
        "state": request.POST.get("payment_state")
    })


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

    email = body.get("email")
    phone = body.get("phone")
    name = body.get("payerName")
    payment_o.customer = models.Customer.find_customer(email=email, phone=phone, name=name)
    payment_o.save()

    token = settings.WORLDPAY_LIVE_KEY if payment_o.environment == models.Payment.ENVIRONMENT_LIVE \
        else settings.WORLDPAY_TEST_KEY

    description = payment_o.description
    total = int(payment_o.total * 100)

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
            message = gpay.unseal_google_token(body["googleData"]["tokenizationData"]["token"],
                                               test=payment_o.environment != models.Payment.ENVIRONMENT_LIVE)
        except gpay.GPayError as e:
            sentry_sdk.capture_exception(e)
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

        if payment_o.environment != models.Payment.ENVIRONMENT_LIVE:
            payment_o.state = models.Payment.STATE_PAID
            payment_o.payment_method = f"{body['googleData']['description']}"
            payment_o.save()
            return HttpResponse(json.dumps({
                "state": "SUCCESS"
            }))
    else:
        raise SuspiciousOperation()

    r = requests.post("https://api.worldpay.com/v1/orders", headers={
        "Authorization": token
    }, json=order_data)
    data = r.json()

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


def take_masterpass_payment_live(request, payment_id, redirect_url):
    return take_masterpass_payment(request, payment_id, redirect_url, "https://api.mastercard.com/")


def take_masterpass_payment_test(request, payment_id, redirect_url):
    auth = mastercard.MastercardAuth(settings.MASTERPASS_TEST_KEY, settings.MASTERPASS_TEST_P12_KEY,
                                     settings.MASTERPASS_TEST_KEY_PASS)
    return take_masterpass_payment(request, payment_id, redirect_url, "https://sandbox.api.mastercard.com/", auth)


def take_masterpass_payment(request, payment_id, redirect_url_b64, base_url, auth):
    if not request.session.get("sess_id"):
        request.session["sess_id"] = str(uuid.uuid4())
        request.session.save()

    payment_o = get_object_or_404(models.Payment, id=payment_id)

    if payment_o.state != payment_o.STATE_OPEN:
        raise Http404()

    redirect_url = base64.b64decode(redirect_url_b64).decode()
    mp_status = request.GET.get("mpstatus")
    transaction_id = request.GET.get("oauth_verifier")
    description = payment_o.description
    total = int(payment_o.total * 100)

    if mp_status != "success":
        return redirect(redirect_url)

    def handle_redirect(state):
        state_form_url = reverse("payment:payment_state")
        state_form_url = f"{state_form_url}?redirect_url={redirect_url_b64}&state={state}&payment_id={payment_id}"
        return redirect(state_form_url)

    def handle_postback(success: bool):
        r = requests.post(f"{base_url}masterpass/postback", auth=auth, json={
            "transactionId": transaction_id,
            "currency": "GBP",
            "amount": float(payment_o.total),
            "paymentDate": datetime.datetime.now().isoformat(),
            "paymentSuccessful": success,
            "paymentCode": "UNAVLB"
        })
        print(r.text)
        r.raise_for_status()

    r = requests.get(f"{base_url}masterpass/paymentdata/{transaction_id}", auth=auth, params={
        "checkoutId": "5dc2ffcbc3154881a9f4a5f63c9ab2b1",
        "cartId": payment_id
    })
    body = r.json()

    if r.status_code != 200:
        return handle_redirect("failure")

    card = body["card"]
    personalInfo = body["personalInfo"]

    email = personalInfo.get("recipientEmailAddress")
    phone = personalInfo.get("recipientPhone")
    name = personalInfo.get("recipientName")
    try:
        payment_o.customer = models.Customer.find_customer(email=email, phone=phone, name=name)
        payment_o.save()
    except ValueError:
        pass

    billingAddress = {
        "address1": card["billingAddress"]["line1"],
        "postalCode": card["billingAddress"]["postalCode"],
        "city": card["billingAddress"]["city"],
        "countryCode": card["billingAddress"]["country"],
        "state": card["billingAddress"]["subdivision"],
        "telephoneNumber": phone
    }
    if card["billingAddress"].get("line2"):
        billingAddress["address2"] = card["billingAddress"]["line2"]
    if card["billingAddress"].get("line3"):
        billingAddress["address3"] = card["billingAddress"]["line3"]
    order_data = {
        "orderType": "ECOM",
        "orderDescription": description,
        "customerOrderCode": payment_o.id,
        "amount": total,
        "currencyCode": "GBP",
        "name": name,
        "shopperEmailAddress": payment_o.customer.email,
        "billingAddress": billingAddress,
        "shopperIpAddress": get_client_ip(request),
        "shopperUserAgent": request.META["HTTP_USER_AGENT"],
        "shopperAcceptHeader": request.META.get("HTTP_ACCEPT"),
        "shopperSessionId": request.session.get("sess_id", ""),
        # "is3DSOrder": True,
        "authorizeOnly": total == 0,
        "paymentMethod": {
            "name": card["cardHolderName"],
            "expiryMonth": card["expiryMonth"],
            "expiryYear": card["expiryYear"],
            "cardNumber": card["accountNumber"],
            "cvc": card.get("cvc"),
            "type": "Card"
        }
    }

    method_description = card["brandName"]
    if card.get("lastFour"):
        method_description += f" {card['lastFour']}"
    else:
        method_description += f" {card['accountNumber'][:-4]}"

    if payment_o.environment != models.Payment.ENVIRONMENT_LIVE:
        handle_postback(True)
        payment_o.state = models.Payment.STATE_PAID
        payment_o.payment_method = method_description
        payment_o.save()
        return handle_redirect("success")

    r = requests.post("https://api.worldpay.com/v1/orders", headers={
        "Authorization": settings.WORLDPAY_LIVE_KEY
    }, json=order_data)
    data = r.json()
    print(data)

    if data.get("paymentStatus") is None:
        handle_postback(False)
        return handle_redirect("failure")
    elif data["paymentStatus"] in ["SUCCESS", "AUTHORIZED"]:
        handle_postback(True)
        payment_o.state = models.Payment.STATE_PAID
        payment_o.payment_method = method_description
        payment_o.save()
        return handle_redirect("success")
    elif data["paymentStatus"] == "FAILED":
        handle_postback(False)
        return handle_redirect("failure")
    else:
        handle_postback(False)
        return handle_redirect("unknown")
