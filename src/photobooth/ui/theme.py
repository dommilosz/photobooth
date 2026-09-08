"""Shared visual styles for the photobooth UI."""

BG_DARK = "#0a0a0b"
BG_PAGE = "#121214"
BG_NAV = "#1a1a1d"
BG_CARD = "#1f1f22"
BG_ELEVATED = "#28282c"
BORDER = "#34343a"
BORDER_SUBTLE = "#2a2a2e"
TEXT = "#f4f4f5"
TEXT_DIM = "#a1a1aa"
TEXT_MUTED = "#71717a"
ACCENT = "#3ecf8e"
ACCENT_DIM = "#2eb872"
ACCENT_SOFT = "rgba(62, 207, 142, 0.14)"
LINK = "#7eb8da"
RADIUS_SM = 8
RADIUS_MD = 12
RADIUS_LG = 16
FONT_FAMILY = '"Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif'

BTN_PRIMARY = (
    "QPushButton {{ background: {accent}; color: #0a0a0b; font-family: {font};"
    "font-size: {size}px; font-weight: 700; letter-spacing: 0.5px;"
    "border-radius: {radius}px; border: none; padding: {pad}; }}"
    "QPushButton:hover {{ background: #4fe0a0; }}"
    "QPushButton:pressed {{ background: {pressed}; }}"
)

BTN_SECONDARY = (
    "QPushButton {{ background: {bg}; color: {text}; font-family: {font};"
    "font-size: {size}px; font-weight: 600; border-radius: {radius}px;"
    "border: 1px solid {border}; padding: {pad}; }}"
    "QPushButton:hover {{ background: {hover}; border-color: #48484f; }}"
    "QPushButton:pressed {{ background: #222226; }}"
)

BTN_ICON = (
    f"QPushButton {{ background: {BG_ELEVATED}; color: {TEXT}; font-family: {FONT_FAMILY};"
    f"font-size: 20px; border-radius: 22px; border: 1px solid {BORDER}; }}"
    f"QPushButton:hover {{ background: #323238; border-color: #48484f; }}"
    f"QPushButton:pressed {{ background: #26262a; }}"
)

CARD = (
    "QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: {radius}px; }}"
)

SECTION_TITLE = (
    f"color: {TEXT_MUTED}; font-family: {FONT_FAMILY}; font-size: 11px; font-weight: 700;"
    "letter-spacing: 1.2px; margin-top: 8px; padding-bottom: 2px;"
)

PAGE_TITLE = (
    f"color: {TEXT}; font-family: {FONT_FAMILY}; font-size: 18px; font-weight: 600;"
)

FIELD_LABEL = (
    f"color: {TEXT_DIM}; font-family: {FONT_FAMILY}; font-size: 13px;"
    "font-weight: 500; background: transparent; padding-bottom: 2px;"
)

SPINBOX = (
    f"QSpinBox {{ background: {BG_ELEVATED}; color: {TEXT}; font-family: {FONT_FAMILY};"
    f"border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; padding: 10px 12px;"
    f"font-size: 15px; min-height: 20px; }}"
    f"QSpinBox:focus {{ border-color: {ACCENT}; }}"
)

LINE_EDIT = (
    f"QLineEdit {{ background: {BG_ELEVATED}; color: {TEXT}; font-family: {FONT_FAMILY};"
    f"border: 1px solid {BORDER}; border-radius: {RADIUS_SM}px; padding: 10px 12px;"
    f"font-size: 15px; }}"
    f"QLineEdit:focus {{ border-color: {ACCENT}; }}"
)

LINK_BTN = (
    f"QPushButton {{ background: transparent; color: {LINK}; font-family: {FONT_FAMILY};"
    f"font-size: 13px; font-weight: 500; border: none; text-align: left; padding: 6px 0; }}"
    f"QPushButton:hover {{ color: #9eccef; }}"
)

CHECKBOX = (
    f"QCheckBox {{ color: {TEXT}; font-family: {FONT_FAMILY}; font-size: 15px;"
    f"spacing: 10px; background: transparent; }}"
    f"QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 5px;"
    f"border: 1px solid {BORDER}; background: {BG_ELEVATED}; }}"
    f"QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT_DIM}; }}"
)

LAYOUT_PILL = (
    f"QFrame {{ background: {BG_ELEVATED}; border: 1px solid {BORDER};"
    f"border-radius: {RADIUS_MD}px; }}"
    f"QFrame:hover {{ background: #303036; border-color: #48484f; }}"
)

SCROLL_AREA = (
    "QScrollArea { background: transparent; border: none; }"
    f"QScrollBar:vertical {{ width: 14px; background: transparent; margin: 4px 2px; }}"
    f"QScrollBar::handle:vertical {{ background: #48484f; border-radius: 6px; min-height: 32px; }}"
    f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
)

SCROLL_HORIZONTAL = (
    "QScrollArea { background: transparent; border: none; }"
    "QScrollBar:horizontal { height: 14px; background: transparent; margin: 6px 0 0 0; }"
    "QScrollBar::handle:horizontal { background: #48484f; border-radius: 6px; min-width: 40px; }"
    "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }"
)


def primary_btn(size: int = 28, radius: int = 14, pad: str = "0 32px") -> str:
    return BTN_PRIMARY.format(
        accent=ACCENT,
        pressed=ACCENT_DIM,
        size=size,
        radius=radius,
        pad=pad,
        font=FONT_FAMILY,
    )


def secondary_btn(size: int = 18, radius: int = 12, pad: str = "0 24px") -> str:
    return BTN_SECONDARY.format(
        text=TEXT,
        bg=BG_ELEVATED,
        hover="#323238",
        border=BORDER,
        size=size,
        radius=radius,
        pad=pad,
        font=FONT_FAMILY,
    )


def card_style(radius: int = RADIUS_MD) -> str:
    return CARD.format(bg=BG_CARD, border=BORDER_SUBTLE, radius=radius)


def nav_bar() -> str:
    return f"background: {BG_NAV}; border-bottom: 1px solid {BORDER_SUBTLE};"


def dock_bar() -> str:
    return f"background: {BG_NAV}; border-top: 1px solid {BORDER_SUBTLE};"


def scroll_horizontal() -> str:
    return SCROLL_HORIZONTAL


def layout_picker_card(selected: bool) -> str:
    border = ACCENT if selected else BORDER_SUBTLE
    bg = ACCENT_SOFT if selected else BG_CARD
    return (
        f"QFrame#layoutModeCard {{ background: {bg}; border: 3px solid {border};"
        f"border-radius: {RADIUS_MD}px; }}"
        f"QFrame#layoutModeCard QLabel {{ background: transparent; }}"
    )


def app_stylesheet() -> str:
    return f"""
        QWidget {{
            font-family: {FONT_FAMILY};
            color: {TEXT};
        }}
        QLabel {{
            background: transparent;
        }}
        QToolTip {{
            background: {BG_ELEVATED};
            color: {TEXT};
            border: 1px solid {BORDER};
            padding: 6px 10px;
            border-radius: 6px;
        }}
    """
