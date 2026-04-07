"""Shogun UI — dark control-room Gradio theme for The Tenshu."""

from __future__ import annotations

import gradio as gr


def create_tenshu_theme() -> gr.Theme:
    """Create a dark, mission-control themed Gradio theme."""
    return gr.themes.Base(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        font=gr.themes.GoogleFont("Inter"),
        font_mono=gr.themes.GoogleFont("JetBrains Mono"),
    ).set(
        # Background
        body_background_fill="#0a0e1a",
        body_background_fill_dark="#0a0e1a",
        background_fill_primary="#0f1320",
        background_fill_primary_dark="#0f1320",
        background_fill_secondary="#151a2e",
        background_fill_secondary_dark="#151a2e",
        # Borders
        border_color_primary="#1e2540",
        border_color_primary_dark="#1e2540",
        # Text
        body_text_color="#e2e8f0",
        body_text_color_dark="#e2e8f0",
        body_text_color_subdued="#94a3b8",
        body_text_color_subdued_dark="#94a3b8",
        # Buttons
        button_primary_background_fill="#2563eb",
        button_primary_background_fill_dark="#2563eb",
        button_primary_background_fill_hover="#3b82f6",
        button_primary_background_fill_hover_dark="#3b82f6",
        button_primary_text_color="#ffffff",
        button_primary_text_color_dark="#ffffff",
        button_secondary_background_fill="#1e293b",
        button_secondary_background_fill_dark="#1e293b",
        button_secondary_text_color="#e2e8f0",
        button_secondary_text_color_dark="#e2e8f0",
        # Inputs
        input_background_fill="#151a2e",
        input_background_fill_dark="#151a2e",
        input_border_color="#1e2540",
        input_border_color_dark="#1e2540",
        # Blocks
        block_background_fill="#0f1320",
        block_background_fill_dark="#0f1320",
        block_border_color="#1e2540",
        block_border_color_dark="#1e2540",
        block_title_text_color="#e2e8f0",
        block_title_text_color_dark="#e2e8f0",
        block_label_text_color="#94a3b8",
        block_label_text_color_dark="#94a3b8",
        # Shadows
        block_shadow="0 1px 3px rgba(0,0,0,0.4)",
        block_shadow_dark="0 1px 3px rgba(0,0,0,0.4)",
    )
