import dataclasses
import yaml


class CalendarConfig:
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
class MarkdownFormatConfig:
    date_format: str
    time_format: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            date_format=data.get("date_format", "%Y-%m-%d"),
            time_format=data.get("time_format", "%H:%M"),
        )


class Config:
    def __init__(
        self,
        calendars: list[CalendarConfig],
        markdown: MarkdownFormatConfig,
    ):
        self.calendars = calendars
        self.markdown = markdown

    @classmethod
    def from_yaml(cls, yaml_str: str):
        data = yaml.safe_load(yaml_str)
        calendars = [
            CalendarConfig.from_dict(item)
            for item in data.get("calendars", [])
        ]
        markdown = MarkdownFormatConfig.from_dict(
            data.get("markdown", {})
        )
        return cls(calendars=calendars, markdown=markdown)

    @classmethod
    def from_file(cls, path: str):
        with open(path, "r") as f:
            return cls.from_yaml(f.read())
