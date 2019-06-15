import dateutil.parser
import dateutil.relativedelta
import datetime
import inflect
import typing
import pytz
from django.utils import timezone
from . import models
import operator_interface.models

tz = pytz.timezone('Europe/London')
p = inflect.engine()


def get_one_or_none(**kwargs):
    query = models.OpeningHours.objects.filter(**kwargs)
    return query[0] if len(query) > 0 else None


def opening_hours(params, *_):
    def inner():
        def format_hours(time: typing.Union[models.OpeningHours, models.OpeningHoursOverride]):
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

        def format_day(day):
            if day[0] == day[1]:
                day_range = day[0]
            else:
                day_range = f"{day[0]}-{day[1]}"
            return f"{day_range}: {format_hours(day[2])}"

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

        opening_hours_defs = {
            "monday": get_one_or_none(monday=True),
            "tuesday": get_one_or_none(tuesday=True),
            "wednesday": get_one_or_none(wednesday=True),
            "thursday": get_one_or_none(thursday=True),
            "friday": get_one_or_none(friday=True),
            "saturday": get_one_or_none(saturday=True),
            "sunday": get_one_or_none(sunday=True),
        }

        want_date = params.get("date")
        want_date_period = params.get("date-period")
        if want_date is not None and want_date != "":
            want_date = dateutil.parser.parse(want_date).date()

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
                    return f"We are closed today.\n\nDo you need help with anything else?"
                return f"Today we are open {format_hours(hours)}.\n\n" \
                    f"Do you need help with anything else?"
            else:
                next_of_weekday = datetime.date.today() + dateutil.relativedelta.relativedelta(weekday=weekday)
                is_next_of_weekday = want_date == next_of_weekday

                if is_next_of_weekday:
                    if hours is None:
                        return f"We are closed {want_date.strftime('%A')}.\n\n" \
                            f"Do you need help with anything else?"
                    return f"{want_date.strftime('%A')} we are open {format_hours(hours)}.\n\n" \
                        f"Do you need help with anything else?"
                else:
                    if hours is None:
                        return f"On {want_date.strftime('%A %B')} the {p.ordinal(want_date.day)} we are closed.\n\n" \
                            f"Do you need help with anything else?"
                    return f"On {want_date.strftime('%A %B')} the {p.ordinal(want_date.day)} we are open" \
                        f" {format_hours(hours)}.\n\nDo you need help with anything else?"

        days = [("Monday", "Monday", opening_hours_defs["monday"]),
                ("Tuesday", "Tuesday", opening_hours_defs["tuesday"]),
                ("Wednesday", "Wednesday", opening_hours_defs["wednesday"]),
                ("Thursday", "Thursday", opening_hours_defs["thursday"]),
                ("Friday", "Friday", opening_hours_defs["friday"]),
                ("Saturday", "Saturday", opening_hours_defs["saturday"]),
                ("Sunday", "Sunday", opening_hours_defs["sunday"])]

        future_overrides = models.OpeningHoursOverride.objects.filter(
            day__gt=datetime.date.today(), day__lte=datetime.date.today() + datetime.timedelta(weeks=2))

        if want_date_period is not None and want_date_period != "":
            want_date_start = dateutil.parser.parse(want_date_period["startDate"]).date()
            want_date_end = dateutil.parser.parse(want_date_period["endDate"]).date()

            days_in_period = {days[want_date_start.weekday()]}
            day_ids_in_period = {want_date_start.weekday()}
            cur_date = want_date_start
            while cur_date != want_date_end:
                cur_date += datetime.timedelta(days=1)
                days_in_period.add(days[cur_date.weekday()])
                day_ids_in_period.add(cur_date.weekday())

            days_in_period = reduce_days(list(days_in_period))
            days_in_period = map(format_day, days_in_period)
            days = "\n".join(days_in_period)

            future_overrides = filter(lambda f: f.day.weekday() in day_ids_in_period, future_overrides)
            future_overrides_txt = map(lambda d: f"\nOn {d.day.strftime('%A %B')} the {p.ordinal(d.day.day)} we will be"
            f" {'closed' if d.closed else f'open {format_hours(d)}'}", future_overrides)
            future_overrides_txt = "".join(future_overrides_txt)

            return f"Our opening hours are:\n{days}{future_overrides_txt}\n\nDo you need help with anything else?"

        days = reduce_days(days)
        days = map(format_day, days)
        days = "\n".join(days)

        future_overrides_txt = map(lambda d: f"\nOn {d.day.strftime('%A %B')} the {p.ordinal(d.day.day)} we will be"
        f" {'closed' if d.closed else f'open {format_hours(d)}'}", future_overrides)
        future_overrides_txt = "".join(future_overrides_txt)
        return f"Our opening hours are:\n{days}{future_overrides_txt}\n\nDo you need help with anything else?"

    return {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        inner()
                    ]
                },
            },
            {
                "quickReplies": {
                    "quickReplies": [
                        "Yes",
                        "No",
                    ]
                }
            },
        ],
    }


def contact_email(params, text: str, *_):
    contact_details = models.ContactDetails.objects.get()

    return {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        text.replace("$email", contact_details.email)
                    ]
                },
            },
            {
                "quickReplies": {
                    "quickReplies": [
                        "Yes",
                        "No",
                    ]
                }
            },
        ],
    }


def contact_phone(params, text: str, *_):
    contact_details = models.ContactDetails.objects.get()

    return {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        text.replace("$phone", contact_details.phone_number.as_national)
                    ]
                },
            },
            {
                "quickReplies": {
                    "quickReplies": [
                        "Yes",
                        "No",
                    ]
                }
            },
        ],
    }


def contact(params, text: str, *_):
    contact_details = models.ContactDetails.objects.get()

    return {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        text.replace("$phone", contact_details.phone_number.as_national)
                            .replace("$email", contact_details.email)
                    ]
                },
            },
            {
                "quickReplies": {
                    "quickReplies": [
                        "Yes",
                        "No",
                    ]
                }
            },
        ],
    }


def location(params, text: str, *_):
    contact_details = models.ContactDetails.objects.get()

    return {
        "fulfillmentMessages": [
            {
                "text": {
                    "text": [
                        text.replace("$link", contact_details.maps_link)
                    ]
                },
            },
            {
                "quickReplies": {
                    "quickReplies": [
                        "Yes",
                        "No",
                    ]
                }
            },
        ],
    }


def repair(params, _, data):
    brand = params.get("brand")
    model = params.get("iphone-model")
    repair_name = params.get("iphone-repair")

    if len(model) != 0 or len(repair_name) != 0:
        brand = "iPhone"

    if brand is not None and len(brand) != 0:
        if brand == "iPhone":
            if model is not None and repair_name is not None:
                text_out = ["Yes we do fix iPhones"]

                filled = False

                if len(model) == 0:
                    text_out.append("What model is it?")
                elif len(repair_name) == 0:
                    text_out.append("What needs fixing?")
                else:
                    filled = True

                if not filled:
                    session = data.get("session")
                    out = {
                        "fulfillmentMessages": [
                            {
                                "text": {
                                    "text": text_out
                                },
                            }
                        ],
                        "outputContexts": [
                            {
                                "name": f"{session}/contexts/repair",
                                "lifespanCount": 2,
                                "parameters": {
                                    "iphone-model": model,
                                    "iphone-repair": repair_name
                                }
                            }
                        ],

                    }

                if filled:
                    return repair_iphone(params)

                return out

    return {
        "fulfillmentText": "Sorry, we don't fix those"
    }


def repair_iphone(params, *_):
    model = params.get("iphone-model")
    repair_name = params.get("iphone-repair")
    if models is not None and repair_name is not None:
        repair_m = models.IPhoneRepair.objects.filter(name__startswith=model, repair_name=repair_name)

        if len(repair_m) > 0:
            repair_strs = list(map(lambda r: f"A{p.a(f'iPhone {r.name} {repair_name}')[1:]}"
            f" will cost £{r.price}", repair_m))

            return {
                "fulfillmentText": "\n".join(repair_strs)
            }
        else:
            return {
                "fulfillmentText": f"Sorry, but we do not fix iPhone {model} {p.plural(repair_name)}"
            }

    return {}


def rate(params, _, data):
    session = data.get("session")
    session = session.split("/")[-1]
    session_parts = session.split(":")
    if len(session_parts) == 3:
        platform, platform_id, _ = session_parts

        conversation = operator_interface.models.Conversation.objects.get(platform=platform, platform_id=platform_id)

        rating = operator_interface.models.ConversationRating(conversation=conversation, rating=int(params["rating"]))
        rating.save()

    return {}


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


def human_needed(params, text, _):
    if is_open():
        return {
            "fulfillmentText": f"{text}Someone will be here to help you shortly..."
        }
    else:
        return {
            "fulfillmentText": f"{text}We're currently closed but this conversation has been flagged and someone"
            f" will be here to help you as soon as we're open again"
        }


ACTIONS = {
    'support.opening_hours': opening_hours,
    'support.contact': contact,
    'support.contact.phone': contact_phone,
    'support.contact.email': contact_email,
    'support.location': location,
    'repair': repair,
    'repair.iphone': repair_iphone,
    'rate': rate,
    'human_needed': human_needed
}
