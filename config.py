# config.py

import dataclasses

import yaml
from beartype import beartype

from model import Calendar


@beartype
@dataclasses.dataclass
class MarkdownFormatConfig:
    date_format: str
    time_format: str
    overdue_title: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            date_format=data.get("date_format", "%Y-%m-%d"),
            time_format=data.get("time_format", "%H:%M"),
            overdue_title=data.get("overdue_title", "**🚨 Overdue Tasks**"),
        )


@beartype
@dataclasses.dataclass
class VikunjaConfig:
    base_url: str
    api_token: str

    @classmethod
    def from_dict(cls, data: dict):
        base_url = data.get("base_url", "")
        api_token = data.get("api_token", "")
        return cls(base_url=base_url, api_token=api_token)


@beartype
@dataclasses.dataclass
class TelegramConfig:
    api_token: str
    chat_ids: list[str | int]
    welcome_message: str | None

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            api_token=data.get("api_token", ""),
            chat_ids=data.get("chat_ids", []),
            welcome_message=data.get("welcome_message"),
        )


@beartype
@dataclasses.dataclass
class CrawlerConfig:
    crawl_every: int | float
    date_range: tuple[int, int]
    markdown: MarkdownFormatConfig

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            crawl_every=data.get("crawl_every", 300),
            date_range=tuple(data.get("date_range", [0, 6])),
            markdown=MarkdownFormatConfig.from_dict(data.get("markdown", {})),
        )


@beartype
@dataclasses.dataclass
class Config:
    locale: str | None
    timezone: str
    db_path: str
    calendar_groups: dict[str, list[Calendar]]
    crawler: CrawlerConfig
    telegram: TelegramConfig
    vikunja: VikunjaConfig
    image_urls: dict[str, str] = dataclasses.field(default_factory=dict)

    @classmethod
    def from_yaml(cls, yaml_str: str):
        data = yaml.safe_load(yaml_str)
        locale = data.get("locale")
        timezone = data.get("timezone", "UTC") # Default to UTC if not set
        db_path = data.get("db_path", "database.db")
        calendar_groups = {
            group_name: [Calendar.from_dict(item) for item in group]
            for group_name, group in data.get("calendar_groups", {}).items()
        }
        image_urls = data.get("image_urls", {})
        
        if "crawler" in data:
            crawler = CrawlerConfig.from_dict(data["crawler"])
        else:
            crawler = CrawlerConfig(
                crawl_every=data.get("crawl_every", 300),
                date_range=tuple(data.get("date_range", [0, 6])),
                markdown=MarkdownFormatConfig.from_dict(data.get("markdown", {})),
            )
        telegram = TelegramConfig.from_dict(data.get("telegram", {}))
        vikunja = VikunjaConfig.from_dict(data.get("vikunja", {}))

        return cls(
            locale=locale,
            timezone=timezone,
            db_path=db_path,
            calendar_groups=calendar_groups,
            crawler=crawler,
            telegram=telegram,
            vikunja=vikunja,
            image_urls=image_urls,
        )

    @classmethod
    def from_file(cls, path: str):
        with open(path) as f:
            return cls.from_yaml(f.read())
