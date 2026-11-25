from datetime import date, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")


def get_today() -> date:
    return datetime.now(TZ).date()
