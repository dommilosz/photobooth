"""Shared visual styles for the photobooth UI."""

BG_DARK = "#0d0d0d"
BG_PAGE = "#1a1a1a"
BG_NAV = "#222"
BG_CARD = "#252525"
BORDER = "#333"
TEXT = "#eee"
TEXT_DIM = "#aaa"
TEXT_MUTED = "#888"
ACCENT = "#2ecc71"
ACCENT_DIM = "#27ae60"
LINK = "#7eb8da"

BTN_PRIMARY = (
    "QPushButton {{ background: {accent}; color: #fff; font-size: {size}px;"
    "font-weight: bold; border-radius: {radius}px; border: none; padding: {pad}; }}"
    "QPushButton:pressed {{ background: {pressed}; }}"
)

BTN_SECONDARY = (
    "QPushButton {{ background: #3a3a3a; color: {text}; font-size: {size}px;"
    "border-radius: {radius}px; border: none; padding: {pad}; }}"
    "QPushButton:pressed {{ background: #2f2f2f; }}"
)

BTN_ICON = (
    "QPushButton { background: rgba(255,255,255,30); color: #fff; font-size: 22px;"
    "border-radius: 24px; border: 1px solid rgba(255,255,255,40); }"
    "QPushButton:pressed { background: rgba(255,255,255,50); }"
)

CARD = (
    "QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: 12px; }}"
)

GRADIENT_TOP = (
    "QFrame {{ background: qlineargradient("
    "x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,200), stop:1 rgba(0,0,0,0)); }}"
)

GRADIENT_BOTTOM = (
    "QFrame {{ background: qlineargradient("
    "x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0), stop:1 rgba(0,0,0,220)); }}"
)

SECTION_TITLE = (
    "color: {muted}; font-size: 12px; font-weight: bold;"
    "letter-spacing: 1px; margin-top: 4px;"
).format(muted=TEXT_MUTED)

FIELD_LABEL = f"color: {TEXT_DIM}; font-size: 14px; background: transparent;"

SPINBOX = (
    f"QSpinBox {{ background: #333; color: {TEXT}; border: 1px solid #444;"
    f"border-radius: 8px; padding: 10px; font-size: 16px; min-height: 20px; }}"
)

LINE_EDIT = (
    f"QLineEdit {{ background: #333; color: {TEXT}; border: 1px solid #444;"
    f"border-radius: 8px; padding: 10px; font-size: 16px; }}"
)

LINK_BTN = (
    f"QPushButton {{ background: transparent; color: {LINK}; font-size: 14px;"
    f"border: none; text-align: left; padding: 4px 0; }}"
    f"QPushButton:pressed {{ color: #5a9bc4; }}"
)

CHECKBOX = (
    f"QCheckBox {{ color: {TEXT}; font-size: 16px; spacing: 10px; background: transparent; }}"
    f"QCheckBox::indicator {{ width: 22px; height: 22px; border-radius: 6px;"
    f"border: 1px solid #555; background: #333; }}"
    f"QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT_DIM}; }}"
)


def primary_btn(size: int = 28, radius: int = 14, pad: str = "0 32px") -> str:
    return BTN_PRIMARY.format(
        accent=ACCENT, pressed=ACCENT_DIM, size=size, radius=radius, pad=pad
    )


def secondary_btn(size: int = 18, radius: int = 12, pad: str = "0 24px") -> str:
    return BTN_SECONDARY.format(text=TEXT, size=size, radius=radius, pad=pad)


def card_style() -> str:
    return CARD.format(bg=BG_CARD, border=BORDER)
