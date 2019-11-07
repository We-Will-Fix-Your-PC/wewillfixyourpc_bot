from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render, reverse
from . import models, forms
import json
import django_keycloak_auth.users


def form(request, form_type, form_id):
    if form_type == "unlocking":
        unlock_form_o = get_object_or_404(models.UnlockForm, id=form_id)

        if request.method == "POST":
            unlock_form = forms.UnlockForm(request.POST)

            if unlock_form.is_valid():
                unlock_form.clean()
                phone_unlock = unlock_form_o.phone_unlock

                django_keycloak_auth.users.update_user(
                    unlock_form_o.customer_id,
                    force_update=True,
                    first_name=unlock_form.cleaned_data.get("first_name"),
                    last_name=unlock_form.cleaned_data.get("last_name"),
                    email=unlock_form.cleaned_data.get("email"),
                    phone=unlock_form.cleaned_data.get("phone").as_e164,
                )

                # TODO: Integrate with new system
                # payment_o = payment.models.Payment(
                #     state=payment.models.Payment.STATE_OPEN, customer_id=unlock_form_o.customer_id
                # )
                item_data = json.dumps(
                    {
                        "imei": unlock_form.cleaned_data["imei"],
                        "network": phone_unlock.network.name,
                        "make": phone_unlock.brand.name,
                        "model": phone_unlock.device.name
                        if phone_unlock.device
                        else None,
                        "days": phone_unlock.time,
                    }
                )
                # payment_item_o = payment.models.PaymentItem(
                #     payment=payment_o,
                #     item_type="unlock",
                #     item_data=item_data,
                #     title=f"Unlock {phone_unlock.brand.display_name} "
                #     f"{phone_unlock.device.display_name if phone_unlock.device else ''} from "
                #     f"{unlock_form_o.network_name}",
                #     price=phone_unlock.price,
                # )

                # payment_o.save()
                # payment_item_o.save()

                return redirect("payment:gactions_payment", payment_id="")
        else:
            user = django_keycloak_auth.users.get_user_by_id(unlock_form_o.customer_id)
            unlock_form = forms.UnlockForm(
                initial={
                    "first_name": user.user.get("firstName"),
                    "last_name": user.user.get("lastName"),
                    "email": user.user.get("email"),
                    "phone": next(iter(user.user.get("attributes", {}).get("phone", [])), ""),
                }
            )

        return render(
            request,
            "fulfillment/unlock_form.html",
            {"form": unlock_form, "form_o": unlock_form_o},
        )
    else:
        raise Http404()
