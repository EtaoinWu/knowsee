import aiohttp
import icalendar
import recurring_ical_events

from config import Config
from event_trackers import EventTracker


class Downloader:
    def __init__(self):
        self.session = aiohttp.ClientSession()

    async def fetch(self, url: str, fix_apple: bool = False):
        async with self.session.get(url) as response:
            if response.status != 200:
                raise ConnectionError("Failed to fetch calendar data")
            content_type = response.headers.get("Content-Type", "")
            try:
                encoding = content_type.split("charset=")[1]
            except IndexError:
                encoding = "utf-8"

            content = await response.text(encoding=encoding, errors="ignore")
            content = content.replace("\r", "")

            if fix_apple:
                content = content.replace(
                    "TZOFFSETFROM:+5328", "TZOFFSETFROM:+0053"
                )

            return content

    async def close(self):
        await self.session.close()


class Crawler:
    def __init__(
        self,
        config: Config,
        event_trackers: list[EventTracker] = [],
        downloader: Downloader | None = None,
    ):
        self.config = config
        self.event_trackers = event_trackers
        self.downloader = downloader or Downloader()

    async def process_calendars(self, start_date, end_date):
        for cal in self.config.calendars:
            print(f"Processing calendar: {cal.name}")

            try:
                cal_data = await self.downloader.fetch(
                    cal.url, fix_apple=cal.icloud
                )
            except ConnectionError as e:
                print(f"Error fetching calendar data: {e}")
                continue

            ical = icalendar.Calendar.from_ical(cal_data)
            events = recurring_ical_events.of(ical)
            for event in events.between(start_date, end_date):
                if not isinstance(event, icalendar.Event):
                    raise ValueError(
                        f"{event.get('SUMMARY')} is not an Event"
                    )
                for tracker in self.event_trackers:
                    tracker.track_event(event)

    async def close(self):
        await self.downloader.close()
