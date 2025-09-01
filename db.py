from sqlite3 import PARSE_DECLTYPES

import aiosqlite

from model import Calendar, TrackedMsg
from typeutil import safe_must


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path, detect_types=PARSE_DECLTYPES)
        await self.conn.execute("PRAGMA foreign_keys = ON;")
        await self._init_db()

    async def close(self):
        conn = safe_must(self.conn, "database connection")
        await conn.close()
        self.conn = None

    async def _init_db(self):
        conn = safe_must(self.conn, "database connection")
        await conn.executescript("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS tracked_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            message_id INTEGER NOT NULL,
            pinned BOOLEAN NOT NULL DEFAULT 0,
            create_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(chat_id, message_id)
        );
        CREATE TABLE IF NOT EXISTS calendars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            type TEXT NOT NULL CHECK(type = 'ical'),
            url TEXT NOT NULL,
            icloud BOOLEAN NOT NULL DEFAULT 0,
            name TEXT NOT NULL,
            color TEXT NOT NULL,
            UNIQUE(chat_id, name)
        );
        """)
        await conn.commit()

    async def touch_chat(self, chat_id: int) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            INSERT OR IGNORE INTO chats (id) VALUES (?)
            """,
            (chat_id,),
        )
        await conn.commit()

    async def list_all_chats(self) -> list[int]:
        conn = safe_must(self.conn, "database connection")
        cursor = await conn.execute("SELECT id FROM chats")
        rows = await cursor.fetchall()
        await cursor.close()
        return [row[0] for row in rows]

    async def get_calendars_for_chat(
        self, chat_id: int
    ) -> list[Calendar]:
        conn = safe_must(self.conn, "database connection")
        cursor = await conn.execute(
            """
            SELECT type, url, name, color, icloud
            FROM calendars
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            Calendar(
                type=row[0],
                url=row[1],
                name=row[2],
                color=row[3],
                icloud=bool(row[4]) if row[4] is not None else False,
            )
            for row in rows
        ]

    async def add_calendar(
        self, chat_id: int, calendar: Calendar
    ) -> None:
        """Add a calendar for a chat using a CalendarConfig object."""
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            INSERT OR IGNORE INTO calendars (chat_id, type, url, name, color, icloud)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                calendar.type,
                calendar.url,
                calendar.name,
                calendar.color,
                int(calendar.icloud)
                if calendar.icloud is not None
                else 0,
            ),
        )
        await conn.commit()

    async def delete_calendar(self, chat_id: int, name: str) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            DELETE FROM calendars
            WHERE chat_id = ? AND name = ?
            """,
            (chat_id, name),
        )
        await conn.commit()

    async def clear_calendars_for_chat(self, chat_id: int) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            DELETE FROM calendars
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        await conn.commit()

    async def add_tracked_message(
        self, chat_id: int, message_id: int, pinned: bool = False
    ) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            INSERT OR IGNORE INTO tracked_messages (chat_id, message_id, pinned)
            VALUES (?, ?, ?)
            """,
            (chat_id, message_id, int(pinned)),
        )
        await conn.commit()

    async def pin_message(
        self, chat_id: int, message_id: int, pinned: bool = True
    ) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            UPDATE tracked_messages
            SET pinned = ?
            WHERE chat_id = ? AND message_id = ?
            """,
            (int(pinned), chat_id, message_id),
        )
        await conn.commit()

    async def update_message(
        self, chat_id: int, message_id: int
    ) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            UPDATE tracked_messages
            SET update_time = CURRENT_TIMESTAMP
            WHERE chat_id = ? AND message_id = ?
            """,
            (chat_id, message_id),
        )
        await conn.commit()

    async def delete_message(
        self, chat_id: int, message_id: int
    ) -> None:
        conn = safe_must(self.conn, "database connection")
        await conn.execute(
            """
            DELETE FROM tracked_messages
            WHERE chat_id = ? AND message_id = ?
            """,
            (chat_id, message_id),
        )
        await conn.commit()

    async def get_latest_tracked_message(
        self, chat_id: int
    ) -> TrackedMsg | None:
        conn = safe_must(self.conn, "database connection")
        cursor = await conn.execute(
            """
            SELECT chat_id, message_id, pinned, create_time, update_time
            FROM tracked_messages
            WHERE chat_id = ?
            ORDER BY create_time DESC
            LIMIT 1
            """,
            (chat_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row:
            return TrackedMsg(
                chat_id=row[0],
                message_id=row[1],
                pinned=bool(row[2]),
                create_time=row[3],
                update_time=row[4],
            )
        return None

    async def get_all_tracked_messages(
        self, chat_id: int
    ) -> list[TrackedMsg]:
        conn = safe_must(self.conn, "database connection")
        cursor = await conn.execute(
            """
            SELECT chat_id, message_id, pinned, create_time, update_time
            FROM tracked_messages
            WHERE chat_id = ?
            ORDER BY create_time DESC
            """,
            (chat_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [
            TrackedMsg(
                chat_id=row[0],
                message_id=row[1],
                pinned=bool(row[2]),
                create_time=row[3],
                update_time=row[4],
            )
            for row in rows
        ]
