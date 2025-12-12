import unicodedata
from dearpygui import dearpygui as dpg
from final_model import get_response, save_convo

# Palette
BG = (14, 18, 28, 255)
PANEL = (22, 28, 42, 255)
TEXT = (230, 232, 238, 255)
SUBTEXT = (170, 176, 189, 255)
ACCENT = (99, 102, 241, 255)
ACCENT_SOFT = (129, 140, 248, 255)
INPUT_BG = (32, 38, 56, 255)
BORDER = (48, 56, 74, 255)
USER_BUBBLE = (46, 59, 92, 255)
ASSIST_BUBBLE = (32, 40, 58, 255)
BUBBLE_BORDER = (60, 70, 90, 255)
MAX_WRAP_WIDTH = 800


def clean_text(text: str) -> str:
    """Normalize text and replace smart punctuation to avoid missing glyphs."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "—": "—",
        "–": "-",
        "…": "...",
        "\u00a0": " ",  # non-breaking space
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def add_message(prefix: str, content: str, color):
    is_user = prefix.lower() == "you"
    content = clean_text(content)
    with dpg.group(parent="chat_window", horizontal=False):
        dpg.add_text(prefix, color=color)
        dpg.add_spacer(height=2)
        dpg.add_text(content, wrap=MAX_WRAP_WIDTH, color=TEXT)
        dpg.add_spacer(height=8)
        dpg.add_separator()
    dpg.set_y_scroll("chat_window", -1)


def send_message(sender, app_data, user_data):
    user_message = dpg.get_value("input_text")
    if not user_message.strip():
        return
    add_message("You", user_message, ACCENT_SOFT)
    dpg.set_value("input_text", "")

    response = get_response(user_message)
    add_message("Max", response, SUBTEXT)


dpg.create_context()
dpg.create_viewport(title="Chat with Max", width=900, height=780)

# Use a bundled TrueType font for better readability
with dpg.font_registry():
    default_font = dpg.add_font("ARIAL.TTF", 18)

# Global theme
with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, BG)
        dpg.add_theme_color(dpg.mvThemeCol_Text, TEXT)
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 8)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 10, 8)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 6, 6)
        dpg.add_theme_color(dpg.mvThemeCol_Border, BORDER)
    with dpg.theme_component(dpg.mvInputText):
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg, INPUT_BG)
        dpg.add_theme_color(dpg.mvThemeCol_Text, TEXT)
        dpg.add_theme_color(dpg.mvThemeCol_Border, BORDER)
    with dpg.theme_component(dpg.mvButton):
        dpg.add_theme_color(dpg.mvThemeCol_Button, ACCENT)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, ACCENT_SOFT)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, ACCENT)

with dpg.window(
    label="Chat with Max",
    tag="main_window",
    width=880,
    height=740,
    pos=(10, 10),
    no_title_bar=True,
):
    dpg.add_text("Chat with Max", color=TEXT, bullet=False, tag="title_text")
    dpg.add_spacer(height=6)
    dpg.add_separator()

    with dpg.child_window(
        tag="chat_window",
        width=-1,
        height=560,
        border=False,
        horizontal_scrollbar=False,
    ):
        dpg.add_text("Say hi to start the conversation.", color=SUBTEXT)

    dpg.add_spacer(height=6)
    with dpg.group(horizontal=True):
        dpg.add_input_text(
            tag="input_text",
            width=650,
            height=45,
            hint="Type your message...",
            on_enter=True,
            callback=send_message,
        )
        dpg.add_button(label="Send", width=150, height=45, callback=send_message)

dpg.bind_theme(global_theme)
dpg.bind_font(default_font)

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()

save_convo()
