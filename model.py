# model.py

import dataclasses
from datetime import datetime
from typing import Protocol

from beartype import beartype, typing


@beartype
class Calendar:
    def __init__(
        self,
        type: str,
        url: str,
        name: str,
        color: str,
        icloud: bool | None = None,
    ):
        if type not in ["ical", "vikunja", "donetick"]:
            raise ValueError(f"Unsupported calendar type: {type}")
        if type == "ical" and not url:
            raise ValueError("ical type requires a url")
        self.type = type
        self.url = url
        self.name = name
        self.color = color
        self.icloud = icloud or False

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            type=data["type"],
            name=data["name"],
            url=data.get("url", ""),
            color=data.get("color", "#cccccc"),
            icloud=data.get("icloud"),
        )


@dataclasses.dataclass
class TrackedMsg:
    chat_id: int
    message_id: int
    pinned: bool
    create_time: datetime
    update_time: datetime


@beartype
@dataclasses.dataclass
class VikunjaTask:
    title: str
    due_date: str | None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            title=data.get("title", "Untitled Task"),
            due_date=data.get("due_date"),
        )


@beartype
@dataclasses.dataclass
class DonetickTask:
    title: str
    due_date: str | None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            title=data.get("name", "Untitled Task"),
            due_date=data.get("nextDueDate"),
        )


@beartype
@typing.runtime_checkable
class TaskLike(Protocol):
    title: str
    due_date: str | None


@beartype
@dataclasses.dataclass
class DisplayEvent:
    start: datetime
    end: datetime
    title: str
    all_day: bool
    overdue: bool = False
