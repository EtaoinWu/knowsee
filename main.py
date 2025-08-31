import argparse
import datetime

import icalendar
import recurring_ical_events
import urllib3

from config import Config
from event_trackers import EventTracker, MDTracker


class Downloader:
    def __init__(self, http: urllib3.PoolManager | None = None):
        if http is None:
            http = urllib3.PoolManager()

        self.http = http

    def fetch(self, url: str, fix_apple: bool = False):
        response = self.http.request("GET", url)
        if response.status != 200 or not response.data:
            raise ConnectionError("Failed to fetch calendar data")
        content_type = response.headers.get("Content-Type", "")
        try:
            encoding = content_type.split("charset=")[1]
        except IndexError:
            encoding = "utf-8"

        content = response.data.decode(encoding, errors="ignore")
        content = content.replace("\r", "")

        if fix_apple:
            content = content.replace(
                "TZOFFSETFROM:+5328", "TZOFFSETFROM:+0053"
            )

        return content


def main():
    parser = argparse.ArgumentParser(
        description="Knowsee main entry point."
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--days-minus",
        type=int,
        default=0,
        help="Number of days before (default: 0)",
    )
    parser.add_argument(
        "--days-plus",
        type=int,
        default=7,
        help="Number of days to after (default: 7)",
    )
    args = parser.parse_args()

    print(f"Days minus: {args.days_minus}, Days plus: {args.days_plus}")
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=args.days_minus)
    end_date = today + datetime.timedelta(days=args.days_plus)

    print(f"Using config file: {args.config}")
    config = Config.from_file(args.config)

    downloader = Downloader()
    md_tracker = MDTracker(config.markdown)
    event_trackers: list[EventTracker] = [md_tracker]

    for cal in config.calendars:
        print(f"Processing calendar: {cal.name}")

        try:
            cal_data = downloader.fetch(cal.url, fix_apple=cal.icloud)
        except ConnectionError as e:
            print(f"Error fetching calendar data: {e}")

        ical = icalendar.Calendar.from_ical(cal_data)
        events = recurring_ical_events.of(ical)
        for event in events.between(start_date, end_date):
            if not isinstance(event, icalendar.Event):
                raise ValueError(
                    f"{event.get('SUMMARY')} is not an Event"
                )
            for tracker in event_trackers:
                tracker.track_event(event)

    print(md_tracker.generate_markdown())
    print(md_tracker.generate_json())


if __name__ == "__main__":
    main()
