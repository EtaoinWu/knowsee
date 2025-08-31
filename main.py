import argparse
import asyncio
import datetime

from config import Config
from crawler import Crawler
from event_trackers import MDTracker


async def main():
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
        help="Number of days before today (default: 0)",
    )
    parser.add_argument(
        "--days-plus",
        type=int,
        default=7,
        help="Number of days after today (default: 7)",
    )
    args = parser.parse_args()

    print(f"Days minus: {args.days_minus}, Days plus: {args.days_plus}")
    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=args.days_minus)
    end_date = today + datetime.timedelta(days=args.days_plus)

    print(f"Using config file: {args.config}")
    config = Config.from_file(args.config)

    md_tracker = MDTracker(config.markdown)

    crawler = Crawler(config, [md_tracker])
    await crawler.process_calendars(start_date, end_date)

    print(md_tracker.generate_markdown())
    print(md_tracker.generate_json())

    await crawler.close()


if __name__ == "__main__":
    asyncio.run(main())
