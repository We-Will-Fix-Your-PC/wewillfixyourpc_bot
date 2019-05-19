import dateutil.parser
import dateutil.relativedelta
import datetime
import typing
from . import models


def opening_hours(params, _):
    def inner():
        def suffix(d):
            return 'th' if 11 <= d <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d % 10, 'th')

        def get_one_or_none(**kwargs):
            query = models.OpeningHours.objects.filter(**kwargs)
            return query[0] if len(query) > 0 else None

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
                        return f"On {want_date.strftime('%A %B the %-d')}{suffix(want_date.day)} we are closed.\n\n" \
                            f"Do you need help with anything else?"
                    return f"On {want_date.strftime('%A %B the %-d')}{suffix(want_date.day)} we are open" \
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
            future_overrides_txt = map(lambda d: f"On {d.day.strftime('%A %B %-d')}{suffix(d.day.day)} we will be"
            f" {'closed' if d.closed else f'open {format_hours(d)}'}", future_overrides)
            future_overrides_txt = "\n".join(future_overrides_txt)

            return f"Our opening hours are:\n{days}\n{future_overrides_txt}.\n\nDo you need help with anything else?"

        days = reduce_days(days)
        days = map(format_day, days)
        days = "\n".join(days)

        future_overrides_txt = map(lambda d: f"On {d.day.strftime('%A %B %-d')}{suffix(d.day.day)} we will be"
        f" {'closed' if d.closed else f'open {format_hours(d)}'}", future_overrides)
        future_overrides_txt = "\n".join(future_overrides_txt)
        return f"Our opening hours are:\n{days}\n{future_overrides_txt}.\n\nDo you need help with anything else?"

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
                },
                "platform": "FACEBOOK"
            },
        ],
    }


def contact_email(_, text: str):
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
                },
                "platform": "FACEBOOK"
            },
        ],
    }


def contact_phone(_, text: str):
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
                },
                "platform": "FACEBOOK"
            },
        ],
    }


def contact(_, text: str):
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
                },
                "platform": "FACEBOOK"
            },
        ],
    }


def location(_, text: str):
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
                },
                "platform": "FACEBOOK"
            },
        ],
    }


ACTIONS = {
    'support.opening_hours': opening_hours,
    'support.contact': contact,
    'support.contact.phone': contact_phone,
    'support.contact.email': contact_email,
    'support.location': location,
}
