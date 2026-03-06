Knowsee: A bot for displaying calendars
========================

Knowsee fetches events and tasks from multiple sources and posts a
Markdown summary to Telegram chats.

Supported source types:

- `ical`: regular iCalendar feeds
- `vikunja`: Vikunja tasks API
- `donetick`: Donetick chores API (`/eapi/v1/chore` with `secretkey`)

Use `config.sample.yaml` as the reference for setup. To enable task
sources, add a calendar group item with `type: vikunja` or
`type: donetick`, and configure credentials under `vikunja:` and
`donetick:` sections.

