"""Shogun UI — The Tenshu dark theme.

Color palette extracted from the Shogun logo:
  - Deep black background: #050508 → #0a0e1a
  - Steel blue (S-shield, armor): #3a7cc0 → #6eb5e8
  - Gold/amber (kabuto horns, orbs): #d4a017 → #f0c040
  - Silver/metallic (text, plating): #b0bec5 → #e0e6eb
  - Orange glow accent: #e8841c
"""

from __future__ import annotations

import gradio as gr


# ── Logo palette tokens ──────────────────────────────────────
SHOGUN_BLACK = "#050508"
SHOGUN_DARK = "#0a0e1a"
SHOGUN_PANEL = "#0e1225"
SHOGUN_CARD = "#121830"
SHOGUN_BORDER = "#1a2040"

SHOGUN_STEEL = "#4a8cc7"        # primary steel blue
SHOGUN_STEEL_LIGHT = "#6eb5e8"  # lighter steel
SHOGUN_STEEL_DIM = "#2d5a8a"    # muted steel

SHOGUN_GOLD = "#d4a017"         # primary gold
SHOGUN_GOLD_LIGHT = "#f0c040"   # bright gold
SHOGUN_GOLD_DIM = "#8a6a10"     # muted gold

SHOGUN_SILVER = "#c8d0d8"       # primary text
SHOGUN_SILVER_DIM = "#7a8899"   # subdued text
SHOGUN_ORANGE = "#e8841c"       # accent glow


def create_tenshu_theme() -> gr.Theme:
    """Create the Shogun dark theme matching the brand logo."""
    return gr.themes.Base(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        font=gr.themes.GoogleFont("Inter"),
        font_mono=gr.themes.GoogleFont("JetBrains Mono"),
    ).set(
        # Background
        body_background_fill=SHOGUN_DARK,
        body_background_fill_dark=SHOGUN_DARK,
        background_fill_primary=SHOGUN_PANEL,
        background_fill_primary_dark=SHOGUN_PANEL,
        background_fill_secondary=SHOGUN_CARD,
        background_fill_secondary_dark=SHOGUN_CARD,
        # Borders
        border_color_primary=SHOGUN_BORDER,
        border_color_primary_dark=SHOGUN_BORDER,
        # Text — silver/metallic
        body_text_color=SHOGUN_SILVER,
        body_text_color_dark=SHOGUN_SILVER,
        body_text_color_subdued=SHOGUN_SILVER_DIM,
        body_text_color_subdued_dark=SHOGUN_SILVER_DIM,
        # Primary buttons — steel blue
        button_primary_background_fill=SHOGUN_STEEL,
        button_primary_background_fill_dark=SHOGUN_STEEL,
        button_primary_background_fill_hover=SHOGUN_STEEL_LIGHT,
        button_primary_background_fill_hover_dark=SHOGUN_STEEL_LIGHT,
        button_primary_text_color="#ffffff",
        button_primary_text_color_dark="#ffffff",
        # Secondary buttons — dark panel
        button_secondary_background_fill=SHOGUN_CARD,
        button_secondary_background_fill_dark=SHOGUN_CARD,
        button_secondary_text_color=SHOGUN_SILVER,
        button_secondary_text_color_dark=SHOGUN_SILVER,
        # Inputs
        input_background_fill=SHOGUN_CARD,
        input_background_fill_dark=SHOGUN_CARD,
        input_border_color=SHOGUN_BORDER,
        input_border_color_dark=SHOGUN_BORDER,
        # Blocks
        block_background_fill=SHOGUN_PANEL,
        block_background_fill_dark=SHOGUN_PANEL,
        block_border_color=SHOGUN_BORDER,
        block_border_color_dark=SHOGUN_BORDER,
        block_title_text_color=SHOGUN_SILVER,
        block_title_text_color_dark=SHOGUN_SILVER,
        block_label_text_color=SHOGUN_SILVER_DIM,
        block_label_text_color_dark=SHOGUN_SILVER_DIM,
        # Shadows
        block_shadow="0 2px 8px rgba(0,0,0,0.5)",
        block_shadow_dark="0 2px 8px rgba(0,0,0,0.5)",
    )
