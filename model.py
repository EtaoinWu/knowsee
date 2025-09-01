import dataclasses
from datetime import datetime

from beartype import beartype


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
        if type != "ical":
            raise ValueError(f"Unsupported calendar type: {type}")
        self.type = type
        self.url = url
        self.name = name
        self.color = color
        self.icloud = icloud or False

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            type=data["type"],
            url=data["url"],
            name=data["name"],
            color=data["color"],
            icloud=data.get("icloud"),
        )


@dataclasses.dataclass
class TrackedMsg:
    chat_id: int
    message_id: int
    pinned: bool
    create_time: datetime
    update_time: datetime
