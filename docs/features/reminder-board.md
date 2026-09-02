# Bushido Reminder Board

The Reminder Board is Shogun's operational short-term memory for unresolved future work, as well as a durable scheduler for explicit user reminders. It is intentionally separate from Archives, which store knowledge, and AgentFlow, which owns multi-step or tool-using work.

Items show their origin (`ai`, `user`, or `system`), operational type, owner, review time, rationale, confidence, source message, and optional expiry. Shogun can create, list, resolve, and snooze its own obligations through governed native tools, with duplicate suppression for matching unresolved items.

An AI-owned one-time item becomes `due` after its notification and stays visible until Shogun or the operator resolves or reschedules it. A user reminder retains fire-and-complete behavior.

## Scope

- One-time, daily, weekday, weekly, and minute/hour interval reminders
- UTC timestamp storage with IANA timezones for calendar recurrence
- User, tenant, agent, conversation, and topic ownership fields
- In-app, Telegram, or combined in-app and Telegram delivery
- Pause, resume, ten-minute-or-custom snooze, complete, and cancel actions
- Durable occurrence history and duplicate-worker claim protection
- Deterministic parsing for common phrases such as `tomorrow at 9`, `in 30 minutes`, `every weekday at 7:30`, `every Monday`, and `every 30 minutes`
- Read-only visibility of existing AgentFlow schedules in the Bushido UI
- Prompt injection of a compact list of unresolved obligations on every Mission Mode turn
- AI-owned obligations, follow-ups, checks, and deferred work with rationale and expiry

External checks, conditional watches, autonomous tool actions, and AgentFlow triggering remain separate governed capabilities. A board item records the obligation; it does not itself authorize or execute external work.

## UI

Open **Bushido** and use **Reminder Board**. Filter the board by AI, user, or system origin. The creation form always creates an explicit user reminder; AI and system origins are reserved for governed internal tools. The AgentFlows view reflects schedules owned by AgentFlow and does not copy or edit them.

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
