"""The Tenshu — Main Gradio application for Shogun mission control."""

from __future__ import annotations

import gradio as gr

from shogun.ui.theme import create_tenshu_theme

# ── Logo as base64 data URI (avoids file-serving config) ─────
import pathlib
import base64

def _logo_data_uri() -> str:
    """Load the Shogun logo as a base64 data URI."""
    logo_path = pathlib.Path(__file__).parent / "static" / "images" / "shogun-logo.png"
    if logo_path.exists():
        data = logo_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{b64}"
    return ""

_LOGO_URI = _logo_data_uri()


# ── Custom CSS ───────────────────────────────────────────────
TENSHU_CSS = """
/* Force dark mode at the root level */
html, body {
    color-scheme: dark !important;
}

:root, .dark, .gradio-container {
    --body-background-fill: #0a0e1a !important;
    --background-fill-primary: #0e1225 !important;
    --background-fill-secondary: #121830 !important;
    --border-color-primary: #1a2040 !important;
    --body-text-color: #c8d0d8 !important;
    --body-text-color-subdued: #7a8899 !important;
    --block-background-fill: #0e1225 !important;
    --block-border-color: #1a2040 !important;
    --block-title-text-color: #c8d0d8 !important;
    --block-label-text-color: #7a8899 !important;
    --input-background-fill: #121830 !important;
    --input-border-color: #1a2040 !important;
    --button-primary-background-fill: #4a8cc7 !important;
    --button-primary-background-fill-hover: #6eb5e8 !important;
    --button-primary-text-color: #ffffff !important;
    --button-secondary-background-fill: #121830 !important;
    --button-secondary-text-color: #c8d0d8 !important;
    --table-even-background-fill: #121830 !important;
    --table-odd-background-fill: #0e1225 !important;
    --table-row-focus: #1a2040 !important;
    --neutral-50: #0a0e1a !important;
    --neutral-100: #0e1225 !important;
    --neutral-200: #121830 !important;
    --neutral-300: #1a2040 !important;
    --neutral-400: #3a4560 !important;
    --neutral-500: #5a6580 !important;
    --neutral-600: #7a8899 !important;
    --neutral-700: #c8d0d8 !important;
    --neutral-800: #e0e6eb !important;
    --neutral-900: #f0f2f5 !important;
    --neutral-950: #ffffff !important;
    --color-accent: #4a8cc7 !important;
    --shadow-drop: 0 2px 8px rgba(0,0,0,0.5) !important;
    --block-shadow: 0 2px 8px rgba(0,0,0,0.5) !important;
}

/* Global container */
.gradio-container {
    max-width: 100% !important;
    background: #0a0e1a !important;
    color: #c8d0d8 !important;
}
.dark .gradio-container, .gradio-container {
    background: #0a0e1a !important;
}

/* Top bar — deep black with subtle steel-blue bottom glow */
.shogun-topbar {
    background: linear-gradient(135deg, #050508 0%, #0a0e1a 100%) !important;
    border-bottom: 1px solid #1a2040;
    box-shadow: 0 2px 12px rgba(74, 140, 199, 0.08);
    padding: 6px 16px !important;
    min-height: 56px;
}
.shogun-topbar .prose h1 {
    font-size: 20px; margin: 0; color: #d4a017;
    text-shadow: 0 0 12px rgba(212, 160, 23, 0.25);
}
.shogun-topbar .prose p { font-size: 12px; margin: 0; color: #7a8899; }

/* Logo in topbar — constrained size */
.shogun-logo-wrap {
    display: flex; align-items: center; gap: 12px;
}
.shogun-logo-wrap img {
    height: 44px !important; width: auto !important;
    max-height: 44px !important;
    object-fit: contain;
    filter: drop-shadow(0 0 6px rgba(74, 140, 199, 0.3));
}

/* Status pills */
.status-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.status-online  { background: #0a3020; color: #6ee7b7; }
.status-healthy { background: #0a3020; color: #6ee7b7; }
.status-warning { background: #3d2808; color: #f0c040; }
.status-error   { background: #3d0808; color: #fca5a5; }
.status-offline { background: #121830; color: #7a8899; }

/* Left nav — matches deep black */
.shogun-nav {
    background: #050508 !important;
    border-right: 1px solid #1a2040;
    min-width: 180px;
}
.shogun-nav button {
    text-align: left !important;
    justify-content: flex-start !important;
    border: none !important;
    border-radius: 6px !important;
    margin: 2px 4px !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    color: #7a8899 !important;
    background: transparent !important;
    transition: all 0.2s ease !important;
}
.shogun-nav button:hover {
    background: #121830 !important;
    color: #c8d0d8 !important;
}
.shogun-nav button.selected {
    background: #121830 !important;
    color: #4a8cc7 !important;
    font-weight: 600 !important;
    border-left: 2px solid #d4a017 !important;
}

/* Cards + all block/panel backgrounds */
.shogun-card,
.block, .panel, .form, .tabitem, .tab-nav,
.table-wrap, .dataframe {
    background: #121830 !important;
    border-color: #1a2040 !important;
}
.shogun-card {
    border-radius: 10px;
    padding: 16px;
}

/* Main workspace */
.shogun-main {
    padding: 16px !important;
    overflow-y: auto;
    background: #0e1225 !important;
}

/* Tables — dark rows */
.dataframe tbody tr { background: #0e1225 !important; color: #c8d0d8 !important; }
.dataframe tbody tr:nth-child(even) { background: #121830 !important; }
.dataframe thead { background: #121830 !important; color: #c8d0d8 !important; }
.dataframe td, .dataframe th { border-color: #1a2040 !important; color: #c8d0d8 !important; }

/* Inputs, dropdowns */
input, textarea, select, .input-wrap, .secondary-wrap {
    background: #121830 !important;
    color: #c8d0d8 !important;
    border-color: #1a2040 !important;
}

/* Button overrides */
.primary { background: #4a8cc7 !important; }
.primary:hover { background: #6eb5e8 !important; }
.secondary { background: #121830 !important; border-color: #1a2040 !important; }
.stop { background: #7f1d1d !important; }

/* Section headers — gold accent */
.section-header {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #d4a017;
    margin: 16px 0 8px 0;
    font-weight: 700;
}

/* Gold accent for h2 page titles */
.shogun-main .prose h2 { color: #6eb5e8; }
.shogun-main .prose h3 { color: #c8d0d8; }
"""

# ── Navigation Items ─────────────────────────────────────────
NAV_ITEMS = [
    ("⬡ Overview", "overview"),
    ("Shogun", "shogun"),
    ("Samurai", "samurai"),
    ("Archives", "archives"),
    ("Kaizen", "kaizen"),
    ("Bushido", "bushido"),
    ("The Katana", "katana"),
    ("The Torii", "torii"),
    ("Dojo", "dojo"),
    ("Logs", "logs"),
    ("Help & Guide", "guide"),
]


def _status_pill(text: str, status: str = "online") -> str:
    """Generate HTML for a status pill."""
    return f'<span class="status-pill status-{status}">{text}</span>'


def _build_top_bar():
    """Build the top status bar with Shogun logo."""
    with gr.Row(elem_classes=["shogun-topbar"]):
        with gr.Column(scale=2, min_width=240):
            gr.HTML(
                f"""<div style="display:flex; align-items:center; gap:12px;">
                    <img src="{_LOGO_URI}" alt="Shogun"
                         style="height:44px; width:auto; max-height:44px; object-fit:contain;
                                filter:drop-shadow(0 0 6px rgba(74,140,199,0.3));" />
                    <div>
                        <div style="font-size:18px; font-weight:700; color:#d4a017;
                             text-shadow: 0 0 10px rgba(212,160,23,0.2);">
                            SHOGUN
                        </div>
                        <div style="font-size:11px; color:#7a8899;">
                            The Tenshu — Mission Control
                        </div>
                    </div>
                </div>"""
            )
        with gr.Column(scale=4, min_width=300):
            gr.HTML(
                f"""<div style="display:flex; gap:12px; align-items:center; padding-top:8px; flex-wrap:wrap;">
                    {_status_pill("Runtime: Online", "online")}
                    {_status_pill("Security: Guarded", "healthy")}
                    {_status_pill("Telegram: N/A", "offline")}
                    {_status_pill("Qdrant: Pending", "warning")}
                    {_status_pill("0 Samurai", "offline")}
                </div>"""
            )
        with gr.Column(scale=1, min_width=120):
            gr.HTML(
                '<div style="text-align:right; padding-top:10px; color:#7a8899; font-size:12px;">'
                'v0.1.0</div>'
            )


def _build_page_overview():
    """Overview page — command center summary."""
    gr.Markdown("## Overview", elem_id="page-title")
    gr.Markdown("*Central command dashboard. Monitor system health, active profiles, and real-time event streams.*")

    refresh_btn = gr.Button("🔄 Refresh Dashboard", variant="secondary", size="sm")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### System Health")
            health_table = gr.Dataframe(
                value=[
                    ["Runtime", "🟢 Online"],
                    ["Database", "🟢 Healthy"],
                    ["Qdrant", "🟡 Pending"],
                    ["Telegram", "⚪ Not Configured"],
                ],
                headers=["Component", "Status"],
                interactive=False,
            )
        with gr.Column():
            gr.Markdown("### Active Shogun Profile")
            shogun_table = gr.Dataframe(
                value=[
                    ["Persona", "Not configured"],
                    ["Status", "—"],
                    ["Spawn Policy", "—"],
                    ["Autonomy", "—"],
                ],
                headers=["Setting", "Value"],
                interactive=False,
            )
        with gr.Column():
            gr.Markdown("### Security Posture")
            security_table = gr.Dataframe(
                value=[
                    ["Tier", "Guarded"],
                    ["File Access", "Scoped"],
                    ["Network", "Allowlist"],
                    ["Shell", "Disabled"],
                ],
                headers=["Domain", "Status"],
                interactive=False,
            )

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Active Samurai")
            samurai_table = gr.Dataframe(
                value=[],
                headers=["Name", "Role", "Status", "Model", "Last Active"],
                interactive=False,
            )
        with gr.Column():
            gr.Markdown("### Recent Events")
            gr.Dataframe(
                value=[],
                headers=["Time", "Source", "Event", "Severity"],
                interactive=False,
            )

    gr.Markdown("### Quick Actions")
    with gr.Row():
        gr.Button("➕ Create Samurai", variant="primary", size="sm")
        gr.Button("📦 Install Skill", variant="secondary", size="sm")
        gr.Button("🔄 Run Bushido", variant="secondary", size="sm")
        gr.Button("📂 Open Archives", variant="secondary", size="sm")
        gr.Button("🛡 Change Security Tier", variant="secondary", size="sm")

    # Wire refresh
    def _refresh_overview():
        from shogun.ui.ui_actions import load_overview
        data = load_overview()
        return (
            data["health"],
            data["shogun_profile"],
            data["security"],
            data["samurai_rows"],
        )

    refresh_btn.click(
        fn=_refresh_overview,
        outputs=[health_table, shogun_table, security_table, samurai_table],
    )



def _build_page_shogun():
    """Shogun configuration page."""
    gr.Markdown("## Shogun Configuration")
    gr.Markdown("*Define the core identity, primary persona, and base intelligence stack for your Shogun.*")

    status_msg = gr.Markdown("", elem_id="shogun-status")

    with gr.Tabs():
        with gr.Tab("General"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Identity & Persona")
                    name_input = gr.Textbox(label="Name", value="Primary Shogun")
                    persona_dd = gr.Dropdown(
                        label="Persona",
                        choices=["Strategist", "Field Commander", "Analyst"],
                        value="Strategist",
                    )
                    tone_dd = gr.Dropdown(
                        label="Tone",
                        choices=["analytical", "direct", "supportive", "strategic"],
                        value="analytical",
                    )
                    autonomy_slider = gr.Slider(
                        label="Autonomy", minimum=0, maximum=100, value=50, step=10
                    )
                    risk_dd = gr.Dropdown(
                        label="Risk Tolerance",
                        choices=["low", "medium", "high"],
                        value="low",
                    )
                    verbosity_dd = gr.Dropdown(
                        label="Verbosity",
                        choices=["low", "medium", "high"],
                        value="medium",
                    )
                with gr.Column():
                    gr.Markdown("### Model Stack")
                    gr.Dropdown(label="Primary Model", choices=["(Configure providers first)"])
                    gr.Dropdown(label="Fallback 1", choices=["(Configure providers first)"])
                    gr.Dropdown(label="Fallback 2", choices=["(Configure providers first)"])
                    gr.Dropdown(label="Routing Policy", choices=["Balanced", "Cost-optimized", "Quality-first"])
                    gr.Number(label="Temperature", value=0.4, minimum=0, maximum=2, step=0.1)
                    gr.Number(label="Max Context Injection", value=8, minimum=1, maximum=50, step=1)
            with gr.Row():
                save_btn = gr.Button("💾 Save Configuration", variant="primary")
                gr.Button("🧪 Test Persona", variant="secondary")
                revert_btn = gr.Button("↩ Revert", variant="secondary")
        with gr.Tab("Behavior"):
            gr.Markdown("### Kaizen Excerpt")
            gr.Code(label="Behavioral Rules", language="yaml", value="priorities:\n  - Safety before autonomy\n  - Use existing skills when possible\n  - Escalate ambiguous high-risk actions")
        with gr.Tab("Permissions"):
            gr.Markdown("### Permissions Summary")
            gr.Dataframe(
                value=[
                    ["Network", "Limited (Allowlist)"],
                    ["File Write", "App scope only"],
                    ["Subagent Spawn", "Allowed"],
                    ["Skill Auto-install", "Off"],
                ],
                headers=["Permission", "Status"],
                interactive=False,
            )

    # Wire save
    def _save_config(name, persona, tone, autonomy, risk, verbosity):
        from shogun.ui.ui_actions import save_shogun_config
        return save_shogun_config(name, persona, tone, autonomy, risk, verbosity)

    save_btn.click(
        fn=_save_config,
        inputs=[name_input, persona_dd, tone_dd, autonomy_slider, risk_dd, verbosity_dd],
        outputs=[status_msg],
    )

    # Wire revert (reload from DB)
    def _revert_config():
        from shogun.ui.ui_actions import load_shogun_config
        cfg = load_shogun_config()
        autonomy_map = {"low": 20, "medium": 50, "high": 80}
        return (
            cfg["name"],
            gr.update(value=cfg["persona"], choices=cfg["persona_names"] or ["Strategist", "Field Commander", "Analyst"]),
            cfg["tone"],
            autonomy_map.get(cfg["autonomy"], 50),
            cfg["risk_tolerance"],
            cfg["verbosity"],
            f"*Loaded from database.*",
        )

    revert_btn.click(
        fn=_revert_config,
        outputs=[name_input, persona_dd, tone_dd, autonomy_slider, risk_dd, verbosity_dd, status_msg],
    )


def _build_page_samurai():
    """Samurai management page."""
    gr.Markdown("## Samurai Management")
    gr.Markdown("*Deploy and manage specialized autonomous agents (Samurai) to execute domain-specific missions.*")

    samurai_status = gr.Markdown("", elem_id="samurai-status")
    # Hidden state for selected agent ID
    selected_id = gr.State("")

    with gr.Row():
        with gr.Column(scale=1, min_width=200):
            gr.Markdown("### Registry")
            refresh_btn = gr.Button("🔄 Refresh", variant="secondary", size="sm")
            registry_table = gr.Dataframe(
                value=[],
                headers=["Name", "Slug", "Status", "ID"],
                interactive=False,
            )
        with gr.Column(scale=3):
            gr.Markdown("### Samurai Configuration")
            gr.Markdown("*Fill in the fields below and click Create to add a new Samurai.*")
            with gr.Row():
                sam_name = gr.Textbox(label="Name", interactive=True)
                sam_role = gr.Dropdown(label="Role", choices=["research", "coding", "security", "memory", "custom"], value="research")
            with gr.Row():
                sam_persona = gr.Dropdown(label="Persona", choices=["Analyst", "Strategist", "Field Commander"], value="Analyst")
                gr.Dropdown(label="Primary Model", choices=["(Configure providers first)"])
            with gr.Row():
                sam_security = gr.Dropdown(label="Security Tier", choices=["shrine", "guarded", "tactical", "campaign", "ronin"], value="guarded")
                sam_spawn = gr.Dropdown(label="Spawn Rule", choices=["manual", "auto", "shogun_decides"], value="manual")
            with gr.Row():
                create_btn = gr.Button("➕ Create New", variant="primary", size="sm")
                gr.Button("📋 Duplicate", variant="secondary", size="sm")
                suspend_btn = gr.Button("⏸ Suspend", variant="secondary", size="sm")
                delete_btn = gr.Button("🗑 Delete", variant="stop", size="sm")

    gr.Markdown("### Active / Recent Missions")
    gr.Dataframe(
        value=[],
        headers=["Mission ID", "Samurai", "Task", "Status", "Duration", "Outcome"],
        interactive=False,
    )

    # Wire Refresh
    def _refresh_samurai():
        from shogun.ui.ui_actions import list_samurai
        return list_samurai()

    refresh_btn.click(fn=_refresh_samurai, outputs=[registry_table])

    # Wire Create
    def _create_samurai(name, role, persona, security, spawn):
        from shogun.ui.ui_actions import create_samurai, list_samurai
        msg = create_samurai(name, role, persona, security, spawn)
        rows = list_samurai()
        return msg, rows, ""  # clear name field

    create_btn.click(
        fn=_create_samurai,
        inputs=[sam_name, sam_role, sam_persona, sam_security, sam_spawn],
        outputs=[samurai_status, registry_table, sam_name],
    )

    # Wire row select → capture agent ID
    def _on_row_select(evt: gr.SelectData, table_data):
        if evt.index and len(evt.index) >= 1:
            row_idx = evt.index[0]
            if table_data and row_idx < len(table_data):
                agent_id = table_data[row_idx][3]  # ID column
                agent_name = table_data[row_idx][0]
                return agent_id, f"*Selected: {agent_name}*"
        return "", ""

    registry_table.select(
        fn=_on_row_select,
        inputs=[registry_table],
        outputs=[selected_id, samurai_status],
    )

    # Wire Suspend
    def _suspend(agent_id):
        from shogun.ui.ui_actions import suspend_samurai, list_samurai
        msg = suspend_samurai(agent_id)
        rows = list_samurai()
        return msg, rows

    suspend_btn.click(
        fn=_suspend,
        inputs=[selected_id],
        outputs=[samurai_status, registry_table],
    )

    # Wire Delete
    def _delete(agent_id):
        from shogun.ui.ui_actions import delete_samurai, list_samurai
        msg = delete_samurai(agent_id)
        rows = list_samurai()
        return msg, rows, ""

    delete_btn.click(
        fn=_delete,
        inputs=[selected_id],
        outputs=[samurai_status, registry_table, selected_id],
    )


def _build_page_archives():
    """Archives / memory browser page."""
    gr.Markdown("## Archives — Memory Browser")
    gr.Markdown("*Explore and manage the long-term memory layer, including episodic, semantic, and procedural knowledge.*")

    with gr.Row():
        gr.Textbox(label="Search memories", scale=4)
        gr.Dropdown(label="Type", choices=["All", "Episodic", "Semantic", "Procedural", "Persona", "Skills"], scale=1)
        gr.Dropdown(label="Agent", choices=["All"], scale=1)
        gr.Button("🔍 Search", variant="primary", scale=1, size="sm")

    with gr.Row():
        with gr.Column(scale=1, min_width=180):
            gr.Markdown("### Collections")
            gr.Radio(["Episodic", "Semantic", "Procedural", "Persona", "Skills"], label="Memory Type")
        with gr.Column(scale=3):
            gr.Markdown("### Search Results")
            gr.Dataframe(
                value=[],
                headers=["ID", "Type", "Title", "Importance", "Last Recalled"],
                interactive=False,
            )
            gr.Markdown("### Retrieval Inspector")
            gr.Dataframe(
                value=[],
                headers=["Dense Score", "Sparse Score", "Recency Boost", "Persona Boost", "Final"],
                interactive=False,
            )


def _build_page_kaizen():
    """Kaizen constitutional layer page."""
    gr.Markdown("## Kaizen — Constitutional Layer")
    gr.Markdown("*The guiding principles and versioned behavioral rules that define how your agents operate.*")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Current Constitution")
            gr.Code(
                label="Active Kaizen Profile",
                language="yaml",
                value="priorities:\n  - Safety before autonomy\n  - Use existing trusted skills\n  - Escalate ambiguous high-risk actions\n\nbehavior_rules:\n  - rule: Require approval for new external API endpoints\n    severity: high\n\ndelegation_rules:\n  - task_type: research\n    preferred_samurai_role: research",
                interactive=True,
            )
        with gr.Column():
            gr.Markdown("### Proposed Changes")
            gr.Dataframe(
                value=[],
                headers=["Change", "Source", "Status"],
                interactive=False,
            )
    gr.Markdown("### Version History")
    gr.Dataframe(
        value=[],
        headers=["Version", "Change Summary", "Approved By", "Date"],
        interactive=False,
    )


def _build_page_bushido():
    """Bushido reflection engine page."""
    gr.Markdown("## Bushido — Reflection Engine")
    gr.Markdown("*Automated optimization and self-correction loop. Agents reflect on performance to improve over time.*")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Scheduled Cycles")
            gr.Checkbox(label="Nightly Consolidation", value=True)
            gr.Checkbox(label="Weekly Performance Audit", value=True)
            gr.Checkbox(label="Skill Health Check", value=True)
            gr.Checkbox(label="Persona Drift Check", value=False)
            with gr.Row():
                gr.Button("▶ Run Now", variant="primary", size="sm")
                gr.Button("⏸ Pause All", variant="secondary", size="sm")
        with gr.Column():
            gr.Markdown("### Latest Reflection Report")
            gr.Textbox(label="Summary", value="No Bushido cycles have run yet.", lines=6, interactive=False)

    gr.Markdown("### Job Queue")
    gr.Dataframe(
        value=[],
        headers=["Job ID", "Type", "Status", "Started", "Duration", "Outcome"],
        interactive=False,
    )


def _build_page_katana():
    """The Katana — models, APIs, tools page."""
    gr.Markdown("## The Katana — Models, APIs & Tools")
    gr.Markdown("*The toolset hub. Manage LLM providers, API integrations, and specialized agent tools.*")

    with gr.Tabs():
        with gr.Tab("Providers"):
            gr.Button("➕ Add Provider", variant="primary", size="sm")
            gr.Dataframe(
                value=[],
                headers=["Provider", "Type", "Status", "Health", "Models"],
                interactive=False,
            )
        with gr.Tab("Models"):
            gr.Dataframe(
                value=[],
                headers=["Model", "Provider", "Modality", "Context", "Cost", "Status"],
                interactive=False,
            )
        with gr.Tab("APIs & Tools"):
            gr.Button("➕ Add API", variant="primary", size="sm")
            gr.Dataframe(
                value=[],
                headers=["Tool", "Type", "Status", "Risk", "Scope"],
                interactive=False,
            )
        with gr.Tab("Routing Rules"):
            gr.Dataframe(
                value=[],
                headers=["Task Type", "Primary Model", "Fallbacks", "Cost Profile", "Latency Bias"],
                interactive=False,
            )


def _build_page_torii():
    """The Torii — security posture page."""
    gr.Markdown("## The Torii — Security & Permissions")
    gr.Markdown("*Security gateway. Define system-wide safety tiers and monitor environment access-control.*")

    gr.Markdown("### Active Security Tier")
    gr.Radio(
        ["Shrine (Locked)", "Guarded (Default)", "Tactical", "Campaign", "Ronin (Open)"],
        value="Guarded (Default)",
        label="Security Tier",
    )

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Permission Domains")
            gr.Dataframe(
                value=[
                    ["Filesystem", "Scoped", "🟢"],
                    ["Network", "Allowlist", "🟢"],
                    ["Shell / Process", "Disabled", "🟢"],
                    ["Skills", "Approval Required", "🟢"],
                    ["Subagent Spawning", "Allowed (max 5)", "🟡"],
                    ["Memory Writes", "Allowed", "🟡"],
                ],
                headers=["Domain", "Mode", "Risk"],
                interactive=False,
            )
        with gr.Column():
            gr.Markdown("### Safety Controls")
            gr.Checkbox(label="Enable Dry Run Mode", value=False)
            gr.Checkbox(label="Require Approval for New Skills", value=True)
            gr.Checkbox(label="Global Kill Switch", value=True)
            gr.Button("🔴 Activate Kill Switch", variant="stop", size="sm")
            gr.Button("📤 Export Policy", variant="secondary", size="sm")


def _build_page_dojo():
    """Dojo — skills system page."""
    gr.Markdown("## Dojo — Skills System")
    gr.Markdown("*The skill registry. Discover and install specialized capabilities from OpenClaw College.*")

    with gr.Row():
        gr.Dropdown(label="Source", choices=["OpenClawCollege.com"], scale=2)
        gr.Button("🔄 Refresh", variant="secondary", size="sm", scale=1)
        gr.Button("➕ Add Repository", variant="secondary", size="sm", scale=1)

    with gr.Row():
        gr.Textbox(label="Search Skills", scale=4)
        gr.Dropdown(label="Category", choices=["All"], scale=1)
        gr.Dropdown(label="Trust", choices=["All", "Trusted", "Unverified"], scale=1)
        gr.Button("🔍 Search", variant="primary", size="sm", scale=1)

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Available Skills")
            gr.Dataframe(
                value=[],
                headers=["Skill", "Type", "Version", "Trust"],
                interactive=False,
            )
        with gr.Column(scale=2):
            gr.Markdown("### Skill Details")
            gr.Markdown("*Select a skill to view details.*")

    gr.Markdown("### Installed Skills")
    gr.Dataframe(
        value=[],
        headers=["Skill", "Version", "Status", "Auto-update", "Last Health Check"],
        interactive=False,
    )


def _build_page_logs():
    """Logs and audit page."""
    gr.Markdown("## Logs & Audit")
    gr.Markdown("*System-wide diagnostic stream and mission audit trail for transparency and debugging.*")

    with gr.Row():
        gr.Dropdown(label="Severity", choices=["All", "debug", "info", "warn", "error", "critical"], scale=1)
        gr.Dropdown(label="Agent", choices=["All"], scale=1)
        gr.Dropdown(label="Type", choices=["All"], scale=1)
        gr.Textbox(label="Search", scale=2)
        gr.Button("🔍 Filter", variant="primary", size="sm", scale=1)

    gr.Dataframe(
        value=[],
        headers=["Timestamp", "Source", "Event Type", "Severity", "Summary"],
        interactive=False,
    )


def _build_page_guide():
    """Help & Guide page — framework documentation."""
    gr.Markdown("## Shogun — Framework Guide")
    gr.Markdown("*New to Shogun? This guide explains the core architecture and how to master your autonomous workspace.*")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### 🏛 Core Philosophy")
            gr.Markdown(
                "Shogun is a **Modular Monolith** for AI orchestration. It is designed to be "
                "agent-independent, security-first, and zero-dependency (SQLite/Embedded Qdrant)."
            )

            gr.Markdown("### 🛠 High-Level Architecture")
            gr.Markdown(
                "1. **The Shogun**: Your primary 'Strategist' agent. It doesn't do tasks; it delegates them.\n"
                "2. **The Samurai**: Specialized agents created by Shogun to handle specific domains (Coding, Research, etc.).\n"
                "3. **The Katana**: The tools, models, and APIs that agents use to interact with the world.\n"
                "4. **The Dojo**: Where skills are learned and registered (OpenClaw integration).\n"
                "5. **Archives**: Long-term memory storage enabling session-to-session persistence."
            )

        with gr.Column():
            gr.Markdown("### 🚀 Quick Start")
            gr.Markdown(
                "1. **Katana**: First, add an LLM provider (OpenAI, Anthropic, or Ollama) in the Katana tab.\n"
                "2. **Shogun**: Select your primary model and define your Shogun's persona.\n"
                "3. **Torii**: Set your security tier. 'Guarded' is recommended for initial use.\n"
                "4. **Samurai**: Spawn your first specialist to begin executing missions."
            )

            gr.Markdown("### 📜 The Bushido & Kaizen")
            gr.Markdown(
                "- **Kaizen** is the Constitution. It defines the 'laws' your agents cannot break.\n"
                "- **Bushido** is the Reflection engine. It's an automated loop where agents review their "
                "past actions to improve their importance scores and strategy."
            )



# ── Page registry ────────────────────────────────────────────
PAGE_BUILDERS = {
    "overview": _build_page_overview,
    "shogun": _build_page_shogun,
    "samurai": _build_page_samurai,
    "archives": _build_page_archives,
    "kaizen": _build_page_kaizen,
    "bushido": _build_page_bushido,
    "katana": _build_page_katana,
    "torii": _build_page_torii,
    "dojo": _build_page_dojo,
    "logs": _build_page_logs,
    "guide": _build_page_guide,
}


def create_tenshu_ui() -> tuple:
    """Build the complete Tenshu UI.

    Returns:
        Tuple of (app, theme, css, js) — Gradio 6.0 requires
        theme/css/js to be passed to launch() or mount_gradio_app(),
        not to the Blocks constructor.
    """
    theme = create_tenshu_theme()

    # Force dark mode via JS
    dark_js = "() => { document.body.classList.add('dark'); document.querySelector('.gradio-container').classList.add('dark'); }"

    with gr.Blocks(
        title="Shogun — The Tenshu",
    ) as app:
        # Top bar
        _build_top_bar()

        # Main layout
        with gr.Row():
            # Left nav
            with gr.Column(scale=1, min_width=180, elem_classes=["shogun-nav"]):
                gr.Markdown('<p class="section-header">NAVIGATION</p>')
                nav_buttons = []
                for label, key in NAV_ITEMS:
                    btn = gr.Button(label, size="sm", elem_id=f"nav-{key}")
                    nav_buttons.append((btn, key))

            # Main workspace
            with gr.Column(scale=6, elem_classes=["shogun-main"]):
                # Create all pages as separate groups
                page_groups = {}
                for key, builder_fn in PAGE_BUILDERS.items():
                    visible = key == "overview"
                    with gr.Group(visible=visible) as group:
                        builder_fn()
                    page_groups[key] = group

        # Wire navigation
        def make_nav_handler(target_key):
            def handler():
                return [gr.update(visible=(k == target_key)) for k in PAGE_BUILDERS]
            return handler

        for btn, key in nav_buttons:
            btn.click(
                fn=make_nav_handler(key),
                outputs=list(page_groups.values()),
            )

    return app, theme, TENSHU_CSS, dark_js


