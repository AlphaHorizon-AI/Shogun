"""Native Skills — Internal system capabilities exposed directly to the Shogun orchestrator LLM."""

import json
import logging
from typing import Any

from fastapi import HTTPException

from shogun.schemas.common import DecayClass

logger = logging.getLogger("shogun.native_skills")

NATIVE_TOOLS = [
    {
        "type": "function",
        "risk": "low",
        "category": "debug",
        "function": {
            "name": "echo_tool",
            "description": "A debug tool that echoes back exactly what you send it. Use this to verify that the tool execution pipeline is working.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to echo back.",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "debug",
        "function": {
            "name": "tool_list_debug",
            "description": "A debug tool that returns a list of all tools available to the current mission context.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "agents",
        "function": {
            "name": "spawn_samurai",
            "description": "Spawn a new Samurai agent in the Dojo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the Samurai agent.",
                    },
                    "role": {
                        "type": "string",
                        "description": "The specific role or designation.",
                    },
                    "persona": {
                        "type": "string",
                        "description": "A brief description of their personality and expertise.",
                    },
                    "security_tier": {
                        "type": "string",
                        "enum": ["shrine", "guarded", "tactical", "campaign", "ronin"],
                        "description": "Security tier for the new Samurai (typically tactical or guarded).",
                    },
                },
                "required": ["name", "role", "persona", "security_tier"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "system",
        "function": {
            "name": "list_available_models",
            "description": "List all active model providers and the models they have available.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "system",
        "function": {
            "name": "update_model_settings",
            "description": "Update Shogun's primary and fallback models. Use when the user requests to switch the core model.",
            "parameters": {
                "type": "object",
                "properties": {
                    "primary_model": {
                        "type": "string",
                        "description": "The fully qualified primary model string (e.g. 'provider-id::model-name'). Use list_available_models if unsure.",
                    },
                    "fallback_models": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of fully qualified models to fall back to.",
                    },
                },
                "required": ["primary_model"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "memory",
        "function": {
            "name": "store_memory",
            "description": (
                "Store durable information in Shogun Archives. Optionally set decay_type to control decay. "
                "Use sticky only for stable, high-confidence preferences, project facts, durable signals, or "
                "operating conventions; never for temporary task state, news, speculation, or claims likely to change."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short descriptive title for this memory (e.g. 'Operator name is Michael').",
                    },
                    "content": {
                        "type": "string",
                        "description": "The full content to remember. Be detailed and specific.",
                    },
                    "memory_type": {
                        "type": "string",
                        "enum": ["episodic", "semantic", "procedural", "persona", "skill"],
                        "description": (
                            "Type: 'persona' for identity/preferences/personal info, 'semantic' for facts/knowledge, "
                            "'episodic' for events, 'procedural' for how-to patterns."
                        ),
                    },
                    "importance": {
                        "type": "number",
                        "description": (
                            "How important this is (0.0-1.0). Use 0.9+ for identity/preferences, "
                            "0.5-0.8 for general facts."
                        ),
                    },
                    "decay_type": {
                        "type": "string",
                        "enum": [item.value for item in DecayClass],
                        "description": (
                            "Optional decay behavior. If omitted or null, the existing importance-based default is "
                            "used. Sticky is governed and reserved for important long-term memories."
                        ),
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional labels used to organize and retrieve this memory.",
                    },
                },
                "required": ["title", "content", "memory_type", "importance"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "memory",
        "function": {
            "name": "reminder_board_add",
            "description": "Record a concrete unresolved future obligation on Shogun's operational Reminder Board. Do not use for ordinary facts or vague ideas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short, action-oriented obligation title."},
                    "description": {"type": "string", "description": "Optional details needed when the item is reviewed."},
                    "item_type": {"type": "string", "enum": ["obligation", "follow_up", "check", "deferred", "reminder"]},
                    "review_at": {"type": "string", "description": "ISO-8601 date/time when this must be reviewed."},
                    "review_in_minutes": {"type": "integer", "minimum": 1, "description": "Relative review time; use instead of review_at."},
                    "reason": {"type": "string", "description": "Why this remains unresolved and belongs on the board."},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "expires_in_hours": {"type": "integer", "minimum": 1, "maximum": 8760},
                    "priority": {"type": "integer", "minimum": 0, "maximum": 100},
                    "source_message_id": {"type": "string"},
                },
                "required": ["title", "reason"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "memory",
        "function": {
            "name": "reminder_board_list",
            "description": "List Shogun's unresolved operational obligations and reminders.",
            "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}},
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "memory",
        "function": {
            "name": "reminder_board_update",
            "description": "Resolve, cancel, pause, resume, or snooze an existing Reminder Board item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "action": {"type": "string", "enum": ["complete", "cancel", "pause", "resume", "snooze"]},
                    "snooze_minutes": {"type": "integer", "minimum": 1, "maximum": 525600},
                },
                "required": ["task_id", "action"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "comms",
        "function": {
            "name": "fetch_inbox",
            "description": "Fetch a list of emails from a mail folder. Returns message summaries with UID, sender, subject, date, and a short body preview. Use this to check the inbox or any folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "The mail folder to fetch from (e.g. 'INBOX', 'Sent', 'Drafts'). Defaults to 'INBOX'.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number for pagination (1-based). Defaults to 1.",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Number of messages per page. Defaults to 10.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "comms",
        "function": {
            "name": "read_email",
            "description": "Read the full contents of a specific email by its UID. Returns the complete body text, HTML, sender, subject, date, and attachments list. Use this after fetch_inbox to read a specific message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "uid": {
                        "type": "string",
                        "description": "The UID of the email message to read (obtained from fetch_inbox results).",
                    },
                    "folder": {
                        "type": "string",
                        "description": "The mail folder the message is in. Defaults to 'INBOX'.",
                    },
                },
                "required": ["uid"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "comms",
        "function": {
            "name": "send_email",
            "description": "Send an email via the configured SMTP account. Use this to compose new emails or reply to messages. For replies, include the original context in the body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_address": {
                        "type": "string",
                        "description": "Recipient email address.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body text (plain text).",
                    },
                    "cc_address": {
                        "type": "string",
                        "description": "Optional CC recipients (comma-separated).",
                    },
                    "bcc_address": {
                        "type": "string",
                        "description": "Optional BCC recipients (comma-separated).",
                    },
                },
                "required": ["to_address", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "comms",
        "function": {
            "name": "send_telegram_message",
            "description": (
                "Send a text message through the configured Telegram bot. For forum supergroups, "
                "provide message_thread_id to target a specific topic. During an inbound Telegram "
                "request, omitting it replies in the current topic; otherwise omission posts normally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": "integer",
                        "description": "Telegram chat, group, or supergroup ID.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Plain-text message to send.",
                    },
                    "message_thread_id": {
                        "type": "integer",
                        "description": (
                            "Optional forum topic thread ID. Use this for a forum supergroup to "
                            "post in a specific topic."
                        ),
                    },
                },
                "required": ["chat_id", "text"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "comms",
        "function": {
            "name": "list_calendar_events",
            "description": "List calendar events within a date range. Returns event titles, times, locations, and descriptions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (e.g. '2026-05-22T00:00:00'). Defaults to today.",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (e.g. '2026-05-29T23:59:59'). Defaults to 7 days from start.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "comms",
        "function": {
            "name": "create_calendar_event",
            "description": "Create a new calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Event title.",
                    },
                    "start": {
                        "type": "string",
                        "description": "Event start time in ISO format (e.g. '2026-05-22T14:00:00').",
                    },
                    "end": {
                        "type": "string",
                        "description": "Event end time in ISO format (e.g. '2026-05-22T15:00:00').",
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional event location.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional event description or notes.",
                    },
                    "all_day": {
                        "type": "boolean",
                        "description": "Whether this is an all-day event. Defaults to false.",
                    },
                },
                "required": ["title", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "comms",
        "function": {
            "name": "list_cron_jobs",
            "description": "List all Bushido schedules (cron jobs). Returns each job's name, type, frequency, schedule time, enabled status, and next run time.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "comms",
        "function": {
            "name": "create_cron_job",
            "description": "Create a new custom Bushido schedule (cron job). Specify the job type, frequency, schedule time, and optional task instruction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Display name for this schedule (e.g. 'Nightly Memory Consolidation').",
                    },
                    "job_type": {
                        "type": "string",
                        "enum": ["memory_consolidation", "performance_audit", "skill_health_check", "persona_drift_check", "custom_task"],
                        "description": "Type of job to schedule.",
                    },
                    "frequency": {
                        "type": "string",
                        "enum": ["hourly", "nightly", "weekly", "monthly", "one_off"],
                        "description": "How often the job runs. Defaults to 'nightly'.",
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "Time of day to run in HH:MM format (e.g. '02:00'). Used for nightly/weekly/monthly.",
                    },
                    "task_instruction": {
                        "type": "string",
                        "description": "Optional custom instruction text for the job to execute.",
                    },
                    "is_enabled": {
                        "type": "boolean",
                        "description": "Whether to enable the job immediately. Defaults to true.",
                    },
                },
                "required": ["name", "job_type"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "comms",
        "function": {
            "name": "delete_cron_job",
            "description": "Delete a custom Bushido schedule (cron job) by its ID. Preset schedules cannot be deleted, only disabled.",
            "parameters": {
                "type": "object",
                "properties": {
                    "schedule_id": {
                        "type": "string",
                        "description": "The UUID of the schedule to delete.",
                    },
                },
                "required": ["schedule_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workflow",
        "function": {
            "name": "list_agent_flows",
            "description": "List AgentFlows and Flow Stacks with IDs, types, status, and graph sizes. Use this to discover a workflow before inspecting it with get_agent_flow or get_flow_stack.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["all", "active", "draft", "paused"],
                        "description": "Filter by status. Defaults to 'all'.",
                    },
                    "search": {
                        "type": "string",
                        "description": "Case-insensitive substring match on flow name or description.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Pagination page number (1-based). Defaults to 1.",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Results per page. Defaults to 20.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workflow",
        "function": {
            "name": "get_agent_flow",
            "description": "Read one complete AgentFlow, including metadata, every node and node config, and every edge. Always inspect a flow with this tool before editing its graph.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "UUID of the AgentFlow returned by list_agent_flows."},
                },
                "required": ["flow_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workflow",
        "function": {
            "name": "get_flow_stack",
            "description": "Read one complete Flow Stack, including its ordered phases, child AgentFlow references, mappings, node configs, and edges. Always inspect a stack before editing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_stack_id": {"type": "string", "description": "UUID of a Flow Stack returned by list_agent_flows."},
                },
                "required": ["flow_stack_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workflow",
        "function": {
            "name": "set_agent_flow_status",
            "description": (
                "Activate or pause one existing AgentFlow by ID. Inspect the flow first. "
                "Campaign and Ronin posture may perform this lifecycle change autonomously; "
                "lower postures require AgentFlow activation permission or one-time approval."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_id": {
                        "type": "string",
                        "description": "UUID of the AgentFlow returned by list_agent_flows.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "paused"],
                        "description": "Set active to enable the flow/schedule or paused to disable it.",
                    },
                },
                "required": ["flow_id", "status"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workflow",
        "function": {
            "name": "create_agent_flow",
            "description": "Create a new Agent Flow workflow with nodes and edges. Use this when the user asks you to build, design, or create a workflow or pipeline for orchestrating AI agents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the workflow (e.g. 'Research Pipeline', 'Content Review Flow').",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of the workflow's purpose.",
                    },
                    "activate": {
                        "type": "boolean",
                        "description": "Activate the AgentFlow immediately after creation. Defaults to false and requires the separate AgentFlow activation permission.",
                    },
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Unique node ID (e.g. 'node-1', 'node-2')."},
                                "node_type": {
                                    "type": "string",
                                    "enum": [
                                        "input", "samurai", "coding", "shogun_approval", "logic", "output",
                                        "mado_browser", "email_send", "channel_send", "workspace",
                                        "office", "subflow", "stack_orchestrator",
                                    ],
                                    "description": (
                                        "Type of node. Use channel_send—not output—for Telegram or Teams delivery."
                                    ),
                                },
                                "label": {"type": "string", "description": "Display label for the node."},
                                "position_x": {"type": "number", "description": "X position on canvas (start at 100, space 300 apart)."},
                                "position_y": {"type": "number", "description": "Y position on canvas (start at 200, space 150 apart)."},
                                "config": {
                                    "type": "object",
                                    "description": (
                                        "Node-specific config. For a document input sourced from a file attached "
                                        "to the current Comms message, copy the exact server-verified file_id from "
                                        "the attachment manifest into document_source='attachment' and "
                                        "attachment_file_id. For an existing workspace file, use "
                                        "document_source='workspace' and workspace_path relative to the workspace."
                                    ),
                                },
                            },
                            "required": ["id", "node_type", "label"],
                        },
                        "description": "Array of workflow nodes.",
                    },
                    "edges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_node_id": {"type": "string", "description": "ID of the source node."},
                                "target_node_id": {"type": "string", "description": "ID of the target node."},
                                "label": {"type": "string", "description": "Optional edge label."},
                            },
                            "required": ["source_node_id", "target_node_id"],
                        },
                        "description": "Array of connections between nodes.",
                    },
                },
                "required": ["name", "nodes", "edges"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "browser",
        "function": {
            "name": "browse_web",
            "description": "Browse a web page using Mado browser automation. Navigate to a URL and extract content. Requires Mado to be enabled in the Torii security settings. You can use 'extract_preset' to target specific types of content without knowing CSS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to navigate to.",
                    },
                    "extract_type": {
                        "type": "string",
                        "enum": ["text", "html"],
                        "description": "What to extract from the page: 'text' for readable content, 'html' for raw HTML.",
                    },
                    "extract_preset": {
                        "type": "string",
                        "enum": ["headlines", "links", "article", "news_cards", "tables", "images", "lists", "prices", "full_page"],
                        "description": "Smart extraction preset. Use instead of 'selector' for common extraction patterns: 'headlines' for all headings, 'links' for all links, 'article' for the main article body, 'news_cards' for news feeds, 'tables' for structured data, 'images' for image sources, 'lists' for bullet/numbered lists, 'prices' for product pricing, 'full_page' for everything.",
                    },
                    "selector": {
                        "type": "string",
                        "description": "Optional CSS selector to extract content from a specific element. Use extract_preset instead if you don't know the exact CSS selector.",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "browser",
        "function": {
            "name": "take_screenshot",
            "description": "Take a screenshot of the current browser page. Must have navigated to a URL first using browse_web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "If true, capture the full scrollable page. Default: false (viewport only).",
                    },
                },
            },
        },
    },
    # ── Ronin Desktop Control ──────────────────────────────────────
    {
        "type": "function",
        "risk": "low",
        "category": "desktop",
        "function": {
            "name": "desktop_screenshot",
            "description": "Take a screenshot of the entire desktop screen (not just a browser — the full OS desktop). Requires Ronin desktop control to be enabled in Torii security settings (TACTICAL tier or higher). Use this when you need to see what is on screen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {
                        "type": "string",
                        "description": "Optional region as 'x,y,width,height' pixels. Omit for full screen.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "desktop",
        "function": {
            "name": "desktop_click",
            "description": "Click a position on the desktop screen. Requires explicitly enabled Ronin Desktop Control in RONIN posture. Use desktop_screenshot first to identify coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "X coordinate (pixels from left).",
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate (pixels from top).",
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "description": "Mouse button to click. Defaults to 'left'.",
                    },
                    "clicks": {
                        "type": "integer",
                        "description": "Number of clicks (1=single, 2=double). Defaults to 1.",
                    },
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "desktop",
        "function": {
            "name": "desktop_type",
            "description": "Type text using the keyboard on the desktop. Requires explicitly enabled Ronin Desktop Control in RONIN posture. Can also send hotkeys like 'ctrl+c', 'alt+tab', 'enter'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to type. For hotkeys, use format like 'ctrl+c', 'alt+tab', 'enter', 'escape'.",
                    },
                    "is_hotkey": {
                        "type": "boolean",
                        "description": "If true, interpret 'text' as a hotkey combo instead of literal text. Defaults to false.",
                    },
                    "interval": {
                        "type": "number",
                        "description": "Delay between keystrokes in seconds. Defaults to 0.02.",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "desktop",
        "function": {
            "name": "desktop_list_windows",
            "description": "List visible desktop windows and owning processes. Ronin posture and explicit desktop enablement are required.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "desktop",
        "function": {
            "name": "desktop_open_application",
            "description": "Launch an application through the governed Ronin pipeline. High-risk operator approval is required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "application": {"type": "string", "description": "Executable name or approved application path."},
                    "expected_window": {"type": "string", "description": "Window title fragment for verification."},
                },
                "required": ["application"],
            },
        },
    },
    # ── Office App Mode — Excel (Katana) ─────────────────────────
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_excel_open",
            "description": "Open an Excel workbook (.xlsx) from the approved input folder. Returns workbook metadata including sheet names. Must be called before any other Excel operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the .xlsx file. Must be within the configured Office input folder.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_excel_open_attachment",
            "description": (
                "Open an Excel workbook attached to the current chat by its server-verified file_id. "
                "Returns workbook metadata and the canonical file_path to use for later Excel calls."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "The file_id shown in the attached-files manifest.",
                    },
                },
                "required": ["file_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_excel_read_range",
            "description": "Read cell values from an Excel sheet. Returns a 2D array of values. The workbook must be opened first with office_excel_open.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened workbook.",
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet to read from.",
                    },
                    "range": {
                        "type": "string",
                        "description": "Cell range to read (e.g. 'A1:D10'). Omit to read all used cells.",
                    },
                },
                "required": ["file_path", "sheet_name"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_excel_write_range",
            "description": "Write values to an Excel sheet. Provide a 2D array of values and a start cell or range. The workbook must be opened first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened workbook.",
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Target sheet name.",
                    },
                    "range": {
                        "type": "string",
                        "description": "Start cell or range (e.g. 'B4' or 'B4:D12').",
                    },
                    "values": {
                        "type": "array",
                        "items": {"type": "array", "items": {}},
                        "description": "2D array of values to write, e.g. [['Name', 'Age'], ['Alice', 30]].",
                    },
                },
                "required": ["file_path", "sheet_name", "range", "values"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_excel_list_sheets",
            "description": "List all sheet names in an opened Excel workbook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened workbook.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_excel_save_as",
            "description": "Save the Excel workbook to the approved output folder with a versioned filename. The output path is auto-generated.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened workbook.",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the output file (without extension). A timestamp suffix will be added automatically.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_excel_export_pdf",
            "description": "Export the Excel workbook to PDF format. Requires Microsoft Excel to be installed (uses COM automation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the workbook to export.",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the PDF file (without extension).",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_excel_get_metadata",
            "description": "Get metadata about an opened Excel workbook (sheet names, creator, dates, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened workbook.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_excel_calculate",
            "description": "Recalculate all formulas in the workbook. Requires Microsoft Excel to be installed (uses COM automation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the workbook to recalculate.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    # ── Office App Mode — Word (Katana) ──────────────────────────
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_word_open",
            "description": "Open a Word document (.docx) from the approved input folder. Returns document metadata. Must be called before other Word operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the .docx file. Must be within the configured Office input folder.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_replace_placeholders",
            "description": "Replace {{placeholder}} patterns in a Word document with provided values. Searches paragraphs, tables, headers, and footers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                    "mapping": {
                        "type": "object",
                        "description": "Dictionary of placeholder → replacement value, e.g. {'{{company_name}}': 'Acme Corp', '{{date}}': '2026-06-30'}.",
                    },
                },
                "required": ["file_path", "mapping"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_insert_table",
            "description": "Insert a table into a Word document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column header strings.",
                    },
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {}},
                        "description": "2D array of row data.",
                    },
                },
                "required": ["file_path", "headers", "rows"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_save_as",
            "description": "Save the Word document to the approved output folder with a versioned filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the output file (without extension).",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_export_pdf",
            "description": "Export the Word document to PDF. Requires Microsoft Word installed (uses COM).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the document to export.",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the PDF file.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_word_get_metadata",
            "description": "Get metadata about an opened Word document (paragraph count, tables, author, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_word_read_text",
            "description": "Read text from a Word document, bounded to protect the model context. Use office_word_read_pages when the user requests specific pages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Maximum characters to return. Defaults to 30000.",
                        "minimum": 1000,
                        "maximum": 100000,
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_word_read_page",
            "description": "Read one rendered page from a Word document. Use this for page-by-page translation. The document is opened automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the Word document.",
                    },
                    "page": {
                        "type": "integer",
                        "description": "Page number to read (1-based).",
                        "minimum": 1,
                    },
                },
                "required": ["file_path", "page"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_word_read_pages",
            "description": "Read only a requested page range from a Word document. Use this instead of office_word_read_text when the user asks for specific pages. The document is opened automatically if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the Word document.",
                    },
                    "start_page": {
                        "type": "integer",
                        "description": "First page to read (1-based).",
                        "minimum": 1,
                    },
                    "end_page": {
                        "type": "integer",
                        "description": "Last page to read, inclusive (1-based).",
                        "minimum": 1,
                    },
                },
                "required": ["file_path", "start_page", "end_page"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_word_read_headings",
            "description": "Read all headings from an opened Word document. Returns a list of {level, text} objects. Call office_word_open first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_insert_paragraph",
            "description": "Insert a paragraph of text into an opened Word document. Optionally set the style (e.g. 'Heading 1', 'Normal').",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened document.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text content to insert.",
                    },
                    "style": {
                        "type": "string",
                        "description": "Paragraph style (e.g. 'Normal', 'Heading 1'). Optional.",
                    },
                },
                "required": ["file_path", "text"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_create",
            "description": "Create a new blank Word document (.docx) at the specified path in the workspace. Returns the absolute path to the created file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Path for the new document (relative to workspace, e.g. 'Output/report.docx').",
                    },
                },
                "required": ["output_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_word_create_from_text",
            "description": "Create, overwrite, or append text to a Word document. Use this after translating one page of content; no separate open, create, insert, or save call is needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Output path relative to the workspace, e.g. 'Output/translated.docx'.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Complete text to write into the Word document.",
                    },
                    "append": {
                        "type": "boolean",
                        "description": "False for the first page; true to append later translated pages.",
                    },
                },
                "required": ["output_path", "text"],
            },
        },
    },
    # ── Office App Mode — PowerPoint (Katana) ────────────────────
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_pptx_open",
            "description": "Open a PowerPoint presentation (.pptx) from the approved input folder. Returns presentation metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the .pptx file.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_pptx_replace_placeholders",
            "description": "Replace {{placeholder}} patterns across all slides and tables in a PowerPoint presentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened presentation.",
                    },
                    "mapping": {
                        "type": "object",
                        "description": "Dictionary of placeholder → replacement value.",
                    },
                },
                "required": ["file_path", "mapping"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_pptx_insert_table",
            "description": "Insert a table on a specific slide in a PowerPoint presentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened presentation.",
                    },
                    "slide_index": {
                        "type": "integer",
                        "description": "Index of the slide to insert the table on (0-based).",
                    },
                    "headers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Column header strings.",
                    },
                    "rows": {
                        "type": "array",
                        "items": {"type": "array", "items": {}},
                        "description": "2D array of row data.",
                    },
                },
                "required": ["file_path", "slide_index", "headers", "rows"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_pptx_insert_image",
            "description": "Insert an image on a specific slide. The image must be from an approved folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened presentation.",
                    },
                    "slide_index": {
                        "type": "integer",
                        "description": "Index of the slide (0-based).",
                    },
                    "image_path": {
                        "type": "string",
                        "description": "Path to the image file.",
                    },
                },
                "required": ["file_path", "slide_index", "image_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_pptx_save_as",
            "description": "Save the presentation to the approved output folder with a versioned filename.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened presentation.",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the output file (without extension).",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_pptx_export_pdf",
            "description": "Export the presentation to PDF. Requires Microsoft PowerPoint installed (uses COM).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the presentation to export.",
                    },
                    "output_name": {
                        "type": "string",
                        "description": "Base name for the PDF file.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "office",
        "function": {
            "name": "office_pptx_get_metadata",
            "description": "Get metadata about an opened PowerPoint presentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the already-opened presentation.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    # ── Office App Mode — Outlook (Katana) ───────────────────────
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_outlook_create_draft",
            "description": "Create a new draft email in Outlook. This is the primary way to compose emails — provide all fields in one call. The draft is saved but NOT sent. Requires Microsoft Outlook installed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of recipient email addresses.",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (HTML supported).",
                    },
                    "cc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "CC recipients (optional).",
                    },
                    "bcc": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "BCC recipients (optional).",
                    },
                },
                "required": ["recipients", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_outlook_attach_file",
            "description": "Attach a file to an existing Outlook draft. The file must be from an approved output folder.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft ID returned by office_outlook_create_draft.",
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to attach.",
                    },
                },
                "required": ["draft_id", "file_path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "office",
        "function": {
            "name": "office_outlook_save_draft",
            "description": "Explicitly save an Outlook draft and open it in Outlook for human review.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft ID to save and display.",
                    },
                },
                "required": ["draft_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "office",
        "function": {
            "name": "office_outlook_send",
            "description": "Send an Outlook draft email. HIGH-RISK: This will actually send the email. Requires human-in-the-loop approval. Only available at Tactical posture and above.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {
                        "type": "string",
                        "description": "The draft ID to send.",
                    },
                },
                "required": ["draft_id"],
            },
        },
    },
    # ── Workspace Tools ──────────────────────────────────────────────
    {
        "type": "function",
        "risk": "low",
        "category": "workspace",
        "function": {
            "name": "workspace_info",
            "description": "Get information about the agent workspace: its absolute path, whether access is enabled at the current security posture, and disk usage summary.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workspace",
        "function": {
            "name": "workspace_list",
            "description": "List files and directories inside the workspace. Optionally provide a relative subdirectory path to list. Returns file names, sizes, and types.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path inside the workspace to list. Use '.' or omit for the workspace root.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workspace",
        "function": {
            "name": "workspace_read",
            "description": "Read the contents of a text file from the workspace. Provide a relative file path within the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file inside the workspace.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workspace",
        "function": {
            "name": "workspace_write",
            "description": "Write or create a text file in the workspace. If the file exists, it will be overwritten. Parent directories are created automatically.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path for the file inside the workspace.",
                    },
                    "content": {
                        "type": "string",
                        "description": "The text content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workspace",
        "function": {
            "name": "workspace_mkdir",
            "description": "Create a subdirectory inside the workspace. Parent directories are created automatically if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the directory to create inside the workspace.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "workspace",
        "function": {
            "name": "workspace_delete",
            "description": "Delete a file from the workspace. Cannot delete directories — only individual files. This action is irreversible.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file to delete inside the workspace.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workspace",
        "function": {
            "name": "workspace_read_image",
            "description": "Read and visually inspect an image file from the workspace. Returns the image content so you can see and describe what is in the image. Supports JPEG, PNG, GIF, WebP. Use this for Telegram-uploaded photos or any workspace images you need to understand.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the image file inside the workspace.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "comms",
        "function": {
            "name": "telegram_list_groups",
            "description": "List all Telegram groups and supergroups this bot knows about. Shows group name, type, admin status, and known topics/threads. The bot discovers groups when it is added to them or when messages are received. If a group is missing, ask the user to send a message in that group first.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "workspace",
        "function": {
            "name": "workspace_read_pdf",
            "description": "Extract text content from a PDF file in the workspace. Returns the text of each page. Use this to read PDFs uploaded via Telegram or saved in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the PDF file inside the workspace.",
                    },
                    "pages": {
                        "type": "string",
                        "description": "Optional. Page range to extract, e.g. '1-5' or '1,3,7'. Omit to extract all pages.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "dojo",
        "function": {
            "name": "dojo_browse_skills",
            "description": "Browse the OpenClaw College skill catalog. Search for skills by keyword, category, or specialization. Returns skill names, descriptions, IDs, risk tiers, and categories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Optional search keyword to filter skills.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category slug to filter by (e.g. 'automation', 'data-analysis').",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "dojo",
        "function": {
            "name": "dojo_install_skill",
            "description": "Install a skill from the OpenClaw College catalog into the local Shogun system. Requires the skill's OpenClaw ID and name. Only available when skill auto-install is enabled in the posture.",
            "parameters": {
                "type": "object",
                "properties": {
                    "openclaw_skill_id": {
                        "type": "string",
                        "description": "The OpenClaw skill ID to install.",
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "Human-readable name of the skill.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Brief description of what the skill does.",
                    },
                },
                "required": ["openclaw_skill_id", "skill_name"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "dojo",
        "function": {
            "name": "dojo_enroll_specialization",
            "description": "Enroll the registered Shogun agent in an OpenClaw College specialization. Prior passed exams are evaluated immediately and eligible badges are awarded.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialization_id": {
                        "type": "string",
                        "description": "The OpenClaw specialization ID or slug.",
                    },
                },
                "required": ["specialization_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "dojo",
        "function": {
            "name": "dojo_evaluate_achievements",
            "description": "Reevaluate all enrolled OpenClaw College specializations and award every badge whose required skill exams have been passed.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "dojo",
        "function": {
            "name": "dojo_list_installed",
            "description": "List all skills currently installed in the local Shogun Dojo. Shows skill name, version, status, and installation details.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function", "risk": "low", "category": "skill_usage",
        "function": {
            "name": "skills_get_active",
            "description": "List the validated skills currently active for a run. This is read-only and does not bypass activation policy.",
            "parameters": {"type": "object", "properties": {
                "run_id": {"type": "string", "description": "Run ID whose active skills should be returned."}
            }, "required": ["run_id"]},
        },
    },
    {
        "type": "function", "risk": "low", "category": "skill_usage",
        "function": {
            "name": "skills_request_activation",
            "description": "Request deterministic skill activation for an objective. The policy pipeline makes the final decision.",
            "parameters": {"type": "object", "properties": {
                "objective": {"type": "string"}, "context": {"type": "string"},
                "run_id": {"type": "string"}, "available_tools": {"type": "array", "items": {"type": "string"}}
            }, "required": ["objective"]},
        },
    },
    {
        "type": "function", "risk": "low", "category": "skill_usage",
        "function": {
            "name": "skills_explain_active",
            "description": "Explain which skills are active, why they were selected, and their bounded context use.",
            "parameters": {"type": "object", "properties": {
                "run_id": {"type": "string"}
            }, "required": ["run_id"]},
        },
    },
    {
        "type": "function", "risk": "low", "category": "skill_usage",
        "function": {
            "name": "skills_report_outcome",
            "description": "Report the outcome of one policy-approved active skill usage record.",
            "parameters": {"type": "object", "properties": {
                "active_skill_run_id": {"type": "string"},
                "outcome": {"type": "string", "enum": ["success", "partial", "failed", "not_used", "blocked", "unknown"]},
                "outcome_summary": {"type": "string"}
            }, "required": ["active_skill_run_id", "outcome"]},
        },
    },
    {
        "type": "function", "risk": "low", "category": "system",
        "function": {"name": "model_router_get_active_profile", "description": "Get the active governed model routing profile.",
                     "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function", "risk": "low", "category": "system",
        "function": {"name": "model_router_preview_route", "description": "Preview which eligible model the router would select without executing it.",
                     "parameters": {"type": "object", "properties": {
                         "prompt": {"type": "string"}, "task_type": {"type": "string"},
                         "required_capabilities": {"type": "array", "items": {"type": "string"}},
                         "complexity": {"type": "integer", "minimum": 1, "maximum": 5},
                         "profile": {"type": "string"}}, "required": ["prompt"]}},
    },
    {
        "type": "function", "risk": "low", "category": "system",
        "function": {"name": "model_router_request_route", "description": "Request and audit a governed model routing decision.",
                     "parameters": {"type": "object", "properties": {
                         "prompt": {"type": "string"}, "task_type": {"type": "string"},
                         "required_capabilities": {"type": "array", "items": {"type": "string"}},
                         "profile": {"type": "string"}}, "required": ["prompt"]}},
    },
    {
        "type": "function", "risk": "low", "category": "system",
        "function": {"name": "model_router_request_escalation", "description": "Request the next governed model after failure or failed verification.",
                     "parameters": {"type": "object", "properties": {
                         "prompt": {"type": "string"}, "task_type": {"type": "string"},
                         "previous_model": {"type": "string"}, "escalation_level": {"type": "integer", "minimum": 1, "maximum": 2}},
                         "required": ["prompt", "previous_model"]}},
    },
    {
        "type": "function", "risk": "low", "category": "system",
        "function": {"name": "model_router_log_outcome", "description": "Log token, latency, success, and error outcome for a routing decision.",
                     "parameters": {"type": "object", "properties": {
                         "routing_decision_id": {"type": "string"}, "model_id": {"type": "string"},
                         "provider": {"type": "string"}, "input_tokens": {"type": "integer"},
                         "output_tokens": {"type": "integer"}, "latency_ms": {"type": "integer"},
                         "success": {"type": "boolean"}, "error": {"type": "string"}},
                         "required": ["model_id", "provider"]}},
    },
    {
        "type": "function", "risk": "low", "category": "visual",
        "function": {
            "name": "get_recent_images",
            "description": "List recent governed images from chat or Telegram so you can refer to them by artifact ID.",
            "parameters": {"type": "object", "properties": {
                "limit": {"type": "integer", "description": "Number of images, from 1 to 20."},
                "chat_session_id": {"type": "string", "description": "Optional chat or Telegram conversation ID."}
            }}
        }
    },
    {
        "type": "function", "risk": "low", "category": "visual",
        "function": {
            "name": "get_image_metadata",
            "description": "Get safe metadata for a governed image artifact.",
            "parameters": {"type": "object", "properties": {"artifact_id": {"type": "string"}}, "required": ["artifact_id"]}
        }
    },
    {
        "type": "function", "risk": "low", "category": "visual",
        "function": {
            "name": "describe_image",
            "description": "Use a permitted vision model to describe a governed chat or Telegram image.",
            "parameters": {"type": "object", "properties": {
                "artifact_id": {"type": "string"}, "prompt": {"type": "string"}
            }, "required": ["artifact_id"]}
        }
    },
    {
        "type": "function", "risk": "low", "category": "visual",
        "function": {
            "name": "inspect_image",
            "description": "Inspect a governed image for a specific detail or extract visible text.",
            "parameters": {"type": "object", "properties": {
                "artifact_id": {"type": "string"}, "prompt": {"type": "string"}
            }, "required": ["artifact_id", "prompt"]}
        }
    },
    {
        "type": "function", "risk": "low", "category": "visual",
        "function": {
            "name": "extract_image_text",
            "description": "Extract visible text from a governed image while preserving reading order.",
            "parameters": {"type": "object", "properties": {"artifact_id": {"type": "string"}}, "required": ["artifact_id"]}
        }
    },
    {
        "type": "function", "risk": "low", "category": "visual",
        "function": {
            "name": "compare_images",
            "description": "Compare two governed images with a permitted vision model.",
            "parameters": {"type": "object", "properties": {
                "first_artifact_id": {"type": "string"}, "second_artifact_id": {"type": "string"}, "prompt": {"type": "string"}
            }, "required": ["first_artifact_id", "second_artifact_id"]}
        }
    },
    {
        "type": "function", "risk": "medium", "category": "visual",
        "function": {
            "name": "attach_image_to_stack",
            "description": "Attach a governed image artifact as a durable input/evidence artifact on an existing Flow Stack run.",
            "parameters": {"type": "object", "properties": {
                "artifact_id": {"type": "string"}, "stack_run_id": {"type": "string"}
            }, "required": ["artifact_id", "stack_run_id"]}
        }
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workflow",
        "function": {
            "name": "patch_agent_flow",
            "description": "Safely add, update, or delete selected AgentFlow nodes and edges while preserving everything else. Call get_agent_flow first and use the returned UUIDs. Prefer config_patch for targeted config changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "UUID of the existing standard AgentFlow."},
                    "node_operations": {
                        "type": "array",
                        "description": "Targeted node operations. Deleting a node also deletes its connected edges.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {"type": "string", "enum": ["add", "update", "delete"]},
                                "node_id": {"type": "string", "description": "Existing node UUID for update/delete; optional new UUID for add."},
                                "node_type": {"type": "string"},
                                "label": {"type": "string"},
                                "position_x": {"type": "number"},
                                "position_y": {"type": "number"},
                                "config": {"type": "object", "description": "Complete replacement config."},
                                "config_patch": {"type": "object", "description": "Top-level config fields to merge into the existing config."},
                            },
                            "required": ["op"],
                        },
                    },
                    "edge_operations": {
                        "type": "array",
                        "description": "Targeted edge operations using node and edge UUIDs from get_agent_flow.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {"type": "string", "enum": ["add", "update", "delete"]},
                                "edge_id": {"type": "string", "description": "Existing edge UUID for update/delete; optional new UUID for add."},
                                "source_node_id": {"type": "string"},
                                "target_node_id": {"type": "string"},
                                "source_handle": {"type": "string"},
                                "target_handle": {"type": "string"},
                                "label": {"type": "string"},
                                "edge_type": {"type": "string"},
                                "config": {"type": "object", "description": "Complete replacement config."},
                                "config_patch": {"type": "object", "description": "Top-level config fields to merge into the existing config."},
                            },
                            "required": ["op"],
                        },
                    },
                },
                "required": ["flow_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workflow",
        "function": {
            "name": "edit_agent_flow",
            "description": "Edit AgentFlow metadata or replace its complete graph. Inspect with get_agent_flow first; prefer patch_agent_flow for targeted graph changes that preserve untouched elements. Activation is governed separately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "ID of the existing AgentFlow."},
                    "name": {"type": "string", "description": "Optional new name."},
                    "description": {"type": "string", "description": "Optional new description."},
                    "trigger_type": {"type": "string", "description": "Optional trigger type ('scheduled', 'manual', 'api', 'event')."},
                    "schedule_config": {"type": "object", "description": "Optional schedule config (e.g. {'frequency': 'nightly', 'schedule_time': '12:00'})."},
                    "schedule_time": {"type": "string", "description": "Optional schedule run time in HH:MM format (e.g. '12:00'). Shortcut for schedule_config."},
                    "schedule_frequency": {"type": "string", "description": "Optional schedule frequency ('hourly', 'nightly', 'weekly', 'monthly'). Shortcut for schedule_config."},
                    "nodes": {"type": "array", "items": {"type": "object"}, "description": "Optional complete replacement list of AgentFlow nodes."},
                    "edges": {"type": "array", "items": {"type": "object"}, "description": "Optional complete replacement list of AgentFlow connections."},
                    "activate": {"type": "boolean", "description": "Activate after editing. Requires the separate AgentFlow activation permission."},
                },
                "required": ["flow_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "workflow",
        "function": {
            "name": "delete_agent_flow",
            "description": "Soft-delete an existing AgentFlow after operator confirmation. Requires the explicit AgentFlow delete permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_id": {"type": "string", "description": "ID of the AgentFlow to delete."},
                },
                "required": ["flow_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workflow",
        "function": {
            "name": "edit_flow_stack",
            "description": "Edit an existing Flow Stack's metadata and optionally replace its ordered AgentFlow phases. Activation is governed separately.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_stack_id": {"type": "string", "description": "ID of the existing Flow Stack."},
                    "name": {"type": "string", "description": "Optional new stack name."},
                    "description": {"type": "string", "description": "Optional new stack description."},
                    "flow_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2, "description": "Optional ordered replacement phases."},
                    "version_mode": {"type": "string", "enum": ["locked", "latest"], "description": "Child version policy. Defaults to locked."},
                    "timeout_seconds": {"type": "integer", "description": "Timeout for each phase."},
                    "activate": {"type": "boolean", "description": "Activate after editing. Requires the separate Flow Stack activation permission."},
                },
                "required": ["flow_stack_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "workflow",
        "function": {
            "name": "delete_flow_stack",
            "description": "Soft-delete an existing Flow Stack after operator confirmation. Requires the explicit Flow Stack delete permission.",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_stack_id": {"type": "string", "description": "ID of the Flow Stack to delete."},
                },
                "required": ["flow_stack_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "medium",
        "category": "workflow",
        "function": {
            "name": "create_flow_stack",
            "description": "Create a connected Flow Stack from two or more existing AgentFlows. The stack remains a draft unless activation is explicitly requested and permitted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the Flow Stack."},
                    "description": {"type": "string", "description": "Purpose of the Flow Stack."},
                    "flow_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "description": "Ordered IDs of existing AgentFlows to connect as stack phases.",
                    },
                    "version_mode": {"type": "string", "enum": ["locked", "latest"], "description": "Lock child versions or follow latest. Defaults to locked."},
                    "timeout_seconds": {"type": "integer", "description": "Timeout for each child flow. Defaults to 600."},
                    "activate": {"type": "boolean", "description": "Activate the Flow Stack immediately. Defaults to false and requires the separate Flow Stack activation permission."},
                },
                "required": ["name", "flow_ids"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "dojo",
        "function": {
            "name": "dojo_take_exam",
            "description": "Take the OpenClaw College certification exam for an installed or catalog skill. Returns pass/fail, score, model, and test metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "openclaw_skill_id": {
                        "type": "string",
                        "description": "The OpenClaw skill ID to certify.",
                    },
                },
                "required": ["openclaw_skill_id"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "dojo",
        "function": {
            "name": "dojo_get_achievements",
            "description": "Show the registered Shogun agent's Dojo achievements, installed skill count, badges, and exam totals.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "dojo",
        "function": {
            "name": "dojo_get_transcript",
            "description": "Show the OpenClaw College certification transcript and exam history for the registered Shogun agent.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "mcp",
        "function": {
            "name": "mcp_list_tools",
            "description": "List callable tools exposed by a registered Katana MCP connector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connector_slug": {
                        "type": "string",
                        "description": "The Katana MCP connector slug, e.g. 'openclaw-dojo'.",
                    },
                },
                "required": ["connector_slug"],
            },
        },
    },
    {
        "type": "function",
        "risk": "high",
        "category": "mcp",
        "function": {
            "name": "mcp_call_tool",
            "description": "Call a tool exposed by a registered Katana MCP connector. Use mcp_list_tools first to discover tool names and input schemas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connector_slug": {
                        "type": "string",
                        "description": "The Katana MCP connector slug, e.g. 'openclaw-dojo'.",
                    },
                    "tool_name": {
                        "type": "string",
                        "description": "The MCP tool name to call.",
                    },
                    "arguments": {
                        "type": "object",
                        "description": "JSON arguments for the MCP tool.",
                    },
                },
                "required": ["connector_slug", "tool_name"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "mcp",
        "function": {
            "name": "mcp_list_resources",
            "description": "List resources exposed by a registered Katana MCP connector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connector_slug": {
                        "type": "string",
                        "description": "The Katana MCP connector slug, e.g. 'openclaw-dojo'.",
                    },
                },
                "required": ["connector_slug"],
            },
        },
    },
    {
        "type": "function",
        "risk": "low",
        "category": "mcp",
        "function": {
            "name": "mcp_read_resource",
            "description": "Read a resource exposed by a registered Katana MCP connector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connector_slug": {
                        "type": "string",
                        "description": "The Katana MCP connector slug, e.g. 'openclaw-dojo'.",
                    },
                    "uri": {
                        "type": "string",
                        "description": "The MCP resource URI to read.",
                    },
                },
                "required": ["connector_slug", "uri"],
            },
        },
    },
    {
        "type": "function", "risk": "low", "category": "ide",
        "function": {"name": "ide_list_workspaces", "description": "List approved VS Code workspaces available to Shogun IDE Mode.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function", "risk": "low", "category": "ide",
        "function": {"name": "ide_list_files", "description": "List files in an approved VS Code workspace.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "glob": {"type": "string"}}, "required": ["workspace_id"]}},
    },
    {
        "type": "function", "risk": "low", "category": "ide",
        "function": {"name": "ide_read_file", "description": "Read a file inside an approved VS Code workspace.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "path": {"type": "string"}}, "required": ["workspace_id", "path"]}},
    },
    {
        "type": "function", "risk": "low", "category": "ide",
        "function": {"name": "ide_search", "description": "Search text across an approved VS Code workspace.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "query": {"type": "string"}, "glob": {"type": "string"}}, "required": ["workspace_id", "query"]}},
    },
    {
        "type": "function", "risk": "high", "category": "ide",
        "function": {"name": "ide_apply_patch", "description": "Apply reviewed resulting file content in an approved VS Code workspace. A rollback snapshot and unified diff are created automatically.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "path": {"type": "string"}, "content": {"type": "string"}, "approved": {"type": "boolean"}}, "required": ["workspace_id", "path", "content"]}},
    },
    {
        "type": "function", "risk": "high", "category": "ide",
        "function": {"name": "ide_run_task", "description": "Run an approved test, lint, or build command in a VS Code workspace and return its verified output.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "command": {"type": "string"}, "approved": {"type": "boolean"}}, "required": ["workspace_id", "command"]}},
    },
    {
        "type": "function", "risk": "low", "category": "ide",
        "function": {"name": "ide_memory_search", "description": "Search project-scoped programming memory before diagnosing or editing an approved VS Code workspace. Returns prior solutions, corrections, failed approaches, evidence, and validation status for this repository only.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer", "default": 8}, "include_global": {"type": "boolean", "default": False}}, "required": ["workspace_id", "query"]}},
    },
    {
        "type": "function", "risk": "medium", "category": "ide",
        "function": {"name": "ide_memory_store", "description": "Store a reusable project-scoped programming solution only after operator confirmation or successful tests. Include evidence and sources when research was used.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "title": {"type": "string"}, "problem": {"type": "string"}, "solution": {"type": "string"}, "kind": {"type": "string", "enum": ["solution", "correction", "pattern", "project_fact", "failed_approach"]}, "evidence": {"type": "string"}, "validation_status": {"type": "string", "enum": ["unverified", "operator_confirmed", "tests_passed", "production_confirmed"]}, "confidence_score": {"type": "number"}, "languages": {"type": "array", "items": {"type": "string"}}, "files": {"type": "array", "items": {"type": "string"}}, "source_urls": {"type": "array", "items": {"type": "string"}}, "tags": {"type": "array", "items": {"type": "string"}}}, "required": ["workspace_id", "title", "problem", "solution", "validation_status"]}},
    },
    {
        "type": "function", "risk": "low", "category": "ide",
        "function": {"name": "ide_memory_reinforce", "description": "Record whether a recalled programming memory solved the current task, raising or lowering its future confidence.", "parameters": {"type": "object", "properties": {"workspace_id": {"type": "string"}, "memory_id": {"type": "string"}, "successful": {"type": "boolean", "default": True}}, "required": ["workspace_id", "memory_id"]}},
    },
    # ── Order 15: Skill Lifecycle Tools ──────────────────────────
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_detect_type", "description": "Detect a workspace file by extension, MIME, magic bytes, and content without trusting its extension alone.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Approved workspace or artifact path."}}, "required": ["path"]}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_inspect", "description": "Safely inspect a file with its deterministic adapter and return a normalized profile, schema, preview, warnings, and file ID.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "source": {"type": "string"}}}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_read", "description": "Read bounded content from an attached file ID or approved workspace path. Supports text/data files, PDF pages, Word documents, Excel sheets, and PowerPoint slides without executing content.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "start": {"type": "integer", "minimum": 1}, "end": {"type": "integer", "minimum": 1}, "sheet": {"type": "string"}, "max_chars": {"type": "integer", "minimum": 1000, "maximum": 100000}}}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_preview", "description": "Return a bounded, secret-masked preview through the detected format adapter.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}}}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_schema", "description": "Return the inferred schema or structural outline without sending the complete file to the model.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}}}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_query", "description": "Query a registered or approved file using JSON path, column=value, field=value, config path, or text search.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_extract", "description": "Extract bounded deterministic content and structural metadata from a supported file without executing it.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}}}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_compare", "description": "Compare two approved files by normalized profile, format, schema, and content hash.",
                     "parameters": {"type": "object", "properties": {"left_path": {"type": "string"}, "right_path": {"type": "string"}}, "required": ["left_path", "right_path"]}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_validate", "description": "Deterministically validate a file with the correct safe parser.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}}}},
    },
    {
        "type": "function", "risk": "medium", "category": "files",
        "function": {"name": "file_transform", "description": "Transform a supported file to JSON, CSV, TSV, or Markdown in the approved workspace without overwriting its source.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "target_format": {"type": "string", "enum": ["json", "csv", "tsv", "md"]}, "output_filename": {"type": "string"}, "sanitize_formulas": {"type": "boolean"}}, "required": ["target_format"]}},
    },
    {
        "type": "function", "risk": "medium", "category": "files",
        "function": {"name": "file_export", "description": "Export a supported transformation as a new versioned artifact without overwriting the source.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "target_format": {"type": "string", "enum": ["json", "csv", "tsv", "md"]}, "output_filename": {"type": "string"}, "sanitize_formulas": {"type": "boolean"}}, "required": ["target_format"]}},
    },
    {
        "type": "function", "risk": "high", "category": "files",
        "function": {"name": "file_archive_extract_selected", "description": "Extract explicitly selected safe ZIP members under the approved workspace. Blocks traversal, symlinks, executables, bombs, and silent overwrite.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "members": {"type": "array", "items": {"type": "string"}}, "output_directory": {"type": "string"}, "allow_overwrite": {"type": "boolean"}}, "required": ["members"]}},
    },
    {
        "type": "function", "risk": "medium", "category": "files",
        "function": {"name": "file_index_profile", "description": "Store only a normalized file profile, schema, summary, file ID, and hash in memory; never embeds a large raw structured file.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "agent_id": {"type": "string"}, "title": {"type": "string"}}, "required": ["agent_id"]}},
    },
    {
        "type": "function", "risk": "medium", "category": "files",
        "function": {"name": "file_index", "description": "Index a normalized file profile and artifact reference in memory, never the entire large raw file.",
                     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "file_id": {"type": "string"}, "agent_id": {"type": "string"}, "title": {"type": "string"}}, "required": ["agent_id"]}},
    },
    {
        "type": "function", "risk": "low", "category": "files",
        "function": {"name": "file_list_formats", "description": "List registered file adapters, capabilities, risk, read/write/index support, and status.",
                     "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function", "risk": "medium", "category": "skill_lifecycle",
        "function": {
            "name": "dojo_author_skill",
            "description": "Create a new skill draft in the Dojo. Generates the skill package (skill.md, manifest.json, changelog.md) and registers it in the database with lifecycle_state='draft'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Display name for the skill (e.g. 'Business Email Reply')."},
                    "description": {"type": "string", "description": "Short description of what the skill does."},
                    "body_text": {"type": "string", "description": "Full skill instructions in markdown. If empty, a template is generated."},
                    "category": {"type": "string", "description": "Skill category (e.g. 'communication', 'research', 'coding'). Defaults to 'general'."},
                    "triggers": {"type": "array", "items": {"type": "string"}, "description": "Activation trigger phrases (e.g. ['email reply', 'business response'])."},
                    "risk_tier": {"type": "string", "enum": ["low", "medium", "high", "critical"], "description": "Risk tier for the skill. Defaults to 'low'."},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization and search."},
                    "requires_tools": {"type": "array", "items": {"type": "string"}, "description": "List of tool names this skill requires."},
                    "version": {"type": "string", "description": "Semantic version number. Defaults to '1.0.0'."},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function", "risk": "low", "category": "skill_lifecycle",
        "function": {
            "name": "dojo_validate_skill",
            "description": "Run the quality gate and validation checks on a skill. Checks: manifest, body text, triggers, risk tier, forbidden instructions, credentials, posture bypass, version format, changelog, and validation tests. Returns detailed pass/fail results and score.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "UUID of the skill to validate."},
                },
                "required": ["skill_id"],
            },
        },
    },
    {
        "type": "function", "risk": "high", "category": "skill_lifecycle",
        "function": {
            "name": "dojo_publish_skill",
            "description": "Publish a validated skill to a provider (local folder or OpenClaw College). Runs quality gate first unless skipped. Packages the skill and records the publication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "UUID of the skill to publish."},
                    "provider": {"type": "string", "enum": ["local", "openclaw_college"], "description": "Publishing provider. Defaults to 'local'."},
                    "skip_quality_gate": {"type": "boolean", "description": "If true, skip the quality gate check. Defaults to false."},
                },
                "required": ["skill_id"],
            },
        },
    },
]


def generate_tool_prompt(tools: list[dict]) -> str:
    """Generate a human-readable tool description block for prompt injection.

    When a model does not support the OpenAI structured `tools` API parameter,
    we inject this text block into the system prompt instead. The model is
    instructed to output tool calls in a parseable `<tool_call>` format.
    """
    lines = [
        "## Available Tools",
        "",
        "You have access to the following tools. When you decide to call a tool, you must execute it by writing the tool call in one of the following formats.",
        "Write exactly one tool call in the `<tool_call>` tag format, using a JSON object for arguments:",
        "",
        "<tool_call>",
        'tool_name({"param1": "value1", "param2": "value2"})',
        "</tool_call>",
        "",
        "For example, to list available models, output exactly:",
        "<tool_call>",
        "list_available_models()",
        "</tool_call>",
        "",
        "CRITICAL RULES:",
        "- You MUST output the tool call exactly as defined. Do not modify the tool name.",
        "- Arguments MUST be valid JSON. Escape quotes and newlines inside string values.",
        "- Output ONLY ONE tool call at a time, then STOP and wait for the result.",
        "- Do NOT hallucinate or fabricate tool results. The system will execute the tool and provide the real output.",
        "- After receiving a tool result, continue with your next action or provide the final answer.",
        "- For tools with no required parameters, call them with empty parentheses: tool_name()",
        "",
        "### Tool Definitions",
        "",
    ]

    for tool in tools:
        func = tool["function"]
        name = func["name"]
        desc = func["description"]
        params = func.get("parameters", {}).get("properties", {})
        required = func.get("parameters", {}).get("required", [])

        # Build parameter signature
        param_parts = []
        for pname, pdef in params.items():
            ptype = pdef.get("type", "string")
            is_req = pname in required
            marker = " [REQUIRED]" if is_req else ""
            param_parts.append(f'{pname}: {ptype}{marker}')

        sig = ", ".join(param_parts) if param_parts else ""
        lines.append(f"**{name}**({sig})")
        lines.append(f"  {desc}")

        # Parameter details
        if params:
            for pname, pdef in params.items():
                pdesc = pdef.get("description", "")
                is_req = pname in required
                enum = pdef.get("enum")
                enum_str = f" (one of: {', '.join(enum)})" if enum else ""
                req_str = " ⚠️ required" if is_req else ""
                lines.append(f"  - `{pname}`: {pdesc}{enum_str}{req_str}")
        lines.append("")

    return "\n".join(lines)


def _serialize_flow_for_agent(flow, *, include_phases: bool = False) -> dict[str, Any]:
    """Return the complete, stable graph representation exposed to read tools."""
    ordered_nodes = sorted(flow.nodes or [], key=lambda node: (node.position_x, node.position_y, str(node.id)))
    ordered_edges = sorted(flow.edges or [], key=lambda edge: str(edge.id))
    payload: dict[str, Any] = {
        "flow_id": str(flow.id),
        "name": flow.name,
        "description": flow.description or "",
        "status": flow.status,
        "flow_type": flow.flow_type,
        "trigger_type": flow.trigger_type,
        "schedule_config": flow.schedule_config or {},
        "viewport": flow.viewport or {},
        "version": flow.version,
        "input_contract": flow.input_contract or {},
        "output_contract": flow.output_contract or {},
        "risk_tier": flow.risk_tier,
        "default_timeout_seconds": flow.default_timeout_seconds,
        "allow_as_subflow": flow.allow_as_subflow,
        "required_tools": flow.required_tools or [],
        "nodes": [
            {
                "node_id": str(node.id),
                "node_type": node.node_type,
                "label": node.label,
                "position_x": node.position_x,
                "position_y": node.position_y,
                "config": node.config or {},
            }
            for node in ordered_nodes
        ],
        "edges": [
            {
                "edge_id": str(edge.id),
                "source_node_id": str(edge.source_node_id),
                "target_node_id": str(edge.target_node_id),
                "source_handle": edge.source_handle,
                "target_handle": edge.target_handle,
                "label": edge.label,
                "edge_type": edge.edge_type,
                "config": edge.config or {},
            }
            for edge in ordered_edges
        ],
    }
    if include_phases:
        payload["phases"] = [
            {
                "phase": index,
                "node_id": str(node.id),
                "label": node.label,
                "child_flow_id": (node.config or {}).get("child_flow_id"),
                "version_mode": (node.config or {}).get("child_flow_version_mode"),
                "child_flow_version": (node.config or {}).get("child_flow_version"),
                "execution_mode": (node.config or {}).get("execution_mode"),
                "timeout_seconds": (node.config or {}).get("timeout_seconds"),
                "on_failure": (node.config or {}).get("on_failure"),
                "input_mapping": (node.config or {}).get("input_mapping", {}),
                "output_mapping": (node.config or {}).get("output_mapping", {}),
            }
            for index, node in enumerate(
                (node for node in ordered_nodes if node.node_type == "subflow"),
                start=1,
            )
        ]
    return payload


WORKFLOW_TOOL_PERMISSIONS = {
    # list_agent_flows is intentionally omitted — it is read-only and should
    # always be available when the tool passes posture filtering, so the agent
    # can discover flow IDs before editing / deleting.
    "create_agent_flow": ("agentflow", "allow_create"),
    "edit_agent_flow": ("agentflow", "allow_edit"),
    "patch_agent_flow": ("agentflow", "allow_edit"),
    "set_agent_flow_status": ("agentflow", "allow_activate"),
    "delete_agent_flow": ("agentflow", "allow_delete"),
    "create_flow_stack": ("flow_stack", "allow_create"),
    "edit_flow_stack": ("flow_stack", "allow_edit"),
    "delete_flow_stack": ("flow_stack", "allow_delete"),
}

# Keep workflow mutation tools callable when their persistent permission is
# disabled. Medium-risk operations can be authorized by the operator's explicit
# instruction in the current turn; destructive deletes still pass through the
# interactive ToolGate confirmation.
WORKFLOW_ONE_TIME_CONFIRM_TOOLS = set(WORKFLOW_TOOL_PERMISSIONS)


async def _shogun_workflow_permission(db_session, category: str, permission: str) -> bool:
    """Read an explicit Shogun workflow permission; missing always means denied."""
    from sqlalchemy import select
    from shogun.db.models.agent import Agent
    from shogun.db.models.security_policy import SecurityPolicy

    result = await db_session.execute(
        select(Agent)
        .where(
            Agent.agent_type == "shogun",
            Agent.is_primary.is_(True),
            Agent.is_deleted.is_(False),
        )
        .limit(1)
    )
    shogun = result.scalar_one_or_none()
    if not shogun:
        return False
    custom = (shogun.bushido_settings or {}).get("custom_permissions")
    permissions = custom if custom else None
    if permissions is None and shogun.security_policy_id:
        policy = await db_session.get(SecurityPolicy, shogun.security_policy_id)
        permissions = policy.permissions if policy else None
    return bool((permissions or {}).get(category, {}).get(permission, False))


async def _shogun_workflow_activation_allowed(
    db_session,
    category: str,
    confirmed_permissions: set[tuple[str, str]],
) -> bool:
    """Allow lifecycle control autonomously at Campaign/Ronin, or by permission below it."""
    from shogun.services.posture_guard import get_posture_tool_filter

    posture = await get_posture_tool_filter()
    if posture.get("active_tier", "tactical") in {"campaign", "ronin"}:
        return True
    permission = (category, "allow_activate")
    return (
        permission in confirmed_permissions
        or await _shogun_workflow_permission(db_session, *permission)
    )


async def execute_native_tool(
    name: str,
    args: dict[str, Any],
    db_session,
    *,
    operator_confirmed_permissions: set[tuple[str, str]] | None = None,
) -> str:
    """Route tool execution from LLM to underlying services."""
    logger.info(f"Executing native skill: {name} with args {args}")
    confirmed_permissions = operator_confirmed_permissions or set()
    
    try:
        if name.startswith("file_"):
            import uuid

            from shogun.services.file_formats import (
                FileFormatError,
                FileFormatService,
                FileSafetyGate,
                registry,
            )
            from shogun.services.posture_guard import get_posture_permissions
            from shogun.services.tool_gate import (
                evaluate_tool_path_controls,
                get_local_filesystem_controls,
                get_tool_allowed_roots,
                get_toolgate_scope,
            )

            if name == "file_list_formats":
                return json.dumps({"status": "success", "formats": registry.formats()}, default=str)
            try:
                posture = await get_posture_permissions()
                scope = get_toolgate_scope(posture)["key"]
                filesystem = get_local_filesystem_controls(scope)
                configured_roots = get_tool_allowed_roots(name, scope)
                allowed_roots = (
                    configured_roots
                    if filesystem["enabled"]
                    else [*FileSafetyGate().allowed_roots, *configured_roots]
                )
                service = FileFormatService(db_session, allowed_roots=allowed_roots)
                if name == "file_compare":
                    result = await service.compare(str(args.get("left_path") or ""), str(args.get("right_path") or ""))
                    await db_session.commit()
                    return json.dumps(result, default=str, ensure_ascii=False)
                file_id = uuid.UUID(str(args["file_id"])) if args.get("file_id") else None
                if file_id and filesystem["enabled"]:
                    from shogun.db.models.file_artifact import FileArtifact

                    artifact = await db_session.get(FileArtifact, file_id)
                    allowed, _ = evaluate_tool_path_controls(
                        name,
                        {**args, "path": artifact.path if artifact else ""},
                        scope,
                    )
                    if not allowed:
                        raise FileFormatError(
                            "The shared filesystem policy denied this file operation.",
                            "policy_blocked",
                        )
                reference = {"path": args.get("path"), "file_id": file_id}
                if not reference["path"] and not file_id:
                    raise FileFormatError("path or file_id is required.", "invalid_request")
                if name == "file_detect_type":
                    result = await service.detect(**reference)
                elif name == "file_read":
                    result = await service.read(
                        **reference,
                        start=int(args.get("start") or 1),
                        end=int(args["end"]) if args.get("end") is not None else None,
                        sheet=args.get("sheet"),
                        max_chars=int(args.get("max_chars") or 40000),
                    )
                elif name in {"file_inspect", "file_preview", "file_schema"}:
                    result = await service.inspect(**reference, source=str(args.get("source") or "agent"))
                    if name == "file_preview":
                        result = {key: result[key] for key in ("status", "file_id", "format_id", "summary", "preview", "warnings", "audit_event_id")}
                    elif name == "file_schema":
                        result = {"status": "success", "file_id": result["file_id"], "format_id": result["format_id"],
                                  "summary": result["summary"], "schema": result["schema"], "warnings": result["warnings"]}
                    await db_session.commit()
                elif name == "file_query":
                    result = await service.query(str(args.get("query") or ""), limit=int(args.get("limit") or 100), **reference)
                elif name == "file_extract":
                    inspected = await service.inspect(**reference, source="agent")
                    result = {
                        "status": "success", "file_id": inspected["file_id"], "format_id": inspected["format_id"],
                        "operation": "extract", "summary": inspected["summary"], "data": inspected["data"],
                        "preview": inspected["preview"], "warnings": inspected["warnings"],
                        "artifacts": [], "audit_event_id": inspected["audit_event_id"],
                    }
                    await db_session.commit()
                elif name == "file_validate":
                    result = await service.validate(**reference)
                    await db_session.commit()
                elif name in {"file_transform", "file_export"}:
                    result = await service.transform(
                        str(args.get("target_format") or ""), args.get("output_filename"),
                        {"sanitize_formulas": args.get("sanitize_formulas", True)}, **reference,
                    )
                elif name == "file_archive_extract_selected":
                    result = await service.extract_archive(
                        list(args.get("members") or []), args.get("output_directory"),
                        bool(args.get("allow_overwrite", False)), True, **reference,
                    )
                elif name in {"file_index_profile", "file_index"}:
                    result = await service.index_profile(uuid.UUID(str(args.get("agent_id") or "")), args.get("title"), **reference)
                else:
                    raise FileFormatError(f"Unknown file tool: {name}", "unsupported_operation")
                return json.dumps(result, default=str, ensure_ascii=False)
            except (FileFormatError, ValueError) as exc:
                await db_session.rollback()
                logger.warning("File tool request rejected: %s", exc)
                return json.dumps({"status": "failed", "error_type": getattr(exc, "error_type", "invalid_request"),
                                   "message": "The file operation could not be completed.", "warnings": [], "artifacts": []})

        if name in {"get_recent_images", "get_image_metadata", "describe_image", "inspect_image", "extract_image_text", "compare_images", "attach_image_to_stack"}:
            import uuid
            from shogun.services.visual_intake import VisualIntakeError, VisualIntakeService

            visual = VisualIntakeService(db_session)
            if name == "get_recent_images":
                images = await visual.recent(
                    limit=max(1, min(int(args.get("limit", 5)), 20)),
                    chat_session_id=args.get("chat_session_id"),
                )
                return json.dumps({"status": "success", "images": [visual._public(item) for item in images]})

            if name == "compare_images":
                try:
                    first = await visual.get(uuid.UUID(str(args.get("first_artifact_id", ""))))
                    second = await visual.get(uuid.UUID(str(args.get("second_artifact_id", ""))))
                    if not first or not second:
                        raise VisualIntakeError("Both image artifacts are required.")
                    analysis = await visual.compare(first, second, str(args.get("prompt") or "Compare these images and explain material differences."))
                    await db_session.commit()
                    return json.dumps({"status": "success", "result": analysis.result_text, "model": analysis.model_used})
                except (ValueError, VisualIntakeError) as exc:
                    logger.warning("Visual analysis request rejected: %s", exc)
                    return json.dumps({"status": "error", "message": "The visual analysis request could not be completed."})

            try:
                artifact_id = uuid.UUID(str(args.get("artifact_id", "")))
            except ValueError:
                return json.dumps({"status": "error", "message": "artifact_id must be a valid UUID."})
            artifact = await visual.get(artifact_id)
            if not artifact:
                return json.dumps({"status": "error", "message": "Image artifact not found."})
            if name == "get_image_metadata":
                return json.dumps({"status": "success", "image": visual._public(artifact)})
            if name == "attach_image_to_stack":
                try:
                    linked = await visual.attach_to_stack(artifact, uuid.UUID(str(args.get("stack_run_id", ""))))
                    await db_session.commit()
                    return json.dumps({"status": "success", "stack_artifact_id": str(linked.id)})
                except (ValueError, VisualIntakeError) as exc:
                    logger.warning("Visual stack request rejected: %s", exc)
                    return json.dumps({"status": "error", "message": "The visual stack request could not be completed."})

            default_prompt = (
                "Describe this image accurately, including visible text and important details."
                if name == "describe_image" else
                "Transcribe all visible text faithfully and preserve reading order."
                if name == "extract_image_text" else
                "Inspect the requested image detail and answer with visual evidence."
            )
            prompt = str(args.get("prompt") or default_prompt)
            try:
                analysis = await visual.analyze(artifact, prompt, "extract_text" if name == "extract_image_text" else "describe" if name == "describe_image" else "inspect")
                await db_session.commit()
                return json.dumps({
                    "status": "success", "artifact_id": str(artifact.id), "result": analysis.result_text,
                    "model": analysis.model_used, "provider": analysis.provider_used,
                })
            except VisualIntakeError as exc:
                logger.warning("Visual intake request rejected: %s", exc)
                return json.dumps({"status": "error", "message": "The visual intake request could not be completed."})

        if name == "spawn_samurai":
            # ── Posture enforcement: kill switch + subagent limit ──
            from shogun.services.posture_guard import check_kill_switch, check_subagent_limit_soft
            try:
                from shogun.api.security import _get_agent_posture
                posture = await _get_agent_posture()
                if posture.get("kill_switch_active", False):
                    return json.dumps({
                        "status": "error",
                        "message": "⛩️ HARAKIRI is active — all AI operations are suspended. Cannot spawn agents."
                    })
            except Exception:
                pass
            limit_error = await check_subagent_limit_soft()
            if limit_error:
                return json.dumps({"status": "error", "message": limit_error})

            from shogun.services.agent_service import AgentService
            svc = AgentService(db_session)
            # Create the agent via service directly
            new_agent = await svc.create(
                agent_type="samurai",
                name=args["name"],
                slug=args["name"].lower().replace(" ", "-"),
                description=f"{args['role']} - {args['persona']}",
                status="active",
                spawn_policy="manual" # Or derived...
            )

            # ── Inject Kaizen governance into the new agent ──────────
            try:
                from shogun.api.kaizen import build_governance_prompt_block
                governance_block = build_governance_prompt_block()
                bs = dict(new_agent.bushido_settings) if new_agent.bushido_settings else {}
                bs["governance_prompt"] = governance_block
                new_agent.bushido_settings = bs
            except Exception as gov_err:
                logger.warning("Failed to inject governance into spawned Samurai: %s", gov_err)

            # Update cache context so next stream shows +1 agent
            import time
            from shogun.api.agents import _CTX_CACHE
            _CTX_CACHE["ts"] = 0 
            
            await db_session.commit()
            
            return json.dumps({
                "status": "success", 
                "message": f"Samurai '{args['name']}' successfully spawned at tier '{args['security_tier']}' with Kaizen governance applied."
            })
            
        elif name == "echo_tool":
            return json.dumps({
                "status": "success",
                "echoed_text": args.get("text", "")
            })
            
        elif name == "tool_list_debug":
            return json.dumps({
                "status": "success",
                "available_tools": [t["function"]["name"] for t in NATIVE_TOOLS]
            })
            
        elif name == "list_available_models":
            from sqlalchemy import select
            from shogun.db.models.model_provider import ModelProvider
            
            providers = await db_session.execute(
                select(ModelProvider).where(ModelProvider.status == "connected")
            )
            
            res = {}
            for p in providers.scalars().all():
                models = p.config.get("models", [])
                if p.config.get("model_id"):
                    models.append(p.config.get("model_id"))
                res[f"{p.name} (UUID: {p.id})"] = models
                
            return json.dumps({
                "status": "success",
                "available_providers_and_models": res
            })
            
        elif name == "update_model_settings":
            from shogun.db.models.agent import Agent
            from sqlalchemy import select
            
            shogun_res = await db_session.execute(
                select(Agent).where(
                    Agent.agent_type == "shogun",
                    Agent.is_primary == True,
                    Agent.is_deleted == False
                ).limit(1)
            )
            shogun = shogun_res.scalar_one_or_none()
            if not shogun:
                return json.dumps({"status": "error", "message": "Primary Shogun not found."})
                
            bushido = dict(shogun.bushido_settings) if shogun.bushido_settings else {}
            bushido["primary_model"] = args["primary_model"]
            if "fallback_models" in args:
                bushido["fallback_models"] = args["fallback_models"]
                
            shogun.bushido_settings = bushido
            db_session.add(shogun)
            await db_session.commit()
            
            return json.dumps({
                "status": "success", 
                "message": f"Successfully updated primary model to {args['primary_model']}."
            })

        elif name.startswith("model_router_"):
            from shogun.schemas.model_router import ModelRouteRequest, ModelUsageCreate
            from shogun.services.model_router import ModelRoutingService, ModelUsageLogger

            router = ModelRoutingService(db_session)
            if name == "model_router_get_active_profile":
                profile = await router.active_profile()
                return json.dumps({"status": "success", "profile": profile.name, "profile_id": str(profile.id)})
            if name == "model_router_log_outcome":
                usage = await ModelUsageLogger(db_session).log(ModelUsageCreate(
                    routing_decision_id=args.get("routing_decision_id"), model_id=args["model_id"],
                    provider=args["provider"], input_tokens=int(args.get("input_tokens", 0)),
                    output_tokens=int(args.get("output_tokens", 0)), latency_ms=int(args.get("latency_ms", 0)),
                    success=bool(args.get("success", True)), error_json={"message": args.get("error")} if args.get("error") else {},
                ))
                await db_session.commit()
                return json.dumps({"status": "success", "usage_event_id": str(usage.id)})
            escalation = int(args.get("escalation_level", 1)) if name == "model_router_request_escalation" else 0
            request = ModelRouteRequest(
                prompt=str(args.get("prompt", "")), task_type=args.get("task_type"),
                required_capabilities=args.get("required_capabilities") or ["chat"],
                complexity_override=args.get("complexity"), profile_override=args.get("profile"),
                escalation_level=escalation,
                exclude_model_ids=[args["previous_model"]] if args.get("previous_model") else [],
                verification_status="failed" if escalation else None,
                metadata={"requested_by": "shogun_agent"},
            )
            result = await router.route(request, persist=name != "model_router_preview_route")
            if name != "model_router_preview_route": await db_session.commit()
            return json.dumps({"status": "success", **result.payload}, default=str)

        elif name in {"reminder_board_add", "reminder_board_list", "reminder_board_update"}:
            import uuid
            from datetime import datetime, timedelta, timezone

            from sqlalchemy import select
            from shogun.db.models.agent import Agent
            from shogun.services.reminder_service import ReminderService

            shogun = await db_session.scalar(
                select(Agent).where(
                    Agent.agent_type == "shogun",
                    Agent.is_primary.is_(True),
                    Agent.is_deleted.is_(False),
                ).limit(1)
            )
            if not shogun:
                return json.dumps({"status": "error", "message": "Primary Shogun not found."})
            service = ReminderService(db_session)
            if name == "reminder_board_list":
                limit = min(50, max(1, int(args.get("limit", 10))))
                context = await service.prompt_context(agent_id=shogun.id, limit=limit)
                await db_session.commit()
                return json.dumps({"status": "success", "board": context})
            if name == "reminder_board_update":
                try:
                    task_id = uuid.UUID(str(args["task_id"]))
                    task = await service.transition(
                        task_id,
                        str(args["action"]),
                        snooze_minutes=int(args.get("snooze_minutes", 10)),
                    )
                except (ValueError, KeyError) as exc:
                    logger.warning("Invalid Reminder Board update request", exc_info=exc)
                    return json.dumps({"status": "error", "message": "Invalid Reminder Board update request."})
                if not task:
                    return json.dumps({"status": "error", "message": "Reminder Board item not found."})
                await db_session.commit()
                return json.dumps({"status": "success", "task_id": str(task.id), "state": task.status})

            now = datetime.now(timezone.utc)
            try:
                title = str(args["title"]).strip()
                reason = str(args["reason"]).strip()
                item_type = str(args.get("item_type", "obligation"))
                confidence = float(args.get("confidence", 1.0))
                priority = int(args.get("priority", 50))
                if not title or not reason:
                    raise ValueError("title and reason are required")
                if item_type not in {"obligation", "follow_up", "check", "deferred", "reminder"}:
                    raise ValueError("unsupported item_type")
                if not 0 <= confidence <= 1 or not 0 <= priority <= 100:
                    raise ValueError("confidence or priority is outside its allowed range")
                if args.get("review_at"):
                    review_at = datetime.fromisoformat(str(args["review_at"]).replace("Z", "+00:00"))
                    if review_at.tzinfo is None:
                        review_at = review_at.replace(tzinfo=timezone.utc)
                else:
                    review_at = now + timedelta(minutes=int(args["review_in_minutes"]))
                if review_at <= now:
                    raise ValueError("review time must be in the future")
                expires_at = now + timedelta(hours=int(args.get("expires_in_hours", 168)))
                if expires_at <= review_at:
                    expires_at = review_at + timedelta(days=7)
                task, created = await service.create_ai_obligation(
                    title=title,
                    description=args.get("description"),
                    item_type=item_type,
                    review_at=review_at,
                    reason=reason,
                    confidence=confidence,
                    expires_at=expires_at,
                    source_message_id=args.get("source_message_id"),
                    priority=priority,
                    agent_id=shogun.id,
                )
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("Invalid Reminder Board item", exc_info=exc)
                return json.dumps({"status": "error", "message": "Invalid Reminder Board item."})
            await db_session.commit()
            return json.dumps({
                "status": "success",
                "created": created,
                "task_id": str(task.id),
                "message": "Obligation recorded." if created else "Matching unresolved obligation already exists.",
            })

        elif name == "store_memory":
            from sqlalchemy import select

            from shogun.db.models.agent import Agent
            from shogun.services.event_logger import EventLogger
            from shogun.services.memory_governance import (
                MemoryDecayError,
                validate_agent_decay_request,
            )
            from shogun.services.memory_service import MemoryService

            # Get the primary Shogun agent ID to associate the memory with
            shogun_res = await db_session.execute(
                select(Agent).where(
                    Agent.agent_type == "shogun",
                    Agent.is_primary.is_(True),
                    Agent.is_deleted.is_(False),
                ).limit(1)
            )
            shogun = shogun_res.scalar_one_or_none()
            if not shogun:
                return json.dumps({"status": "error", "message": "Primary Shogun not found."})

            mem_svc = MemoryService(db_session)
            importance = float(args.get("importance", 0.7))
            explicit_decay = args.get("decay_type")
            try:
                explicit_decay = validate_agent_decay_request(
                    explicit_decay,
                    importance=importance,
                    memory_type=args["memory_type"],
                )
            except MemoryDecayError as exc:
                await EventLogger.emit(
                    category="memory",
                    event_type=(
                        "memory.decay_type.invalid"
                        if exc.code == "invalid_decay_type"
                        else "memory.sticky.rejected"
                    ),
                    action="Rejected store_memory decay request",
                    result="rejected",
                    agent_id=str(shogun.id),
                    tool_name="store_memory",
                    detail={
                        "decay_type": args.get("decay_type"),
                        "memory_type": args.get("memory_type"),
                        "importance": importance,
                        "reason": exc.code,
                    },
                    db_session=db_session,
                )
                await db_session.commit()
                return json.dumps(exc.as_dict())

            if explicit_decay is None:
                # Preserve the historical tool behavior when decay_type is omitted.
                is_pinned = importance >= 0.85
                decay = "pinned" if is_pinned else ("slow" if importance >= 0.7 else "medium")
            else:
                decay = explicit_decay
                is_pinned = decay == "pinned"

            record = await mem_svc.create_memory(
                memory_type=args["memory_type"],
                agent_id=shogun.id,
                title=args["title"],
                content=args["content"],
                importance_score=importance,
                relevance_score=0.9,
                confidence_score=0.8,
                decay_class=decay,
                is_pinned=is_pinned,
                tags=args.get("tags") or [],
            )
            await EventLogger.emit(
                category="memory",
                event_type="memory.stored",
                action=f"Stored memory '{args['title']}' through store_memory",
                agent_id=str(shogun.id),
                tool_name="store_memory",
                memory_ids=[str(record.id)],
                detail={
                    "memory_id": str(record.id),
                    "memory_type": args["memory_type"],
                    "importance": importance,
                    "decay_type": decay,
                    "tags": args.get("tags") or [],
                    "source": "store_memory_tool",
                },
                db_session=db_session,
            )
            await db_session.commit()

            return json.dumps({
                "status": "success",
                "message": f"Memory '{args['title']}' stored in Archives (type={args['memory_type']}, importance={importance}, decay_type={decay}, pinned={is_pinned}).",
                "memory_id": str(record.id),
                "decay_type": decay,
            })

        elif name == "fetch_inbox":
            from shogun.services.email_service import EmailService
            email_svc = EmailService(db_session)
            folder = args.get("folder", "INBOX")
            page = args.get("page", 1)
            per_page = args.get("per_page", 10)
            result = await email_svc.fetch_messages(folder=folder, page=page, per_page=per_page)
            # Trim to essential fields for token efficiency
            messages_summary = []
            for msg in result.get("messages", []):
                messages_summary.append({
                    "uid": msg["uid"],
                    "from": msg["from_address"],
                    "to": msg["to_address"],
                    "subject": msg["subject"],
                    "date": msg["date"],
                    "preview": msg.get("body_preview", "")[:120],
                    "is_read": msg["is_read"],
                })
            return json.dumps({
                "status": "success",
                "folder": folder,
                "total": result.get("total", 0),
                "page": page,
                "messages": messages_summary,
            })

        elif name == "read_email":
            from shogun.services.email_service import EmailService
            email_svc = EmailService(db_session)
            uid = args["uid"]
            folder = args.get("folder", "INBOX")
            result = await email_svc.fetch_message(uid=uid, folder=folder)
            return json.dumps({
                "status": "success",
                "uid": result["uid"],
                "from": result["from_address"],
                "to": result["to_address"],
                "subject": result["subject"],
                "date": result["date"],
                "body_text": result.get("body_text", "")[:3000],
                "has_attachments": result.get("has_attachments", False),
                "attachments": result.get("attachments", []),
            })

        elif name == "send_email":
            from shogun.services.email_service import EmailService
            from shogun.schemas.channels import EmailComposeRequest
            email_svc = EmailService(db_session)
            compose = EmailComposeRequest(
                to_address=args["to_address"],
                subject=args["subject"],
                body=args["body"],
                cc_address=args.get("cc_address"),
                bcc_address=args.get("bcc_address"),
            )
            result = await email_svc.send_email(compose)
            return json.dumps({
                "status": "success" if result.get("ok") else "error",
                "message": result.get("message", "Email operation completed."),
            })

        elif name == "send_telegram_message":
            from shogun.services.notification_service import send_channel_message
            from shogun.services.telegram_routing_context import current_telegram_routing

            message_thread_id = args.get("message_thread_id")
            routing = current_telegram_routing() or {}
            if message_thread_id is None and str(args["chat_id"]) == str(routing.get("chat_id")):
                message_thread_id = routing.get("message_thread_id")
            result = await send_channel_message(
                str(args["text"]),
                channel="telegram",
                telegram_chat_ids=[str(int(args["chat_id"]))],
                telegram_message_thread_id=(
                    int(message_thread_id) if message_thread_id is not None else None
                ),
            )
            telegram_result = result.get("telegram", {})
            return json.dumps({
                "status": "success" if telegram_result.get("ok") else "error",
                **telegram_result,
            })

        elif name == "list_calendar_events":
            from shogun.services.calendar_service import CalendarService
            from datetime import datetime, timedelta
            cal_svc = CalendarService(db_session)
            start_str = args.get("start_date")
            end_str = args.get("end_date")
            if start_str:
                start_dt = datetime.fromisoformat(start_str)
            else:
                start_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            if end_str:
                end_dt = datetime.fromisoformat(end_str)
            else:
                end_dt = start_dt + timedelta(days=7)
            events = await cal_svc.get_events(start_date=start_dt, end_date=end_dt)
            events_summary = []
            for ev in events:
                events_summary.append({
                    "id": ev.id,
                    "title": ev.title,
                    "start": str(ev.start),
                    "end": str(ev.end),
                    "location": ev.location,
                    "description": (ev.description or "")[:200],
                    "all_day": ev.all_day,
                })
            return json.dumps({
                "status": "success",
                "range": f"{start_dt.isoformat()} to {end_dt.isoformat()}",
                "count": len(events_summary),
                "events": events_summary,
            })

        elif name == "create_calendar_event":
            from shogun.services.calendar_service import CalendarService
            from shogun.schemas.channels import CalendarEventCreate
            from datetime import datetime
            cal_svc = CalendarService(db_session)
            event_data = CalendarEventCreate(
                title=args["title"],
                start=datetime.fromisoformat(args["start"]),
                end=datetime.fromisoformat(args["end"]),
                location=args.get("location"),
                description=args.get("description"),
                all_day=args.get("all_day", False),
            )
            result = await cal_svc.create_event(event_data)
            return json.dumps({
                "status": "success",
                "message": f"Calendar event '{args['title']}' created successfully.",
                "event_id": result.id,
            })

        elif name == "list_cron_jobs":
            from sqlalchemy import select

            from shogun.db.models.agent_flow import AgentFlow
            from shogun.scheduler import scheduler_job_snapshot
            from shogun.services.bushido_service import BushidoScheduleService

            sched_svc = BushidoScheduleService(db_session)
            records, total = await sched_svc.get_all(limit=200)
            jobs = []
            for r in records:
                jobs.append({
                    "id": str(r.id),
                    "name": r.name,
                    "job_type": r.job_type,
                    "frequency": r.frequency,
                    "schedule_time": r.schedule_time,
                    "is_enabled": r.is_enabled,
                    "is_preset": r.is_preset,
                    "next_run_at": str(r.next_run_at) if r.next_run_at else None,
                    "last_run_at": str(r.last_run_at) if r.last_run_at else None,
                    "source": "bushido",
                })

            flow_result = await db_session.execute(
                select(AgentFlow).where(
                    AgentFlow.trigger_type == "scheduled",
                    AgentFlow.is_deleted.is_(False),
                )
            )
            flows = list(flow_result.scalars().all())
            for flow in flows:
                config = flow.schedule_config or {}
                runtime = scheduler_job_snapshot(f"agentflow_{flow.id}")
                jobs.append({
                    "id": str(flow.id),
                    "name": flow.name,
                    "job_type": "agent_flow",
                    "frequency": config.get("frequency", "nightly"),
                    "schedule_time": config.get("schedule_time", "02:00"),
                    "is_enabled": flow.status == "active",
                    "is_preset": False,
                    "next_run_at": (
                        str(runtime["next_run_at"])
                        if runtime["next_run_at"]
                        else None
                    ),
                    "last_run_at": None,
                    "source": "agent_flow",
                    "scheduler_registered": runtime["scheduler_registered"],
                    "scheduler_job_id": runtime["scheduler_job_id"],
                })
            return json.dumps({
                "status": "success",
                "total": total + len(flows),
                "schedules": jobs,
            })

        elif name == "create_cron_job":
            from shogun.services.bushido_service import BushidoScheduleService
            from shogun.schemas.bushido import BushidoScheduleCreate
            sched_svc = BushidoScheduleService(db_session)
            create_data = BushidoScheduleCreate(
                name=args["name"],
                job_type=args["job_type"],
                frequency=args.get("frequency", "nightly"),
                schedule_time=args.get("schedule_time", "02:00"),
                task_instruction=args.get("task_instruction"),
                is_enabled=args.get("is_enabled", True),
            )
            record = await sched_svc.create(**create_data.model_dump())
            # Register with APScheduler
            try:
                from shogun.scheduler import register_schedule
                await register_schedule(record)
            except Exception as exc:
                logger.warning("Scheduler registration failed: %s", exc)
            return json.dumps({
                "status": "success",
                "message": f"Cron job '{args['name']}' ({args['job_type']}) created and registered.",
                "schedule_id": str(record.id),
            })

        elif name == "delete_cron_job":
            from shogun.services.bushido_service import BushidoScheduleService
            import uuid as _uuid
            sched_svc = BushidoScheduleService(db_session)
            schedule_id = _uuid.UUID(args["schedule_id"])
            record = await sched_svc.get_by_id(schedule_id)
            if not record:
                return json.dumps({"status": "error", "message": "Schedule not found."})
            if record.is_preset:
                return json.dumps({"status": "error", "message": "Preset schedules cannot be deleted. Use toggle to disable them."})
            # Deregister from APScheduler
            try:
                from shogun.scheduler import deregister_schedule
                await deregister_schedule(schedule_id)
            except Exception as exc:
                logger.warning("Scheduler deregistration failed: %s", exc)
            await sched_svc.delete(schedule_id)
            return json.dumps({
                "status": "success",
                "message": f"Cron job '{record.name}' deleted successfully.",
            })

        # ── Order 15: Skill Lifecycle Tool Handlers ─────────────
        elif name == "dojo_author_skill":
            from shogun.services.skill_authoring_service import SkillAuthoringService
            svc = SkillAuthoringService(db_session)
            result = await svc.create_skill_draft(
                name=args["name"],
                category=args.get("category", "general"),
                description=args.get("description", ""),
                body_text=args.get("body_text", ""),
                triggers=args.get("triggers", []),
                risk_tier=args.get("risk_tier", "low"),
                requires_tools=args.get("requires_tools", []),
                tags=args.get("tags", []),
                version=args.get("version", "1.0.0"),
            )
            # Auto-generate validation tests
            try:
                skill_uuid = uuid.UUID(result["skill_id"])
                tests = await svc.generate_validation_tests(skill_uuid)
                result["tests_created"] = len(tests)
            except Exception:
                result["tests_created"] = 0
            await db_session.commit()
            return json.dumps(result)

        elif name == "dojo_validate_skill":
            from shogun.services.skill_quality_gate import SkillQualityGateService
            svc = SkillQualityGateService(db_session)
            skill_uuid = uuid.UUID(args["skill_id"])
            result = await svc.run_quality_gate(skill_uuid)

            # Transition to 'validated' if passed
            if result.get("status") == "passed":
                skill = await db_session.get(Skill, skill_uuid)
                if skill and skill.lifecycle_state in ("draft", "optimized"):
                    skill.lifecycle_state = "validated"
                    result["lifecycle_state"] = "validated"
            await db_session.commit()
            return json.dumps(result)

        elif name == "dojo_publish_skill":
            from shogun.services.skill_publishing import SkillPublishingService
            svc = SkillPublishingService(db_session)
            skill_uuid = uuid.UUID(args["skill_id"])
            result = await svc.publish(
                skill_uuid,
                provider_name=args.get("provider", "local"),
                skip_quality_gate=args.get("skip_quality_gate", False),
            )
            await db_session.commit()
            return json.dumps(result)

        elif name == "list_agent_flows":
            # ── Read-only: list existing flows ──
            from shogun.services.agent_flow_service import AgentFlowService

            flow_svc = AgentFlowService(db_session)

            # Parse parameters
            status_filter = args.get("status", "all")
            if status_filter == "all":
                status_filter = None
            search_filter = args.get("search") or None
            page = max(1, int(args.get("page", 1)))
            per_page = max(1, min(100, int(args.get("per_page", 20))))
            offset = (page - 1) * per_page

            records, total = await flow_svc.list_flows(
                status=status_filter,
                search=search_filter,
                offset=offset,
                limit=per_page,
            )

            flows_out = []
            for r in records:
                # Determine stack membership by checking subflow nodes that reference this flow
                is_stack_member = r.flow_type == "standard" and any(
                    n.node_type == "subflow" for n in (r.nodes or [])
                )
                flows_out.append({
                    "flow_id": str(r.id),
                    "name": r.name,
                    "description": r.description or "",
                    "status": r.status,
                    "flow_type": r.flow_type,
                    "node_count": len(r.nodes) if r.nodes else 0,
                    "edge_count": len(r.edges) if r.edges else 0,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    "is_stack_member": is_stack_member,
                })

            response = {
                "status": "success",
                "flows": flows_out,
                "total": total,
                "page": page,
                "per_page": per_page,
            }

            if total == 0:
                # A successful empty query must never be misreported as a
                # ToolGate denial. Include enough non-secret identity data to
                # detect a UI/Telegram split across databases or instances.
                import hashlib

                from sqlalchemy import func, select
                from shogun.db.models.agent_flow import AgentFlow

                visible_total = await db_session.scalar(
                    select(func.count(AgentFlow.id)).where(
                        AgentFlow.is_deleted == False,
                        AgentFlow.is_template == False,
                    )
                )
                template_total = await db_session.scalar(
                    select(func.count(AgentFlow.id)).where(
                        AgentFlow.is_deleted == False,
                        AgentFlow.is_template == True,
                    )
                )
                deleted_total = await db_session.scalar(
                    select(func.count(AgentFlow.id)).where(AgentFlow.is_deleted == True)
                )
                bind_url = db_session.get_bind().url
                identity_source = "|".join((
                    bind_url.get_backend_name(),
                    bind_url.host or "local",
                    str(bind_url.port or ""),
                    bind_url.database or "memory",
                ))
                database_fingerprint = hashlib.sha256(
                    identity_source.encode("utf-8")
                ).hexdigest()[:12]
                has_filters = status_filter is not None or search_filter is not None
                if visible_total and has_filters:
                    explanation = (
                        "The query succeeded, but its status/search filters matched no flows. "
                        "Retry without filters before concluding that the flow is absent."
                    )
                elif visible_total:
                    explanation = (
                        "The query page is empty even though this database contains visible flows. "
                        "Return to page 1."
                    )
                else:
                    explanation = (
                        "The query succeeded, but this Shogun database contains no visible AgentFlows. "
                        "If the UI shows flows, Telegram and the UI are connected to different "
                        "Shogun instances or databases. A UUID will not bypass that mismatch."
                    )
                response["diagnostic"] = {
                    "result_kind": "successful_empty_query",
                    "toolgate_blocked": False,
                    "database_backend": bind_url.get_backend_name(),
                    "database_fingerprint": database_fingerprint,
                    "visible_unfiltered_total": int(visible_total or 0),
                    "excluded_template_total": int(template_total or 0),
                    "excluded_deleted_total": int(deleted_total or 0),
                    "explanation": explanation,
                    "required_action": (
                        "Do not create a replacement flow and do not speculate that ToolGate blocked "
                        "the query. Report this diagnostic and resolve the database/instance mismatch."
                    ),
                }

            return json.dumps(response)

        elif name in {"get_agent_flow", "get_flow_stack"}:
            import uuid as _uuid

            from shogun.services.agent_flow_service import AgentFlowService

            argument_name = "flow_id" if name == "get_agent_flow" else "flow_stack_id"
            try:
                flow_id = _uuid.UUID(str(args[argument_name]))
            except (KeyError, ValueError):
                return json.dumps({"status": "error", "message": f"{argument_name} must be a valid UUID."})
            flow = await AgentFlowService(db_session).get_flow_full(flow_id)
            expected_type = "standard" if name == "get_agent_flow" else "stack"
            if not flow or flow.flow_type != expected_type or flow.is_template:
                label = "AgentFlow" if expected_type == "standard" else "Flow Stack"
                return json.dumps({"status": "error", "message": f"{label} not found."})
            return json.dumps(
                {
                    "status": "success",
                    "flow": _serialize_flow_for_agent(flow, include_phases=expected_type == "stack"),
                },
                default=str,
                ensure_ascii=False,
            )

        elif name == "set_agent_flow_status":
            import uuid as _uuid

            from shogun.api.agent_flow import _sync_live_flow_schedule
            from shogun.services.agent_flow_service import AgentFlowService
            from shogun.services.posture_guard import get_posture_tool_filter

            posture = await get_posture_tool_filter()
            if not posture.get("agentflow_create", False):
                return json.dumps({
                    "status": "error",
                    "message": "AgentFlow lifecycle control requires Tactical, Campaign, or Ronin posture.",
                })
            if not await _shogun_workflow_activation_allowed(
                db_session, "agentflow", confirmed_permissions
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "agentflow.allow_activate",
                    "message": (
                        "AgentFlow activation and pausing require Campaign/Ronin posture, "
                        "the persistent Allow Activate permission, or one-time approval."
                    ),
                })
            try:
                flow_id = _uuid.UUID(str(args["flow_id"]))
            except (KeyError, ValueError):
                return json.dumps({"status": "error", "message": "flow_id must be a valid UUID."})
            requested_status = str(args.get("status") or "").lower()
            if requested_status not in {"active", "paused"}:
                return json.dumps({
                    "status": "error",
                    "message": "status must be 'active' or 'paused'.",
                })
            flow_svc = AgentFlowService(db_session)
            flow = await flow_svc.get_flow_full(flow_id)
            if not flow or flow.flow_type != "standard" or flow.is_template:
                return json.dumps({"status": "error", "message": "AgentFlow not found."})
            updated = await flow_svc.update_status(flow_id, requested_status)
            try:
                await _sync_live_flow_schedule(updated)
                await db_session.commit()
            except Exception as exc:
                await db_session.rollback()
                logger.exception("AgentFlow lifecycle synchronization failed")
                return json.dumps({
                    "status": "error",
                    "message": "AgentFlow lifecycle change could not be synchronized.",
                })
            return json.dumps({
                "status": "success",
                "message": f"AgentFlow '{updated.name}' is now {requested_status}.",
                "flow_id": str(updated.id),
                "flow_status": requested_status,
                "posture": posture.get("active_tier", "tactical"),
            })

        elif name == "create_agent_flow":
            # ── Posture enforcement: requires agentflow_autonomous ──
            try:
                from shogun.services.posture_guard import get_posture_tool_filter
                posture = await get_posture_tool_filter()
                if not posture.get("agentflow_create", False):
                    return json.dumps({
                        "status": "error",
                        "message": "AgentFlow creation is only available in Tactical, Campaign, or Ronin posture."
                    })
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the AgentFlow posture permission."})
            create_permission = ("agentflow", "allow_create")
            if (
                create_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *create_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "agentflow.allow_create",
                    "message": (
                        "AgentFlow creation requires an explicit operator instruction, a one-time "
                        "ToolGate approval, or the persistent AgentFlow Allow Create permission."
                    ),
                })
            activate = bool(args.get("activate", False))
            if activate and not await _shogun_workflow_activation_allowed(
                db_session, "agentflow", confirmed_permissions
            ):
                return json.dumps({"status": "error", "message": "Shogun may create this AgentFlow as a draft, but AgentFlow activation permission is disabled."})

            from shogun.api.agent_flow import _normalized_schedule_config
            from shogun.services.agent_flow_service import AgentFlowService
            flow_svc = AgentFlowService(db_session)

            # Create the flow
            flow_name = args.get("name", "Untitled Flow")
            flow_desc = args.get("description", "Auto-generated by Shogun")
            requested_nodes = list(args.get("nodes", []))
            input_config = next(
                (
                    dict(node.get("config") or {})
                    for node in requested_nodes
                    if node.get("node_type") == "input"
                ),
                {},
            )
            input_type = str(input_config.get("input_type") or "manual").lower()
            trigger_type = input_type if input_type in {"scheduled", "api", "event"} else "manual"
            schedule_config: dict = {}
            if trigger_type == "scheduled":
                schedule_config = _normalized_schedule_config({
                    "frequency": input_config.get("schedule_frequency", "nightly"),
                    "schedule_time": input_config.get("schedule_time", "07:00"),
                    "schedule_days": input_config.get("schedule_days"),
                    "schedule_day": input_config.get("schedule_day"),
                    "minute_offset": input_config.get("schedule_minute_offset", 0),
                })
            flow = await flow_svc.create(
                name=flow_name,
                description=flow_desc,
                trigger_type=trigger_type,
                schedule_config=schedule_config,
            )

            # Build node and edge payloads
            nodes_data = []
            for i, n in enumerate(requested_nodes):
                nodes_data.append({
                    "id": n.get("id", f"node-auto-{i}"),
                    "node_type": n.get("node_type", "samurai"),
                    "label": n.get("label", f"Node {i+1}"),
                    "position_x": n.get("position_x", 100 + i * 300),
                    "position_y": n.get("position_y", 200),
                    "config": n.get("config", {}),
                })

            edges_data = []
            for j, e in enumerate(args.get("edges", [])):
                edges_data.append({
                    "id": f"edge-auto-{j}",
                    "source_node_id": e.get("source_node_id", ""),
                    "target_node_id": e.get("target_node_id", ""),
                    "source_handle": e.get("source_handle"),
                    "target_handle": e.get("target_handle"),
                    "label": e.get("label"),
                    "edge_type": e.get("edge_type", "default"),
                    "config": {},
                })

            # Save the graph
            await flow_svc.save_flow_graph(
                flow_id=flow.id,
                nodes_data=nodes_data,
                edges_data=edges_data,
                viewport={"x": 0, "y": 0, "zoom": 0.8},
            )
            if activate:
                from shogun.api.agent_flow import _sync_live_flow_schedule

                activated = await flow_svc.update_status(flow.id, "active")
                await _sync_live_flow_schedule(activated)

            await db_session.commit()

            return json.dumps({
                "status": "success",
                "message": f"Agent Flow '{flow_name}' created with {len(nodes_data)} nodes and {len(edges_data)} edges. Open the Samurai Network → Agent Flow tab to view and run it.",
                "flow_id": str(flow.id),
                "flow_status": "active" if activate else "draft",
            })

        elif name == "patch_agent_flow":
            try:
                from shogun.services.posture_guard import get_posture_tool_filter

                posture = await get_posture_tool_filter()
                if not posture.get("agentflow_create", False):
                    return json.dumps({
                        "status": "error",
                        "message": "AgentFlow editing is only available in Tactical, Campaign, or Ronin posture.",
                    })
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the AgentFlow posture permission."})
            edit_permission = ("agentflow", "allow_edit")
            if (
                edit_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *edit_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "agentflow.allow_edit",
                    "message": (
                        "AgentFlow editing is disabled. Enable AgentFlow > Allow Edit in "
                        "Shogun Profile > Permissions, or approve the one-time inline "
                        "ToolGate confirmation when patch_agent_flow is called from Chat."
                    ),
                })

            import uuid as _uuid

            from shogun.services.agent_flow_service import AgentFlowService

            try:
                flow_id = _uuid.UUID(str(args["flow_id"]))
                flow_svc = AgentFlowService(db_session)
                flow = await flow_svc.get_flow_full(flow_id)
                if not flow or flow.flow_type != "standard" or flow.is_template:
                    return json.dumps({"status": "error", "message": "Editable AgentFlow not found."})
                from shogun.api.agent_flow import _sync_live_flow_schedule

                updated = await flow_svc.patch_flow_graph(
                    flow_id,
                    node_operations=list(args.get("node_operations") or []),
                    edge_operations=list(args.get("edge_operations") or []),
                )
                await _sync_live_flow_schedule(updated)
                await db_session.commit()
            except (KeyError, ValueError, TypeError) as exc:
                await db_session.rollback()
                logger.warning("AgentFlow patch request rejected: %s", exc)
                return json.dumps({"status": "error", "message": "The AgentFlow patch request is invalid."})
            return json.dumps(
                {
                    "status": "success",
                    "message": f"AgentFlow '{updated.name}' patched without replacing untouched graph elements.",
                    "flow": _serialize_flow_for_agent(updated),
                },
                default=str,
                ensure_ascii=False,
            )

        elif name == "edit_agent_flow":
            try:
                from shogun.services.posture_guard import get_posture_tool_filter
                posture = await get_posture_tool_filter()
                if not posture.get("agentflow_create", False):
                    return json.dumps({"status": "error", "message": "AgentFlow editing is only available in Tactical, Campaign, or Ronin posture."})
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the AgentFlow posture permission."})
            edit_permission = ("agentflow", "allow_edit")
            if (
                edit_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *edit_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "agentflow.allow_edit",
                    "message": (
                        "AgentFlow editing requires an explicit operator instruction, a one-time "
                        "ToolGate approval, or the persistent AgentFlow Allow Edit permission."
                    ),
                })
            activate = bool(args.get("activate", False))
            if activate and not await _shogun_workflow_activation_allowed(
                db_session, "agentflow", confirmed_permissions
            ):
                return json.dumps({"status": "error", "message": "AgentFlow activation permission is disabled."})

            import uuid as _uuid
            from shogun.api.agent_flow import _normalized_schedule_config, _sync_live_flow_schedule
            from shogun.services.agent_flow_service import AgentFlowService
            flow_svc = AgentFlowService(db_session)
            flow_id = _uuid.UUID(args["flow_id"])
            flow = await flow_svc.get_flow_full(flow_id)
            if not flow or flow.flow_type == "stack" or flow.is_template:
                return json.dumps({"status": "error", "message": "Editable AgentFlow not found."})

            metadata = {key: args[key] for key in ("name", "description", "trigger_type") if key in args}
            raw_sch = dict(args.get("schedule_config") or {})
            if "schedule_time" in args:
                raw_sch["schedule_time"] = args["schedule_time"]
            if "schedule_frequency" in args:
                raw_sch["schedule_frequency"] = args["schedule_frequency"]
                raw_sch["frequency"] = args["schedule_frequency"]

            if raw_sch:
                normalized = _normalized_schedule_config({**(flow.schedule_config or {}), **raw_sch})
                metadata["schedule_config"] = normalized
                metadata.setdefault("trigger_type", "scheduled")
                metadata.setdefault("status", "active")

            if metadata:
                await flow_svc.update(flow_id, **metadata)

            graph_requested = "nodes" in args or "edges" in args
            if graph_requested:
                if "nodes" not in args or "edges" not in args:
                    return json.dumps({"status": "error", "message": "Provide both nodes and edges when replacing an AgentFlow graph."})
                await flow_svc.save_flow_graph(flow_id, args["nodes"], args["edges"], flow.viewport)

            # If schedule parameters changed, keep any Input node config aligned
            updated_flow = await flow_svc.get_flow_full(flow_id)
            if updated_flow and (raw_sch or "trigger_type" in args):
                input_node = next((n for n in updated_flow.nodes if n.node_type == "input"), None)
                if input_node:
                    cfg = dict(input_node.config or {})
                    if updated_flow.trigger_type == "scheduled":
                        cfg["input_type"] = "scheduled"
                        sch = updated_flow.schedule_config or {}
                        cfg["schedule_frequency"] = sch.get("frequency", "nightly")
                        cfg["schedule_time"] = sch.get("schedule_time", "07:00")
                        if "schedule_days" in sch:
                            cfg["schedule_days"] = sch["schedule_days"]
                        if "schedule_day" in sch:
                            cfg["schedule_day"] = sch["schedule_day"]
                        if "minute_offset" in sch:
                            cfg["schedule_minute_offset"] = sch["minute_offset"]
                    else:
                        cfg["input_type"] = updated_flow.trigger_type
                    input_node.config = cfg
                    await db_session.flush()

            if activate or updated_flow.status == "active":
                if activate:
                    updated_flow = await flow_svc.update_status(flow_id, "active")
                await _sync_live_flow_schedule(updated_flow)

            await db_session.commit()
            updated = await flow_svc.get_flow_full(flow_id)
            return json.dumps({
                "status": "success", "message": f"AgentFlow '{updated.name}' updated.",
                "flow_id": str(flow_id), "flow_status": updated.status,
                "trigger_type": updated.trigger_type,
                "schedule_config": updated.schedule_config,
                "version": updated.version,
            })

        elif name == "delete_agent_flow":
            try:
                from shogun.services.posture_guard import get_posture_tool_filter

                posture = await get_posture_tool_filter()
                if not posture.get("agentflow_create", False):
                    return json.dumps({
                        "status": "error",
                        "message": "AgentFlow deletion is only available in Tactical, Campaign, or Ronin posture.",
                    })
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the AgentFlow posture permission."})
            delete_permission = ("agentflow", "allow_delete")
            if (
                delete_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *delete_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "agentflow.allow_delete",
                    "message": "AgentFlow deletion requires one-time ToolGate approval or Allow Delete permission.",
                })

            import uuid as _uuid
            from shogun.services.agent_flow_service import AgentFlowService

            flow_svc = AgentFlowService(db_session)
            try:
                flow_id = _uuid.UUID(args["flow_id"])
            except (KeyError, ValueError):
                return json.dumps({"status": "error", "message": "flow_id must be a valid UUID."})
            flow = await flow_svc.get_flow_full(flow_id)
            if not flow or flow.flow_type == "stack" or flow.is_template:
                return json.dumps({"status": "error", "message": "Deletable AgentFlow not found."})
            flow_name = flow.name
            await flow_svc.delete(flow_id)
            await db_session.commit()
            return json.dumps({
                "status": "success",
                "message": f"AgentFlow '{flow_name}' deleted.",
                "flow_id": str(flow_id),
                "deleted": True,
            })

        elif name == "edit_flow_stack":
            try:
                from shogun.services.posture_guard import get_posture_tool_filter
                posture = await get_posture_tool_filter()
                if not posture.get("flowstack_create", False):
                    return json.dumps({"status": "error", "message": "Flow Stack editing is only available in Tactical, Campaign, or Ronin posture."})
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the Flow Stack posture permission."})
            edit_permission = ("flow_stack", "allow_edit")
            if (
                edit_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *edit_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "flow_stack.allow_edit",
                    "message": (
                        "Flow Stack editing requires an explicit operator instruction, a one-time "
                        "ToolGate approval, or the persistent Flow Stack Allow Edit permission."
                    ),
                })
            activate = bool(args.get("activate", False))
            if activate and not await _shogun_workflow_permission(db_session, "flow_stack", "allow_activate"):
                return json.dumps({"status": "error", "message": "Flow Stack activation permission is disabled."})

            import uuid as _uuid
            from sqlalchemy import select
            from shogun.config import settings
            from shogun.db.models.agent_flow import AgentFlow
            from shogun.services.agent_flow_service import AgentFlowService

            flow_svc = AgentFlowService(db_session)
            stack_id = _uuid.UUID(args["flow_stack_id"])
            stack = await flow_svc.get_flow_full(stack_id)
            if not stack or stack.flow_type != "stack" or stack.is_template:
                return json.dumps({"status": "error", "message": "Editable Flow Stack not found."})
            metadata = {key: args[key] for key in ("name", "description") if key in args}
            if "timeout_seconds" in args:
                metadata["default_timeout_seconds"] = int(args["timeout_seconds"])
            if metadata:
                await flow_svc.update(stack_id, **metadata)

            if "flow_ids" in args:
                flow_ids = [_uuid.UUID(flow_id) for flow_id in args["flow_ids"]]
                if len(flow_ids) < 2:
                    return json.dumps({"status": "error", "message": "A Flow Stack requires at least two AgentFlows."})
                version_mode = args.get("version_mode", "locked")
                if version_mode == "latest" and not settings.flow_stacking_allow_latest_version:
                    return json.dumps({"status": "error", "message": "Latest-version Flow Stack references are disabled."})
                result = await db_session.execute(select(AgentFlow).where(AgentFlow.id.in_(flow_ids), AgentFlow.is_deleted == False))
                selected = {flow.id: flow for flow in result.scalars().all()}
                if any(flow_id not in selected for flow_id in flow_ids):
                    return json.dumps({"status": "error", "message": "One or more AgentFlows could not be found."})
                if any(not selected[flow_id].allow_as_subflow for flow_id in flow_ids):
                    return json.dumps({"status": "error", "message": "One or more AgentFlows cannot be used as a subflow."})
                timeout = int(args.get("timeout_seconds", stack.default_timeout_seconds or 600))
                nodes, edges = [], []
                input_id = str(_uuid.uuid4())
                nodes.append({"id": input_id, "node_type": "input", "label": "Stack Input", "position_x": 0, "position_y": 120, "config": {"input_type": "subflow"}})
                previous_id = input_id
                for index, child_id in enumerate(flow_ids, start=1):
                    child = selected[child_id]
                    node_id = str(_uuid.uuid4())
                    nodes.append({"id": node_id, "node_type": "subflow", "label": child.name, "position_x": index * 280, "position_y": 120, "config": {"child_flow_id": str(child.id), "child_flow_version_mode": version_mode, "child_flow_version": child.version if version_mode == "locked" else None, "execution_mode": "sequential", "timeout_seconds": timeout, "on_failure": "fail_parent", "input_mapping": {}, "output_mapping": {}}})
                    edges.append({"source_node_id": previous_id, "target_node_id": node_id})
                    previous_id = node_id
                output_id = str(_uuid.uuid4())
                nodes.append({"id": output_id, "node_type": "output", "label": "Stack Output", "position_x": (len(flow_ids) + 1) * 280, "position_y": 120, "config": {"output_type": "artifact", "format": "json"}})
                edges.append({"source_node_id": previous_id, "target_node_id": output_id})
                await flow_svc.update(stack_id, required_tools=sorted({tool for flow_id in flow_ids for tool in (selected[flow_id].required_tools or [])}))
                await flow_svc.save_flow_graph(stack_id, nodes, edges, stack.viewport)
            if activate:
                await flow_svc.update_status(stack_id, "active")
            await db_session.commit()
            updated = await flow_svc.get_flow_full(stack_id)
            return json.dumps({
                "status": "success", "message": f"Flow Stack '{updated.name}' updated.",
                "flow_stack_id": str(stack_id), "flow_stack_status": updated.status,
                "version": updated.version,
            })

        elif name == "delete_flow_stack":
            try:
                from shogun.services.posture_guard import get_posture_tool_filter

                posture = await get_posture_tool_filter()
                if not posture.get("flowstack_create", False):
                    return json.dumps({
                        "status": "error",
                        "message": "Flow Stack deletion is only available in Tactical, Campaign, or Ronin posture.",
                    })
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the Flow Stack posture permission."})
            delete_permission = ("flow_stack", "allow_delete")
            if (
                delete_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *delete_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "flow_stack.allow_delete",
                    "message": "Flow Stack deletion requires one-time ToolGate approval or Allow Delete permission.",
                })

            import uuid as _uuid
            from shogun.services.agent_flow_service import AgentFlowService

            flow_svc = AgentFlowService(db_session)
            try:
                stack_id = _uuid.UUID(args["flow_stack_id"])
            except (KeyError, ValueError):
                return json.dumps({"status": "error", "message": "flow_stack_id must be a valid UUID."})
            stack = await flow_svc.get_flow_full(stack_id)
            if not stack or stack.flow_type != "stack" or stack.is_template:
                return json.dumps({"status": "error", "message": "Deletable Flow Stack not found."})
            stack_name = stack.name
            await flow_svc.delete(stack_id)
            await db_session.commit()
            return json.dumps({
                "status": "success",
                "message": f"Flow Stack '{stack_name}' deleted.",
                "flow_stack_id": str(stack_id),
                "deleted": True,
            })

        elif name == "create_flow_stack":
            try:
                from shogun.services.posture_guard import get_posture_tool_filter
                posture = await get_posture_tool_filter()
                if not posture.get("flowstack_create", False):
                    return json.dumps({"status": "error", "message": "Flow Stack creation is only available in Tactical, Campaign, or Ronin posture."})
            except Exception:
                return json.dumps({"status": "error", "message": "Could not verify the Flow Stack posture permission."})
            create_permission = ("flow_stack", "allow_create")
            if (
                create_permission not in confirmed_permissions
                and not await _shogun_workflow_permission(db_session, *create_permission)
            ):
                return json.dumps({
                    "status": "permission_required",
                    "permission": "flow_stack.allow_create",
                    "message": (
                        "Flow Stack creation requires an explicit operator instruction, a one-time "
                        "ToolGate approval, or the persistent Flow Stack Allow Create permission."
                    ),
                })
            activate = bool(args.get("activate", False))
            if activate and not await _shogun_workflow_permission(db_session, "flow_stack", "allow_activate"):
                return json.dumps({"status": "error", "message": "Shogun may create this Flow Stack as a draft, but Flow Stack activation permission is disabled."})

            import uuid as _uuid
            from shogun.api.agent_flow import create_flow_stack
            from shogun.schemas.agent_flow import FlowStackCreate
            from shogun.services.agent_flow_service import AgentFlowService

            body = FlowStackCreate(
                name=args.get("name", "Untitled Flow Stack"),
                description=args.get("description"),
                flow_ids=[_uuid.UUID(flow_id) for flow_id in args.get("flow_ids", [])],
                version_mode=args.get("version_mode", "locked"),
                timeout_seconds=int(args.get("timeout_seconds", 600)),
            )
            flow_svc = AgentFlowService(db_session)
            response = await create_flow_stack(body=body, svc=flow_svc, db=db_session)
            stack_id = response.data.id
            if activate:
                await flow_svc.update_status(stack_id, "active")
            await db_session.commit()
            return json.dumps({
                "status": "success",
                "message": f"Flow Stack '{body.name}' created as {'active' if activate else 'draft'} with {len(body.flow_ids)} AgentFlow phases.",
                "flow_stack_id": str(stack_id),
                "flow_stack_status": "active" if activate else "draft",
            })

        elif name == "browse_web":
            # ── Mado browser automation ──────────────────────────
            from shogun.services.posture_guard import (
                check_mado_access,
                check_mado_session_limit,
            )
            from shogun.services import mado_service
            from shogun.services.mado_service_crud import MadoSessionService
            from datetime import datetime, timezone

            try:
                # One shared gate enforces local Torii, Harakiri, and Gensui.
                await check_mado_access()
            except HTTPException as exc:
                return json.dumps({"status": "error", "message": str(exc.detail)})

            url = args.get("url", "")
            extract_type = args.get("extract_type", "text")
            selector = args.get("selector")
            extract_preset = args.get("extract_preset")

            # Map extract_preset to CSS selector (same presets as Mado Quick Actions)
            PRESET_SELECTORS = {
                "headlines":  "h1, h2, h3, h4, article h2, article h3",
                "links":      "a[href]",
                "article":    'article, [role="article"], .post-content, .entry-content, .article-body, main',
                "news_cards": 'article a, [data-n-tid] a, c-wiz article, [jslog] h3, [jslog] h4',
                "tables":     'table, [role="table"], .data-table',
                "images":     "img[src], picture source",
                "lists":      'ul, ol, dl, [role="list"]',
                "prices":     '[class*="price"], [data-price], .product-card, .product-title',
                "full_page":  "body",
            }
            if extract_preset and extract_preset in PRESET_SELECTORS and not selector:
                selector = PRESET_SELECTORS[extract_preset]

            # ── Resolve or create a Mado session via CRUD ────────
            mado_svc = MadoSessionService(db_session)
            db_record = await mado_svc.get_by_profile_name("native_skill")
            if db_record is None:
                try:
                    await check_mado_session_limit()
                except HTTPException as exc:
                    return json.dumps({"status": "error", "message": str(exc.detail)})
                db_record = await mado_svc.create(
                    name="Agent Browser",
                    profile_name="native_skill",
                    browser_mode="headless",
                    domain_allowlist=[],
                    security_policy={
                        "https_only": False, "downloads": "allowed",
                        "uploads": "allowed", "form_submit": "allowed",
                        "external_navigation": "allowed", "js_execution": "allowed",
                        "max_page_loads": 0,
                    },
                )
                await db_session.commit()

            session_id = str(db_record.id)

            await mado_service.launch_browser(
                session_id=session_id,
                profile_name="native_skill",
                mode="headless",
            )

            # Mark session as active
            await mado_svc.update_status(
                db_record.id, "active",
                last_active_at=datetime.now(timezone.utc),
            )

            # Navigate (native_skill has no domain restrictions — per-session policies apply)
            nav_result = await mado_service.navigate(
                session_id=session_id,
                url=url,
            )

            if nav_result.get("status") == "blocked":
                return json.dumps({
                    "status": "error",
                    "message": f"Navigation blocked: {nav_result.get('reason', 'Domain not allowed')}",
                })

            # Update last URL in session record
            await mado_svc.update_status(
                db_record.id, "active",
                last_url=nav_result.get("url", url),
                last_active_at=datetime.now(timezone.utc),
            )
            await db_session.commit()

            # Extract content
            extract_result = await mado_service.extract_content(
                session_id=session_id,
                selector=selector,
                extract_type=extract_type,
            )

            return json.dumps({
                "status": "success",
                "url": nav_result.get("url", url),
                "title": nav_result.get("title", ""),
                "content": extract_result.get("content", "")[:20000],
            })

        elif name == "take_screenshot":
            # ── Mado screenshot ──────────────────────────────────
            from shogun.services.posture_guard import check_mado_access
            from shogun.services import mado_service
            from shogun.services.mado_service_crud import MadoSessionService
            from datetime import datetime, timezone

            try:
                await check_mado_access()
            except HTTPException as exc:
                return json.dumps({"status": "error", "message": str(exc.detail)})

            # Resolve the native skill session from DB
            mado_svc = MadoSessionService(db_session)
            db_record = await mado_svc.get_by_profile_name("native_skill")
            if db_record is None:
                return json.dumps({
                    "status": "error",
                    "message": "No active browser session. Use browse_web first to navigate to a page.",
                })

            session_id = str(db_record.id)
            full_page = args.get("full_page", False)

            result = await mado_service.screenshot(
                session_id=session_id,
                full_page=full_page,
            )

            # Update session status
            await mado_svc.update_status(
                db_record.id, "active",
                last_active_at=datetime.now(timezone.utc),
            )
            await db_session.commit()

            if result.get("status") == "error":
                return json.dumps({
                    "status": "error",
                    "message": f"Screenshot failed: {result.get('error', 'No active browser session. Use browse_web first.')}",
                })

            return json.dumps({
                "status": "success",
                "message": f"Screenshot saved: {result.get('filename', 'unknown')}",
                "path": result.get("path", ""),
            })

        # ── Ronin Desktop Control ─────────────────────────────
        elif name in ("desktop_screenshot", "desktop_click", "desktop_type", "desktop_list_windows", "desktop_open_application"):
            from shogun.services.posture_guard import get_posture_tool_filter
            from shogun.ronin.core.ronin_controller import get_controller

            posture = await get_posture_tool_filter()
            if not posture.get("ronin_enabled", False):
                tier = posture.get('active_tier', 'unknown').upper()
                return json.dumps({
                    "status": "error",
                    "message": f"Desktop control is disabled at tier {tier}. Desktop control is ONLY available at the RONIN security posture. Switch to Ronin in the Torii to enable it.",
                })

            # Check specific capability
            if name == "desktop_click" and not posture.get("ronin_mouse_enabled", False):
                return json.dumps({"status": "error", "message": "Mouse control is not enabled at the current posture level."})
            if name == "desktop_type" and not posture.get("ronin_keyboard_enabled", False):
                return json.dumps({"status": "error", "message": "Keyboard control is not enabled at the current posture level."})
            if name == "desktop_screenshot" and not posture.get("ronin_screenshots_enabled", True):
                return json.dumps({"status": "error", "message": "Screenshots are not enabled at the current posture level."})
            if name == "desktop_list_windows" and not posture.get("ronin_window_management_enabled", False):
                return json.dumps({"status": "error", "message": "Window management is not enabled."})
            if name == "desktop_open_application" and not posture.get("ronin_native_apps_enabled", False):
                return json.dumps({"status": "error", "message": "Application launch is not enabled."})

            controller = get_controller()
            await controller.initialize()  # ensure environment detection ran

            # Every native desktop tool must traverse the same governed
            # observe/act/verify/retry/audit pipeline as the public API.
            from shogun.ronin.policies.ronin_policy_schema import RoninAction as _RoninAction
            action_type = "desktop.screenshot"
            target = None
            value = None
            metadata: dict[str, Any] = {"max_retries": 2}
            if name == "desktop_click":
                action_type = "desktop.double_click" if int(args.get("clicks", 1)) > 1 else "desktop.click"
                target = f"{int(args['x'])},{int(args['y'])}"
                metadata.update({"x": int(args["x"]), "y": int(args["y"]), "button": args.get("button", "left")})
            elif name == "desktop_type":
                action_type = "desktop.hotkey" if args.get("is_hotkey", False) else "desktop.type"
                value = str(args["text"])
                metadata["interval"] = float(args.get("interval", 0.05))
            elif name == "desktop_list_windows":
                action_type = "os.list_windows"
            elif name == "desktop_open_application":
                action_type = "os.app_launch"
                target = str(args["application"])
                metadata["expected_window"] = args.get("expected_window")
            elif args.get("region"):
                parts = [int(part.strip()) for part in str(args["region"]).split(",")]
                if len(parts) == 4:
                    metadata["region"] = {"left": parts[0], "top": parts[1], "width": parts[2], "height": parts[3]}

            governed_result = await controller.execute(_RoninAction(
                action_type=action_type,
                agent_id="shogun",
                target=target,
                value=value,
                reason="Native Shogun desktop tool",
                metadata=metadata,
            ))
            return json.dumps({
                "status": governed_result.status.value,
                "message": governed_result.error or f"{action_type} completed",
                "verified": governed_result.verified,
                **governed_result.result_data,
            })

            if name == "desktop_screenshot":
                from shogun.ronin.desktop.screenshot_controller import take_screenshot_raw
                region_str = args.get("region")
                region = None
                if region_str:
                    parts = [int(p.strip()) for p in region_str.split(",")]
                    if len(parts) == 4:
                        region = {"left": parts[0], "top": parts[1], "width": parts[2], "height": parts[3]}
                path = await take_screenshot_raw(prefix="agent", region=region)
                if not path:
                    return json.dumps({"status": "error", "message": "Screenshot failed. Is `mss` installed? (pip install mss)"})
                from pathlib import Path as _P
                return json.dumps({
                    "status": "success",
                    "message": f"Desktop screenshot saved: {_P(path).name}",
                    "path": path,
                })

            elif name == "desktop_click":
                import ctypes
                import time as _time
                import asyncio as _aio
                from concurrent.futures import ThreadPoolExecutor as _TPool
                from shogun.ronin.core.komainu import ronin_acting, set_expected_position

                x = int(args["x"])
                y = int(args["y"])
                button = args.get("button", "left")
                clicks_count = int(args.get("clicks", 1))

                def _smooth_click():
                    import pyautogui
                    pyautogui.FAILSAFE = True
                    # Get current cursor position
                    start = pyautogui.position()
                    sx, sy = start.x, start.y

                    logger.info(f"[Ronin Click] Smooth glide ({sx},{sy}) → ({x},{y}) over 0.8s")

                    with ronin_acting(expected_pos=(x, y)):
                        # Smooth cursor interpolation with ease-in-out
                        steps = 50
                        duration = 0.8
                        step_delay = duration / steps
                        for i in range(1, steps + 1):
                            t = i / steps
                            # Smooth ease-in-out: 3t² - 2t³
                            t_eased = t * t * (3 - 2 * t)
                            cx = int(sx + (x - sx) * t_eased)
                            cy = int(sy + (y - sy) * t_eased)
                            ctypes.windll.user32.SetCursorPos(cx, cy)
                            _time.sleep(step_delay)

                        # Brief pause so user sees cursor arrive
                        _time.sleep(0.15)

                        # Click
                        pyautogui.click(button=button, clicks=clicks_count)

                    set_expected_position(x, y)
                    logger.info(f"[Ronin Click] Clicked at ({x},{y}) with {button}")

                loop = _aio.get_event_loop()
                _pool = _TPool(max_workers=1, thread_name_prefix="ronin-click")
                await loop.run_in_executor(_pool, _smooth_click)
                _pool.shutdown(wait=False)

                return json.dumps({
                    "status": "success",
                    "message": f"Clicked at ({x}, {y}) with {button} button ({clicks_count}x).",
                })

            elif name == "desktop_type":
                text = args["text"]
                is_hotkey = args.get("is_hotkey", False)
                interval = float(args.get("interval", 0.05))

                if is_hotkey:
                    from shogun.ronin.policies.ronin_policy_schema import RoninAction as _RA
                    from shogun.ronin.desktop.keyboard_controller import hotkey as ronin_hotkey
                    action_obj = _RA(
                        action_type="desktop.hotkey",
                        agent_id="shogun",
                        target=text,
                        metadata={"keys": text},
                    )
                    result = await ronin_hotkey(action_obj)
                    if result.status.value != "success":
                        return json.dumps({"status": "error", "message": result.error or "Hotkey failed."})
                    return json.dumps({"status": "success", "message": f"Hotkey: {text}"})
                else:
                    import time as _time
                    import asyncio as _aio
                    from concurrent.futures import ThreadPoolExecutor as _TPool
                    from shogun.ronin.core.komainu import ronin_acting

                    def _smooth_type():
                        import pyautogui
                        pyautogui.FAILSAFE = True
                        logger.info(f"[Ronin Keyboard] Typing {len(text)} chars at {interval}s/char")
                        with ronin_acting():
                            for char in text:
                                if char == '\n':
                                    pyautogui.press('enter')
                                elif char == '\t':
                                    pyautogui.press('tab')
                                else:
                                    pyautogui.write(char)
                                _time.sleep(interval)
                        logger.info(f"[Ronin Keyboard] Done typing")

                    loop = _aio.get_event_loop()
                    _pool = _TPool(max_workers=1, thread_name_prefix="ronin-kbd")
                    await loop.run_in_executor(_pool, _smooth_type)
                    _pool.shutdown(wait=False)

                    return json.dumps({
                        "status": "success",
                        "message": f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}",
                    })

        # ── Office App Mode (Katana) ──────────────────────────────
        elif name.startswith("office_"):
            return await _execute_office_tool(name, args, db_session)

        # ── Workspace Tools ──────────────────────────────────────────
        elif name.startswith("workspace_"):
            return await _execute_workspace_tool(name, args)

        elif name.startswith("ide_"):
            return await _execute_ide_tool(name, args)

        # ── Telegram Tools ────────────────────────────────────────────
        elif name == "telegram_list_groups":
            return await _execute_telegram_list_groups()

        elif name.startswith("mcp_"):
            return await _execute_mcp_tool(name, args, db_session)

        # ── Dojo / Skill Tools ────────────────────────────────────────
        elif name.startswith("dojo_"):
            return await _execute_dojo_tool(name, args)
        elif name.startswith("skills_"):
            return await _execute_active_skill_tool(name, args, db_session)

        else:
            return json.dumps({"status": "error", "message": f"Unknown tool: {name}"})
            
    except Exception:
        logger.exception("Native skill execution failed")
        return json.dumps({"status": "error", "message": "Native skill execution failed. Check the Shogun logs."})


# ── Office Tool Executor ─────────────────────────────────────────────
# Tracks open workbook/document/presentation handles across tool calls.
_open_handles: dict[str, Any] = {}  # file_path → handle object


async def _execute_mcp_tool(name: str, args: dict[str, Any], db_session) -> str:
    """Execute tools and resources from registered Katana MCP connectors."""
    from shogun.services.mcp_bridge import (
        call_mcp_tool,
        list_mcp_resources,
        list_mcp_tools,
        read_mcp_resource,
    )

    connector_slug = str(args.get("connector_slug") or "").strip()
    if not connector_slug:
        return json.dumps({"status": "error", "message": "connector_slug is required."})

    try:
        if name == "mcp_list_tools":
            result = await list_mcp_tools(db_session, connector_slug)
        elif name == "mcp_call_tool":
            tool_name = str(args.get("tool_name") or "").strip()
            if not tool_name:
                return json.dumps({"status": "error", "message": "tool_name is required."})
            arguments = args.get("arguments") or {}
            if not isinstance(arguments, dict):
                return json.dumps({"status": "error", "message": "arguments must be a JSON object."})
            result = await call_mcp_tool(db_session, connector_slug, tool_name, arguments)
        elif name == "mcp_list_resources":
            result = await list_mcp_resources(db_session, connector_slug)
        elif name == "mcp_read_resource":
            uri = str(args.get("uri") or "").strip()
            if not uri:
                return json.dumps({"status": "error", "message": "uri is required."})
            result = await read_mcp_resource(db_session, connector_slug, uri)
        else:
            return json.dumps({"status": "error", "message": f"Unknown MCP tool: {name}"})

        return json.dumps({
            "status": "success",
            "connector": result.connector,
            "tool": result.tool,
            "response": result.response,
        })
    except Exception:
        logger.exception("MCP tool execution failed")
        return json.dumps({"status": "error", "message": "MCP tool execution failed. Check the Shogun logs."})


async def _execute_office_tool(name: str, args: dict[str, Any], db_session=None) -> str:
    """Execute an Office App Mode tool.

    All Office tools route through this function, which handles:
      1. Config loading
      2. Path validation
      3. Permission checks
      4. Adapter delegation
      5. Output versioning
      6. Event logging
    """
    import time as _time
    start_ms = int(_time.time() * 1000)

    try:
        from shogun.office.config import load_office_config
        from shogun.office.path_validator import FileBoundaryValidator, PathPurpose
        from shogun.office.permission_engine import (
            check_office_permission, get_current_posture_tier, OfficeAction,
        )
        from shogun.office.output_versioning import version_output_path
        from shogun.office.exceptions import OfficeError

        config = load_office_config()
        if not config.enabled:
            return json.dumps({
                "status": "blocked",
                "message": "Office App Mode is disabled. Enable it in the Katana configuration.",
            })

        validator = FileBoundaryValidator(config)
        tier = await get_current_posture_tier()

        # ── Excel Tools ──────────────────────────────────────────
        if name == "office_excel_open_attachment":
            if db_session is None:
                return json.dumps({"status": "error", "message": "A database session is required."})
            try:
                import uuid as _uuid
                from pathlib import Path as _Path

                from shogun.db.models.file_artifact import FileArtifact
                from shogun.services.file_formats import FileSafetyGate

                artifact = await db_session.get(FileArtifact, _uuid.UUID(str(args["file_id"])))
            except (ValueError, KeyError):
                artifact = None
            if artifact is None:
                return json.dumps({"status": "error", "message": "The attached Excel file was not found."})
            if artifact.format_id not in {"xlsx", "excel"} and not str(artifact.path).lower().endswith(".xlsx"):
                return json.dumps({"status": "error", "message": "The attached file is not an .xlsx workbook."})

            attachment_path, _ = FileSafetyGate().resolve(_Path(artifact.path))
            from shogun.office.adapters.excel_adapter import get_workbook_metadata, open_workbook

            handle = open_workbook(str(attachment_path))
            canonical_path = str(attachment_path)
            _open_handles[canonical_path] = handle
            meta = get_workbook_metadata(handle)
            meta["file_path"] = canonical_path
            await _log_office_event(
                "office.excel.open_attachment",
                "Opened attached workbook",
                "excel",
                canonical_path,
                start_ms=start_ms,
            )
            return json.dumps({"status": "success", "data": meta})

        if name == "office_excel_open":
            vp = validator.validate(args["file_path"], PathPurpose.READ)
            from shogun.office.adapters.excel_adapter import open_workbook, get_workbook_metadata
            handle = open_workbook(str(vp.resolved_path))
            _open_handles[str(vp.resolved_path)] = handle
            meta = get_workbook_metadata(handle)
            await _log_office_event("office.excel.open", "Opened workbook", "excel", str(vp.resolved_path), start_ms=start_ms)
            return json.dumps({"status": "success", "data": meta})

        elif name == "office_excel_read_range":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                vp = validator.validate(fp, PathPurpose.READ)
                from shogun.office.adapters.excel_adapter import open_workbook
                handle = open_workbook(str(vp.resolved_path))
                _open_handles[str(vp.resolved_path)] = handle
                fp = str(vp.resolved_path)
            from shogun.office.adapters.excel_adapter import read_range, read_used_range
            sheet = args["sheet_name"]
            rng = args.get("range")
            data = read_range(handle, sheet, rng) if rng else read_used_range(handle, sheet)
            await _log_office_event("office.excel.read", f"Read {sheet}{'!' + rng if rng else ''}", "excel", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "data": data})

        elif name == "office_excel_write_range":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Workbook not open. Call office_excel_open first."})
            perm = check_office_permission(OfficeAction.WRITE_CONTENT, "excel", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.excel_adapter import write_range
            write_range(handle, args["sheet_name"], args["range"], args["values"])
            await _log_office_event("office.excel.write", f"Wrote to {args['sheet_name']}!{args['range']}", "excel", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Written to {args['sheet_name']}!{args['range']}"})

        elif name == "office_excel_list_sheets":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Workbook not open."})
            from shogun.office.adapters.excel_adapter import list_sheets
            sheets = list_sheets(handle)
            return json.dumps({"status": "success", "data": {"sheets": sheets}})

        elif name == "office_excel_save_as":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Workbook not open."})
            perm = check_office_permission(OfficeAction.SAVE_AS_NEW, "excel", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.excel_adapter import save_as
            from pathlib import Path
            base_name = args.get("output_name") or Path(fp).stem
            out_path = version_output_path(base_name, ".xlsx", config.folders.output)
            result = save_as(handle, str(out_path))
            await _log_office_event("office.excel.save", f"Saved as {out_path.name}", "excel", fp, output_file=result, start_ms=start_ms)
            return json.dumps({"status": "success", "output_file": result})

        elif name == "office_excel_export_pdf":
            fp = args["file_path"]
            perm = check_office_permission(OfficeAction.EXPORT_PDF, "excel", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.excel_adapter import export_pdf
            from pathlib import Path
            base_name = args.get("output_name") or Path(fp).stem
            out_path = version_output_path(base_name, ".pdf", config.folders.output)
            result = await export_pdf(fp, str(out_path))
            await _log_office_event("office.excel.export_pdf", f"Exported PDF {out_path.name}", "excel", fp, output_file=result, start_ms=start_ms)
            return json.dumps({"status": "success", "output_file": result})

        elif name == "office_excel_get_metadata":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Workbook not open."})
            from shogun.office.adapters.excel_adapter import get_workbook_metadata
            meta = get_workbook_metadata(handle)
            return json.dumps({"status": "success", "data": meta})

        elif name == "office_excel_calculate":
            fp = args["file_path"]
            perm = check_office_permission(OfficeAction.CALCULATE, "excel", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.excel_adapter import calculate
            await calculate(fp)
            await _log_office_event("office.excel.calculate", "Recalculated formulas", "excel", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "message": "Formulas recalculated."})

        # ── Word Tools ───────────────────────────────────────────
        elif name == "office_word_open":
            vp = validator.validate(args["file_path"], PathPurpose.READ)
            from shogun.office.adapters.word_adapter import open_document, get_document_metadata
            handle = open_document(str(vp.resolved_path))
            _open_handles[str(vp.resolved_path)] = handle
            meta = get_document_metadata(handle)
            await _log_office_event("office.word.open", "Opened document", "word", str(vp.resolved_path), start_ms=start_ms)
            return json.dumps({"status": "success", "data": meta})

        elif name == "office_word_replace_placeholders":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                vp_auto = validator.validate(fp, PathPurpose.READ)
                handle = _open_handles.get(str(vp_auto.resolved_path))
                if not handle:
                    from shogun.office.adapters.word_adapter import open_document
                    handle = open_document(str(vp_auto.resolved_path))
                    _open_handles[str(vp_auto.resolved_path)] = handle
                fp = str(vp_auto.resolved_path)
            perm = check_office_permission(OfficeAction.WRITE_CONTENT, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.word_adapter import replace_placeholders
            counts = replace_placeholders(handle, args["mapping"])
            await _log_office_event("office.word.replace", f"Replaced placeholders: {sum(counts.values())} total", "word", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "data": {"replacements": counts}})

        elif name == "office_word_insert_table":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Document not open."})
            perm = check_office_permission(OfficeAction.WRITE_CONTENT, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.word_adapter import insert_table
            insert_table(handle, args["headers"], args["rows"])
            await _log_office_event("office.word.insert_table", f"Inserted table ({len(args['headers'])} cols)", "word", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Table inserted ({len(args['headers'])} columns, {len(args['rows'])} rows)"})

        elif name == "office_word_save_as":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Document not open."})
            perm = check_office_permission(OfficeAction.SAVE_AS_NEW, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.word_adapter import save_as
            from pathlib import Path
            base_name = args.get("output_name") or Path(fp).stem
            out_path = version_output_path(base_name, ".docx", config.folders.output)
            result = save_as(handle, str(out_path))
            await _log_office_event("office.word.save", f"Saved as {out_path.name}", "word", fp, output_file=result, start_ms=start_ms)
            return json.dumps({"status": "success", "output_file": result})

        elif name == "office_word_export_pdf":
            fp = args["file_path"]
            perm = check_office_permission(OfficeAction.EXPORT_PDF, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.word_adapter import export_pdf
            from pathlib import Path
            base_name = args.get("output_name") or Path(fp).stem
            out_path = version_output_path(base_name, ".pdf", config.folders.output)
            result = await export_pdf(fp, str(out_path))
            await _log_office_event("office.word.export_pdf", f"Exported PDF {out_path.name}", "word", fp, output_file=result, start_ms=start_ms)
            return json.dumps({"status": "success", "output_file": result})

        elif name == "office_word_get_metadata":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Document not open."})
            from shogun.office.adapters.word_adapter import get_document_metadata
            meta = get_document_metadata(handle)
            return json.dumps({"status": "success", "data": meta})

        elif name == "office_word_read_text":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                # Auto-open: resolve path and check if handle exists under absolute path
                vp = validator.validate(fp, PathPurpose.READ)
                handle = _open_handles.get(str(vp.resolved_path))
                if not handle:
                    # Still not found — auto-open the document
                    from shogun.office.adapters.word_adapter import open_document
                    handle = open_document(str(vp.resolved_path))
                    _open_handles[str(vp.resolved_path)] = handle
                fp = str(vp.resolved_path)
            from shogun.office.adapters.word_adapter import read_text
            text = read_text(handle)
            total_length = len(text)
            max_chars = max(1000, min(int(args.get("max_chars", 30000)), 100000))
            truncated = total_length > max_chars
            if truncated:
                text = text[:max_chars]
            await _log_office_event(
                "office.word.read_text",
                f"Read {len(text)} of {total_length} chars",
                "word",
                fp,
                start_ms=start_ms,
            )
            return json.dumps({
                "status": "success",
                "data": {
                    "text": text,
                    "length": len(text),
                    "total_length": total_length,
                    "truncated": truncated,
                    "message": (
                        "Result was truncated to protect the model context. "
                        "Use office_word_read_pages for a bounded page range."
                        if truncated else ""
                    ),
                },
            })

        elif name in ("office_word_read_page", "office_word_read_pages"):
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                vp = validator.validate(fp, PathPurpose.READ)
                handle = _open_handles.get(str(vp.resolved_path))
                if not handle:
                    from shogun.office.adapters.word_adapter import open_document
                    handle = open_document(str(vp.resolved_path))
                    _open_handles[str(vp.resolved_path)] = handle
                fp = str(vp.resolved_path)
            from shogun.office.adapters.word_adapter import read_pages
            if name == "office_word_read_page":
                start_page = int(args.get("page", 1))
                end_page = start_page
            else:
                start_page = int(args.get("start_page", 1))
                end_page = int(args.get("end_page", start_page))
            page_data = read_pages(handle, start_page, end_page)
            await _log_office_event(
                "office.word.read_page" if name == "office_word_read_page" else "office.word.read_pages",
                f"Read pages {page_data['start_page']}-{page_data['end_page']} "
                f"({page_data['length']} chars)",
                "word",
                fp,
                start_ms=start_ms,
            )
            return json.dumps({"status": "success", "data": page_data})

        elif name == "office_word_read_headings":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                vp = validator.validate(fp, PathPurpose.READ)
                handle = _open_handles.get(str(vp.resolved_path))
                if not handle:
                    from shogun.office.adapters.word_adapter import open_document
                    handle = open_document(str(vp.resolved_path))
                    _open_handles[str(vp.resolved_path)] = handle
                fp = str(vp.resolved_path)
            from shogun.office.adapters.word_adapter import read_headings
            headings = read_headings(handle)
            await _log_office_event("office.word.read_headings", f"Read {len(headings)} headings", "word", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "data": headings})

        elif name == "office_word_insert_paragraph":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                vp_auto = validator.validate(fp, PathPurpose.READ)
                handle = _open_handles.get(str(vp_auto.resolved_path))
                if not handle:
                    from shogun.office.adapters.word_adapter import open_document
                    handle = open_document(str(vp_auto.resolved_path))
                    _open_handles[str(vp_auto.resolved_path)] = handle
                fp = str(vp_auto.resolved_path)
            perm = check_office_permission(OfficeAction.WRITE_CONTENT, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.word_adapter import insert_paragraph
            style = args.get("style", "Normal")
            insert_paragraph(handle, args["text"], style)
            await _log_office_event("office.word.insert_paragraph", f"Inserted paragraph ({len(args['text'])} chars)", "word", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Paragraph inserted ({len(args['text'])} chars)"})

        elif name == "office_word_create":
            perm = check_office_permission(OfficeAction.SAVE_AS_NEW, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            vp = validator.validate(args["output_path"], PathPurpose.WRITE)
            from docx import Document as DocxDocument
            from pathlib import Path
            abs_out = str(vp.resolved_path)
            Path(abs_out).parent.mkdir(parents=True, exist_ok=True)
            doc = DocxDocument()
            doc.save(abs_out)
            # Also open it so subsequent operations can use it
            from shogun.office.adapters.word_adapter import open_document
            handle = open_document(abs_out)
            _open_handles[abs_out] = handle
            await _log_office_event("office.word.create", f"Created document {args['output_path']}", "word", abs_out, start_ms=start_ms)
            return json.dumps({"status": "success", "data": {"path": abs_out, "message": f"Created new document: {args['output_path']}"}})

        # ── PowerPoint Tools ─────────────────────────────────────
        elif name == "office_word_create_from_text":
            perm = check_office_permission(OfficeAction.SAVE_AS_NEW, "word", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            vp = validator.validate(args["output_path"], PathPurpose.WRITE)
            text = str(args.get("text", ""))
            append = bool(args.get("append", False))
            from shogun.office.adapters.word_adapter import create_document_from_text
            handle = create_document_from_text(str(vp.resolved_path), text, append=append)
            abs_out = str(vp.resolved_path)
            _open_handles[abs_out] = handle
            await _log_office_event(
                "office.word.create_from_text",
                f"{'Appended' if append else 'Created'} document text ({len(text)} chars)",
                "word",
                abs_out,
                output_file=abs_out,
                start_ms=start_ms,
            )
            return json.dumps({
                "status": "success",
                "output_file": abs_out,
                "message": f"{'Appended to' if append else 'Created'} Word document with {len(text)} characters.",
            })

        elif name == "office_pptx_open":
            vp = validator.validate(args["file_path"], PathPurpose.READ)
            from shogun.office.adapters.pptx_adapter import open_presentation, get_presentation_metadata
            handle = open_presentation(str(vp.resolved_path))
            _open_handles[str(vp.resolved_path)] = handle
            meta = get_presentation_metadata(handle)
            await _log_office_event("office.pptx.open", "Opened presentation", "powerpoint", str(vp.resolved_path), start_ms=start_ms)
            return json.dumps({"status": "success", "data": meta})

        elif name == "office_pptx_replace_placeholders":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Presentation not open."})
            perm = check_office_permission(OfficeAction.WRITE_CONTENT, "powerpoint", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.pptx_adapter import replace_placeholders
            counts = replace_placeholders(handle, args["mapping"])
            await _log_office_event("office.pptx.replace", f"Replaced placeholders: {sum(counts.values())} total", "powerpoint", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "data": {"replacements": counts}})

        elif name == "office_pptx_insert_table":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Presentation not open."})
            perm = check_office_permission(OfficeAction.WRITE_CONTENT, "powerpoint", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.pptx_adapter import insert_table
            insert_table(handle, args["slide_index"], args["headers"], args["rows"])
            await _log_office_event("office.pptx.insert_table", f"Inserted table on slide {args['slide_index']}", "powerpoint", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Table inserted on slide {args['slide_index']}"})

        elif name == "office_pptx_insert_image":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Presentation not open."})
            perm = check_office_permission(OfficeAction.INSERT_IMAGE, "powerpoint", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.pptx_adapter import insert_image
            insert_image(handle, args["slide_index"], args["image_path"])
            await _log_office_event("office.pptx.insert_image", f"Inserted image on slide {args['slide_index']}", "powerpoint", fp, start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Image inserted on slide {args['slide_index']}"})

        elif name == "office_pptx_save_as":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Presentation not open."})
            perm = check_office_permission(OfficeAction.SAVE_AS_NEW, "powerpoint", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.pptx_adapter import save_as
            from pathlib import Path
            base_name = args.get("output_name") or Path(fp).stem
            out_path = version_output_path(base_name, ".pptx", config.folders.output)
            result = save_as(handle, str(out_path))
            await _log_office_event("office.pptx.save", f"Saved as {out_path.name}", "powerpoint", fp, output_file=result, start_ms=start_ms)
            return json.dumps({"status": "success", "output_file": result})

        elif name == "office_pptx_export_pdf":
            fp = args["file_path"]
            perm = check_office_permission(OfficeAction.EXPORT_PDF, "powerpoint", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.pptx_adapter import export_pdf
            from pathlib import Path
            base_name = args.get("output_name") or Path(fp).stem
            out_path = version_output_path(base_name, ".pdf", config.folders.output)
            result = await export_pdf(fp, str(out_path))
            await _log_office_event("office.pptx.export_pdf", f"Exported PDF {out_path.name}", "powerpoint", fp, output_file=result, start_ms=start_ms)
            return json.dumps({"status": "success", "output_file": result})

        elif name == "office_pptx_get_metadata":
            fp = args["file_path"]
            handle = _open_handles.get(fp)
            if not handle:
                return json.dumps({"status": "error", "message": "Presentation not open."})
            from shogun.office.adapters.pptx_adapter import get_presentation_metadata
            meta = get_presentation_metadata(handle)
            return json.dumps({"status": "success", "data": meta})

        # ── Outlook Tools ────────────────────────────────────────
        elif name == "office_outlook_create_draft":
            perm = check_office_permission(OfficeAction.CREATE_DRAFT, "outlook", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.outlook_adapter import create_draft
            result = await create_draft(
                recipients=args["recipients"],
                subject=args["subject"],
                body=args["body"],
                cc=args.get("cc"),
                bcc=args.get("bcc"),
            )
            await _log_office_event(
                "office.outlook.create_draft",
                f"Created draft to {', '.join(args['recipients'])}",
                "outlook", start_ms=start_ms,
            )
            return json.dumps({"status": "success", "data": result.to_dict()})

        elif name == "office_outlook_attach_file":
            perm = check_office_permission(OfficeAction.ATTACH_FILE, "outlook", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            from shogun.office.adapters.outlook_adapter import attach_file
            await attach_file(args["draft_id"], args["file_path"])
            await _log_office_event("office.outlook.attach", f"Attached file to draft {args['draft_id']}", "outlook", start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"File attached to draft {args['draft_id']}"})

        elif name == "office_outlook_save_draft":
            from shogun.office.adapters.outlook_adapter import save_draft, open_draft_for_review
            await save_draft(args["draft_id"])
            await open_draft_for_review(args["draft_id"])
            await _log_office_event("office.outlook.save_draft", f"Saved and displayed draft {args['draft_id']}", "outlook", start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Draft {args['draft_id']} saved and opened in Outlook for review."})

        elif name == "office_outlook_send":
            perm = check_office_permission(OfficeAction.SEND_EMAIL, "outlook", tier)
            if not perm.allowed:
                return json.dumps({"status": "blocked", "message": perm.reason})
            if perm.requires_approval:
                return json.dumps({
                    "status": "approval_required",
                    "message": f"Sending email requires human approval at {tier.upper()} posture. The draft has been saved for review.",
                    "draft_id": args["draft_id"],
                })
            from shogun.office.adapters.outlook_adapter import send_with_confirmation
            await send_with_confirmation(args["draft_id"])
            await _log_office_event("office.outlook.send", f"Sent email from draft {args['draft_id']}", "outlook", start_ms=start_ms)
            return json.dumps({"status": "success", "message": f"Email sent from draft {args['draft_id']}"})

        else:
            return json.dumps({"status": "error", "message": f"Unknown office tool: {name}"})

    except OfficeError as exc:
        logger.warning("Office tool error (%s): %s", name, exc)
        elapsed = int(_time.time() * 1000) - start_ms
        try:
            await _log_office_event(
                f"office.error.{name}", str(exc), result="error",
                start_ms=start_ms,
            )
        except Exception:
            pass
        return json.dumps({
            "status": "error",
            "message": "The Office operation could not be completed.",
            "context": {},
        })
    except Exception as exc:
        logger.error("Office tool unexpected error (%s): %s", name, exc, exc_info=True)
        return json.dumps({"status": "error", "message": "The Office operation failed unexpectedly. Check the Shogun logs."})


async def _log_office_event(
    event_type: str,
    action: str,
    application: str = "",
    input_file: str = "",
    output_file: str = "",
    result: str = "success",
    start_ms: int = 0,
) -> None:
    """Helper to emit Office events through EventLogger."""
    import time as _time
    try:
        from shogun.services.event_logger import EventLogger
        elapsed = int(_time.time() * 1000) - start_ms if start_ms else None
        await EventLogger.emit_office_event(
            event_type=event_type,
            action=action,
            application=application,
            input_file=input_file,
            output_file=output_file,
            result=result,
            duration_ms=elapsed,
        )
    except Exception as exc:
        logger.debug("Failed to log office event: %s", exc)


# ── Workspace Tool Execution ─────────────────────────────────────────

def _validate_workspace_path(
    workspace_root: str,
    relative_path: str,
    allowed_roots: list[str] | None = None,
) -> str:
    """Resolve a relative path against the workspace root and validate it.

    Returns the absolute path string if valid.
    Raises ValueError if the path escapes the workspace boundary.
    """
    from pathlib import Path

    root = Path(workspace_root).resolve()
    requested = Path(relative_path)
    if ".." in requested.parts:
        raise ValueError(f"Path traversal blocked: '{relative_path}' cannot contain '..'")

    target = requested.resolve() if requested.is_absolute() else (root / requested).resolve()
    permitted_roots = [root, *(Path(item).resolve() for item in (allowed_roots or []))]
    if not any(target == allowed or allowed in target.parents for allowed in permitted_roots):
        raise ValueError(f"Path escape blocked: '{relative_path}' is outside the configured workspace roots")

    return str(target)


async def _execute_ide_tool(name: str, args: dict[str, Any]) -> str:
    """Route agent calls through the same governed IDE service as the API/bridge."""
    from shogun.services.ide_service import ide_service
    try:
        workspace_id = str(args.get("workspace_id", ""))
        if name == "ide_list_workspaces":
            result = [ide_service.public_workspace(item) for item in ide_service.workspaces.values() if item.approved]
        elif name == "ide_list_files":
            result = await ide_service.list_files(workspace_id, str(args.get("glob") or "*"))
        elif name == "ide_read_file":
            result = await ide_service.read_file(workspace_id, str(args.get("path") or ""))
        elif name == "ide_search":
            result = await ide_service.search(workspace_id, str(args.get("query") or ""), str(args.get("glob") or "*"))
        elif name == "ide_apply_patch":
            result = await ide_service.write(workspace_id, str(args.get("path") or ""), str(args.get("content") or ""), approval=bool(args.get("approved")))
        elif name == "ide_run_task":
            result = await ide_service.run_command(workspace_id, str(args.get("command") or ""), approval=bool(args.get("approved")))
        elif name == "ide_memory_search":
            result = await ide_service.search_programming_memory(
                workspace_id,
                str(args.get("query") or ""),
                int(args.get("limit") or 8),
                bool(args.get("include_global")),
            )
        elif name == "ide_memory_store":
            result = await ide_service.remember_programming_solution(workspace_id, args)
        elif name == "ide_memory_reinforce":
            result = await ide_service.reinforce_programming_memory(
                workspace_id,
                str(args.get("memory_id") or ""),
                bool(args.get("successful", True)),
            )
        else:
            return json.dumps({"status": "error", "message": f"Unknown IDE tool: {name}"})
        return json.dumps({"status": "success", "result": result}, default=str)
    except Exception:
        logger.exception("IDE tool execution failed")
        return json.dumps({"status": "error", "message": "IDE tool execution failed. Check the Shogun logs."})


async def _execute_workspace_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a workspace file-system tool.

    All operations are gated by the posture guard (blocked at SHRINE)
    and path-validated to stay inside the workspace boundary.
    """
    from pathlib import Path

    from shogun.services.posture_guard import check_workspace_access, get_posture_permissions
    from shogun.services.tool_gate import get_tool_allowed_roots, get_toolgate_scope

    try:
        workspace_root = await check_workspace_access()
        posture = await get_posture_permissions()
        scope = get_toolgate_scope(posture)["key"]
        configured_roots = [str(path) for path in get_tool_allowed_roots(name, scope)]
    except Exception:
        logger.exception("Workspace access check failed")
        return json.dumps({"status": "error", "message": "Workspace access was denied."})

    try:
        if name == "workspace_info":
            root = Path(workspace_root)
            total_files = sum(1 for _ in root.rglob("*") if _.is_file())
            total_dirs = sum(1 for _ in root.rglob("*") if _.is_dir())
            total_size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
            size_mb = round(total_size / (1024 * 1024), 2)
            return json.dumps({
                "status": "success",
                "workspace_path": workspace_root,
                "enabled": True,
                "total_files": total_files,
                "total_directories": total_dirs,
                "total_size_mb": size_mb,
                "message": f"Workspace at {workspace_root} — {total_files} files, {total_dirs} directories, {size_mb} MB",
            })

        elif name == "workspace_list":
            rel_path = args.get("path", ".").strip() or "."
            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            if not target_path.exists():
                return json.dumps({"status": "error", "message": f"Directory not found: {rel_path}"})
            if not target_path.is_dir():
                return json.dumps({"status": "error", "message": f"Not a directory: {rel_path}"})

            entries = []
            for item in sorted(target_path.iterdir()):
                entry = {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                }
                if item.is_file():
                    entry["size_bytes"] = item.stat().st_size
                elif item.is_dir():
                    entry["children"] = sum(1 for _ in item.iterdir())
                entries.append(entry)

            return json.dumps({
                "status": "success",
                "path": rel_path,
                "entries": entries,
                "count": len(entries),
            })

        elif name == "workspace_read":
            rel_path = args.get("path", "").strip()
            if not rel_path:
                return json.dumps({"status": "error", "message": "Missing required parameter: path"})

            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            if not target_path.exists():
                return json.dumps({"status": "error", "message": f"File not found: {rel_path}"})
            if not target_path.is_file():
                return json.dumps({"status": "error", "message": f"Not a file: {rel_path}"})

            # Size guard: refuse to read files > 5 MB as text
            size = target_path.stat().st_size
            if size > 5 * 1024 * 1024:
                return json.dumps({"status": "error", "message": f"File too large to read as text: {size} bytes (max 5 MB)"})

            try:
                content = target_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                import mimetypes as _mt
                guessed_mime, _ = _mt.guess_type(target_path.name)
                mime_str = guessed_mime or "unknown"
                hint = ""
                if mime_str.startswith("image/"):
                    hint = " Use the workspace_read_image tool to visually inspect this image."
                elif mime_str == "application/pdf":
                    hint = " Use the workspace_read_pdf tool to extract text from this PDF."
                return json.dumps({
                    "status": "error",
                    "message": f"Cannot read as text (binary file): {rel_path} — detected type: {mime_str}, size: {size} bytes.{hint}",
                })

            return json.dumps({
                "status": "success",
                "path": rel_path,
                "size_bytes": size,
                "content": content,
            })

        elif name == "workspace_write":
            rel_path = args.get("path", "").strip()
            content = args.get("content", "")
            if not rel_path:
                return json.dumps({"status": "error", "message": "Missing required parameter: path"})

            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)

            existed = target_path.exists()
            target_path.write_text(content, encoding="utf-8")
            size = target_path.stat().st_size

            return json.dumps({
                "status": "success",
                "path": rel_path,
                "action": "overwritten" if existed else "created",
                "size_bytes": size,
                "message": f"{'Overwrote' if existed else 'Created'} {rel_path} ({size} bytes)",
            })

        elif name == "workspace_mkdir":
            rel_path = args.get("path", "").strip()
            if not rel_path:
                return json.dumps({"status": "error", "message": "Missing required parameter: path"})

            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            existed = target_path.exists()
            target_path.mkdir(parents=True, exist_ok=True)

            return json.dumps({
                "status": "success",
                "path": rel_path,
                "action": "already_exists" if existed else "created",
                "message": f"{'Already exists' if existed else 'Created'}: {rel_path}",
            })

        elif name == "workspace_delete":
            rel_path = args.get("path", "").strip()
            if not rel_path:
                return json.dumps({"status": "error", "message": "Missing required parameter: path"})

            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            if not target_path.exists():
                return json.dumps({"status": "error", "message": f"File not found: {rel_path}"})
            if target_path.is_dir():
                return json.dumps({"status": "error", "message": f"Cannot delete directories — only files: {rel_path}"})

            size = target_path.stat().st_size
            target_path.unlink()

            return json.dumps({
                "status": "success",
                "path": rel_path,
                "deleted_size_bytes": size,
                "message": f"Deleted: {rel_path} ({size} bytes)",
            })

        elif name == "workspace_read_image":
            rel_path = args.get("path", "").strip()
            if not rel_path:
                return json.dumps({"status": "error", "message": "Missing required parameter: path"})

            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            if not target_path.exists():
                return json.dumps({"status": "error", "message": f"File not found: {rel_path}"})
            if not target_path.is_file():
                return json.dumps({"status": "error", "message": f"Not a file: {rel_path}"})

            import mimetypes as _mt
            guessed_mime, _ = _mt.guess_type(target_path.name)
            mime_type = guessed_mime or "application/octet-stream"
            _IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp", "image/tiff"}
            if mime_type not in _IMAGE_MIMES:
                return json.dumps({
                    "status": "error",
                    "message": f"Not a supported image format: {rel_path} (detected: {mime_type}). Supported: JPEG, PNG, GIF, WebP, BMP, TIFF.",
                })

            # Size guard: refuse images > 10 MB
            size = target_path.stat().st_size
            if size > 10 * 1024 * 1024:
                return json.dumps({"status": "error", "message": f"Image too large: {size} bytes (max 10 MB)"})

            import base64
            data = target_path.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")

            return json.dumps({
                "status": "success",
                "path": rel_path,
                "mime_type": mime_type,
                "size_bytes": size,
                "image_data": f"data:{mime_type};base64,{b64}",
                "message": f"Image loaded: {rel_path} ({mime_type}, {size} bytes). Inspect the image_data field to see the image content.",
            })

        elif name == "workspace_read_pdf":
            rel_path = args.get("path", "").strip()
            if not rel_path:
                return json.dumps({"status": "error", "message": "Missing required parameter: path"})

            target = _validate_workspace_path(workspace_root, rel_path, configured_roots)
            target_path = Path(target)

            if not target_path.exists():
                return json.dumps({"status": "error", "message": f"File not found: {rel_path}"})
            if not target_path.is_file():
                return json.dumps({"status": "error", "message": f"Not a file: {rel_path}"})
            if target_path.suffix.lower() != ".pdf":
                return json.dumps({"status": "error", "message": f"Not a PDF file: {rel_path}"})

            # Size guard: refuse PDFs > 20 MB
            size = target_path.stat().st_size
            if size > 20 * 1024 * 1024:
                return json.dumps({"status": "error", "message": f"PDF too large: {size} bytes (max 20 MB)"})

            try:
                from pypdf import PdfReader
            except ImportError:
                return json.dumps({"status": "error", "message": "PDF reading is not available — pypdf library is not installed."})

            try:
                reader = PdfReader(str(target_path))
                total_pages = len(reader.pages)

                # Parse optional page range
                pages_arg = args.get("pages", "").strip()
                page_indices: list[int] = []
                if pages_arg:
                    for part in pages_arg.split(","):
                        part = part.strip()
                        if "-" in part:
                            start_s, end_s = part.split("-", 1)
                            start_i = max(1, int(start_s.strip()))
                            end_i = min(total_pages, int(end_s.strip()))
                            page_indices.extend(range(start_i - 1, end_i))
                        else:
                            idx = int(part) - 1  # 1-based to 0-based
                            if 0 <= idx < total_pages:
                                page_indices.append(idx)
                else:
                    page_indices = list(range(total_pages))

                # Limit to first 50 pages to avoid context overflow
                if len(page_indices) > 50:
                    page_indices = page_indices[:50]
                    truncated = True
                else:
                    truncated = False

                pages_text = []
                for idx in page_indices:
                    page = reader.pages[idx]
                    text = page.extract_text() or ""
                    pages_text.append({
                        "page": idx + 1,
                        "text": text.strip(),
                    })

                # PDF metadata
                meta = reader.metadata
                pdf_meta = {}
                if meta:
                    for key in ["title", "author", "subject", "creator"]:
                        val = getattr(meta, key, None)
                        if val:
                            pdf_meta[key] = str(val)

                full_text = "\n\n".join(p["text"] for p in pages_text if p["text"])
                char_count = len(full_text)

                return json.dumps({
                    "status": "success",
                    "path": rel_path,
                    "size_bytes": size,
                    "total_pages": total_pages,
                    "pages_extracted": len(page_indices),
                    "truncated": truncated,
                    "metadata": pdf_meta,
                    "char_count": char_count,
                    "pages": pages_text,
                    "message": f"Extracted {char_count} characters from {len(page_indices)}/{total_pages} pages of {rel_path}."
                    + (" (truncated to first 50 pages)" if truncated else ""),
                })
            except Exception:
                logger.exception("Workspace PDF read failed")
                return json.dumps({"status": "error", "message": "Failed to read the PDF. Check the Shogun logs."})

        else:
            return json.dumps({"status": "error", "message": f"Unknown workspace tool: {name}"})

    except ValueError as exc:
        logger.warning("Workspace tool request rejected: %s", exc)
        return json.dumps({"status": "error", "message": "The workspace request is invalid."})
    except Exception:
        logger.exception("Workspace tool execution failed")
        return json.dumps({"status": "error", "message": "Workspace tool execution failed. Check the Shogun logs."})


async def _execute_telegram_list_groups() -> str:
    """Return all known Telegram groups from the topic registry."""
    try:
        from shogun.services.telegram_poller import _load_topic_registry
        registry = _load_topic_registry()

        if not registry:
            return json.dumps({
                "status": "success",
                "groups": [],
                "message": "No Telegram groups discovered yet. The bot learns about groups when it is added to them or receives messages. Ask the user to send a message in any group the bot is a member of, or add the bot to a new group.",
            })

        groups = []
        for chat_id, entry in registry.items():
            chat_type = entry.get("chat_type", "")
            if chat_type not in ("group", "supergroup"):
                continue
            topics = entry.get("topics", {})
            topic_list = [
                {
                    "id": tid,
                    "name": tdata.get("name", "unknown"),
                    "status": tdata.get("status", "open"),
                }
                for tid, tdata in sorted(topics.items())
            ]
            groups.append({
                "chat_id": chat_id,
                "title": entry.get("chat_title", "Unknown"),
                "type": chat_type,
                "bot_status": entry.get("bot_status", "member"),
                "topics": topic_list,
                "topic_count": len(topic_list),
            })

        return json.dumps({
            "status": "success",
            "groups": groups,
            "total": len(groups),
            "message": f"Found {len(groups)} known group(s). Note: the bot only knows about groups where it has received at least one event (message or membership change).",
        })
    except Exception:
        logger.exception("telegram_list_groups failed")
        return json.dumps({"status": "error", "message": "Telegram group lookup failed. Check the Shogun logs."})


async def _execute_active_skill_tool(name: str, args: dict[str, Any], db_session) -> str:
    """Deterministic agent-facing surface for Order 9 active usage."""
    import uuid
    from sqlalchemy import select

    from shogun.api.security import _get_agent_posture
    from shogun.db.models.active_skill_run import ActiveSkillRun
    from shogun.db.models.skill import Skill
    from shogun.schemas.skills import SkillActivationRequest
    from shogun.services.active_skill_service import SkillActivationService

    service = SkillActivationService(db_session)
    if name in {"skills_get_active", "skills_explain_active"}:
        run_id = str(args.get("run_id") or "").strip()
        if not run_id:
            return json.dumps({"status": "error", "message": "run_id is required."})
        rows = (await db_session.execute(
            select(ActiveSkillRun, Skill.name)
            .join(Skill, Skill.id == ActiveSkillRun.skill_id)
            .where(ActiveSkillRun.run_id == run_id)
            .order_by(ActiveSkillRun.relevance_score.desc())
        )).all()
        items = [{
            "active_skill_run_id": str(record.id), "skill_id": str(record.skill_id), "name": skill_name,
            "reason": record.activation_reason, "relevance_score": record.relevance_score,
            "activation_mode": record.activation_mode, "injected_tokens": record.injected_tokens,
            "usage_location": record.usage_location, "outcome": record.outcome,
            "conflict_notes": record.conflict_notes or [],
        } for record, skill_name in rows]
        return json.dumps({"status": "success", "run_id": run_id, "active_skills": items, "total": len(items)})
    if name == "skills_request_activation":
        objective = str(args.get("objective") or "").strip()
        if not objective:
            return json.dumps({"status": "error", "message": "objective is required."})
        posture = await _get_agent_posture()
        result = await service.activate(SkillActivationRequest(
            run_id=str(args.get("run_id") or uuid.uuid4()), objective=objective,
            context=str(args.get("context") or ""), posture=posture.get("active_tier", "guarded"),
            available_tools=list(args.get("available_tools") or []), usage_location="agent_request",
            ide_enabled=bool(posture.get("ide_enabled", False)),
        ))
        await db_session.commit()
        result["active_skills"] = [
            {key: str(value) if isinstance(value, uuid.UUID) else value for key, value in item.items()}
            for item in result["active_skills"]
        ]
        return json.dumps({"status": "success", **result}, default=str)
    if name == "skills_report_outcome":
        try:
            record_id = uuid.UUID(str(args.get("active_skill_run_id") or ""))
            record = await service.outcome(record_id, str(args.get("outcome") or "unknown"), args.get("outcome_summary"))
            await db_session.commit()
            return json.dumps({"status": "success", "active_skill_run_id": str(record.id), "outcome": record.outcome})
        except (ValueError, LookupError) as exc:
            logger.warning("Active skill outcome rejected: %s", exc)
            return json.dumps({"status": "error", "message": "The active skill outcome request is invalid."})
    return json.dumps({"status": "error", "message": f"Unknown active skill tool: {name}"})


async def _execute_dojo_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a Dojo / skill management tool.

    All Dojo tools are gated by the ``skill_auto_install`` posture flag
    via ``filter_tools_by_posture``, so they only appear in Campaign/Ronin.
    """
    try:
        if name == "dojo_browse_skills":
            return await _dojo_browse_skills(args)
        elif name == "dojo_install_skill":
            return await _dojo_install_skill(args)
        elif name == "dojo_list_installed":
            return await _dojo_list_installed()
        elif name == "dojo_take_exam":
            return await _dojo_take_exam(args)
        elif name == "dojo_enroll_specialization":
            return await _dojo_enroll_specialization(args)
        elif name == "dojo_evaluate_achievements":
            return await _dojo_evaluate_achievements()
        elif name == "dojo_get_achievements":
            return await _dojo_get_achievements()
        elif name == "dojo_get_transcript":
            return await _dojo_get_transcript()
        else:
            return json.dumps({"status": "error", "message": f"Unknown dojo tool: {name}"})
    except Exception:
        logger.exception("Dojo tool execution failed")
        return json.dumps({"status": "error", "message": "Dojo tool execution failed. Check the Shogun logs."})


async def _dojo_browse_skills(args: dict[str, Any]) -> str:
    """Browse the OpenClaw College catalog."""
    try:
        from shogun.integrations.openclaw_client import get_openclaw_client

        search = args.get("search", "").strip()
        category = args.get("category", "").strip()

        async with get_openclaw_client() as client:
            # First check if OpenClaw is reachable
            healthy = await client.health_check()
            if not healthy:
                return json.dumps({
                    "status": "error",
                    "message": "OpenClaw College is not reachable. The skill catalog may be offline.",
                })

            # The client uses get_skills() with faculty/subcategory/search params
            skills = await client.get_skills(
                search=search or None,
                subcategory=category or None,
                limit=50,
            )

        # Serialize the OpenClawSkill dataclass objects
        skill_list = []
        for skill in skills:
            skill_list.append({
                "id": skill.id,
                "name": skill.name,
                "slug": skill.slug,
                "description": skill.short_description[:200] if skill.short_description else "",
                "faculty": skill.faculty_id,
                "subcategory": skill.subcategory_id,
                "risk_tier": skill.risk_tier,
                "version": skill.version,
                "author": skill.author_name,
                "status": skill.status,
            })

        return json.dumps({
            "status": "success",
            "skills": skill_list,
            "total": len(skill_list),
            "search": search,
            "category": category,
            "message": f"Found {len(skill_list)} skill(s) in the OpenClaw catalog."
            + (f" Search: '{search}'." if search else "")
            + (f" Category: '{category}'." if category else ""),
        })
    except ImportError:
        return json.dumps({
            "status": "error",
            "message": "OpenClaw integration is not available.",
        })
    except Exception:
        logger.exception("dojo_browse_skills failed")
        return json.dumps({
            "status": "error",
            "message": "Failed to browse the OpenClaw catalog. Check the Shogun logs.",
        })


async def _dojo_install_skill(args: dict[str, Any]) -> str:
    """Install an OpenClaw skill into the local Shogun system."""
    from datetime import datetime, timezone

    openclaw_skill_id = args.get("openclaw_skill_id", "").strip()
    skill_name = args.get("skill_name", "").strip()
    description = args.get("description", "").strip()

    if not openclaw_skill_id or not skill_name:
        return json.dumps({
            "status": "error",
            "message": "Both openclaw_skill_id and skill_name are required.",
        })

    try:
        from shogun.db.engine import async_session_factory
        from shogun.db.models.skill import Skill
        from shogun.db.models.skill_installation import SkillInstallation
        from shogun.db.models.skill_source import SkillSource
        from shogun.integrations.openclaw_client import (
            OPENCLAW_BASE_URL,
            OPENCLAW_SOURCE_NAME,
            OPENCLAW_SOURCE_SLUG,
        )
        from sqlalchemy import select

        async with async_session_factory() as db:
            # Ensure OpenClaw source exists
            result = await db.execute(
                select(SkillSource).where(SkillSource.slug == OPENCLAW_SOURCE_SLUG)
            )
            source = result.scalars().first()
            if not source:
                source = SkillSource(
                    name=OPENCLAW_SOURCE_NAME,
                    slug=OPENCLAW_SOURCE_SLUG,
                    source_type="registry",
                    base_url=OPENCLAW_BASE_URL,
                    default_enabled=True,
                    trust_level="certified",
                    sync_policy="manual_refresh",
                    status="active",
                )
                db.add(source)
                await db.flush()

            # Build slug
            slug = skill_name.lower().replace(" ", "-").replace("&", "and")[:100]

            # Check for duplicate
            result = await db.execute(
                select(Skill).where(Skill.slug == slug, Skill.source_id == source.id)
            )
            existing = result.scalars().first()
            if existing and not existing.is_deleted:
                return json.dumps({
                    "status": "success",
                    "already_installed": True,
                    "skill_id": str(existing.id),
                    "skill_name": existing.name,
                    "message": f"Skill '{existing.name}' is already installed.",
                })

            # Create the Skill record
            skill = Skill(
                source_id=source.id,
                name=skill_name,
                slug=slug,
                version="1.0.0",
                skill_type="single",
                manifest={
                    "openclaw_id": openclaw_skill_id,
                    "risk_tier": "standard",
                    "description": description,
                },
                risk_score=0.3,
                trust_score=80,
                status="installed",
            )
            db.add(skill)
            await db.flush()

            # Create the installation record
            installation = SkillInstallation(
                skill_id=skill.id,
                openclaw_skill_id=openclaw_skill_id,
                target_type="global",
                status="installed",
                installed_version="1.0.0",
                auto_update=False,
                quarantine_status="cleared",
                installed_at=datetime.now(timezone.utc),
                installed_by="agent",
            )
            db.add(installation)
            await db.commit()

            return json.dumps({
                "status": "success",
                "installed": True,
                "skill_id": str(skill.id),
                "skill_name": skill.name,
                "version": "1.0.0",
                "installation_id": str(installation.id),
                "message": f"Successfully installed skill '{skill.name}' from OpenClaw College.",
            })

    except Exception:
        logger.exception("Skill installation failed")
        return json.dumps({"status": "error", "message": "Failed to install the skill. Check the Shogun logs."})


async def _dojo_list_installed() -> str:
    """List all installed skills in the local Shogun system."""
    try:
        from shogun.db.engine import async_session_factory
        from shogun.db.models.skill import Skill
        from shogun.db.models.skill_installation import SkillInstallation
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload

        async with async_session_factory() as db:
            result = await db.execute(
                select(SkillInstallation)
                .where(SkillInstallation.status == "installed")
                .options(joinedload(SkillInstallation.skill))
            )
            installations = list(result.scalars().all())

            if not installations:
                return json.dumps({
                    "status": "success",
                    "skills": [],
                    "total": 0,
                    "message": "No skills are currently installed. Use dojo_browse_skills to find skills and dojo_install_skill to install them.",
                })

            skills_data = []
            for inst in installations:
                skill = inst.skill
                if not skill or skill.is_deleted:
                    continue
                skills_data.append({
                    "skill_id": str(skill.id),
                    "openclaw_skill_id": inst.openclaw_skill_id or (skill.manifest or {}).get("openclaw_id", ""),
                    "name": skill.name,
                    "slug": skill.slug,
                    "version": inst.installed_version or skill.version,
                    "status": inst.status,
                    "installed_at": inst.installed_at.isoformat() if inst.installed_at else None,
                    "installed_by": inst.installed_by,
                    "description": (skill.manifest or {}).get("description", ""),
                })

            return json.dumps({
                "status": "success",
                "skills": skills_data,
                "total": len(skills_data),
                "message": f"{len(skills_data)} skill(s) currently installed.",
            })

    except Exception:
        logger.exception("dojo_list_installed failed")
        return json.dumps({"status": "error", "message": "Installed-skill lookup failed. Check the Shogun logs."})


async def _dojo_get_primary_agent(db):
    from sqlalchemy import select

    from shogun.db.models.agent import Agent

    result = await db.execute(
        select(Agent).where(Agent.is_primary == True, Agent.is_deleted == False)
    )
    return result.scalars().first()


async def _dojo_resolve_primary_model(agent: Any, db) -> str:
    if not getattr(agent, "model_routing_profile_id", None):
        return "unknown"
    try:
        from sqlalchemy import select

        from shogun.db.models.model_routing import ModelRoutingProfile

        result = await db.execute(
            select(ModelRoutingProfile).where(ModelRoutingProfile.id == agent.model_routing_profile_id)
        )
        profile = result.scalars().first()
        if profile and profile.rules:
            for rule in profile.rules:
                if isinstance(rule, dict) and rule.get("model"):
                    return rule["model"]
    except Exception:
        pass
    return "unknown"


async def _dojo_take_exam(args: dict[str, Any]) -> str:
    """Take and submit an OpenClaw certification exam for a skill."""
    openclaw_skill_id = (
        args.get("openclaw_skill_id")
        or args.get("skill_id")
        or ""
    ).strip()
    if not openclaw_skill_id:
        return json.dumps({
            "status": "error",
            "message": "openclaw_skill_id is required.",
        })

    try:
        from shogun.api.dojo import _generate_exam_questions
        from shogun.db.engine import async_session_factory
        from shogun.integrations.openclaw_client import get_openclaw_client

        async with async_session_factory() as db:
            agent = await _dojo_get_primary_agent(db)
            if not agent or not agent.openclaw_agent_id:
                return json.dumps({
                    "status": "error",
                    "message": "The primary Shogun agent is not registered with OpenClaw College.",
                })

            async with get_openclaw_client(
                actor_id=agent.openclaw_agent_id,
                api_key=agent.openclaw_api_key or None,
            ) as client:
                test = await client.find_test(openclaw_skill_id)
                if not test:
                    return json.dumps({
                        "status": "error",
                        "message": f"No exam found for skill {openclaw_skill_id}.",
                    })

                test_id = test["id"]
                pass_threshold = max(90, int(test.get("passThreshold", 90)))
                skill_name = test.get("name", "Unknown Skill")
                skill_content = ""
                faculty = "technical"
                try:
                    skill_data = await client.get_skill_by_id(openclaw_skill_id)
                    if skill_data:
                        faculty = getattr(skill_data, "faculty_id", None) or "technical"
                        skill_name = getattr(skill_data, "name", skill_name) or skill_name
                        skill_content = (
                            getattr(skill_data, "description_md", None)
                            or getattr(skill_data, "short_description", None)
                            or ""
                        )
                except Exception:
                    logger.warning(
                        "Could not load skill content for native exam %s",
                        openclaw_skill_id,
                        exc_info=True,
                    )

                questions = test.get("questions", [])
                if not questions:
                    exam = await client.get_test_questions(test_id)
                    questions = exam.get("questions", []) if isinstance(exam, dict) else []

                if not questions:
                    questions = _generate_exam_questions(skill_name, faculty)

                from shogun.services.openclaw_exam_service import answer_exam_questions

                exam_attempt = await answer_exam_questions(
                    db,
                    agent,
                    skill_name=skill_name,
                    skill_content=skill_content,
                    questions=questions,
                )
                total = exam_attempt["total"]
                correct = exam_attempt["correct"]
                score = exam_attempt["score"]
                model_id = await _dojo_resolve_primary_model(agent, db)
                log_artifact = (
                    f"Native Dojo exam by {agent.name} ({agent.openclaw_agent_id})\n"
                    f"Model: {model_id}\n"
                    f"Test: {test_id} | Questions: {total} | Score: {score}%\n"
                    f"Model-grounded answers: {correct}/{total} correct"
                )
                college_result = await client.submit_test_result(
                    test_id=test_id,
                    agent_id=agent.openclaw_agent_id,
                    score=score,
                    log_artifact=log_artifact,
                    agent_name=agent.name,
                    model_id=model_id,
                    review=exam_attempt["exam_review"],
                )

            if score >= pass_threshold:
                from shogun.services.skill_memory_sync import mark_skill_achieved_and_sync

                await mark_skill_achieved_and_sync(db, agent.id, openclaw_skill_id)

        return json.dumps({
            "status": "success",
            "openclaw_skill_id": openclaw_skill_id,
            "test_id": test_id,
            "questions_total": total,
            "questions_correct": correct,
            "score": score,
            "pass_threshold": pass_threshold,
            "passed": score >= pass_threshold,
            "agent_name": agent.name,
            "model_id": model_id,
            "college_result": college_result,
            "message": f"Exam completed with score {score}%.",
        })
    except Exception:
        logger.exception("dojo_take_exam failed")
        return json.dumps({"status": "error", "message": "The Dojo exam failed. Check the Shogun logs."})


async def _dojo_get_achievements() -> str:
    """Return local install counts plus College achievements."""
    try:
        from sqlalchemy import func as sa_func, select

        from shogun.db.engine import async_session_factory
        from shogun.db.models.skill_installation import SkillInstallation
        from shogun.integrations.openclaw_client import get_openclaw_client

        async with async_session_factory() as db:
            agent = await _dojo_get_primary_agent(db)
            installed_result = await db.execute(
                select(sa_func.count()).select_from(SkillInstallation).where(
                    SkillInstallation.status == "installed"
                )
            )
            installed_count = installed_result.scalar() or 0
            installed_ids_result = await db.execute(
                select(SkillInstallation.openclaw_skill_id).where(
                    SkillInstallation.status == "installed"
                )
            )
            installed_skill_ids = [row[0] for row in installed_ids_result.fetchall() if row[0]]

            if not agent or not agent.openclaw_agent_id:
                return json.dumps({
                    "status": "success",
                    "registered": False,
                    "skills_installed": installed_count,
                    "installed_skill_ids": installed_skill_ids,
                    "badges": [],
                    "specializations_earned": [],
                    "message": "Local installed skills are available, but the primary agent is not registered with OpenClaw College.",
                })

            async with get_openclaw_client() as client:
                agent_data = await client.get_agent_by_id(agent.openclaw_agent_id)
                badge_catalog = await client.get_badges() if agent_data else []
                specialization_resp = await client.client.get(f"{client.base_url}/specializations")
                specialization_catalog = specialization_resp.json() if specialization_resp.is_success else []

        test_results = (agent_data or {}).get("testResults", [])
        credential_provenance = (agent_data or {}).get("credentialProvenance") or {}
        skill_provenance = credential_provenance.get("skills") or {}
        badge_provenance = credential_provenance.get("badges") or {}
        specialization_provenance = credential_provenance.get("specializations") or {}
        legacy_model = "unknown (legacy credential)"
        specialization_by_id = {item.get("id"): item for item in specialization_catalog}
        specialization_by_badge = {item.get("badgeId"): item for item in specialization_catalog}

        def models_for_specialization(item):
            required_ids = set(item.get("requiredSkillIds") or [])
            models = {
                result.get("modelId") or result.get("model_id") or legacy_model
                for result in test_results
                if result.get("skillId") in required_ids
                and (
                    result.get("verificationStatus") == "approved"
                    or result.get("passed") is True
                    or result.get("score", 0) >= result.get("passThreshold", 85)
                )
            }
            return sorted(models) or [legacy_model]
        achieved_skills = [
            {
                **result,
                "credential_model_ids": (
                    skill_provenance.get(result.get("skillId"), {}).get("modelIds")
                    or [result.get("modelId") or result.get("model_id") or legacy_model]
                ),
            }
            for result in test_results
            if result.get("verificationStatus") == "approved"
            or result.get("passed") is True
            or (result.get("score", 0) >= result.get("passThreshold", 85))
        ]
        exams_passed = sum(
            1 for result in test_results
            if result.get("verificationStatus") == "approved"
            or result.get("passed") is True
            or (result.get("score", 0) >= result.get("passThreshold", 85))
        )
        badge_ids = (agent_data or {}).get("badges", [])
        earned_badges = (agent_data or {}).get("earnedBadges") or [
            {
                **badge,
                "name": badge.get("name") or badge.get("title"),
                "description": badge.get("description") or badge.get("descriptionMd", ""),
            }
            for badge in badge_catalog
            if badge.get("id") in badge_ids
        ]
        earned_badges = [
            {
                **badge,
                "credential_model_ids": (
                    badge_provenance.get(badge.get("id"), {}).get("modelIds")
                    or models_for_specialization(specialization_by_badge.get(badge.get("id"), {}))
                ),
            }
            for badge in earned_badges
        ]
        specialization_ids = (agent_data or {}).get("specializations", [])
        earned_specializations = (agent_data or {}).get("earnedSpecializations") or [
            {**item, "name": item.get("name") or item.get("title")}
            for item in specialization_catalog
            if item.get("id") in specialization_ids
        ]
        earned_specializations = [
            {
                **item,
                "credential_model_ids": (
                    specialization_provenance.get(item.get("id"), {}).get("modelIds")
                    or models_for_specialization(specialization_by_id.get(item.get("id"), item))
                ),
            }
            for item in earned_specializations
        ]
        return json.dumps({
            "status": "success",
            "registered": True,
            "openclaw_agent_id": agent.openclaw_agent_id,
            "agent_name": (agent_data or {}).get("name", agent.name),
            "badges": earned_badges,
            "specializations_earned": earned_specializations,
            "achieved_skills": achieved_skills,
            "credential_provenance": credential_provenance,
            "enrollments": (agent_data or {}).get("enrollments", []),
            "skills_completed": (agent_data or {}).get("skillsCompleted", len({
                result.get("skillId") for result in test_results if result.get("skillId")
            })),
            "skills_installed": installed_count,
            "installed_skill_ids": installed_skill_ids,
            "exams_passed": exams_passed,
            "exams_total": len(test_results),
        })
    except Exception:
        logger.exception("dojo_get_achievements failed")
        return json.dumps({"status": "error", "message": "Achievement lookup failed. Check the Shogun logs."})


async def _dojo_enroll_specialization(args: dict[str, Any]) -> str:
    """Enroll the primary agent and apply prior exam credit immediately."""
    specialization_id = str(args.get("specialization_id") or "").strip()
    if not specialization_id:
        return json.dumps({"status": "error", "message": "specialization_id is required."})
    try:
        from shogun.db.engine import async_session_factory
        from shogun.integrations.openclaw_client import get_openclaw_client

        async with async_session_factory() as db:
            agent = await _dojo_get_primary_agent(db)
            if not agent or not agent.openclaw_agent_id:
                return json.dumps({"status": "error", "message": "Agent is not registered with OpenClaw College."})
            async with get_openclaw_client(
                actor_id=agent.openclaw_agent_id,
                api_key=agent.openclaw_api_key or None,
            ) as client:
                result = await client.enroll_specialization(specialization_id, agent.openclaw_agent_id)
        return json.dumps({"status": "success", **result}, default=str)
    except Exception:
        logger.exception("dojo_enroll_specialization failed")
        return json.dumps({"status": "error", "message": "Specialization enrollment failed. Check the Shogun logs."})


async def _dojo_evaluate_achievements() -> str:
    """Reevaluate all College enrollments for the primary agent."""
    try:
        from shogun.db.engine import async_session_factory
        from shogun.integrations.openclaw_client import get_openclaw_client

        async with async_session_factory() as db:
            agent = await _dojo_get_primary_agent(db)
            if not agent or not agent.openclaw_agent_id:
                return json.dumps({"status": "error", "message": "Agent is not registered with OpenClaw College."})
            async with get_openclaw_client(
                actor_id=agent.openclaw_agent_id,
                api_key=agent.openclaw_api_key or None,
            ) as client:
                result = await client.evaluate_achievements(agent.openclaw_agent_id)
        return json.dumps({"status": "success", **result}, default=str)
    except Exception:
        logger.exception("dojo_evaluate_achievements failed")
        return json.dumps({"status": "error", "message": "Achievement evaluation failed. Check the Shogun logs."})


async def _dojo_get_transcript() -> str:
    """Return the registered agent's OpenClaw transcript."""
    try:
        from shogun.db.engine import async_session_factory
        from shogun.integrations.openclaw_client import get_openclaw_client

        async with async_session_factory() as db:
            agent = await _dojo_get_primary_agent(db)
            if not agent or not agent.openclaw_agent_id:
                return json.dumps({
                    "status": "error",
                    "message": "The primary Shogun agent is not registered with OpenClaw College.",
                })

            async with get_openclaw_client(
                actor_id=agent.openclaw_agent_id,
                api_key=agent.openclaw_api_key or None,
            ) as client:
                transcript = await client.get_agent_transcript(agent.openclaw_agent_id)

        if not transcript:
            return json.dumps({
                "status": "error",
                "message": "Transcript not found.",
            })

        return json.dumps({
            "status": "success",
            "openclaw_agent_id": agent.openclaw_agent_id,
            "test_results": transcript.get("testResults", []),
            "transcript": transcript.get("transcript", []),
            "profile": transcript,
        })
    except Exception:
        logger.exception("dojo_get_transcript failed")
        return json.dumps({"status": "error", "message": "Transcript lookup failed. Check the Shogun logs."})
