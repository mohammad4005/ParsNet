import jdatetime
from django import template

register = template.Library()


@register.filter
def jalali(value, date_format="%Y/%m/%d"):
    """Render a Gregorian date or datetime in the Persian calendar."""
    if not value:
        return "—"
    try:
        return jdatetime.date.fromgregorian(date=value.date() if hasattr(value, "date") else value).strftime(date_format)
    except (TypeError, ValueError, AttributeError):
        return value


@register.filter
def jalali_datetime(value):
    if not value:
        return "—"
    try:
        return jdatetime.datetime.fromgregorian(datetime=value).strftime("%Y/%m/%d · %H:%M")
    except (TypeError, ValueError, AttributeError):
        return value
