import abc
import asyncio
import collections
import datetime
import functools
import json
import random
from collections import namedtuple
from io import BytesIO
from typing import Any, Dict, List, Optional, Text, Tuple, Union

import dateutil.parser
import django_keycloak_auth.users
import fuzzywuzzy.fuzz
import fuzzywuzzy.process
import fuzzywuzzy.string_processing
import fuzzywuzzy.utils
import inflect
import keycloak.exceptions
import phonenumbers
import pytz
import rasa_sdk.events
import requests
from asgiref.sync import async_to_sync, sync_to_async
from django.conf import settings
from django.core.files.storage import DefaultStorage
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormAction

import operator_interface.models
import rasa_api.models
from fulfillment import models

tz = pytz.timezone("Europe/London")
p = inflect.engine()

SurfaceCapabilities = namedtuple(
    "SurfaceCapabilities",
    "instant_response_required supports_sign_in input_supported highest_input_supported",
)


def get_one_or_none(**kwargs):
    query = models.OpeningHours.objects.filter(**kwargs)
    return query[0] if len(query) > 0 else None


def is_open_on(
    date: datetime.date,
) -> Union[bool, models.OpeningHours, models.OpeningHoursOverride]:
    opening_hours_defs = [
        get_one_or_none(monday=True),
        get_one_or_none(tuesday=True),
        get_one_or_none(wednesday=True),
        get_one_or_none(thursday=True),
        get_one_or_none(friday=True),
        get_one_or_none(saturday=True),
        get_one_or_none(sunday=True),
    ]
    weekday = date.weekday()
    hours = opening_hours_defs[weekday]

    override = models.OpeningHoursOverride.objects.filter(day=datetime.date.today())
    if len(override) > 0:
        override = override[0]
        return False if override.close else override

    return False if hours is None else hours


def is_open_at(date, time):
    hours = is_open_on(date)
    if not hours:
        return False

    time_open = timezone.make_naive(
        timezone.make_aware(datetime.datetime.combine(date, hours.open), tz).astimezone(
            pytz.utc
        )
    ).time()
    time_close = timezone.make_naive(
        timezone.make_aware(
            datetime.datetime.combine(date, hours.close), tz
        ).astimezone(pytz.utc)
    ).time()

    if time < time_open:
        return False
    elif time > time_close:
        return False

    return True


def is_open():
    return is_open_at(datetime.datetime.today(), datetime.datetime.now().time())


def format_hours(time: Union[models.OpeningHours, models.OpeningHoursOverride]):
    try:
        if time.closed:
            return "closed"
    except AttributeError:
        pass
    if time is None:
        return "closed"
    open_t = time.open.strftime("%I:%M %p")
    close_t = time.close.strftime("%I:%M %p")
    return f"open {open_t} - {close_t}"


def format_day(day):
    if day[0] == day[1]:
        day_range = day[0]
    else:
        day_range = f"{day[0]}-{day[1]}"
    return f"On {day_range} we are {format_hours(day[2])}."


def reduce_days(days: List[Tuple[str, str, models.OpeningHours]]):
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
            days[cur_day][2].close == days[next_day][2].close
        ):
            days[cur_day] = (days[cur_day][0], days[next_day][1], days[cur_day][2])
            days.remove(days[next_day])
            continue
        cur_day += 1
    return days


def sender_id_to_conversation(sender_id):
    sender_id = sender_id.split(":")
    if len(sender_id) >= 2:
        platform = sender_id[0]
        platform_id = sender_id[1]
        try:
            conversation = operator_interface.models.Conversation.objects.get(
                platform=platform, platform_id=platform_id
            )

            return conversation
        except operator_interface.models.Conversation.DoesNotExist:
            return None


def update_user_info(
    conversation: operator_interface.models.Conversation,
    email=None,
    force_update=True,
    **kwargs,
):
    if not conversation.conversation_user_id and email:
        user = django_keycloak_auth.users.get_or_create_user(
            email=email,
            first_name=conversation.conversation_name,
            required_actions=["UPDATE_PASSWORD", "UPDATE_PROFILE", "VERIFY_EMAIL"],
            **kwargs,
        )
        if user:
            django_keycloak_auth.users.link_roles_to_user(user.get("id"), ["customer"])
            conversation.conversation_user_id = user.get("id")
            conversation.save()

    if conversation.conversation_user_id:
        django_keycloak_auth.users.update_user(
            conversation.conversation_user_id, force_update=force_update, **kwargs
        )


def get_conversation_capabilities(sender_id) -> SurfaceCapabilities:
    conversation = sender_id_to_conversation(sender_id)

    if conversation is None:
        return None

    instant_response_required = False
    supports_sign_in = False
    input_supported = "text"
    highest_input_supported = None

    if conversation:
        if (
            conversation.platform
            == operator_interface.models.Conversation.GOOGLE_ACTIONS
        ):
            instant_response_required = True
            supports_sign_in = True
            input_supported = "voice"
            platform_from_id = json.loads(conversation.additional_conversation_data)
            for c in platform_from_id["surfaceCapabilities"]:
                if c.get("name") == "actions.capability.WEB_BROWSER":
                    input_supported = "web_form"
            for s in platform_from_id["availableSurfaces"]:
                for c in s.get("capabilities", []):
                    if c.get("name") == "actions.capability.WEB_BROWSER":
                        highest_input_supported = "web_form"

    return SurfaceCapabilities(
        instant_response_required=instant_response_required,
        supports_sign_in=supports_sign_in,
        input_supported=input_supported,
        highest_input_supported=highest_input_supported,
    )


class ActionRequestHuman(Action):
    def name(self) -> Text:
        return "request_human"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        capabilities = await sync_to_async(get_conversation_capabilities)(
            tracker.sender_id
        )

        if not capabilities or not capabilities.instant_response_required:
            dispatcher.utter_message(
                f"Someone will be here to help you shortly..."
                if await sync_to_async(is_open)()
                else f"We're currently closed but this conversation has been flagged and someone"
                f" will be here to help you as soon as we're open again."
            )
            dispatcher.utter_custom_json({"type": "request_human"})
        else:
            config = await sync_to_async(models.ContactDetails.objects.get)()

            dispatcher.utter_message(
                "Unfortunately an agent can't respond to you through this communication channel, "
                "but if you phone or email us we'll be happy to assist!"
            )
            dispatcher.utter_custom_json(
                {
                    "type": "card",
                    "card": {
                        "title": "Contact us",
                        "text": f"Our email is {config.email}.  \n"
                        f"Our phone number is {config.phone_number.as_national}.  \n"
                        f"View our Google Maps listing for further details",
                        "button": {
                            "title": "Open google maps",
                            "link": config.maps_link,
                        },
                    },
                }
            )

        return []


class ActionGreet(Action):
    def name(self) -> Text:
        return "greet"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        utterance: rasa_api.models.Utterance = await sync_to_async(
            rasa_api.models.Utterance.objects.get
        )(name="utter_greet")
        utterance_choice: rasa_api.models.UtteranceResponse = await sync_to_async(
            lambda: random.choice(utterance.utteranceresponse_set.all())
        )()

        dispatcher.utter_message(utterance_choice.text)

        return []


class ActionUpdateInfoSlots(Action):
    def name(self) -> Text:
        return "update_info_slots"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)
        capabilities = await sync_to_async(get_conversation_capabilities)(
            tracker.sender_id
        )
        out = []

        if conversation:
            admin_client = await sync_to_async(
                django_keycloak_auth.clients.get_keycloak_admin_client
            )()

            if not conversation.conversation_user_id:
                if conversation.conversation_name:
                    out.append(
                        rasa_sdk.events.SlotSet("name", conversation.conversation_name)
                    )
            else:
                try:
                    user = await sync_to_async(
                        lambda: admin_client.users.by_id(
                            conversation.conversation_user_id
                        ).get()
                    )()
                except keycloak.exceptions.KeycloakClientError:
                    user = {}

                first_name = user.get("firstName", "")
                last_name = user.get("lastName", "")
                email = user.get("email", None)
                name = f"{first_name} {last_name}"
                attributes = user.get("attributes", {})
                phone_number = next(iter(attributes.get("phone", [])), None)

                out.append(rasa_sdk.events.SlotSet("name", name))

                if phone_number:
                    out.append(rasa_sdk.events.SlotSet("phone_number", phone_number))
                if email:
                    out.append(rasa_sdk.events.SlotSet("email", email))

        out.extend(
            [
                rasa_sdk.events.SlotSet(
                    "instant_response_required", capabilities.instant_response_required
                ),
                rasa_sdk.events.SlotSet(
                    "sign_in_supported", capabilities.supports_sign_in
                ),
                rasa_sdk.events.SlotSet(
                    "input_supported", capabilities.input_supported
                ),
                rasa_sdk.events.SlotSet(
                    "highest_input_supported", capabilities.highest_input_supported
                ),
            ]
        )

        return out


class ActionSignIn(Action):
    def name(self) -> Text:
        return "sign_in"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_custom_json(
            {"type": "request", "request": "sign_in", "text": "Please sign in",}
        )

        return []


class ActionMoveToWebForm(Action):
    def name(self) -> Text:
        return "move_to_web_form_device"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)

        if conversation:
            if (
                conversation.platform
                == operator_interface.models.Conversation.GOOGLE_ACTIONS
            ):
                dispatcher.utter_custom_json(
                    {
                        "type": "request",
                        "request": "google_move_web_browser",
                        "text": "",
                    }
                )

        return []


class ActionCatPic(Action):
    def name(self) -> Text:
        return "cat_pic"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        utterance: rasa_api.models.Utterance = await sync_to_async(
            rasa_api.models.Utterance.objects.get
        )(name="utter_cheer_up")
        utterance_choice: rasa_api.models.UtteranceResponse = await sync_to_async(
            lambda: random.choice(utterance.utteranceresponse_set.all())
        )()

        dispatcher.utter_message(utterance_choice.text)

        cat = requests.get("https://cataas.com/cat")
        if cat.status_code == 200:
            fs = DefaultStorage()
            file = BytesIO(cat.content)
            img = Image.open(file)
            file_name = fs.save(f"cat.{img.format.lower()}", BytesIO(cat.content))

            dispatcher.utter_image_url(fs.base_url + file_name)
        else:
            dispatcher.utter_image_url(utterance_choice.image.url)

        return []


class ActionAskAffirmation(Action):
    def name(self) -> Text:
        return "action_default_ask_affirmation"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        possible_intent = tracker.latest_message["intent"]["name"]

        if possible_intent is not None:
            dispatcher.utter_button_message(
                f"I don't think I understood that correctly 🤔. Did you mean {possible_intent}",
                [
                    {"title": "Yes", "payload": f"/{possible_intent}"},
                    {"title": "No", "payload": "/out_of_scope"},
                ],
            )
            return []
        else:
            dispatcher.utter_message(
                "I am but a computer 🤖, could you rephrase that for me please?"
            )
            return []


class ActionOpeningHours(Action):
    def name(self) -> Text:
        return "support_opening_hours"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        entities = tracker.latest_message.get("entities", [])
        time = next((x for x in entities if x.get("entity") == "time"), None)
        time = time.get("additional_info") if time else None

        opening_hours_defs = {
            "monday": await sync_to_async(get_one_or_none)(monday=True),
            "tuesday": await sync_to_async(get_one_or_none)(tuesday=True),
            "wednesday": await sync_to_async(get_one_or_none)(wednesday=True),
            "thursday": await sync_to_async(get_one_or_none)(thursday=True),
            "friday": await sync_to_async(get_one_or_none)(friday=True),
            "saturday": await sync_to_async(get_one_or_none)(saturday=True),
            "sunday": await sync_to_async(get_one_or_none)(sunday=True),
        }
        days = [
            ("Monday", "Monday", opening_hours_defs["monday"]),
            ("Tuesday", "Tuesday", opening_hours_defs["tuesday"]),
            ("Wednesday", "Wednesday", opening_hours_defs["wednesday"]),
            ("Thursday", "Thursday", opening_hours_defs["thursday"]),
            ("Friday", "Friday", opening_hours_defs["friday"]),
            ("Saturday", "Saturday", opening_hours_defs["saturday"]),
            ("Sunday", "Sunday", opening_hours_defs["sunday"]),
        ]
        future_overrides = await sync_to_async(
            lambda: list(
                models.OpeningHoursOverride.objects.filter(
                    day__gt=datetime.date.today(),
                    day__lte=datetime.date.today() + datetime.timedelta(weeks=2),
                )
            )
        )()

        if time is not None:
            is_day = (
                False
                if time["type"] == "interval"
                else time["grain"] not in ["week", "month", "year"]
            )
            if is_day:
                want_date = dateutil.parser.parse(time["value"]).date()
                date_overrides = await sync_to_async(
                    lambda: list(
                        models.OpeningHoursOverride.objects.filter(day=want_date)
                    )
                )()
                if len(date_overrides) == 0:
                    date_override = None
                else:
                    date_override = date_overrides[0]

                is_today = want_date == datetime.date.today()
                weekday = want_date.weekday()
                hours = (
                    list(opening_hours_defs.values())[weekday]
                    if date_override is None
                    else (None if date_override.closed else date_override)
                )

                if is_today:
                    if hours is None:
                        dispatcher.utter_message("We are closed today.")
                    else:
                        dispatcher.utter_message(f"Today we are {format_hours(hours)}.")
                else:
                    next_of_weekday = datetime.date.today() + dateutil.relativedelta.relativedelta(
                        weekday=weekday
                    )
                    is_next_of_weekday = want_date == next_of_weekday

                    if is_next_of_weekday:
                        if hours is None:
                            dispatcher.utter_message(
                                f"We are closed {want_date.strftime('%A')}."
                            )
                        else:
                            dispatcher.utter_message(
                                f"{want_date.strftime('%A')} we are "
                                f"{format_hours(hours)}."
                            )
                    else:
                        if hours is None:
                            dispatcher.utter_message(
                                f"On {want_date.strftime('%A %B')} the {p.ordinal(want_date.day)}"
                                f" we are closed."
                            )
                        else:
                            dispatcher.utter_message(
                                f"On {want_date.strftime('%A %B')} the {p.ordinal(want_date.day)}"
                                f" we are {format_hours(hours)}."
                            )
                return []
            else:
                if time["type"] == "interval":
                    want_date_start = dateutil.parser.parse(
                        time["from"]["value"]
                    ).date()
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

                days_in_period = reduce_days(list(days_in_period))
                days_in_period = map(format_day, days_in_period)
                days = "\n".join(days_in_period)

                future_overrides = filter(
                    lambda f: f.day.weekday() in day_ids_in_period, future_overrides
                )
                future_overrides_txt = map(
                    lambda d: f"\nOn {d.day.strftime('%A %B')} the {p.ordinal(d.day.day)} we will be "
                    f"{format_hours(d)}.",
                    future_overrides,
                )
                future_overrides_txt = "".join(future_overrides_txt)

                dispatcher.utter_message(f"{days}{future_overrides_txt}")
                return []

        days = reduce_days(days)
        days = map(format_day, days)
        days = "\n".join(days)

        future_overrides_txt = map(
            lambda d: f"\nOn {d.day.strftime('%A %B')} the {p.ordinal(d.day.day)} we will be "
            f"{format_hours(d)}.",
            future_overrides,
        )
        future_overrides_txt = "".join(future_overrides_txt)
        dispatcher.utter_message(f"{days}{future_overrides_txt}")
        return []


class ActionContact(Action):
    def name(self) -> Text:
        return "support_contact"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        contact_details = await sync_to_async(models.ContactDetails.objects.get)()
        dispatcher.utter_message(
            f"You can phone us on {contact_details.phone_number.as_national},"
            f"or email us at {contact_details.email}."
        )
        return []


class ActionContactPhone(Action):
    def name(self) -> Text:
        return "support_contact_phone"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        contact_details = await sync_to_async(models.ContactDetails.objects.get)()
        dispatcher.utter_message(
            f"You can phone us on {contact_details.phone_number.as_national}."
        )
        return []


class ActionContactEmail(Action):
    def name(self) -> Text:
        return "support_contact_email"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        contact_details = await sync_to_async(models.ContactDetails.objects.get)()
        dispatcher.utter_message(f"You can email us at {contact_details.email}.")
        return []


class ActionLocation(Action):
    def name(self) -> Text:
        return "support_location"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        contact_details = await sync_to_async(models.ContactDetails.objects.get)()
        capabilities = await sync_to_async(get_conversation_capabilities)(
            tracker.sender_id
        )

        if capabilities.input_supported != "voice":
            dispatcher.utter_message(
                f"You can find us on Google Maps using the link below."
            )
            dispatcher.utter_custom_json(
                {
                    "type": "card",
                    "card": {
                        "title": "Google maps",
                        "text": "View us on google maps",
                        "button": {"title": "Open", "link": contact_details.maps_link},
                    },
                }
            )
        else:
            dispatcher.utter_message(f"Our address is;\n{contact_details.address}")
        return []


class ActionRepair(Action):
    def name(self) -> Text:
        return "repair"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        device_model = tracker.get_slot("device_model")
        repair_name = tracker.get_slot("device_repair")

        not_repairable = rasa_sdk.events.SlotSet("repairable", False)
        repairable = rasa_sdk.events.SlotSet("repairable", True)

        device_models = (
            await sync_to_async(
                lambda: list(
                    models.Model.objects.filter(name__startswith=device_model.lower())
                )
            )()
            if device_model
            else []
        )
        repair = (
            await sync_to_async(
                lambda: next(
                    models.RepairType.objects.filter(
                        name=repair_name.lower()
                    ).iterator(),
                    None,
                )
            )()
            if repair_name
            else None
        )

        if len(device_models) >= 1 and repair is not None:
            repair_strs = []

            for d in device_models:
                repair_m = await sync_to_async(
                    lambda: next(
                        models.Repair.objects.filter(
                            device=d, repair=repair
                        ).iterator(),
                        None,
                    )
                )()
                if repair_m:
                    repair_strs.append(
                        f"A{p.a(f'{d.display_name} {repair.display_name}')[1:]} will cost "
                        f"£{repair_m.price} and will take roughly {repair_m.repair_time}."
                    )

            if len(repair_strs):
                for r in repair_strs:
                    dispatcher.utter_message(r)
                return [repairable]
            else:
                dispatcher.utter_message(
                    f"Sorry, but a {device_model} {repair_name} isn't on my price list but if you bring the device "
                    f"in we'll be happy to help!"
                )
            return [
                rasa_sdk.events.SlotSet("device_model", None),
                rasa_sdk.events.SlotSet("device_repair", None),
                not_repairable,
            ]

        dispatcher.utter_message(
            f"Sorry, but a {device_model} {repair_name} isn't on my price list but if you bring the device "
            f"in we'll be happy to help!"
        )
        return [
            rasa_sdk.events.SlotSet("device_model", None),
            rasa_sdk.events.SlotSet("device_repair", None),
            not_repairable,
        ]


class ActionRepairBookCheck(Action):
    def name(self) -> Text:
        return "repair_book_check"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        device_model = tracker.get_slot("device_model")
        repair_name = tracker.get_slot("device_repair")

        device_models = (
            await sync_to_async(
                lambda: list(
                    models.Model.objects.filter(name__startswith=device_model.lower())
                )
            )()
            if device_model
            else []
        )
        repair = (
            await sync_to_async(
                lambda: next(
                    models.RepairType.objects.filter(
                        name=repair_name.lower()
                    ).iterator(),
                    None,
                )
            )()
            if repair_name
            else None
        )

        if len(device_models) > 1 and repair is not None:
            dispatcher.utter_template("utter_clarify_model", tracker)
            dispatcher.utter_message(
                ", or ".join(
                    [
                        ", ".join([m.display_name for m in device_models[:-1]]),
                        device_models[-1].display_name,
                    ]
                )
                + "?"
            )
            dispatcher.utter_custom_json(
                {
                    "type": "selection",
                    "selection": {
                        "title": "Device model",
                        "items": [
                            {"title": m.display_name, "key": f"device_model:{m.id}"}
                            for m in device_models
                        ],
                    },
                }
            )
            return [
                rasa_sdk.events.SlotSet("repairable", False),
                rasa_sdk.events.SlotSet(
                    "list_items",
                    [
                        {"id": d.id, "name": d.name, "display_name": d.display_name}
                        for d in device_models
                    ],
                ),
            ]

        return []


class ActionRepairBookClarify(Action):
    def name(self) -> Text:
        return "repair_book_clarify"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        list_items = tracker.get_slot("list_items")
        device_model = next(
            (
                m
                for m in tracker.get_latest_entity_values("device_model")
                if m is not None
            ),
            None,
        )
        try:
            number = next(
                (
                    int(n)
                    for n in tracker.get_latest_entity_values("number")
                    if n is not None
                ),
                None,
            )
        except ValueError:
            number = None
        try:
            ordinal = next(
                (
                    int(o)
                    for o in tracker.get_latest_entity_values("ordinal")
                    if not None
                ),
                None,
            )
        except ValueError:
            ordinal = None
        try:
            mention = next(
                (
                    o.lower()
                    for o in tracker.get_latest_entity_values("mention")
                    if not None
                ),
                None,
            )
        except ValueError:
            mention = None

        device_model = (
            await sync_to_async(
                lambda: next(
                    models.Model.objects.filter(
                        name__startswith=device_model.lower()
                    ).iterator(),
                    None,
                )
            )()
            if device_model
            else None
        )

        if device_model:
            return [rasa_sdk.events.SlotSet("repairable", True)]
        elif mention:
            if mention == "last":
                return [
                    rasa_sdk.events.SlotSet("repairable", True),
                    rasa_sdk.events.SlotSet("device_model", list_items[-1]["name"]),
                ]
            elif mention == "first":
                return [
                    rasa_sdk.events.SlotSet("repairable", True),
                    rasa_sdk.events.SlotSet("device_model", list_items[0]["name"]),
                ]
        elif number or ordinal:
            if ordinal and not number:
                number = ordinal

            if number < len(list_items):
                return [
                    rasa_sdk.events.SlotSet("repairable", True),
                    rasa_sdk.events.SlotSet("device_model", list_items[number]["name"]),
                ]

        dispatcher.utter_template("utter_clarify_model", tracker)
        dispatcher.utter_message(
            ", or".join(
                [
                    ", ".join([m["display_name"] for m in list_items[:-1]]),
                    list_items[-1]["display_name"],
                ]
            )
            + "?"
        )
        dispatcher.utter_custom_json(
            {
                "type": "selection",
                "selection": {
                    "title": "Device model",
                    "items": [
                        {"title": m["display_name"], "key": f"device_mode:{m['id']}"}
                        for m in list_items
                    ],
                },
            }
        )
        return []


class BaseForm(abc.ABC, FormAction):
    def name(self):
        return None

    async def validate_brand(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ):
        asked_once = tracker.get_slot("asked_once")
        asked_once = True if asked_once else False
        brand = await sync_to_async(lambda: list(models.Brand.objects.all()))()
        top_choice = fuzzywuzzy.process.extractOne(
            value.lower(),
            brand,
            lambda v: fuzzywuzzy.utils.full_process(getattr(v, "name", v)),
        )

        if not top_choice or top_choice[1] <= 50:
            if not asked_once:
                dispatcher.utter_message("Hmmm 🤔, I don't recognise that brand.")
                return {"brand": None, "asked_once": True}
            else:
                return {"brand": value, "asked_once": False}
        elif top_choice[1] > 70:
            return {"brand": top_choice[0].name}
        else:
            if not asked_once:
                dispatcher.utter_message(
                    f"Hmmm 🤔, I don't recognise that brand, did you mean "
                    f"{top_choice[0].display_name}?"
                )
                return {"brand": None, "asked_once": True}
            else:
                return {"brand": value, "asked_once": False}

    async def validate_device_model(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ):
        asked_once = tracker.get_slot("asked_once")
        asked_once = True if asked_once else False
        model = await sync_to_async(lambda: list(models.Model.objects.all()))()
        top_choice = fuzzywuzzy.process.extractOne(
            value.lower(),
            model,
            lambda v: fuzzywuzzy.string_processing.StringProcessor.strip(
                fuzzywuzzy.string_processing.StringProcessor.to_lower_case(
                    getattr(v, "name", v)
                )
            ),
            functools.partial(fuzzywuzzy.fuzz.WRatio, full_process=False),
        )

        if not top_choice or top_choice[1] <= 50:
            if not asked_once:
                dispatcher.utter_message("Hmmm 🤔, I don't recognise that model")
                return {"device_model": None, "asked_once": True}
            else:
                return {"device_model": value, "asked_once": False}
        elif top_choice[1] > 70:
            return {"device_model": top_choice[0].name}
        else:
            if not asked_once:
                dispatcher.utter_message(
                    f"Hmmm 🤔, I don't recognise that model, did you mean "
                    f"{top_choice[0].display_name}?"
                )
                return {"device_model": None, "asked_once": True}
            else:
                return {"device_model": value, "asked_once": False}

    async def validate_phone_number(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        try:
            phone = phonenumbers.parse(value, settings.PHONENUMBER_DEFAULT_REGION)
        except phonenumbers.phonenumberutil.NumberParseException:
            dispatcher.utter_message(
                "Hmmm 🤔, that's doesn't look like a valid phone number ☎️ to me."
            )
            return {"phone_number": None}

        if not phonenumbers.is_valid_number(phone):
            dispatcher.utter_message(
                "Hmmm 🤔, that's doesn't look like a valid phone number ☎️ to me."
            )
            return {"phone_number": None}
        else:
            phone = phonenumbers.format_number(
                phone, phonenumbers.PhoneNumberFormat.E164
            )
            conversation = await sync_to_async(sender_id_to_conversation)(
                tracker.sender_id
            )

            if conversation:
                async_to_sync(sync_to_async(update_user_info))(
                    conversation, phone=phone
                )

            return {"phone_number": phone}

    async def validate_email(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)

        if conversation:
            await sync_to_async(update_user_info)(conversation, email=value)

        return {"email": value}

    async def validate_name(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)

        if conversation:
            await sync_to_async(update_user_info)(
                conversation, first_name=value, force_update=False
            )

        return {"name": value}

    async def validate_network(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        loop = asyncio.get_event_loop()

        asked_once = tracker.get_slot("asked_once")
        asked_once = True if asked_once else False
        networks = await sync_to_async(lambda: list(models.Network.objects.all()))()
        alt_networks = await sync_to_async(
            lambda: list(models.NetworkAlternativeName.objects.all())
        )()
        networks = [(n.name, n) for n in networks]
        networks.extend([(n.name, n) for n in alt_networks])

        top_choice = fuzzywuzzy.process.extractOne(
            (value.lower(), None), networks, lambda v: v[0]
        )

        if not top_choice:
            if not asked_once:
                dispatcher.utter_message("Hmmm 🤔, I don't recognise that network.")
                return {"network": None, "asked_once": True}
            else:
                return {"network": value, "asked_once": False}
        elif top_choice[1] > 70:
            return {"network": top_choice[0][0]}
        else:
            if not asked_once:
                dispatcher.utter_message(
                    f"Hmmm 🤔, I don't recognise that network, did you mean "
                    f"{top_choice[0][1].display_name}?."
                )
                return {"network": None, "asked_once": True}
            else:
                return {"network": value, "asked_once": False}


class RepairForm(BaseForm):
    def name(self) -> Text:
        return "repair_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        brand = tracker.get_slot("brand")
        brand = brand if brand else ""
        if tracker.get_slot("device_model") is not None:
            return ["device_model", "device_repair"]
        elif brand.lower() in ["iphone", "ipad"]:
            return ["brand", "device_model", "device_repair"]
        else:
            return ["brand"]

    def slot_mappings(self):
        return {
            "brand": [self.from_entity(entity="brand"), self.from_text()],
            "device_model": [self.from_entity(entity="device_model"), self.from_text()],
            "device_repair": [
                self.from_entity(entity="device_repair"),
                self.from_text(),
            ],
        }

    def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        dispatcher.utter_template("utter_looking_up", tracker)
        return []

    async def validate_device_model(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        brand = tracker.get_slot("brand")
        brand = brand if brand else ""
        if brand.lower() in ["iphone", "ipad", ""]:
            return await super().validate_device_model(
                value, dispatcher, tracker, domain
            )
        else:
            return {"device_model": None}

    async def validate_device_repair(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        asked_once = tracker.get_slot("asked_once")
        asked_once = True if asked_once else False
        repair = await sync_to_async(lambda: list(models.RepairType.objects.all()))()
        top_choice = fuzzywuzzy.process.extractOne(
            value.lower(),
            repair,
            lambda v: fuzzywuzzy.utils.full_process(getattr(v, "name", v)),
        )

        if not top_choice:
            if not asked_once:
                dispatcher.utter_message("Hmmm 🤔, I don't recognise that repair.")
                return {"device_repair": None, "asked_once": True}
            else:
                return {"device_repair": value, "asked_once": False}
        elif top_choice[1] > 70:
            return {"device_repair": top_choice[0].name}
        else:
            if not asked_once:
                dispatcher.utter_message(
                    f"Hmmm 🤔, I don't recognise that repair, did you mean "
                    f"{top_choice[0].display_name}?"
                )
                return {"device_repair": None, "asked_once": True}
            else:
                return {"device_repair": value, "asked_once": False}


class RepairBookForm(BaseForm):
    def name(self) -> Text:
        return "repair_book_form"

    @staticmethod
    async def required_slots(tracker: Tracker) -> List[Text]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)
        ask_phone = (
            (
                False
                if conversation.platform
                == operator_interface.models.Conversation.GOOGLE_ACTIONS
                else True
            )
            if conversation
            else True
        )

        if not ask_phone:
            return ["name", "email", "date", "time"]
        else:
            return ["name", "phone_number", "email", "date", "time"]

    def slot_mappings(self):
        return {
            "name": [self.from_entity(entity="name"), self.from_text()],
            "phone_number": self.from_entity(
                entity="phone-number", not_intent=["imei"]
            ),
            "email": self.from_entity(entity="email"),
            "date": self.from_entity(entity="time"),
            "time": self.from_entity(entity="time"),
        }

    async def validate_date(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        value_dt = datetime.datetime.fromisoformat(value)

        if value_dt.date() < timezone.now().date():
            dispatcher.utter_message("That date is in the past")
            return {"date": None}

        if not await sync_to_async(is_open_on)(value_dt.date()):
            dispatcher.utter_message(
                f"Sorry, but we're closed on {value_dt.strftime('%A')} the {p.ordinal(value_dt.day)}."
            )
            return {"date": None}

        return {"date": value}

    async def validate_time(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        date = tracker.get_slot("date")
        if not date:
            return {"time": None}
        date = datetime.datetime.fromisoformat(date)
        value = next(
            filter(
                lambda e: e.get("entity") == "time",
                tracker.latest_message.get("entities"),
            ),
            None,
        )

        if value:
            value = value.get("additional_info", {})
            if value.get("grain") in ["no-grain", "second", "minute", "hour"]:
                value_dt = datetime.datetime.fromisoformat(value.get("value"))
                if await sync_to_async(is_open_at)(date, value_dt.time()):
                    pass
                elif await sync_to_async(is_open_at)(
                    date, (value_dt + datetime.timedelta(hours=12)).time()
                ):
                    value_dt = value_dt + datetime.timedelta(hours=12)
                    value_dh = value_dt.replace(date.year, date.month, date.day)
                else:
                    dispatcher.utter_message(
                        f"Sorry, we're not open then. "
                        f"On that day we are {format_hours(await sync_to_async(is_open_on)(date))}"
                    )
                    return {"time": None}

                if (
                    value_dt < timezone.now()
                    and date.date() == datetime.datetime.today()
                ):
                    dispatcher.utter_message("That time is in the past")
                    return {"time": None}

                return {"time": value_dt.time().isoformat()}

        return {"time": None}

    async def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)

        date = datetime.datetime.fromisoformat(tracker.get_slot("date"))
        time = datetime.time.fromisoformat(tracker.get_slot("time"))
        date = date.replace(
            hour=time.hour,
            minute=time.minute,
            second=time.second,
            microsecond=time.microsecond,
        )

        device_model = tracker.get_slot("device_model")
        repair_name = tracker.get_slot("device_repair")

        device_model = await sync_to_async(
            lambda: models.Model.objects.filter(name=device_model.lower()).first()
        )()
        repair = await sync_to_async(
            lambda: models.RepairType.objects.filter(name=repair_name.lower()).first()
        )()

        repair_m = await sync_to_async(
            lambda: models.Repair.objects.filter(
                device=device_model, repair=repair
            ).first()
        )()
        booking_m = models.RepairBooking(
            repair=repair_m, customer_id=conversation.conversation_user_id, time=date
        )
        await sync_to_async(booking_m.save)()

        dispatcher.utter_template("utter_booking", tracker)
        return [
            rasa_sdk.events.SlotSet("date", None),
            rasa_sdk.events.SlotSet("time", None),
        ]


class ActionUnlockLookup(Action):
    def name(self) -> Text:
        return "unlock_lookup"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        brand = tracker.get_slot("brand")  # type: Text
        device_model = tracker.get_slot("device_model")  # type: Text
        network = tracker.get_slot("network")  # type: Text

        not_unlockable = rasa_sdk.events.SlotSet("unlockable", False)
        unlockable = rasa_sdk.events.SlotSet("unlockable", True)

        network_o = await sync_to_async(
            lambda: list(models.Network.objects.filter(name=network.lower()))
        )()
        if not len(network_o):
            network_alt_o = models.NetworkAlternativeName.objects.filter(
                name=network.lower()
            )
            if not len(network_alt_o):
                dispatcher.utter_message(
                    f"Sorry, we can't unlock phones from {network}."
                )
                return [not_unlockable]
            else:
                network_o = network_alt_o[0].network
                network_name = network_alt_o[0].display_name
        else:
            network_o = network_o[0]
            network_name = network_o.display_name

        brand_o: Optional[models.Brand] = next(
            models.Brand.objects.filter(name=brand.lower()).iterator(), None
        )
        if not brand_o:
            dispatcher.utter_message(f"Sorry, we can't unlock {brand} phones.")
            return [not_unlockable]

        if device_model is not None:
            device_model_o: Optional[models.Model] = next(
                models.Model.objects.filter(name=device_model).iterator(), None
            )
            if not device_model_o:
                dispatcher.utter_message(f"Sorry, we can't unlock an {device_model}.")
                return [not_unlockable]
        else:
            device_model_o = None

        unlock_o: List[models.PhoneUnlock] = models.PhoneUnlock.objects.filter(
            network=network_o, brand=brand_o, device=device_model_o
        )
        if not len(unlock_o):
            dispatcher.utter_message(
                f"Sorry, we can't unlock a {brand_o.display_name} "
                f"{device_model if device_model else ''} from {network_name}."
            )
            return [not_unlockable]
        else:
            unlock_o: models.PhoneUnlock = unlock_o[0]
            dispatcher.utter_message(
                f"Unlocking a {brand_o.display_name} "
                f"{device_model_o.display_name if device_model_o else ''} "
                f"from {network_name} will cost £{unlock_o.price} and take {unlock_o.time}."
            )
            return [unlockable]


class ActionOrderUnlock(Action):
    def name(self) -> Text:
        return "unlock_order"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        brand: Text = tracker.get_slot("brand")
        device_model: Text = tracker.get_slot("device_model")
        network: Text = tracker.get_slot("network")
        imei: Text = tracker.get_slot("imei")

        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)

        if conversation:
            try:
                network_o = models.Network.objects.get(name=network.lower())
                network_name = network_o.display_name
            except models.Network.DoesNotExist:
                network_alt_o = models.NetworkAlternativeName.objects.get(
                    name=network.lower()
                )
                network_o = network_alt_o.network
                network_name = network_alt_o.display_name
            brand_o = models.Brand.objects.get(name=brand.lower())
            device_model_o = (
                models.Model.objects.get(name=device_model.lower())
                if device_model
                else None
            )

            unlock_o: models.PhoneUnlock = models.PhoneUnlock.objects.get(
                network=network_o, brand=brand_o, device=device_model_o
            )

            # TODO: Integrate with new system
            # payment_o = payment.models.Payment(
            #     state=payment.models.Payment.STATE_OPEN, customer_id=conversation.conversation_user_id
            # )
            item_data = json.dumps(
                {
                    "imei": imei,
                    "network": network_o.name,
                    "make": brand_o.name,
                    "model": device_model_o.name if device_model_o else None,
                    "days": unlock_o.ti,
                }
            )
            # payment_item_o = payment.models.PaymentItem(
            #     payment=payment_o,
            #     item_type="unlock",
            #     item_data=item_data,
            #     title=f"Unlock {brand_o.display_name} {device_model_o.display_name if device_model_o else ''} from "
            #     f"{network_name}",
            #     price=unlock_o.price,
            # )

            # payment_o.save()
            # payment_item_o.save()

            # dispatcher.utter_custom_json(
            #     {"type": "payment", "payment_id": str(payment_o.id)}
            # )

        return []


class ActionUnlockClear(Action):
    def name(self) -> Text:
        return "unlock_clear"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        return [
            rasa_sdk.events.SlotSet("brand", None),
            rasa_sdk.events.SlotSet("device_model", None),
            rasa_sdk.events.SlotSet("network", None),
            rasa_sdk.events.SlotSet("imei", None),
        ]


class UnlockLookupForm(BaseForm):
    def name(self) -> Text:
        return "unlock_lookup_form"

    @staticmethod
    async def required_slots(tracker: Tracker) -> List[Text]:
        required = ["brand"]

        model_needed = False
        brand = tracker.get_slot("brand")
        if brand is not None:
            brand_o = await sync_to_async(
                lambda: next(
                    models.Brand.objects.filter(name=brand.lower()).iterator(), None
                )
            )()
            if brand_o:
                phone_unlocks = await sync_to_async(
                    lambda: next(
                        models.PhoneUnlock.objects.filter(
                            brand=brand_o, device=None
                        ).iterator(),
                        None,
                    )
                )()
                model_needed = phone_unlocks is None

        if model_needed:
            required.append("device_model")

        required.extend(["network"])

        return required

    def slot_mappings(self):
        return {
            "brand": [self.from_entity(entity="brand"), self.from_text()],
            "device_model": [self.from_entity(entity="device_model"), self.from_text()],
            "network": [self.from_entity(entity="network"), self.from_text()],
        }

    def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        dispatcher.utter_template("utter_looking_up", tracker)
        return []


class UnlockOrderForm(BaseForm):
    def name(self) -> Text:
        return "unlock_order_form"

    @staticmethod
    async def required_slots(tracker: Tracker) -> List[Text]:
        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)
        ask_phone = (
            (
                False
                if conversation.platform
                == operator_interface.models.Conversation.GOOGLE_ACTIONS
                else True
            )
            if conversation
            else True
        )

        if not ask_phone:
            return ["name", "email", "imei"]
        else:
            return ["name", "phone_number", "email", "imei"]

    def slot_mappings(self):
        return {
            "name": [self.from_entity(entity="name"), self.from_text()],
            "phone_number": self.from_entity(
                entity="phone-number", not_intent=["imei"]
            ),
            "email": self.from_entity(entity="email"),
            "imei": [
                self.from_entity(entity="imei"),
                self.from_entity(entity="number"),
                self.from_text(),
            ],
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

    def validate_imei(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        try:
            checksum = self.luhn_checksum(value)
        except ValueError:
            checksum = 1

        if checksum or len(str(value)) != 15:
            dispatcher.utter_message(
                "Hmmm 🤔, that doesn't look like an IMEI, try again..."
            )
            return {"imei": None}

        return {"imei": value}

    def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        return []


class UnlockOrderWebForm(Action):
    def name(self) -> Text:
        return "unlock_order_web_form"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        brand = tracker.get_slot("brand")  # type: Text
        device_model = tracker.get_slot("device_model")  # type: Text
        network = tracker.get_slot("network")  # type: Text

        conversation = await sync_to_async(sender_id_to_conversation)(tracker.sender_id)

        if conversation:
            try:
                network_o: models.Network = await sync_to_async(
                    models.Network.objects.get
                )(name=network.lower())
                network_name = network_o.display_name
            except models.Network.DoesNotExist:
                network_alt_o = await sync_to_async(
                    models.NetworkAlternativeName.objects.get
                )(name=network.lower())
                network_o = network_alt_o.network
                network_name = network_alt_o.display_name
            brand_o: models.Brand = await sync_to_async(models.Brand.objects.get)(
                name=brand.lower()
            )
            device_model_o = (
                await sync_to_async(models.Model.objects.get)(name=device_model.lower())
                if device_model
                else None
            )

            unlock_o: models.PhoneUnlock = await sync_to_async(
                models.PhoneUnlock.objects.get
            )(network=network_o, brand=brand_o, device=device_model_o)

            unlock_form = models.UnlockForm(
                phone_unlock=unlock_o,
                network_name=network_name,
                customer_id=conversation.conversation_user_id,
            )
            await sync_to_async(unlock_form.save)()

            dispatcher.utter_message("Continue with your order here")
            dispatcher.utter_custom_json(
                {
                    "type": "card",
                    "card": {
                        "title": "Complete your order",
                        "text": "Open this form to complete your order",
                        "button": {
                            "title": "Open",
                            "link": settings.EXTERNAL_URL_BASE + reverse(
                                "fulfillment:form",
                                kwargs={
                                    "form_type": "unlocking",
                                    "form_id": str(unlock_form.id),
                                },
                            ),
                        },
                    },
                }
            )
        return []


class ActionRateSlot(Action):
    def name(self) -> Text:
        return "rate_slot"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
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
        return {"rating": [self.from_entity(entity="number")]}

    def validate_rating(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Optional[Dict[Text, Any]]:
        try:
            value = int(value)

            if value < 1 or value > 10:
                dispatcher.utter_message("Please enter a number between 1 and 10.")
                return {"rating": None}

            return {"rating": value}
        except ValueError:
            dispatcher.utter_message("Please enter a number.")
            return {"rating": None}

    async def submit(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        rating = operator_interface.models.ConversationRating(
            sender_id=tracker.sender_id, rating=tracker.get_slot("rating")
        )
        await sync_to_async(rating.save)()
        return []
