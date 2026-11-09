import datetime


class SystemClock:
    """Local time (the container's TZ)."""

    def now(self) -> datetime.datetime:
        return datetime.datetime.now().astimezone()
