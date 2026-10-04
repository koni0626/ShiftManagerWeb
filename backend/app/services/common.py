from datetime import date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo


def today():
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()


def encode(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, Decimal):
        return float(value)
    return value


def dto(row, fields=None):
    return {
        key: encode(getattr(row, key))
        for key in (fields or row.__table__.columns.keys())
    }


def active_membership(row, day):
    return row.valid_from <= day and (row.valid_until is None or day <= row.valid_until)
