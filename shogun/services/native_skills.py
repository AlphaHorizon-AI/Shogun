"""Native Skills — Internal system capabilities exposed directly to the Shogun orchestrator LLM."""

import json
import logging
from typing import Any

from fastapi import HTTPException

from shogun.db.engine import async_session_factory
from shogun.api.agents import _get_system_context

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
            "description": "Store important information in your persistent Archives memory system. Use this when the user shares personal details (e.g. their name), preferences, facts, or anything worth remembering across sessions.",
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
                        "enum": ["episodic", "semantic", "procedural", "persona"],
                        "description": "Type: 'persona' for identity/preferences/personal info, 'semantic' for facts/knowledge, 'episodic' for events, 'procedural' for how-to patterns.",
                    },
                    "importance": {
                        "type": "number",
                        "description": "How important this is (0.0-1.0). Use 0.9+ for identity/preferences, 0.5-0.8 for general facts.",
                    },
                },
                "required": ["title", "content", "memory_type", "importance"],
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
                        "enum": ["consolidation", "reflection", "pruning", "calibration", "health_check", "custom"],
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
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Unique node ID (e.g. 'node-1', 'node-2')."},
                                "node_type": {"type": "string", "enum": ["input", "samurai", "shogun_approval", "logic", "output", "mado_browser"], "description": "Type of node."},
                                "label": {"type": "string", "description": "Display label for the node."},
                                "position_x": {"type": "number", "description": "X position on canvas (start at 100, space 300 apart)."},
                                "position_y": {"type": "number", "description": "Y position on canvas (start at 200, space 150 apart)."},
                                "config": {"type": "object", "description": "Node-specific config (task_description, approval_mode, condition_expression, etc.)."},
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
            "description": "Click a position on the desktop screen. Requires Ronin desktop control with mouse enabled (TACTICAL tier or higher). Use desktop_screenshot first to see the screen and identify coordinates.",
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
            "description": "Type text using the keyboard on the desktop. Requires Ronin desktop control with keyboard enabled (TACTICAL tier or higher). Can also send hotkeys like 'ctrl+c', 'alt+tab', 'enter'.",
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


async def execute_native_tool(name: str, args: dict[str, Any], db_session) -> str:
    """Route tool execution from LLM to underlying services."""
    logger.info(f"Executing native skill: {name} with args {args}")
    
    try:
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

        elif name == "store_memory":
            from shogun.services.memory_service import MemoryService
            from shogun.db.models.agent import Agent
            from sqlalchemy import select

            # Get the primary Shogun agent ID to associate the memory with
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

            mem_svc = MemoryService(db_session)
            importance = float(args.get("importance", 0.7))
            is_pinned = importance >= 0.85  # High-importance memories get auto-pinned
            decay = "slow" if importance >= 0.7 else "medium"
            if is_pinned:
                decay = "pinned"

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
            )
            await db_session.commit()

            return json.dumps({
                "status": "success",
                "message": f"Memory '{args['title']}' stored in Archives (type={args['memory_type']}, importance={importance}, pinned={is_pinned}).",
                "memory_id": str(record.id),
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
            from shogun.services.bushido_schedule_service import BushidoScheduleService
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
                })
            return json.dumps({
                "status": "success",
                "total": total,
                "schedules": jobs,
            })

        elif name == "create_cron_job":
            from shogun.services.bushido_schedule_service import BushidoScheduleService
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
            from shogun.services.bushido_schedule_service import BushidoScheduleService
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

        elif name == "create_agent_flow":
            # ── Posture enforcement: requires agentflow_autonomous ──
            try:
                from shogun.services.posture_guard import get_posture_permissions
                perms = await get_posture_permissions()
                if not perms.get("agentflow_autonomous", False):
                    return json.dumps({
                        "status": "error",
                        "message": "Autonomous Agent Flow creation requires CAMPAIGN or RONIN security tier. Current tier does not permit agentflow_autonomous."
                    })
            except Exception:
                pass  # If posture guard unavailable, allow

            from shogun.services.agent_flow_service import AgentFlowService
            flow_svc = AgentFlowService(db_session)

            # Create the flow
            flow_name = args.get("name", "Untitled Flow")
            flow_desc = args.get("description", "Auto-generated by Shogun")
            flow = await flow_svc.create(
                name=flow_name,
                description=flow_desc,
                trigger_type="manual",
            )

            # Build node and edge payloads
            nodes_data = []
            for i, n in enumerate(args.get("nodes", [])):
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

            await db_session.commit()

            return json.dumps({
                "status": "success",
                "message": f"Agent Flow '{flow_name}' created with {len(nodes_data)} nodes and {len(edges_data)} edges. Open the Samurai Network → Agent Flow tab to view and run it.",
                "flow_id": str(flow.id),
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
        elif name in ("desktop_screenshot", "desktop_click", "desktop_type"):
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

            controller = get_controller()
            await controller.initialize()  # ensure environment detection ran

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
            return await _execute_office_tool(name, args)

        # ── Workspace Tools ──────────────────────────────────────────
        elif name.startswith("workspace_"):
            return await _execute_workspace_tool(name, args)

        else:
            return json.dumps({"status": "error", "message": f"Unknown tool: {name}"})
            
    except Exception as e:
        logger.error(f"Native skill execution failed: {e}", exc_info=True)
        return json.dumps({"status": "error", "message": str(e)})


# ── Office Tool Executor ─────────────────────────────────────────────
# Tracks open workbook/document/presentation handles across tool calls.
_open_handles: dict[str, Any] = {}  # file_path → handle object


async def _execute_office_tool(name: str, args: dict[str, Any]) -> str:
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
            "message": str(exc),
            "context": exc.context.to_dict() if exc.context else {},
        })
    except Exception as exc:
        logger.error("Office tool unexpected error (%s): %s", name, exc, exc_info=True)
        return json.dumps({"status": "error", "message": f"Unexpected error: {exc}"})


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

def _validate_workspace_path(workspace_root: str, relative_path: str) -> str:
    """Resolve a relative path against the workspace root and validate it.

    Returns the absolute path string if valid.
    Raises ValueError if the path escapes the workspace boundary.
    """
    from pathlib import Path

    root = Path(workspace_root).resolve()
    # Reject obvious traversal patterns
    if ".." in relative_path or relative_path.startswith("/") or relative_path.startswith("\\"):
        raise ValueError(f"Path traversal blocked: '{relative_path}' — paths must be relative and cannot contain '..'")

    # Reject UNC paths
    if relative_path.startswith("\\\\"):
        raise ValueError(f"UNC paths are not allowed: '{relative_path}'")

    target = (root / relative_path).resolve()

    # Final containment check
    try:
        target.relative_to(root)
    except ValueError:
        raise ValueError(f"Path escape blocked: '{relative_path}' resolves outside the workspace boundary")

    return str(target)


async def _execute_workspace_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a workspace file-system tool.

    All operations are gated by the posture guard (blocked at SHRINE)
    and path-validated to stay inside the workspace boundary.
    """
    import os
    from pathlib import Path
    from shogun.services.posture_guard import check_workspace_access

    try:
        workspace_root = await check_workspace_access()
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc.detail if hasattr(exc, 'detail') else exc)})

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
            target = _validate_workspace_path(workspace_root, rel_path)
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

            target = _validate_workspace_path(workspace_root, rel_path)
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
                return json.dumps({"status": "error", "message": f"Cannot read as text (binary file): {rel_path}"})

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

            target = _validate_workspace_path(workspace_root, rel_path)
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

            target = _validate_workspace_path(workspace_root, rel_path)
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

            target = _validate_workspace_path(workspace_root, rel_path)
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

        else:
            return json.dumps({"status": "error", "message": f"Unknown workspace tool: {name}"})

    except ValueError as exc:
        return json.dumps({"status": "error", "message": str(exc)})
    except Exception as exc:
        logger.error(f"Workspace tool execution failed: {exc}", exc_info=True)
        return json.dumps({"status": "error", "message": str(exc)})
