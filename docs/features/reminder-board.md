# Bushido Reminder Board

The Reminder Board is Shogun's durable scheduler for lightweight L0 reminders. It is intentionally separate from AgentFlow: reminders deliver a message, while multi-step or tool-using work remains an AgentFlow responsibility.

## First-release scope

- One-time, daily, weekday, weekly, and minute/hour interval reminders
- UTC timestamp storage with IANA timezones for calendar recurrence
- User, tenant, agent, conversation, and topic ownership fields
- In-app, Telegram, Teams, or combined delivery
- Pause, resume, ten-minute-or-custom snooze, complete, and cancel actions
- Durable occurrence history and duplicate-worker claim protection
- Deterministic parsing for common phrases such as `tomorrow at 9`, `in 30 minutes`, `every weekday at 7:30`, `every Monday`, and `every 30 minutes`
- Read-only visibility of existing AgentFlow schedules in the Bushido UI

External checks, conditional watches, autonomous tool actions, shared team boards, and AgentFlow triggering are deliberately excluded from this L0 release. They require Gensui policy evaluation and stronger identity enforcement before enablement.

## UI

Open **Bushido** and use **Reminder Board**. The Reminders view creates and manages lightweight reminders. The AgentFlows view reflects schedules owned by AgentFlow and does not copy or edit them.

## API

All endpoints use the `/api/v1/bushido` prefix:

- `GET/POST /reminders`
- `GET/PATCH /reminders/{task_id}`
- `POST /reminders/{task_id}/pause`
- `POST /reminders/{task_id}/resume`
- `POST /reminders/{task_id}/snooze`
- `POST /reminders/{task_id}/complete`
- `POST /reminders/{task_id}/cancel`
- `GET /reminders/{task_id}/runs`
- `POST /reminders/parse`

The create payload defaults to tenant `local`, user `local_user`, timezone `UTC`, and in-app delivery. Channel adapters use `conversation_id` and Telegram's optional numeric `topic_id` when supplied.

## Runtime behavior

APScheduler invokes a database due scanner once per minute. A conditional database update claims each due task for five minutes, so overlapping workers cannot both deliver it. Each claimed occurrence creates an `agent_scheduled_task_runs` record. Recurring reminders skip stale occurrences after downtime and schedule the next future occurrence; one-time reminders are delivered once and completed.

Delivery failures are retained in run history. The current release does not automatically retry failed external delivery.
