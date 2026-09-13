# -*- coding: utf-8 -*-
"""自绘控件：圆角文本区（聚焦时底部显示 accent 蓝线）。

Tk 的 tk.Text 画不了圆角，也没有聚焦下划线，所以用 Canvas 画外观、把 Text 内嵌进去：
    Frame（外层底色 = 所在容器底色）
      └ Canvas：圆角矩形（填充=文本框底色，描边=边框色）+ 聚焦时的底部蓝线
          └ Text（无边框，内缩在圆角矩形里）

对外的 Text 接口通过 __getattr__ 转发，调用方可以当作 tk.Text 使用
（get / insert / delete / config / cget ... 都可用）。
"""

import tkinter as tk


class RoundedTextArea(tk.Frame):
    def __init__(self, parent, font=None, radius=8, inner_pad=(6, 4, 6, 8), **text_kw):
        super().__init__(parent, bd=0, highlightthickness=0)
        self._radius = radius
        self._pad_left, self._pad_top, self._pad_right, self._pad_bottom = inner_pad
        self._focused = False
        self._bg_color = "#ffffff"
        self._border_color = "#8a8a8a"
        self._accent_color = "#0067c0"
        self._outer_bg = None

        self.canvas = tk.Canvas(self, bd=0, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(self.canvas, bd=0, highlightthickness=0, relief=tk.FLAT, font=font, **text_kw)
        self._window = self.canvas.create_window(0, 0, anchor="nw", window=self.text)
        self.canvas.bind("<Configure>", self._on_configure)
        self.text.bind("<FocusIn>", self._on_focus_in, add="+")
        self.text.bind("<FocusOut>", self._on_focus_out, add="+")

    # ------------------------------------------------------------------
    # 颜色
    # ------------------------------------------------------------------
    def configure_colors(self, bg=None, fg=None, border=None, accent=None,
                         outer_bg=None, caret=None, select_bg=None, select_fg=None):
        """设置配色。bg/fg 为文本框底色与文字色，border 为描边，accent 为聚焦时的底部线颜色。"""
        if bg is not None:
            self._bg_color = bg
        if border is not None:
            self._border_color = border
        if accent is not None:
            self._accent_color = accent
        if outer_bg is not None:
            self._outer_bg = outer_bg

        options = {}
        if bg is not None:
            options["bg"] = bg
        if fg is not None:
            options["fg"] = fg
        if caret is not None:
            options["insertbackground"] = caret
        if select_bg is not None:
            options["selectbackground"] = select_bg
        if select_fg is not None:
            options["selectforeground"] = select_fg
        if options:
            self.text.configure(**options)
        self.canvas.configure(bg=self._outer_bg if self._outer_bg is not None else self._bg_color)
        self._redraw()

    @property
    def bg_color(self):
        return self._bg_color

    @property
    def border_color(self):
        return self._border_color

    @property
    def accent_color(self):
        return self._accent_color

    @property
    def focused(self):
        return self._focused

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _on_configure(self, event=None):
        self._redraw()

    def _on_focus_in(self, event=None):
        self._focused = True
        self._redraw()

    def _on_focus_out(self, event=None):
        self._focused = False
        self._redraw()

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        """用平滑多边形近似圆角矩形（Tk 没有原生圆角）。"""
        points = [
            x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
        ]
        return self.canvas.create_polygon(points, smooth=True, splinesteps=24, **kw)

    def _redraw(self):
        canvas = self.canvas
        canvas.delete("chrome")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            return

        self._round_rect(0, 0, width - 1, height - 1, self._radius,
                         fill=self._bg_color, outline=self._border_color, tags="chrome")
        if self._focused:
            # 聚焦时的底部蓝线：两端各内缩一个圆角半径，避免戳出圆角外
            inset = self._radius + 2
            canvas.create_line(inset, height - 2, width - inset, height - 2,
                               fill=self._accent_color, width=2, tags="chrome")
        canvas.tag_lower("chrome")

        canvas.coords(self._window, self._pad_left, self._pad_top)
        canvas.itemconfigure(
            self._window,
            width=max(1, width - self._pad_left - self._pad_right),
            height=max(1, height - self._pad_top - self._pad_bottom),
        )

    # ------------------------------------------------------------------
    # 转发到内嵌的 Text（当 tk.Text 用）
    # ------------------------------------------------------------------
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        text = self.__dict__.get("text")
        if text is None:
            raise AttributeError(name)
        return getattr(text, name)

    # configure/cget 在 Frame 上已存在，不会走 __getattr__，这里显式转发到内部 Text，
    # 否则 area.cget("bg") 会拿到外层 Frame 的底色、area.config(fg=...) 会报 unknown option。
    def config(self, **kw):
        text = self.__dict__.get("text")
        if text is not None:
            try:
                return text.configure(**kw)
            except tk.TclError:
                pass
        return super().configure(**kw)

    configure = config

    def cget(self, key):
        text = self.__dict__.get("text")
        if text is not None:
            try:
                return text.cget(key)
            except tk.TclError:
                pass
        return super().cget(key)
