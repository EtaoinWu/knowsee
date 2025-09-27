# event_trackers.py

import abc
import dataclasses
import datetime
import json
import logging
import zoneinfo
from typing import Self, cast, override

import icalendar
from beartype import beartype
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta

from config import MarkdownFormatConfig
from model import DisplayEvent, VikunjaTask

EventType = icalendar.Event
logger = logging.getLogger(__name__)


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
class MDTracker(EventTracker):
    def __init__(self, cfg: MarkdownFormatConfig, timezone: str = "UTC"):
        self.events: list[DisplayEvent] = []
        self.cfg = cfg
        try:
            self.tz = zoneinfo.ZoneInfo(timezone)
        except zoneinfo.ZoneInfoNotFoundError:
            logger.error(f"Timezone '{timezone}' not found. Defaulting to UTC.")
            self.tz = zoneinfo.ZoneInfo("UTC")
    
    def _normalize_datetime(self, dt: datetime.datetime) -> datetime.datetime:
        """Converts any datetime to the configured target timezone."""
        if dt.tzinfo is None:
            # If the datetime is naive, assume it's in the target timezone.
            return dt.replace(tzinfo=self.tz)
        else:
            # If it's aware, convert it to the target timezone.
            return dt.astimezone(self.tz)

    @override
    def track_event(self, event: EventType) -> Self:
        dtstart = event.get("DTSTART")
        dtend = event.get("DTEND")
        title = str(event.get("SUMMARY", ""))

        if not isinstance(dtstart, icalendar.vDDDTypes):
            raise TypeError(f"DTSTART of {title} is not a vDDDTypes")
        if not isinstance(dtend, icalendar.vDDDTypes):
            raise TypeError(f"DTEND of {title} is not a vDDDTypes")

        start_dt = vdd_to_datetime(dtstart.dt)
        end_dt = vdd_to_datetime(dtend.dt)
        if start_dt is None:
            raise TypeError(f"DTSTART of {title} is invalid")

        all_day = not isinstance(dtstart.dt, datetime.datetime)
        if end_dt is None:
            end_dt = start_dt + (relativedelta(days=1) if all_day else relativedelta(hours=1))

        # Normalize both start and end times to the configured timezone
        final_start = self._normalize_datetime(start_dt)
        final_end = self._normalize_datetime(end_dt)

        print(title, final_start, final_end, all_day)

        self.events.append(
            DisplayEvent(start=final_start, end=final_end, title=title, all_day=all_day)
        )
        return self

    def track_task(self, task: VikunjaTask) -> Self:
        if not task.due_date:
            return self

        # Parse the ISO string, which will be timezone-aware (likely UTC)
        due_aware = isoparse(task.due_date)
        
        # Convert the due date to the configured local timezone
        due_local = due_aware.astimezone(self.tz)
        
        # Get the current time in the same timezone for an accurate comparison
        now_local = datetime.datetime.now(self.tz)
        
        is_overdue = due_local < now_local

        self.events.append(
            DisplayEvent(
                start=due_local,
                end=due_local,
                title=task.title,
                all_day=False, # Tasks are treated as timed events
                overdue=is_overdue
            )
        )
        return self

    def generate_markdown(self) -> str:
        overdue_tasks = sorted(
            [e for e in self.events if e.overdue], key=lambda e: e.start
        )
        scheduled_events = [e for e in self.events if not e.overdue]

        markdown = []

        # Process Overdue Tasks
        if overdue_tasks:
            markdown.append(self.cfg.overdue_title)
            for task in overdue_tasks:
                due_str = task.start.strftime(f"{self.cfg.date_format} {self.cfg.time_format}")
                markdown.append(f"*Due {due_str}*: {task.title}")
            markdown.append("") # Add a blank line for separation

        # Process Scheduled Events
        date_maps: dict[datetime.date, list[DisplayEvent]] = {}
        for event in scheduled_events:
            date = event.start.date()
            if date not in date_maps:
                date_maps[date] = []
            date_maps[date].append(event)

        for date, events in sorted(date_maps.items()):
            date_str = date.strftime(self.cfg.date_format)
            all_day = [event for event in events if event.all_day]
            timed = sorted([event for event in events if not event.all_day], key=lambda e: e.start)

            markdown.append(f"**{date_str}**")
            for event in all_day:
                markdown.append(f"*All day*: {event.title}")
            for event in timed:
                start = event.start.strftime(self.cfg.time_format)
                # For tasks, start and end are the same
                if event.start == event.end:
                    markdown.append(f"*{start}*: {event.title}")
                else:
                    end = event.end.strftime(self.cfg.time_format)
                    markdown.append(f"*{start} - {end}*: {event.title}")
            markdown.append("")

        return "\n".join(markdown)

    @override
    def clear(self) -> Self:
        self.events.clear()
        return self