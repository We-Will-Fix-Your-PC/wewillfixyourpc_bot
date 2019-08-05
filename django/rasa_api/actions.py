from fulfillment import models
import rasa_api.models
import operator_interface.models
import payment.models
import datetime
import random
import collections
from django.utils import timezone
from django.conf import settings
import pytz
import time
import json
import inflect
import phonenumbers
import fuzzywuzzy.process
import fuzzywuzzy.utils
import dateutil.parser
import rasa_sdk.events
from rasa_sdk import Action, Tracker
from rasa_sdk.forms import FormAction
from rasa_sdk.executor import CollectingDispatcher
from typing import Text, List, Dict, Any, Union, Optional

tz = pytz.timezone('Europe/London')
p = inflect.engine()


def get_one_or_none(**kwargs):
    query = models.OpeningHours.objects.filter(**kwargs)
    return query[0] if len(query) > 0 else None


def is_open():
    opening_hours_defs = [
        get_one_or_none(monday=True),
        get_one_or_none(tuesday=True),
        get_one_or_none(wednesday=True),
        get_one_or_none(thursday=True),
        get_one_or_none(friday=True),
        get_one_or_none(saturday=True),
        get_one_or_none(sunday=True),
    ]
    today = datetime.date.today()
    weekday = today.weekday()
    hours = opening_hours_defs[weekday]

    if hours is None:
        return False

    now = datetime.datetime.now().time()
    time_open = timezone.make_naive(timezone.make_aware(
        datetime.datetime.combine(today, hours.open), tz)
                                    .astimezone(pytz.utc)).time()
    time_close = timezone.make_naive(timezone.make_aware(
        datetime.datetime.combine(today, hours.close), tz)
                                     .astimezone(pytz.utc)).time()

    if now < time_open:
        return False
    elif now > time_close:
        return False

    return True


class ActionRequestHuman(Action):
    def name(self) -> Text:
        return "request_human"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(f"Someone will be here to help you shortly..." if is_open() else
                                 f"We're currently closed but this conversation has been flagged and someone"
                                 f" will be here to help you as soon as we're open again")
        dispatcher.utter_custom_json({
            "type": "request_human"
        })
        return []


class ActionGreet(Action):
    def name(self) -> Text:
        return "greet"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        utterance = rasa_api.models.Utterance.objects.get(name="utter_greet")
        utterance_choice = random.choice(utterance.utteranceresponse_set.all())  \
            # type: rasa_api.models.UtteranceResponse

        dispatcher.utter_message(utterance_choice.text)

        sender_id = tracker.sender_id.split(":")
        if len(sender_id) >= 2:
            platform = sender_id[0]
            platform_id = sender_id[1]
            try:
                conversation = operator_interface.models.Conversation.objects.get(
                    platform=platform, platform_id=platform_id
                )

                return [rasa_sdk.events.SlotSet("name", conversation.customer_name)]
            except operator_interface.models.Conversation.DoesNotExist:
                pass

        return []


class ActionAskAffirmation(Action):
    def name(self) -> Text:
        return "action_default_ask_affirmation"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        possible_intent = tracker.latest_message["intent"]["name"]

        if possible_intent is not None:
            dispatcher.utter_button_message(
                f"I don't think I understood that correctly 🤔. Did you mean {possible_intent}", [{
                    "title": "Yes",
                    "payload": f"/{possible_intent}"
                }, {
                    "title": "No",
                    "payload": "/out_of_scope"
                }])
            return []
        else:
            dispatcher.utter_message("I am but a computer 🤖, could you rephrase that for me please?")
            return []


class ActionOpeningHours(Action):
    def name(self) -> Text:
        return "support_opening_hours"

    @staticmethod
    def format_hours(time: Union[models.OpeningHours, models.OpeningHoursOverride]):
        try:
            if time.closed:
                return "Closed"
        except AttributeError:
            pass
        if time is None:
            return "Closed"
        open_t = time.open.strftime("%I:%M %p")
        close_t = time.close.strftime("%I:%M %p")
        return f"{open_t} - {close_t}"

    def format_day(self, day):
        if day[0] == day[1]:
            day_range = day[0]
        else:
            day_range = f"{day[0]}-{day[1]}"
        return f"{day_range}: {self.format_hours(day[2])}"

    @staticmethod
    def reduce_days(days):
        cur_day = 0
        while cur_day < len(days):
            next_day = cur_day + 1
            if next_day == len(days):
                next_day = 0
            if (days[cur_day][2] is None) and (days[next_day][2] is None):
                days[cur_day] = (days[cur_day][0], days[next_day][1], days[cur_day][2])
                days.remove(days[next_day])
                continue
            elif (days[cur_day][2] is None) or (days[next_day][2] is None):
                pass
            elif (days[cur_day][2].open == days[next_day][2].open) and (
                    days[cur_day][2].close == days[next_day][2].close):
                days[cur_day] = (days[cur_day][0], days[next_day][1], days[cur_day][2])
                days.remove(days[next_day])
                continue
            cur_day += 1
        return days

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message.get("entities", [])
        time = next((x for x in entities if x.get("entity") == "time"), None)
        time = time.get('additional_info') if time else None

        opening_hours_defs = {
            "monday": get_one_or_none(monday=True),
            "tuesday": get_one_or_none(tuesday=True),
            "wednesday": get_one_or_none(wednesday=True),
            "thursday": get_one_or_none(thursday=True),
            "friday": get_one_or_none(friday=True),
            "saturday": get_one_or_none(saturday=True),
            "sunday": get_one_or_none(sunday=True),
        }
        days = [("Monday", "Monday", opening_hours_defs["monday"]),
                ("Tuesday", "Tuesday", opening_hours_defs["tuesday"]),
                ("Wednesday", "Wednesday", opening_hours_defs["wednesday"]),
                ("Thursday", "Thursday", opening_hours_defs["thursday"]),
                ("Friday", "Friday", opening_hours_defs["friday"]),
                ("Saturday", "Saturday", opening_hours_defs["saturday"]),
                ("Sunday", "Sunday", opening_hours_defs["sunday"])]
        future_overrides = models.OpeningHoursOverride.objects.filter(
            day__gt=datetime.date.today(), day__lte=datetime.date.today() + datetime.timedelta(weeks=2))

        if time is not None:
            is_day = False if time["type"] == "interval" else time["grain"] not in ["week", "month", "year"]
            if is_day:
                want_date = dateutil.parser.parse(time["value"]).date()
                date_overrides = models.OpeningHoursOverride.objects.filter(day=want_date)
                if len(date_overrides) == 0:
                    date_override = None
                else:
                    date_override = date_overrides[0]

                is_today = want_date == datetime.date.today()
                weekday = want_date.weekday()
                hours = list(opening_hours_defs.values())[weekday] if date_override is None else \
                    (None if date_override.closed else date_override)

                if is_today:
                    if hours is None:
                        dispatcher.utter_message("We are closed today.")
                    else:
                        dispatcher.utter_message(f"Today we are open {self.format_hours(hours)}.")
                else:
                    next_of_weekday = datetime.date.today() + dateutil.relativedelta.relativedelta(weekday=weekday)
                    is_next_of_weekday = want_date == next_of_weekday

                    if is_next_of_weekday:
                        if hours is None:
                            dispatcher.utter_message(f"We are closed {want_date.strftime('%A')}.")
                        else:
                            dispatcher.utter_message(f"{want_date.strftime('%A')} we are open "
                                                     f"{self.format_hours(hours)}.")
                    else:
                        if hours is None:
                            dispatcher.utter_message(f"On {want_date.strftime('%A %B')} the {p.ordinal(want_date.day)}"
                                                     f" we are closed.")
                        else:
                            dispatcher.utter_message(f"On {want_date.strftime('%A %B')} the {p.ordinal(want_date.day)}"
                                                     f" we are open {self.format_hours(hours)}.")
                return []
            else:
                if time["type"] == "interval":
                    want_date_start = dateutil.parser.parse(time["from"]["value"]).date()
                    want_date_end = dateutil.parser.parse(time["to"]["value"]).date()
                else:
                    want_date_start = dateutil.parser.parse(time["value"]).date()
                    if time["grain"] == "week":
                        want_date_end = want_date_start + datetime.timedelta(weeks=1)
                    elif time["grain"] == "month":
                        want_date_end = want_date_start + datetime.timedelta(weeks=4)
                    elif time["grain"] == "year":
                        want_date_end = want_date_start + datetime.timedelta(days=365)
                    else:
                        want_date_end = want_date_start

                days_in_period = collections.OrderedDict()
                days_in_period[days[want_date_start.weekday()]] = None
                day_ids_in_period = collections.OrderedDict()
                day_ids_in_period[want_date_start.weekday()] = None
                cur_date = want_date_start
                while cur_date != want_date_end:
                    cur_date += datetime.timedelta(days=1)
                    days_in_period[days[cur_date.weekday()]] = None
                    day_ids_in_period[cur_date.weekday()] = None
                days_in_period = days_in_period.keys()
                day_ids_in_period = day_ids_in_period.keys()

                days_in_period = self.reduce_days(list(days_in_period))
                days_in_period = map(self.format_day, days_in_period)
                days = "\n".join(days_in_period)

                future_overrides = filter(lambda f: f.day.weekday() in day_ids_in_period, future_overrides)
                future_overrides_txt = map(
                    lambda d: f"\nOn {d.day.strftime('%A %B')} the {p.ordinal(d.day.day)} we will be"
                              f" {'closed' if d.closed else f'open {self.format_hours(d)}'}",
                    future_overrides)
                future_overrides_txt = "".join(future_overrides_txt)

                dispatcher.utter_message(f"Our opening hours are:\n{days}{future_overrides_txt}")
                return []

        days = self.reduce_days(days)
        days = map(self.format_day, days)
        days = "\n".join(days)

        future_overrides_txt = map(lambda d: f"\nOn {d.day.strftime('%A %B')} the {p.ordinal(d.day.day)} we will be"
                                             f" {'closed' if d.closed else f'open {self.format_hours(d)}'}",
                                   future_overrides)
        future_overrides_txt = "".join(future_overrides_txt)
        dispatcher.utter_message(f"Our opening hours are:\n{days}{future_overrides_txt}")
        return []


class ActionContact(Action):
    def name(self) -> Text:
        return "support_contact"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        contact_details = models.ContactDetails.objects.get()
        dispatcher.utter_message(f"You can phone us on {contact_details.phone_number.as_national},"
                                 f"or email us at {contact_details.email}")
        return []


class ActionContactPhone(Action):
    def name(self) -> Text:
        return "support_contact_phone"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        contact_details = models.ContactDetails.objects.get()
        dispatcher.utter_message(f"You can phone us on {contact_details.phone_number.as_national}")
        return []


class ActionContactEmail(Action):
    def name(self) -> Text:
        return "support_contact_email"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        contact_details = models.ContactDetails.objects.get()
        dispatcher.utter_message(f"You can email us at {contact_details.email}")
        return []


class ActionLocation(Action):
    def name(self) -> Text:
        return "support_location"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        contact_details = models.ContactDetails.objects.get()
        dispatcher.utter_message(f"You can find us on Google Maps at {contact_details.maps_link}")
        return []


class ActionRepair(Action):
    def name(self) -> Text:
        return "repair"

    def generic_repair(self, model_o, model: Text, repair_name: Text, dispatcher: CollectingDispatcher):
        repair_m = model_o.objects.filter(name__startswith=model.lower(), repair_name=repair_name.lower())

        if len(repair_m) > 0:
            repair_strs = map(lambda r: f"A{p.a(f'{r.name} {repair_name}')[1:]} will cost £{r.price}"
                                        f" and will take roughly {r.repair_time}", repair_m)
            for r in repair_strs:
                dispatcher.utter_message(r)
        else:
            dispatcher.utter_message(f"Sorry, but we do not fix {model} {p.plural(repair_name)}")

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        brand = tracker.get_slot("brand")
        iphone_model = tracker.get_slot("iphone_model")
        ipad_model = tracker.get_slot("ipad_model")
        repair_name = tracker.get_slot("iphone_repair")

        time.sleep(3)

        if iphone_model is not None:
            brand = "iPhone"

        if ipad_model is not None:
            brand = "iPad"

        if brand is not None:
            if brand == "iPhone":
                if iphone_model is not None and repair_name is not None:
                    self.generic_repair(models.IPhoneRepair, iphone_model, repair_name, dispatcher)
                    return []
            elif brand == "iPad":
                if ipad_model is not None and repair_name is not None:
                    self.generic_repair(models.IPadRepair, ipad_model, repair_name, dispatcher)
                    return []

        dispatcher.utter_message("Sorry, we don't fix those")
        return []


class RepairForm(FormAction):
    def name(self) -> Text:
        return "repair_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        if tracker.get_slot("iphone_model") is not None:
            return ["iphone_repair"]
        elif tracker.get_slot("ipad_model") is not None:
            return ["iphone_repair"]
        elif tracker.get_slot('brand') == 'iPad':
            return ["brand", "ipad_model", "iphone_repair"]
        elif tracker.get_slot('brand') == 'iPhone':
            return ["brand", "iphone_model", "iphone_repair"]
        else:
            return ["brand"]

    def slot_mappings(self):
        return {
            "brand": self.from_entity(entity="brand"),
            "iphone_model": self.from_entity(entity="iphone_model"),
            "ipad_model": self.from_entity(entity="ipad_model"),
            "iphone_repair": self.from_entity(entity="iphone_repair"),
        }

    def submit(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict]:
        dispatcher.utter_template('utter_looking_up', tracker)
        return []


class ActionUnlockLookup(Action):
    def name(self) -> Text:
        return "unlock_lookup"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        brand = tracker.get_slot("brand")  # type: Text
        iphone_model = tracker.get_slot("iphone_model")  # type: Text
        network = tracker.get_slot("network")  # type: Text

        time.sleep(3)

        if iphone_model is not None:
            brand = "iPhone"

        not_unlockable = rasa_sdk.events.SlotSet("unlockable", False)
        unlockable = rasa_sdk.events.SlotSet("unlockable", True)

        network_o = models.Network.objects.filter(name=network.lower())
        if not len(network_o):
            network_alt_o = models.NetworkAlternativeName.objects.filter(name=network.lower())
            if not len(network_alt_o):
                dispatcher.utter_message(f"Sorry, we can't unlock phones from {network}")
                return [not_unlockable]
            else:
                network_o = network_alt_o[0].network
                network_name = network_alt_o[0].display_name
        else:
            network_o = network_o[0]
            network_name = network_o.display_name

        brand_o = models.Brand.objects.filter(name=brand.lower())  # type: List[models.Brand]
        if not len(brand_o):
            dispatcher.utter_message(f"Sorry, we can't unlock {brand} phones")
            return [not_unlockable]
        brand_o = brand_o[0]  # type: models.Brand

        unlock_o = models.PhoneUnlock.objects.filter(
            network=network_o, brand=brand_o, device=iphone_model if iphone_model else None
        )  # type: List[models.PhoneUnlock]
        print(network_o, brand_o, iphone_model)
        if not len(unlock_o):
            dispatcher.utter_message(f"Sorry, we can't unlock a {brand_o.display_name} "
                                     f"{iphone_model if iphone_model else ''} from {network_name}")
            return [not_unlockable]
        else:
            unlock_o = unlock_o[0]  # type: models.PhoneUnlock
            dispatcher.utter_message(f"Unlocking a {brand_o.display_name} {iphone_model if iphone_model else ''} "
                                     f"from {network_name} will cost £{unlock_o.price} and take {unlock_o.time}")
            return [unlockable]


class ActionOrderUnlock(Action):
    def name(self) -> Text:
        return "unlock_order"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        brand = tracker.get_slot("brand")  # type: Text
        iphone_model = tracker.get_slot("iphone_model")  # type: Text
        network = tracker.get_slot("network")  # type: Text
        name = tracker.get_slot("name")  # type: Text
        phone_number = tracker.get_slot("phone_number")  # type: Text
        email = tracker.get_slot("email")  # type: Text
        imei = tracker.get_slot("imei")  # type: Text

        if iphone_model is not None:
            brand = "iPhone"

        network_o = models.Network.objects.get(name=network.lower())
        brand_o = models.Brand.objects.get(name=brand.lower())

        unlock_o = models.PhoneUnlock.objects.get(
            network=network_o, brand=brand_o, device=iphone_model.lower() if iphone_model else None
        )  # type: models.PhoneUnlock

        customer_o = payment.models.Customer.find_customer(name=name, email=email, phone=phone_number)
        payment_o = payment.models.Payment(
            state=payment.models.Payment.STATE_OPEN, environment=payment.models.Payment.ENVIRONMENT_TEST,
            customer=customer_o
        )
        item_data = json.dumps({
            "imei": imei,
            "network": network_o.name,
            "make": brand_o.name,
            "model": unlock_o.device,
            "days": unlock_o.time
        })
        payment_item_o = payment.models.PaymentItem(
            payment=payment_o, item_type="unlock", item_data=item_data,
            title=f"Unlock {brand_o.name} {iphone_model if iphone_model else ''} from {network_o.name}",
            price=unlock_o.price
        )

        payment_o.save()
        payment_item_o.save()

        dispatcher.utter_custom_json({
            "type": "payment",
            "payment_id": str(payment_o.id)
        })


class ActionUnlockClear(Action):
    def name(self) -> Text:
        return "unlock_clear"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [
            rasa_sdk.events.SlotSet("brand", None),
            rasa_sdk.events.SlotSet("iphone_model", None),
            rasa_sdk.events.SlotSet("network", None),
            rasa_sdk.events.SlotSet("imei", None),
        ]


class UnlockForm(FormAction):
    def name(self) -> Text:
        return "unlock_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        required = []

        if tracker.get_slot("iphone_model") is not None:
            required.append("iphone_model")
        elif tracker.get_slot('brand') == 'iPhone':
            required.extend(["brand", "iphone_model"])
        else:
            required.append("brand")

        required.extend(["network", "name", "phone_number", "email", "imei"])

        return required

    def slot_mappings(self):
        return {
            "brand": [self.from_entity(entity="brand"), self.from_text()],
            "iphone_model": self.from_entity(entity="iphone_model"),
            "network": [self.from_entity(entity="network"), self.from_text()],
            "name": [self.from_entity(entity="name"), self.from_text()],
            "phone_number": self.from_entity(entity="phone-number", not_intent=["imei"]),
            "email": self.from_entity(entity="email"),
            "imei": [self.from_entity(entity="imei"), self.from_entity(entity="number"), self.from_text()]
        }

    @staticmethod
    def luhn_checksum(number):
        def digits_of(n):
            return [int(d) for d in str(n)]

        digits = digits_of(number)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = 0
        checksum += sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d * 2))
        return checksum % 10

    def validate_imei(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker,
                      domain: Dict[Text, Any]) -> Optional[Dict[Text, Any]]:
        try:
            checksum = self.luhn_checksum(value)
        except ValueError:
            checksum = 1

        if checksum or len(str(value)) != 15:
            dispatcher.utter_message("Hmmm 🤔, that doesn't look like an IMEI, try again...")
            return {"imei": None}

        return {"imei": value}

    def validate_brand(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker,
                      domain: Dict[Text, Any]) -> Optional[Dict[Text, Any]]:
        brand = models.Brand.objects.all()
        top_choice = fuzzywuzzy.process.extractOne(
            value.lower(), brand, lambda v: fuzzywuzzy.utils.full_process(getattr(v, "name", v))
        )

        if not top_choice:
            dispatcher.utter_message("Hmmm 🤔, I don't recognise that brand")
            return {"brand": None}
        elif top_choice[1] > 70:
            return {"brand": top_choice[0].name}
        else:
            dispatcher.utter_message(f"Hmmm 🤔, I don't recognise that brand, did you mean "
                                     f"{top_choice[0].display_name}?")
            return {"brand": None}

    def validate_network(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker,
                      domain: Dict[Text, Any]) -> Optional[Dict[Text, Any]]:
        networks = models.Network.objects.all()
        alt_networks = models.NetworkAlternativeName.objects.all()
        networks = [(n.name, n) for n in networks]
        networks.extend([(n.name, n.network) for n in alt_networks])

        top_choice = fuzzywuzzy.process.extractOne((value.lower(), None), networks, lambda v: v[0])

        if not top_choice:
            dispatcher.utter_message("Hmmm 🤔, I don't recognise that network")
            return {"network": None}
        elif top_choice[1] > 70:
            return {"network": top_choice[0][0]}
        else:
            dispatcher.utter_message(f"Hmmm 🤔, I don't recognise that network, did you mean "
                                     f"{top_choice[0][1].display_name}?")
            return {"network": None}

    def validate_phone_number(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker,
                      domain: Dict[Text, Any]) -> Optional[Dict[Text, Any]]:
        try:
            phone = phonenumbers.parse(value, settings.PHONENUMBER_DEFAULT_REGION)
        except phonenumbers.phonenumberutil.NumberParseException:
            dispatcher.utter_message("Hmmm 🤔, that's doesn't look like a valid phone number ☎️ to me")
            return {"phone_number": None}

        if not phonenumbers.is_valid_number(phone):
            dispatcher.utter_message("Hmmm 🤔, that's doesn't look like a valid phone number ☎️ to me")
            return {"phone_number": None}
        else:
            return {"phone_number": phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.E164)}

    def submit(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict]:
        dispatcher.utter_template('utter_looking_up', tracker)
        return []


class ActionRateSlot(Action):
    def name(self) -> Text:
        return "rate_slot"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        val = next(tracker.get_latest_entity_values("number"), None)
        if val:
            return [rasa_sdk.events.SlotSet("rating", val)]
        return []


class RateForm(FormAction):
    def name(self) -> Text:
        return "rate_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        return ["rating"]

    def slot_mappings(self):
        return {
            "rating": [
                self.from_entity(entity="number"),
            ]
        }

    def validate_rating(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker,
                        domain: Dict[Text, Any]) -> Optional[Dict[Text, Any]]:
        try:
            value = int(value)

            if value < 1 or value > 10:
                dispatcher.utter_message("Please enter a number between 1 and 10")
                return {"rating": None}

            return {"rating": value}
        except ValueError:
            dispatcher.utter_message("Please enter a number")
            return {"rating": None}

    def submit(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict]:
        rating = operator_interface.models.ConversationRating(sender_id=tracker.sender_id,
                                                              rating=tracker.get_slot("rating"))
        rating.save()
        return []
