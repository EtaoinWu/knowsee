# crawler.py

import datetime
import logging
from collections.abc import AsyncGenerator

import aiohttp
import icalendar
import recurring_ical_events
from beartype import beartype
from dateutil.parser import isoparse
from dateutil.relativedelta import relativedelta

from config import CrawlerConfig, DonetickConfig, VikunjaConfig
from model import Calendar, DonetickTask, VikunjaTask

# Set up module-level logger
logger = logging.getLogger(__name__)


@beartype
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

            content = await response.text(
                encoding=encoding, errors="ignore"
            )
            content = content.replace("\r", "")

            if fix_apple:
                content = content.replace(
                    "TZOFFSETFROM:+5328", "TZOFFSETFROM:+0053"
                )

            return content
            
    async def fetch_json(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        source_name: str = "JSON API",
    ) -> list[dict]:
        headers = headers or {}
        params = params or {}
        async with self.session.get(url, headers=headers, params=params) as response:
            if response.status != 200:
                text = await response.text()
                logger.error(
                    "Failed to fetch %s. Status: %s, Body: %s",
                    source_name,
                    response.status,
                    text,
                )
                raise ConnectionError(f"Failed to fetch {source_name}")
            return await response.json()

    async def close(self):
        await self.session.close()


@beartype
class VikunjaFetcher:
    def __init__(self, config: VikunjaConfig, downloader: Downloader):
        self.config = config
        self.downloader = downloader

    async def fetch_tasks(self, days_forward: int) -> list[VikunjaTask]:
        # This filter gets tasks that are not done AND are due anytime
        # up to `days_forward` from now. This includes overdue tasks.
        filter_query = f'done = false && (due_date <= now/d+{days_forward}d)'
        
        url = f"{self.config.base_url}/api/v1/tasks/all"
        headers = {"Authorization": f"Bearer {self.config.api_token}"}
        params = {"filter": filter_query}

        try:
            tasks_data = await self.downloader.fetch_json(
                url,
                headers=headers,
                params=params,
                source_name="Vikunja tasks",
            )
            return [VikunjaTask.from_dict(task) for task in tasks_data]
        except Exception as e:
            logger.error(f"Error fetching Vikunja tasks: {e}")
            return []


@beartype
class DonetickFetcher:
    def __init__(self, config: DonetickConfig, downloader: Downloader):
        self.config = config
        self.downloader = downloader

    async def fetch_tasks(self, days_forward: int) -> list[DonetickTask]:
        url = f"{self.config.base_url}/eapi/v1/chore"
        headers = {"secretkey": self.config.secret_key}

        try:
            chores_data = await self.downloader.fetch_json(
                url,
                headers=headers,
                source_name="Donetick chores",
            )
        except Exception as e:
            logger.error(f"Error fetching Donetick chores: {e}")
            return []

        cutoff = datetime.datetime.now(
            datetime.UTC
        ) + relativedelta(days=days_forward)
        tasks: list[DonetickTask] = []

        for chore in chores_data:
            if not chore.get("isActive", True):
                continue

            status = chore.get("status")
            if status is not None and status != 0:
                continue

            task = DonetickTask.from_dict(chore)
            if not task.due_date:
                continue

            try:
                due_dt = isoparse(task.due_date)
            except ValueError:
                logger.warning(
                    "Skipping Donetick task with invalid due date: %s",
                    task.title,
                )
                continue

            if due_dt.tzinfo is None:
                due_dt = due_dt.replace(tzinfo=datetime.UTC)

            if due_dt <= cutoff:
                tasks.append(task)

        return tasks


@beartype
class Crawler:
    def __init__(
        self,
        config: CrawlerConfig,
        downloader: Downloader | None = None,
    ):
        self.config = config
        self.downloader = downloader or Downloader()

    async def process_calendars(
        self,
        calendar_configs: list[Calendar],
    ) -> AsyncGenerator[icalendar.Event]:
        today = datetime.date.today()
        # Ensure date ranges are handled correctly regardless of +/- signs
        start_date = today + relativedelta(days=self.config.date_range[0])
        end_date = today + relativedelta(days=self.config.date_range[1])
        
        for cal in calendar_configs:
            logger.info(f"Processing calendar: {cal.name}")

            try:
                cal_data = await self.downloader.fetch(
                    cal.url, fix_apple=cal.icloud
                )
            except ConnectionError as e:
                logger.error(f"Error fetching calendar data: {e}")
                continue

            ical = icalendar.Calendar.from_ical(cal_data)
            events = recurring_ical_events.of(ical)
            for event in events.between(start_date, end_date):
                if not isinstance(event, icalendar.Event):
                    raise ValueError(
                        f"{event.get('SUMMARY')} is not an Event"
                    )
                yield event

    async def close(self):
        await self.downloader.close()
