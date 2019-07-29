from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render, get_object_or_404
from . import models
import json


def fb_payment(request, payment_id):
    return render(request, "payment/fb_payment.html", {"payment_id": payment_id})


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
