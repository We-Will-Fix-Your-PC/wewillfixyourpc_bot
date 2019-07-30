from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from . import models
import json
import decimal
import requests
import uuid


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def fb_payment(request, payment_id):
    if not request.session.get("sess_id"):
        request.session["sess_id"] = str(uuid.uuid4())
        request.session.save()
    return render(request, "payment/fb_payment.html",
                  {"payment_id": payment_id, "accepts_header": request.META.get('HTTP_ACCEPT')})


@csrf_exempt
def fb_payment_3ds(request, payment_id):
    return worldpay_handle_3ds(request, payment_id, "payment/fb_payment_3ds.html")


def payment(request, payment_id):
    payment_o = get_object_or_404(models.Payment, id=payment_id)
    if payment_o.state != payment_o.STATE_OPEN:
        return HttpResponseNotFound()

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


def take_worldpay_payment(request, payment_id):
    payment_o = get_object_or_404(models.Payment, id=payment_id)
    if payment_o.state != payment_o.STATE_OPEN:
        return HttpResponseNotFound()

    if request.method != "POST":
        return HttpResponseBadRequest()

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest()

    token = settings.WORLDPAY_LIVE_KEY if payment_o.environment == models.Payment.ENVIRONMENT_LIVE \
        else settings.WORLDPAY_TEST_KEY

    total = decimal.Decimal('0.0')
    description = []
    for item in payment_o.paymentitem_set.all():
        total += item.price
        description.append(item.title)
    description = ", ".join(description)
    total = int(total * 100)

    if payment_o.customer is None:
        email = body.get("email")
        phone = body.get("phone")
        name = body.get("payerName")
        customer = models.Customer.objects.filter(email=email, phone=phone, name=name)
        if len(customer) > 0:
            customer = customer[0]
        else:
            customer = models.Customer(name=name, email=email, phone=phone)
            customer.save()

        payment_o.customer = customer
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
        r = requests.post("https://api.worldpay.com/v1/orders", headers={
            "Authorization": token
        }, json=dict(token=body["token"], **order_data))
    elif body.get("googleData"):
        try:
            google_token = json.loads(body["googleData"])
        except json.JSONDecodeError:
            return HttpResponseBadRequest()

        if google_token["protocolVersion"] != "ECv2":
            return HttpResponseBadRequest()

        google_keys_url = "https://payments.developers.google.com/paymentmethodtoken/keys.json" \
            if payment_o.environment == models.Payment.ENVIRONMENT_LIVE else \
            "https://payments.developers.google.com/paymentmethodtoken/test/keys.json"
        google_keys = requests.get(google_keys_url)
        google_keys.raise_for_status()
        google_keys = google_keys.json()["keys"]

        google_key = filter(lambda k: k["protocolVersion"], google_keys)[0]

        print(google_key)
        return HttpResponse(json.dumps({
            "state": "SUCCESS"
        }))

    else:
        return HttpResponseBadRequest()

    data = r.json()

    if data.get("paymentStatus") is None:
        return HttpResponse(json.dumps({
            "state": "FAILED"
        }))
    elif data["paymentStatus"] in ["SUCCESS", "AUTHORIZED"]:
        payment_o.state = models.Payment.STATE_PAID
        payment_o.save()
        return HttpResponse(json.dumps({
            "state": "SUCCESS"
        }))
    elif data["paymentStatus"] == "PRE_AUTHORIZED":
        return HttpResponse(json.dumps({
            "state": "3DS",
            "oneTime3DsToken": data["oneTime3DsToken"],
            "redirectURL": data["redirectURL"],
            "orderCode": data["orderCode"],
            "sessionID": request.session.get("sess_id", "")
        }))
    elif data["paymentStatus"] == "FAILED":
        return HttpResponse(json.dumps({
            "state": "FAILED"
        }))
    else:
        return HttpResponse(json.dumps({
            "state": "UNKNOWN"
        }))


def worldpay_handle_3ds(request, payment_id, template):
    payment_o = get_object_or_404(models.Payment, id=payment_id)
    if payment_o.state != payment_o.STATE_OPEN:
        return HttpResponseNotFound()

    if request.method != "POST":
        return HttpResponseBadRequest()

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
    print(data)

    if data.get("paymentStatus") is None:
        return render(request, template, {"payment_id": payment_id, "3ds_approved": False})

    if data["paymentStatus"] in ["SUCCESS", "AUTHORIZED"]:
        payment_o.state = models.Payment.STATE_PAID
        payment_o.save()
        return render(request, template, {"payment_id": payment_id, "3ds_approved": True})
    else:
        return render(request, template, {"payment_id": payment_id, "3ds_approved": False})
