
# Apple libraries
from Quartz import (
    kCGEventFlagMaskAlternate,
    kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl,
    kCGEventFlagMaskShift,
)


CLAUDE_WEBSITE_URL = "https://claude.ai"
GEMINI_WEBSITE_URL = "https://gemini.google.com?referrer=macos-gemini-overlay"
DEFAULT_WEBSITE_URL = GEMINI_WEBSITE_URL
LOGO_WHITE_PATH = "logo/logo_white.png"
LOGO_BLACK_PATH = "logo/logo_black.png"
FRAME_SAVE_NAME = "GeminiWindowFrame"
APP_TITLE = "Gemini"
PERMISSION_CHECK_EXIT = 1
CORNER_RADIUS = 15.0
DRAG_AREA_HEIGHT = 30
STATUS_ITEM_CONTEXT = 1
MENU_ITEM_SWITCH_TO_CLAUDE = "Switch to Claude"
MENU_ITEM_SWITCH_TO_GEMINI = "Switch to Gemini"
LAUNCHER_TRIGGER_MASK = (
    kCGEventFlagMaskShift |
    kCGEventFlagMaskControl |
    kCGEventFlagMaskAlternate |
    kCGEventFlagMaskCommand
)
# Default trigger is "Option + Space".
LAUNCHER_TRIGGER = {
    "flags": kCGEventFlagMaskAlternate,
    "key": 49
}
