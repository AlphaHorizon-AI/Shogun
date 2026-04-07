"""The Tenshu — Main Gradio application for Shogun mission control."""

from __future__ import annotations

import gradio as gr

from shogun.ui.theme import create_tenshu_theme


# ── Custom CSS ───────────────────────────────────────────────
TENSHU_CSS = """
/* Global */
.gradio-container { max-width: 100% !important; }

/* Top bar */
.shogun-topbar {
    background: linear-gradient(135deg, #0f1320 0%, #151a2e 100%);
    border-bottom: 1px solid #1e2540;
    padding: 8px 16px !important;
    min-height: 60px;
}
.shogun-topbar .prose h1 { font-size: 20px; margin: 0; color: #60a5fa; }
.shogun-topbar .prose p { font-size: 12px; margin: 0; color: #94a3b8; }

/* Status pills */
.status-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}
.status-online { background: #064e3b; color: #6ee7b7; }
.status-healthy { background: #064e3b; color: #6ee7b7; }
.status-warning { background: #78350f; color: #fbbf24; }
.status-error { background: #7f1d1d; color: #fca5a5; }
.status-offline { background: #1e293b; color: #94a3b8; }

/* Left nav */
.shogun-nav {
    background: #0a0e1a !important;
    border-right: 1px solid #1e2540;
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
    color: #94a3b8 !important;
    background: transparent !important;
    transition: all 0.15s ease !important;
}
.shogun-nav button:hover {
    background: #151a2e !important;
    color: #e2e8f0 !important;
}
.shogun-nav button.selected {
    background: #1e293b !important;
    color: #60a5fa !important;
    font-weight: 600 !important;
}

/* Cards */
.shogun-card {
    background: #151a2e;
    border: 1px solid #1e2540;
    border-radius: 10px;
    padding: 16px;
}

/* Main workspace */
.shogun-main {
    padding: 16px !important;
    overflow-y: auto;
}

/* Section headers */
.section-header {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #475569;
    margin: 16px 0 8px 0;
    font-weight: 700;
}
"""

# ── Navigation Items ─────────────────────────────────────────
NAV_ITEMS = [
    ("⬡ Overview", "overview"),
    ("将 Shogun", "shogun"),
    ("侍 Samurai", "samurai"),
    ("巻 Archives", "archives"),
    ("改 Kaizen", "kaizen"),
    ("武 Bushido", "bushido"),
    ("刀 The Katana", "katana"),
    ("⛩ The Torii", "torii"),
    ("道 Dojo", "dojo"),
    ("📋 Logs", "logs"),
]


def _status_pill(text: str, status: str = "online") -> str:
    """Generate HTML for a status pill."""
    return f'<span class="status-pill status-{status}">{text}</span>'


def _build_top_bar():
    """Build the top status bar."""
    with gr.Row(elem_classes=["shogun-topbar"]):
        with gr.Column(scale=2, min_width=200):
            gr.Markdown("# ⬡ SHOGUN\n*The Tenshu — Mission Control*")
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
            gr.Markdown("*v0.1.0*", elem_classes=["text-right"])


def _build_page_overview():
    """Overview page — command center summary."""
    gr.Markdown("## ⬡ Overview", elem_id="page-title")

    with gr.Row():
        with gr.Column():
            gr.Markdown("### System Health")
            gr.Dataframe(
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
            gr.Dataframe(
                value=[
                    ["Persona", "Not configured"],
                    ["Primary Model", "Not configured"],
                    ["Fallbacks", "0"],
                    ["Autonomy", "—"],
                ],
                headers=["Setting", "Value"],
                interactive=False,
            )
        with gr.Column():
            gr.Markdown("### Security Posture")
            gr.Dataframe(
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
            gr.Dataframe(
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


def _build_page_shogun():
    """Shogun configuration page."""
    gr.Markdown("## 将 Shogun Configuration")
    with gr.Tabs():
        with gr.Tab("General"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Identity & Persona")
                    gr.Textbox(label="Name", value="Primary Shogun")
                    gr.Dropdown(label="Persona", choices=["Strategist", "Field Commander", "Analyst"], value="Strategist")
                    gr.Dropdown(label="Tone", choices=["analytical", "direct", "supportive", "strategic"], value="analytical")
                    gr.Slider(label="Autonomy", minimum=0, maximum=100, value=50, step=10)
                    gr.Dropdown(label="Risk Tolerance", choices=["low", "medium", "high"], value="low")
                    gr.Dropdown(label="Verbosity", choices=["low", "medium", "high"], value="medium")
                with gr.Column():
                    gr.Markdown("### Model Stack")
                    gr.Dropdown(label="Primary Model", choices=["(Configure providers first)"])
                    gr.Dropdown(label="Fallback 1", choices=["(Configure providers first)"])
                    gr.Dropdown(label="Fallback 2", choices=["(Configure providers first)"])
                    gr.Dropdown(label="Routing Policy", choices=["Balanced", "Cost-optimized", "Quality-first"])
                    gr.Number(label="Temperature", value=0.4, minimum=0, maximum=2, step=0.1)
                    gr.Number(label="Max Context Injection", value=8, minimum=1, maximum=50, step=1)
            with gr.Row():
                gr.Button("💾 Save Configuration", variant="primary")
                gr.Button("🧪 Test Persona", variant="secondary")
                gr.Button("↩ Revert", variant="secondary")
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


def _build_page_samurai():
    """Samurai management page."""
    gr.Markdown("## 侍 Samurai Management")
    with gr.Row():
        with gr.Column(scale=1, min_width=200):
            gr.Markdown("### Registry")
            gr.Button("➕ Create New", variant="primary", size="sm")
            gr.Dataframe(
                value=[],
                headers=["Name", "Role", "Status"],
                interactive=False,
            )
        with gr.Column(scale=3):
            gr.Markdown("### Samurai Configuration")
            gr.Markdown("*Select a Samurai from the registry, or create a new one.*")
            with gr.Row():
                gr.Textbox(label="Name", interactive=True)
                gr.Dropdown(label="Role", choices=["research", "coding", "security", "memory", "custom"])
            with gr.Row():
                gr.Dropdown(label="Persona", choices=["Analyst", "Strategist", "Field Commander"])
                gr.Dropdown(label="Primary Model", choices=["(Configure providers first)"])
            with gr.Row():
                gr.Dropdown(label="Security Tier", choices=["shrine", "guarded", "tactical", "campaign", "ronin"])
                gr.Dropdown(label="Spawn Rule", choices=["manual", "auto", "shogun_decides"])
            with gr.Row():
                gr.Button("💾 Save", variant="primary", size="sm")
                gr.Button("📋 Duplicate", variant="secondary", size="sm")
                gr.Button("⏸ Suspend", variant="secondary", size="sm")
                gr.Button("🗑 Delete", variant="stop", size="sm")

    gr.Markdown("### Active / Recent Missions")
    gr.Dataframe(
        value=[],
        headers=["Mission ID", "Samurai", "Task", "Status", "Duration", "Outcome"],
        interactive=False,
    )


def _build_page_archives():
    """Archives / memory browser page."""
    gr.Markdown("## 巻 Archives — Memory Browser")
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
    gr.Markdown("## 改 Kaizen — Constitutional Layer")
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
    gr.Markdown("## 武 Bushido — Reflection Engine")
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
    gr.Markdown("## 刀 The Katana — Models, APIs & Tools")
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
    gr.Markdown("## ⛩ The Torii — Security & Permissions")
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
    gr.Markdown("## 道 Dojo — Skills System")
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
    gr.Markdown("## 📋 Logs & Audit")
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
}


def create_tenshu_ui() -> gr.Blocks:
    """Build the complete Tenshu UI."""
    theme = create_tenshu_theme()

    with gr.Blocks(
        theme=theme,
        css=TENSHU_CSS,
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

    return app
