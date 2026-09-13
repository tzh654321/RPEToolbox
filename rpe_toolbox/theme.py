# -*- coding: utf-8 -*-
"""界面主题（sv-ttk 外观）与配套的自绘控件配色。

sv-ttk 提供 sun-valley 浅色/深色两套主题，但它只影响 ttk 控件；
文本框（tk.Text）、灰色提示文字等仍需手动配色，配色表统一放在这里。
"""

DEFAULT_THEME = "light"
THEMES = ("light", "dark")
ALIASES = {
    "sun-valley-light": "light",
    "sunvalley-light": "light",
    "sun-valley-dark": "dark",
    "sunvalley-dark": "dark",
}

PALETTES = {
    "light": {
        "bg": "#fafafa",
        "fg": "#1c1c1c",
        "muted": "#6b6b6b",
        # 输入/输出框：纯白底 + 深灰描边，与 #fafafa 的窗口底色拉开对比
        "text_bg": "#ffffff",
        "text_fg": "#1c1c1c",
        "text_border": "#8a8a8a",
        "text_border_width": 1,
        # 聚焦时输入框底部的提示线（Win11 浅色强调色）
        "accent": "#0067c0",
        "select_bg": "#cce4ff",
        "select_fg": "#101010",
        "caret": "#1c1c1c",
        "error": "#b3261e",
    },
    "dark": {
        "bg": "#1c1c1c",
        "fg": "#e8e8e8",
        "muted": "#9a9a9a",
        # 输入/输出框：比窗口底色更深 + 亮灰描边，暗色下也能看清边界
        "text_bg": "#0e0e0e",
        "text_fg": "#e8e8e8",
        "text_border": "#5a5a5a",
        "text_border_width": 1,
        # 聚焦时输入框底部的提示线（Win11 深色强调色）
        "accent": "#60cdff",
        "select_bg": "#2f5d8a",
        "select_fg": "#ffffff",
        "caret": "#e8e8e8",
        "error": "#ff6b6b",
    },
}


def normalize(name):
    """把别名/大小写统一成 light / dark；无法识别时返回默认主题。"""
    if not name:
        return DEFAULT_THEME
    key = str(name).strip().lower()
    key = ALIASES.get(key, key)
    return key if key in THEMES else DEFAULT_THEME


# 三个操作按钮沿用最初规定的配色（背景, 前景, 按下时的背景）
# 注意：sv-ttk 载入主题时会调用 tk_setPalette，把经典 tk 控件的配色重置成主题色，
# 所以这些颜色必须在每次应用主题之后重新套用（见 app._apply_button_colors）。
BUTTON_COLORS = {
    "convert": ("#8EC990", "#0C4E1A", "#7CBB7E"),
    "copy": ("#E6E7AB", "#5A550E", "#D5D69A"),
    "clear": ("#e6766e", "#EEDFE5", "#D6665E"),
}


def palette(theme):
    """取配色字典（含 bg/fg/text_*/error 等键）。"""
    return PALETTES[normalize(theme)]


def other(theme):
    """取相反主题（用于切换）。"""
    return "dark" if normalize(theme) == "light" else "light"
