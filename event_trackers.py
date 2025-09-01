import abc
import dataclasses
import datetime
import json
from typing import Self, cast, override

import icalendar
from beartype import beartype
from dateutil.relativedelta import relativedelta

from config import MarkdownFormatConfig

EventType = icalendar.Event


class EventTracker(abc.ABC):
    @abc.abstractmethod
    def track_event(self, event: EventType) -> Self:
        ...

    def track_events(self, events: list[EventType]) -> Self:
        for event in events:
            self = self.track_event(event)
        return self

    @abc.abstractmethod
    def clear(self) -> Self:
        ...


@beartype
class PrintTracker(EventTracker):
    @override
    def track_event(self, event: EventType) -> Self:
        print(
            f"{event.get('SUMMARY', '')}, at {event.get('DTSTART', '')}"
        )
        return self

    @override
    def clear(self) -> Self:
        return self


@beartype
def vdd_to_datetime(
    dt: datetime.datetime
    | datetime.date
    | datetime.timedelta
    | datetime.time,
) -> datetime.datetime | None:
    if isinstance(dt, datetime.datetime):
        return dt
    elif isinstance(dt, datetime.date):
        return datetime.datetime.combine(dt, datetime.time.min)
    else:
        return None


@beartype
@dataclasses.dataclass
class EventMD:
    start: datetime.datetime
    end: datetime.datetime
    title: str
    allDay: bool


@beartype
class MDTracker(EventTracker):
    def __init__(self, cfg: MarkdownFormatConfig):
        self.events: list[EventMD] = []
        self.cfg = cfg

    @override
    def track_event(self, event: EventType) -> Self:
        dtstart = event.get("DTSTART")
        dtend = event.get("DTEND")
        title = event.get("SUMMARY", "")

        if not isinstance(dtstart, icalendar.vDDDTypes):
            raise TypeError(f"DTSTART of {title} is not a vDDDTypes")

        if not isinstance(dtend, icalendar.vDDDTypes):
            raise TypeError(f"DTEND of {title} is not a vDDDTypes")

        if dtstart.params.get("VALUE") == "DATE":
            # is a full day event
            start = vdd_to_datetime(dtstart.dt)  # type: ignore
            end = vdd_to_datetime(dtend.dt)  # type: ignore
            if start is None:
                raise TypeError(f"DTSTART of {title} is not a date")
            if end is None:
                end = start + relativedelta(days=1)
            self.events.append(
                EventMD(start=start, end=end, title=title, allDay=True)
            )
        else:
            if dtstart.params.get("VALUE") is not None:
                raise TypeError(
                    f"DTSTART of {title} is not a date or time"
                )
            start = cast(datetime.datetime, dtstart.dt)
            end = cast(datetime.datetime, dtend.dt)
            self.events.append(
                EventMD(start=start, end=end, title=title, allDay=False)
            )

        return self

    def generate_markdown(self) -> str:
        date_maps: dict[
            datetime.date,
            list[EventMD],
        ] = {}
        for event in self.events:
            date = event.start.date()

            if date not in date_maps:
                date_maps[date] = []
            date_maps[date].append(event)

        markdown = []
        for date, events in sorted(date_maps.items()):
            date_str = date.strftime(self.cfg.date_format)
            all_day = [event for event in events if event.allDay]
            timed = [event for event in events if not event.allDay]
            timed.sort(key=lambda e: e.start)

            markdown.append(f"**{date_str}**")
            for event in all_day:
                markdown.append(f"*All day*: {event.title}")
            for event in timed:
                start = event.start.strftime(self.cfg.time_format)
                end = event.end.strftime(self.cfg.time_format)
                markdown.append(f"*{start} - {end}*: {event.title}")
            markdown.append("")

        return "\n".join(markdown)

    def generate_dict(self) -> list[dict]:
        return [
            {
                "title": event.title,
                "start": event.start.isoformat(),
                "end": event.end.isoformat(),
                "allDay": event.allDay,
            }
            for event in self.events
        ]

    def generate_json(self) -> str:
        return json.dumps(self.generate_dict(), indent=2)

    @override
    def clear(self):
        self.events.clear()
