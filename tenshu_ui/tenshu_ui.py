import reflex as rx
import asyncio
from shogun.ui.ui_actions import _load_overview

# Theme matching Shogun CSS
style = {
    ":root": {
        "body_background_fill": "#0a0e1a",
        "background_fill_primary": "#0e1225",
        "background_fill_secondary": "#121830",
        "border_color_primary": "#1a2040",
        "body_text_color": "#c8d0d8",
        "body_text_color_subdued": "#7a8899",
        "color_accent": "#4a8cc7",
        "color_accent_hover": "#6eb5e8",
        "gold_accent": "#d4a017",
    },
    "body": {
        "background_color": "#0a0e1a",
        "color": "#c8d0d8",
        "font_family": "system-ui, sans-serif"
    },
    # General layout overrides
    rx.box: {
        "box_sizing": "border-box"
    },
    rx.table.root: {
        "width": "100%",
        "background": "#0e1225",
        "border": "1px solid #1a2040",
        "border_radius": "8px",
        "margin_bottom": "1rem",
    },
    rx.table.header: {
        "background": "#121830",
        "color": "#c8d0d8",
    },
    rx.table.cell: {
        "border_bottom": "1px solid #1a2040",
        "color": "#7a8899",
    },
    rx.table.row_header_cell: {
        "border_bottom": "1px solid #1a2040",
        "color": "#c8d0d8",
    }
}

# --- State Management ---

class ChatState(rx.State):
    chat_history: list[tuple[str, str]] = []
    user_msg: str = ""

    def set_user_msg(self, value: str):
        self.user_msg = value

    def submit_msg(self):
        if not self.user_msg:
            return
        bot_msg = f"Shogun acknowledges: '{self.user_msg}'. Awaiting parameters."
        self.chat_history.append((self.user_msg, bot_msg))
        self.user_msg = ""

class OverviewState(rx.State):
    health_data: list[list[str]] = [
        ["Runtime", "🟢 Online"],
        ["Database", "🟢 Healthy"],
        ["Qdrant", "🟡 Pending"],
        ["Telegram", "⚪ Not Configured"],
    ]
    shogun_profile: list[list[str]] = [
        ["Persona", "Not configured"],
        ["Status", "—"],
        ["Spawn Policy", "—"],
        ["Autonomy", "—"],
    ]
    security_data: list[list[str]] = [
        ["Tier", "Guarded"],
        ["File Access", "Scoped"],
        ["Network", "Allowlist"],
        ["Shell", "Disabled"],
    ]
    samurai_data: list[list[str]] = []

    async def fetch_data(self):
        data = await _load_overview()
        self.health_data = data["health"]
        self.shogun_profile = data["shogun_profile"]
        self.security_data = data["security"]
        self.samurai_data = data["samurai_rows"]

# --- Components ---

# The Top Navigation Bar
def top_bar() -> rx.Component:
    return rx.hstack(
        # Top bar styling
        rx.hstack(
            rx.image(src="/images/shogun-logo.png", height="44px", filter="drop-shadow(0 0 6px rgba(74,140,199,0.3))"),
            rx.vstack(
                rx.heading("SHOGUN", size="4", color="#d4a017", text_shadow="0 0 10px rgba(212,160,23,0.2)", margin="0"),
                rx.text("The Tenshu — Mission Control", size="1", color="#7a8899", margin="0"),
                spacing="0",
                align_items="start"
            ),
            spacing="3",
            align_items="center"
        ),
        width="100%",
        padding="12px 24px",
        background="linear-gradient(135deg, #050508 0%, #0a0e1a 100%)",
        border_bottom="1px solid #1a2040",
        box_shadow="0 2px 12px rgba(74, 140, 199, 0.08)",
    )

# The Left Sidebar Navigation
def sidebar() -> rx.Component:
    nav_items = [
        ("⬡ Overview [Command Center]", "/"),
        ("Shogun [My Agent]", "/shogun"),
        ("Samurai [Sub-Agents]", "/samurai"),
        ("Comms [Chat]", "/chat"),
    ]

    return rx.vstack(
        rx.text("NAVIGATION", size="1", weight="bold", color="#d4a017", margin_bottom="1em", letter_spacing="1.5px"),
        *[
            rx.link(
                rx.button(
                    label,
                    background="transparent",
                    color="#7a8899",
                    _hover={"background": "#121830", "color": "#c8d0d8"},
                    width="100%",
                    justify="start",
                    padding_y="3",
                ),
                href=path,
                width="100%",
                text_decoration="none"
            ) for label, path in nav_items
        ],
        width="250px",
        min_width="250px",
        height="100%",
        background="#050508",
        border_right="1px solid #1a2040",
        padding="20px",
        align_items="stretch",
    )

# The App Layout Wrapper
def layout(*children) -> rx.Component:
    return rx.vstack(
        top_bar(),
        rx.hstack(
            sidebar(),
            rx.box(
                *children,
                padding="24px",
                width="100%",
                height="100%",
                overflow_y="auto",
                background="#0e1225"
            ),
            width="100%",
            height="calc(100vh - 69px)",
            align_items="stretch",
            spacing="0",
        ),
        width="100vw",
        height="100vh",
        spacing="0",
    )

@rx.page(route="/", title="Shogun - Overview", on_load=OverviewState.fetch_data)
def index() -> rx.Component:
    def custom_table(title, headers, rows):
        return rx.vstack(
            rx.heading(title, size="4", color="#c8d0d8", margin_bottom="2"),
            rx.data_table(
                data=rows,
                columns=[{"title": h, "id": str(i)} for i, h in enumerate(headers)],
                pagination=False,
                search=False,
                sort=False,
                style={"background": "#0e1225", "color": "#7a8899"}
            ),
            width="100%",
            align_items="start"
        )

    return layout(
        rx.hstack(
            rx.vstack(
                rx.heading("Overview", size="6", color="#6eb5e8", margin_bottom="2"),
                rx.text("Central command dashboard. Monitor system health, active profiles, and real-time event streams.", color="#c8d0d8"),
                align_items="start"
            ),
            rx.spacer(),
            rx.button("🔄 Refresh Dashboard", on_click=OverviewState.fetch_data, bg="#121830", color="#c8d0d8", border="1px solid #1a2040", _hover={"bg": "#1a2040"}),
            width="100%",
            align_items="center",
            margin_bottom="6"
        ),
        
        rx.hstack(
            custom_table("System Health", ["Component", "Status"], OverviewState.health_data),
            custom_table("Active Shogun Profile", ["Setting", "Value"], OverviewState.shogun_profile),
            custom_table("Security Posture", ["Domain", "Status"], OverviewState.security_data),
            spacing="5",
            width="100%",
            align_items="start",
            margin_bottom="6"
        ),

        rx.hstack(
            custom_table("Active Samurai", ["Name", "Role", "Status", "Model", "Last Active"], OverviewState.samurai_data),
            custom_table("Recent Events", ["Time", "Source", "Event", "Severity"], [
                ["2026-04-14 10:00", "System", "Startup", "info"]
            ]), # Mapped statically for now similar to old gradio logic
            spacing="5",
            width="100%",
            align_items="start",
            margin_bottom="6"
        ),

        rx.heading("Quick Actions", size="4", color="#c8d0d8", margin_bottom="3"),
        rx.hstack(
            rx.button("➕ Create Samurai", bg="#4a8cc7", color="white"),
            rx.button("📦 Install Skill", bg="#121830", color="#c8d0d8"),
            rx.button("🔄 Run Bushido", bg="#121830", color="#c8d0d8"),
            rx.button("📂 Open Archives", bg="#121830", color="#c8d0d8"),
            rx.button("🛡 Change Security Tier", bg="#121830", color="#c8d0d8"),
            spacing="3",
        )
    )

def chat_message(msg: list[str]) -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.text(msg[0], color="white"),
            bg="#121830", padding="3", border_radius="8px", align_self="flex-end", max_width="80%",
            border="1px solid #1a2040"
        ),
        rx.box(
            rx.text(msg[1], color="#d4a017"),
            bg="#050508", padding="3", border_radius="8px", align_self="flex-start", max_width="80%",
            border="1px solid #1a2040"
        ),
        width="100%",
        spacing="3",
        margin_bottom="4"
    )

@rx.page(route="/chat", title="Shogun - Comms")
def chat() -> rx.Component:
    return layout(
        rx.heading("Comms — Direct Chat", size="6", color="#6eb5e8", margin_bottom="2"),
        rx.text("Communicate directly with your primary Shogun agent.", color="#c8d0d8", margin_bottom="4"),
        
        rx.box(
            rx.vstack(
                rx.foreach(ChatState.chat_history, chat_message),
                width="100%",
                flex="1",
                overflow_y="auto",
                padding_y="4",
            ),
            rx.hstack(
                rx.input(
                    placeholder="Send directive to the Shogun...",
                    value=ChatState.user_msg,
                    on_change=ChatState.set_user_msg,
                    width="100%",
                    bg="#121830",
                    border="1px solid #1a2040",
                    color="white",
                    on_key_down=rx.cond(
                        rx.Var.create("e.key === 'Enter'"),
                        ChatState.submit_msg,
                        rx.console_log("key")
                    )
                ),
                rx.button("Send", on_click=ChatState.submit_msg, bg="#4a8cc7", color="white"),
                width="100%",
            ),
            width="100%",
            height="500px",
            display="flex",
            flex_direction="column",
            justify_content="space-between",
            background="#0a0e1a",
            border="1px solid #1a2040",
            border_radius="8px",
            padding="20px"
        )
    )

app = rx.App(style=style)
