import argparse
import asyncio
import datetime
import locale
import logging
import signal

from beartype import beartype
from beartype.typing import Callable
from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from config import Config, TelegramConfig
from crawler import Crawler
from db import Database
from event_trackers import MDTracker
from typeutil import must, safe_must

logging.basicConfig(
    style="{", format="{levelname:8s} [{asctime}] {name}: {message}"
)

OLD_MESSAGE_CUTOFF = datetime.timedelta(days=7)

logger = logging.getLogger()

logger.setLevel(logging.INFO)


class BackgroundTaskManager:
    def __init__(self):
        self.tasks = set()

    def run(self, coro: Callable, *args, **kwargs):
        task = asyncio.create_task(coro(*args, **kwargs))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def cancel_tasks(self):
        for task in self.tasks:
            task.cancel()
        self.tasks.clear()


@beartype
async def periodic(
    interval: int | float, fn: Callable, *args, **kwargs
):
    while True:
        await asyncio.gather(
            fn(*args, **kwargs), asyncio.sleep(interval)
        )


@beartype
class BotManager:
    def __init__(
        self,
        config: Config,
        db: Database,
        crawler: Crawler,
        bg: BackgroundTaskManager | None = None,
    ):
        self.config = config.telegram
        self.calendar_groups = config.calendar_groups
        self.app: Application | None = None
        self.db = db
        self.crawler = crawler
        self.bg = bg or BackgroundTaskManager()

    async def update_message(self, chat_id: int, message: str):
        bot: Bot = must(self.app).bot
        latest_pinned = await self.db.get_latest_tracked_message(
            chat_id
        )
        if latest_pinned:
            age = datetime.datetime.now() - latest_pinned.create_time
            if age > OLD_MESSAGE_CUTOFF:
                await self.db.delete_message(
                    chat_id, latest_pinned.message_id
                )
            else:
                try:
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=latest_pinned.message_id,
                            text=message,
                            parse_mode="Markdown",
                        )
                    except TelegramError as e:
                        if "exactly the same" in e.message:
                            logger.info(
                                f"Message in chat {chat_id} is exactly the same, skipping update."
                            )
                        else:
                            raise
                    await self.db.update_message(
                        chat_id, latest_pinned.message_id
                    )
                    return
                except Exception as e:
                    logger.error(
                        f"Failed to update message in chat {chat_id}: {e}"
                    )
                    await self.db.delete_message(
                        chat_id, latest_pinned.message_id
                    )
                    latest_pinned = None
        msg = await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode="Markdown",
            disable_notification=True,
        )
        pinned = False
        try:
            await bot.pin_chat_message(
                chat_id=chat_id, message_id=msg.message_id
            )
            pinned = True
        except Exception as e:
            logger.warning(
                f"Failed to pin message in chat {chat_id}: {e}"
            )
        await self.db.add_tracked_message(
            chat_id, msg.message_id, pinned=pinned
        )

    async def sync_chat(self, chat_id: int):
        calendars = await self.db.get_calendars_for_chat(chat_id)
        tracker = MDTracker(self.crawler.config.markdown)
        async for event in self.crawler.process_calendars(calendars):
            tracker.track_event(event)
        message = tracker.generate_markdown()
        message_suffix = f"\nGenerated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        await self.update_message(chat_id, message + message_suffix)

    async def sync_full(self):
        chat_ids = await self.db.list_all_chats()
        await asyncio.gather(
            *[self.sync_chat(chat_id) for chat_id in chat_ids]
        )

    async def command_start(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        await context.bot.send_message(
            chat_id=safe_must(
                update.effective_chat, "update.effective_chat"
            ).id,
            text=(
                self.config.welcome_message
                or "I'm a bot, please talk to me!"
            ),
        )

    async def command_add_calendar_group(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat = safe_must(update.effective_chat, "update.effective_chat")

        if not (
            chat.id in self.config.chat_ids
            or str(chat.id) in self.config.chat_ids
        ):
            await context.bot.send_message(
                chat_id=chat.id,
                text="You are not authorized to add calendar groups.",
            )
            return

        if not context.args or len(context.args) < 1:
            await context.bot.send_message(
                chat_id=chat.id,
                text="Usage: /add_calendar_group <group_name>",
            )
            return

        await self.db.touch_chat(chat.id)

        group_name = context.args[0]

        if group_name not in self.calendar_groups:
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"Calendar group '{group_name}' does not exist.",
            )
            return

        calendars = self.calendar_groups[group_name]
        for cal in calendars:
            await self.db.add_calendar(chat.id, cal)

        await context.bot.send_message(
            chat_id=chat.id,
            text=f"Added calendar group '{group_name}' with {len(calendars)} calendars.",
        )

        await self.sync_chat(chat.id)

    async def command_clear_group(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat = safe_must(update.effective_chat, "update.effective_chat")

        if not (
            chat.id in self.config.chat_ids
            or str(chat.id) in self.config.chat_ids
        ):
            await context.bot.send_message(
                chat_id=chat.id,
                text="You are not authorized to clear calendar groups.",
            )
            return

        await self.db.clear_calendars_for_chat(chat.id)

        await context.bot.send_message(
            chat_id=chat.id,
            text="Cleared all calendars for this chat.",
        )

    async def command_get_id(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        chat = safe_must(update.effective_chat, "update.effective_chat")
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"Your chat ID is `{chat.id}`",
            parse_mode="Markdown",
        )

    def prepare(self):
        self.app = (
            ApplicationBuilder().token(self.config.api_token).build()
        )
        self.app.add_handlers(
            [
                CommandHandler("start", self.command_start),
                CommandHandler("get_id", self.command_get_id),
                CommandHandler(
                    "add_calendar_group",
                    self.command_add_calendar_group,
                ),
            ]
        )

    async def start(self):
        await self.db.connect()

        app = must(self.app)
        await app.initialize()
        await app.start()
        await must(app.updater).start_polling()

        self.bg.run(
            periodic, self.crawler.config.crawl_every, self.sync_full
        )

    async def stop(self):
        self.bg.cancel_tasks()

        app = must(self.app)
        await must(app.updater).stop()
        await app.stop()
        await app.shutdown()

        await self.db.close()

        await self.crawler.close()


@beartype
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
    args = parser.parse_args()

    print(f"Using config file: {args.config}")
    config = Config.from_file(args.config)
    locale.setlocale(locale.LC_TIME, config.locale)

    db = Database(config.db_path)
    crawler = Crawler(config.crawler)

    telegram = BotManager(config, db, crawler)
    telegram.prepare()

    # Signal handling for graceful shutdown
    stop_event = asyncio.Event()

    def handle_signal():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await telegram.start()

    print("Bot is running. Press Ctrl+C to stop.")

    await stop_event.wait()

    print("Shutting down...")

    await telegram.stop()


if __name__ == "__main__":
    asyncio.run(main())
