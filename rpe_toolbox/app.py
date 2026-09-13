# -*- coding: utf-8 -*-
"""RPEToolbox 主类：界面构建、输入输出与功能分发。

界面文字一律通过 i18n.t(...) 从 assets/lang/<语言>.json 读取，代码中不写死文案；
外观由 sv-ttk（sun-valley）主题统一，缺失该依赖时自动降级为 ttk 默认样式。
"""

import json
import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from . import config, dpi, i18n, resources, theme
from .core import FunctionMixin
from .i18n import t
from .imglib import Image
from .widgets import RoundedTextArea

try:  # sv-ttk 为可选的界面样式依赖，缺失时不影响功能
    import sv_ttk
except ImportError:  # pragma: no cover
    sv_ttk = None

try:  # pywinstyles 让标题栏跟随 Win11 暗/亮色，缺失时不影响功能
    import pywinstyles
except ImportError:  # pragma: no cover
    pywinstyles = None


class RPEToolbox(FunctionMixin):
    # 这两个功能不需要输入 JSON（图片转音符画 / MIDI BPM 提取）
    NO_INPUT_FUNCTIONS = ("image_to_notes", "midi_bpm_extract")

    def __init__(self, root):
        self.root = root
        self.style = ttk.Style(root)
        self.theme_name = config.resolve_theme()
        self._syncing_theme = False
        # 高分屏：启用 DPI 感知后 Tk 的尺寸单位就是物理像素，而字号按点渲染。
        # 若窗口与内边距仍按 96dpi 的数值给，150% 缩放下字会显得过大、界面拥挤，
        # 故统一用 px() 把设计稿数值按当前 DPI 换算。
        self.ui_scale = dpi.dpi_scale() if os.name == "nt" else 1.0
        self.root.title(t("app.title"))
        # 窗口尺寸按缩放放大，同时不超过屏幕可用范围（超出时由两个文本框自适应收缩）
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w = min(self.px(680), max(320, screen_w - self.px(20)))
        win_h = min(self.px(800), max(240, screen_h - self.px(60)))
        self.root.geometry("%dx%d" % (win_w, win_h))
        # 兜底：即使调用方未在 import tkinter 之前启用 DPI 感知，也校准一次缩放因子
        dpi.sync_tk_scaling(self.root)
        # 先隐藏窗口：任务栏按钮在窗口首次显示时快照类图标（Tk 默认是羽毛），
        # 必须在显示前设置好类图标，否则之后修改不会刷新任务栏
        try:
            self.root.withdraw()
            self.root.update()
        except Exception:
            pass
        # 窗口图标：不使用 iconphoto（Tk 会持续把类图标设回 16x16/羽毛），
        # 用 Windows API 设置类图标 32x32（与 exe 图标同源），并由定时器兜底
        try:
            self._apply_taskbar_icon()
            # 窗口显示后再应用一次，避免 Tk 显示阶段覆盖图标
            self.root.after(300, self._apply_taskbar_icon)
            self.root.bind("<Map>", lambda e: self._apply_taskbar_icon())
            self.root.after(3000, self._keep_taskbar_icon)
        except Exception:
            pass
        # 图标已设置，显示窗口（任务栏按钮创建时类图标即为 ico-z1 32x32）
        try:
            self.root.deiconify()
        except Exception:
            pass
        self.ui_font_family = self._get_available_font_family()
        self.root.option_add("*Font", self.font_spec(10))
        self.root.option_add("*Label.Font", self.font_spec(10))
        self.root.option_add("*Button.Font", self.font_spec(10))
        self.root.option_add("*Combobox.Font", self.font_spec(10))

        # 状态变量
        self.functions = {item["name"]: (item["key"], item["desc"]) for item in i18n.function_list()}
        self.function_names = list(self.functions.keys())
        default_function = self.function_names[0] if self.function_names else ""
        self.current_function = tk.StringVar(value=default_function)
        self.dark_mode_var = tk.BooleanVar(value=(self.theme_name == "dark"))
        self.density_var = tk.StringVar(value="16")
        self.allow_shorten_var = tk.BooleanVar(value=True)
        self.distinguish_track_var = tk.BooleanVar(value=False)
        self.stretch_ratio_var = tk.StringVar(value="-1")
        self.time_offset_speed_var = tk.StringVar(value="10")
        self.time_offset_bpm_var = tk.StringVar(value="120")
        self.time_offset_unify_var = tk.BooleanVar(value=True)
        self.lock_aspect_var = tk.BooleanVar(value=True)
        self.rotation_var = tk.StringVar(value=i18n.option_display("rotation", "0"))
        self.midi_path_var = tk.StringVar()
        self.event_type_options = [
            (display, int(key)) for key, display in i18n.option_items("event_type")
        ]
        self.event_source_vars = []
        self.event_target_vars = []
        self.tab_frames = {}
        self.tab_order = []
        self.tab_io = {}
        self._syncing_tab = False
        self.image_ratio = None
        self._syncing_size_vars = False
        self._audio_threads = []
        self._icon_retry = 0

        # 构建界面
        self.create_widgets()

        # 应用主题（sv-ttk + 自绘控件配色），随后才挂上切换回调
        self._apply_theme(self.theme_name)
        self.dark_mode_var.trace_add("write", lambda *_: self._on_dark_mode_toggle())

        # 绑定事件
        self.current_function.trace_add("write", self.on_function_change)
        self.on_function_change()  # 初始化显示状态

    # ------------------------------------------------------------------
    # 尺寸与主题
    # ------------------------------------------------------------------
    def px(self, value):
        """设计稿像素 → 当前 DPI 下的实际像素（非 Windows 或 DPI 感知未启用时为原值）。"""
        return int(round(value * self.ui_scale))

    def font_spec(self, size):
        """Tk 字体规格字符串。

        家族名带空格时必须用 "{家族} 字号" 形式：Tk 会把字体规格当成 Tcl 列表解析，
        不加花括号就会把 "Sarasa Fixed SC 10" 拆成 family=Sarasa / size=Fixed 而报
        "expected integer but got \"Fixed\""。
        """
        return "{%s} %d" % (self.ui_font_family, size)

    def _apply_theme(self, name=None, persist=False):
        """应用主题：sv-ttk 统一 ttk 控件外观，配色表统一自绘控件（文本框、提示文字）。"""
        self.theme_name = theme.normalize(name or self.theme_name)
        palette = theme.palette(self.theme_name)

        if sv_ttk is not None:
            try:
                sv_ttk.set_theme(self.theme_name)
            except Exception:
                pass

        self.text_bg = palette["text_bg"]
        self.text_fg = palette["text_fg"]
        self.error_fg = palette["error"]

        try:
            self.root.configure(bg=palette["bg"])
        except Exception:
            pass

        # ttk 的提示性文字（灰色说明，即功能简介）
        try:
            self.style.configure("Muted.TLabel", foreground=palette["muted"])
        except Exception:
            pass

        self._apply_ui_font()

        # 标题栏跟随暗/亮色（Win11 风格）。注意：pywinstyles 内部会调用 update()，
        # 从而把 sv-ttk 的 tk_setPalette 推迟的重着色执行掉，所以配色必须放在它之后。
        self._apply_titlebar_style()
        self._apply_widget_colors(palette)

        # 同步"深色模式"勾选框，避免回写触发递归
        if hasattr(self, "dark_mode_var"):
            self._syncing_theme = True
            try:
                self.dark_mode_var.set(self.theme_name == "dark")
            finally:
                self._syncing_theme = False

        if persist:
            config.save_theme(self.theme_name)

        # 双保险：万一还有推迟到空闲时执行的重新着色，让自定义配色成为最后生效的一次
        try:
            self.root.after_idle(lambda: self._apply_widget_colors(theme.palette(self.theme_name)))
        except Exception:
            pass

    def _apply_widget_colors(self, palette=None):
        """自绘控件（经典 tk 按钮 / 圆角文本框）配色；所有标签页都要套一遍。"""
        if palette is None:
            palette = theme.palette(self.theme_name)
        outer_bg = self._outer_bg(palette)

        for key, button in self.all_buttons():
            bg, fg, active_bg = theme.BUTTON_COLORS[key]
            try:
                button.configure(bg=bg, fg=fg, activebackground=active_bg, activeforeground=fg,
                                 highlightbackground=bg, highlightcolor=bg)
            except Exception:
                pass

        for area in self.all_text_areas():
            self._style_text_area(area, palette, outer_bg)

    def _outer_bg(self, palette):
        """文本框所在容器的底色（圆角外露的部分要与它一致）。"""
        try:
            color = self.style.lookup("TFrame", "background")
            if color:
                return color
        except Exception:
            pass
        return palette["bg"]

    def _style_text_area(self, area, palette, outer_bg):
        try:
            area.configure_colors(
                bg=palette["text_bg"],
                fg=palette["text_fg"],
                border=palette["text_border"],
                accent=palette["accent"],
                outer_bg=outer_bg,
                caret=palette["caret"],
                select_bg=palette["select_bg"],
                select_fg=palette["select_fg"],
            )
        except Exception:
            pass

    def _apply_ui_font(self):
        """把界面字体套用到 ttk 控件上。

        option_add("*Font") 只对经典 tk 控件生效，ttk 控件必须显式配置样式字体，
        否则按钮/勾选框/下拉框会退回 Tk 默认字体（与最初规定的字体不一致）。
        """
        ui_font = self.font_spec(10)
        for style_name in (".", "TLabel", "TButton", "TCheckbutton", "TCombobox", "TEntry",
                           "Muted.TLabel", "Switch.TCheckbutton", "Accent.TButton"):
            try:
                self.style.configure(style_name, font=ui_font)
            except Exception:
                pass
        # 功能选择栏（标签）字号略小，8 个标签才能排在一行内
        tab_font = self.font_spec(9)
        for style_name in ("TNotebook", "TNotebook.Tab"):
            try:
                self.style.configure(style_name, font=tab_font)
            except Exception:
                pass
        # 下拉列表弹出部分的字体（不是 ttk 样式，走 option 数据库）
        try:
            self.root.option_add("*TCombobox*Listbox.font", ui_font)
        except Exception:
            pass

    def _apply_titlebar_style(self):
        """标题栏跟随主题：深色主题用 Win11 暗色标题栏，浅色主题用亮色。"""
        if pywinstyles is None or os.name != "nt":
            return
        try:
            pywinstyles.apply_style(self.root, "dark" if self.theme_name == "dark" else "light")
        except Exception:
            pass

    def _on_dark_mode_toggle(self):
        if self._syncing_theme:
            return
        self._apply_theme("dark" if self.dark_mode_var.get() else "light", persist=True)

    def _apply_taskbar_icon(self):
        """Windows：用 WM_SETICON 设置任务栏/标题栏图标。

        三管齐下：
        1. 打包环境（frozen）设置 AppUserModelID，任务栏直接使用 exe 资源图标（与 exe 一致）
        2. WM_SETICON 设置窗口小图标(16x16)/大图标(32x32)
        3. SetClassLong 设置类图标，覆盖任务栏/Alt-Tab 读取类图标的路径
        图标均取自 ico-z1.png（与 exe 文件图标同源）。
        """
        if os.name != "nt":
            return
        try:
            import ctypes
            import tempfile

            from PIL import Image

            full_icon = resources.find_full_icon()
            mini_icon = resources.find_icon()
            if not full_icon:
                return

            user32 = ctypes.windll.user32
            # 释放上次加载的图标句柄，避免多次调用泄漏 GDI 句柄
            for h in getattr(self, "_icon_handles", []):
                try:
                    user32.DestroyIcon(h)
                except Exception:
                    pass
            self._icon_handles = []

            # 打包环境：绑定 AppUserModelID，任务栏显示 exe 图标（即 ico-z1.png）
            if getattr(sys, "frozen", False):
                try:
                    shell32 = ctypes.windll.shell32
                    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
                    shell32.SetCurrentProcessExplicitAppUserModelID("rpetoolbox")
                except Exception:
                    pass

            tmp_small_ico = None
            tmp_big_ico = None
            try:
                # 标题栏小图标：使用 mini ico-z1.png（16x16 专用小图，非完整版缩放）
                small_src = mini_icon if mini_icon and os.path.exists(mini_icon) else full_icon
                with tempfile.NamedTemporaryFile(suffix=".ico", delete=False) as f:
                    tmp_small_ico = f.name
                Image.open(small_src).convert("RGBA").save(tmp_small_ico, format="ICO", sizes=[(16, 16)])
                # 任务栏大图标：使用完整版 ico-z1.png
                with tempfile.NamedTemporaryFile(suffix=".ico", delete=False) as f:
                    tmp_big_ico = f.name
                Image.open(full_icon).convert("RGBA").save(tmp_big_ico, format="ICO", sizes=[(32, 32), (48, 48)])

                user32 = ctypes.windll.user32
                # 关键：winfo_id()/枚举均不可靠（Tk 有 TkChild/TkTopLevel 多个窗口），
                # 用 Tk 官方命令 `wm frame` 直接取 TkTopLevel（任务栏看到的显示窗口）句柄。
                hwnd = None
                try:
                    frame = self.root.tk.call("wm", "frame", ".")
                    if frame:
                        hwnd = int(frame, 16)
                except Exception:
                    pass
                if not hwnd:
                    hwnd = self._find_main_window()
                if not hwnd:
                    wid = self.root.winfo_id()
                    hwnd = user32.GetParent(wid) or wid
                if not hwnd:
                    # 窗口可能尚未创建（onefile 解压较慢），稍后重试
                    if getattr(self, "_icon_retry", 0) < 10:
                        self._icon_retry = getattr(self, "_icon_retry", 0) + 1
                        self.root.after(500, self._apply_taskbar_icon)
                    return
                WM_SETICON = 0x0080
                IMAGE_ICON = 1
                LR_LOADFROMFILE = 0x0010
                small = user32.LoadImageW(None, tmp_small_ico, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
                big = user32.LoadImageW(None, tmp_big_ico, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)
                self._icon_handles = [h for h in (small, big) if h]
                if small:
                    user32.SendMessageW(hwnd, WM_SETICON, 0, small)
                if big:
                    user32.SendMessageW(hwnd, WM_SETICON, 1, big)
                # 类图标（关键）：任务栏/Alt-Tab 实际读取的是 TkTopLevel 窗口的类图标
                user32.GetClassLongW.restype = ctypes.c_long
                user32.SetClassLongW.restype = ctypes.c_long
                if big:
                    user32.SetClassLongW(hwnd, -14, big)
                if small:
                    user32.SetClassLongW(hwnd, -34, small)
                # 子类化窗口过程：WM_GETICON 动态返回我们的大/小图标。
                # 任务栏查询窗口图标（而非类图标）时必定拿到 32x32 ico-z1，
                # 不受 Explorer 对窗口类图标的缓存影响。
                self._icon_big = big
                self._icon_small = small
                self._ensure_icon_subclass(hwnd)
                # 发送 WM_SETICON 触发标题栏/任务栏刷新：
                # 标题栏小图标(16x16)，任务栏大图标(32x32)，避免窗口创建时
                # 标题栏快照到类大图标
                user32.SendMessageW(hwnd, 0x0080, 0, small)
                user32.SendMessageW(hwnd, 0x0080, 1, big)
                self._icon_retry = 0
            finally:
                for tmp_ico in (tmp_small_ico, tmp_big_ico):
                    if not tmp_ico:
                        continue
                    try:
                        os.remove(tmp_ico)
                    except Exception:
                        pass
        except Exception:
            pass

    def _find_main_window(self):
        """按窗口标题找到主显示窗口（任务栏/资源管理器看到的顶层窗口）。"""
        if os.name != "nt":
            return None
        try:
            import ctypes
            user32 = ctypes.windll.user32
            found = []
            title = self.root.title()

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def _enum_cb(hwnd, lparam):
                buf = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, buf, 512)
                if buf.value == title:
                    found.append(hwnd)
                return True

            user32.EnumWindows(_enum_cb, 0)
            return found[0] if found else None
        except Exception:
            return None

    def _ensure_icon_subclass(self, hwnd):
        """子类化 TkTopLevel 窗口过程，拦截 WM_GETICON 返回当前图标句柄。"""
        if os.name != "nt":
            return
        if getattr(self, "_icon_hwnd", None) == hwnd:
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            LPARAM = ctypes.c_longlong
            WNDPROC = ctypes.WINFUNCTYPE(LPARAM, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, LPARAM)
            app = self

            @WNDPROC
            def _icon_proc(h, msg, wparam, lparam):
                if msg == 0x007F:  # WM_GETICON
                    v = int(ctypes.cast(wparam, ctypes.c_void_p).value or 0)
                    if v == 1 and getattr(app, "_icon_big", None):
                        return app._icon_big
                    if getattr(app, "_icon_small", None):
                        return app._icon_small
                if msg == 0x0080:  # WM_SETICON：交给 DefWindowProc 存储并触发系统刷新
                    return user32.DefWindowProcW(h, msg, wparam, lparam)
                old_fn = getattr(app, "_icon_old_fn", None)
                if old_fn is not None:
                    return old_fn(h, msg, wparam, lparam)
                return user32.DefWindowProcW(h, msg, wparam, lparam)

            user32.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
            user32.SetWindowLongW.restype = ctypes.c_long
            new_addr = ctypes.cast(_icon_proc, ctypes.c_void_p).value
            old_addr = user32.SetWindowLongW(hwnd, -4, new_addr)  # GWL_WNDPROC
            self._icon_old_fn = ctypes.cast(ctypes.c_void_p(old_addr), WNDPROC)
            if not hasattr(self, "_icon_wndproc_refs"):
                self._icon_wndproc_refs = []
            self._icon_wndproc_refs.append(_icon_proc)  # 保持引用，防止回调被 GC
            self._icon_hwnd = hwnd
        except Exception:
            pass

    def _keep_taskbar_icon(self):
        """定时检查任务栏大图标：若被 Tk 重置（如变回 16x16/羽毛），重新应用。"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.GetClassLongW.restype = ctypes.c_long
            hwnd = None
            try:
                frame = self.root.tk.call("wm", "frame", ".")
                if frame:
                    hwnd = int(frame, 16)
            except Exception:
                pass
            if hwnd and self._icon_handles:
                cur = user32.GetClassLongW(hwnd, -14)
                if cur not in self._icon_handles:
                    self._apply_taskbar_icon()
        except Exception:
            pass
        try:
            self.root.after(3000, self._keep_taskbar_icon)
        except Exception:
            pass

    def shutdown(self):
        """退出清理：销毁 Tk 窗口并等待音频线程结束，降低打包后临时目录清理失败的概率。"""
        try:
            self.root.destroy()
        except Exception:
            pass
        for t_ in getattr(self, "_audio_threads", []):
            try:
                t_.join(timeout=2)
            except Exception:
                pass
        # 释放 PhotoImage 等持有文件句柄的对象
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        # 留出时间给杀软扫描/句柄释放，降低 onefile 临时目录删除失败概率
        try:
            import time
            time.sleep(0.5)
        except Exception:
            pass

    def _play_button_sound(self, kind):
        file_name = {
            "convert": "click1.ogg",
            "convert_error": "click4.ogg",
            "copy": "click2.ogg",
            "clear": "click3.ogg",
        }.get(kind)
        if not file_name:
            return

        audio_path = resources.audio_path(file_name)
        if not os.path.exists(audio_path):
            return

        def worker():
            try:
                import pygame
                import time as _time
                pygame.mixer.init()
                try:
                    sound = pygame.mixer.Sound(audio_path)
                    sound.play()
                    # 等待播放结束再释放 mixer，避免退出时持有 _MEIPASS 内音频文件句柄
                    try:
                        _time.sleep(max(0.0, sound.get_length() + 0.15))
                    except Exception:
                        pass
                finally:
                    pygame.mixer.quit()
            except Exception:
                return

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            self._audio_threads.append(thread)
        except AttributeError:
            self._audio_threads = [thread]

    def _get_available_font_family(self):
        """界面字体：按最初规定的优先级取等宽中文字体。

        更纱黑体有多个变体（Gothic/UI/Mono/Term/Fixed），这里优先取等宽的那些
        （Mono > Fixed > Term，简体优先 SC，其次 HC/CL/TC 等区域变体），
        再退回微软雅黑等宽 / Consolas / 系统等宽 / 雅黑。
        """
        available = set(tkfont.families())
        preferred = []
        for region in ("SC", "HC", "CL", "TC", "J", "K"):
            for variant in ("Mono", "Fixed", "Term", "Gothic", "UI"):
                preferred.append("Sarasa %s %s" % (variant, region))
        preferred += ["Microsoft YaHei Mono", "Consolas", "monospace",
                      "微软雅黑", "Microsoft YaHei", "Arial"]
        for family in preferred:
            if family in available:
                return family
        return "Arial"

    def _get_code_font(self):
        return self.font_spec(9)

    def create_widgets(self):
        # 1. 顶部：功能简介（灰字，开关左侧）
        frame_top = ttk.Frame(self.root, padding=(self.px(0), self.px(5)))
        frame_top.pack(fill=tk.X, padx=self.px(10))

        self.dark_mode_check = ttk.Checkbutton(
            frame_top, text=t("labels.dark_mode"), variable=self.dark_mode_var, style="Switch.TCheckbutton")
        self.dark_mode_check.pack(side=tk.RIGHT, padx=self.px(5))

        self.desc_label = ttk.Label(frame_top, text="", style="Muted.TLabel", font=self.font_spec(8),
                                    wraplength=self.px(540), justify=tk.RIGHT)
        self.desc_label.pack(side=tk.RIGHT, padx=self.px(5))

        # 2. 功能切换：Notebook；每个标签页里依次是「该功能的选项 → 输入JSON → 三个按钮 → 输出JSON」
        #    （需求五的顺序，其中输入/按钮/输出与选项同处一页）
        self.notebook_host = ttk.Frame(self.root)
        self.notebook_host.pack(fill=tk.BOTH, expand=True, padx=self.px(10), pady=(0, self.px(8)))
        self.notebook = ttk.Notebook(self.notebook_host)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        for item in i18n.function_list():
            tab = ttk.Frame(self.notebook, padding=self.px(6))
            self.notebook.add(tab, text=item.get("tab") or item["name"])
            self.tab_frames[item["key"]] = tab
            self.tab_order.append(item["key"])
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._build_function_tabs()

    def _build_function_tabs(self):
        """每个功能一页：页内先放该功能的选项，再放输入JSON / 按钮 / 输出JSON。"""
        self._build_option_widgets()

        for key in self.tab_order:
            self.tab_io[key] = self._build_io_panel(
                self.tab_frames[key],
                with_input=key not in self.NO_INPUT_FUNCTIONS,
            )

    def _build_io_panel(self, parent, with_input=True):
        """在标签页内建一套 输入JSON / 转换·复制结果·清空输入输出 / 输出JSON。

        Tk 的控件不能同时属于多个容器，所以每个标签页各持有一套；这样切换功能时
        各自的输入输出也会分别保留。图片转音符画 / MIDI BPM 提取 不需要输入框。
        """
        panel = {"buttons": {}}

        # 输入区始终建好，只是图片转音符画 / MIDI BPM 提取 两页不显示（保持结构一致）
        frame_input = ttk.Frame(parent)
        if with_input:
            frame_input.pack(fill=tk.BOTH, expand=True, pady=(0, self.px(4)))
        ttk.Label(frame_input, text=t("labels.input_json"), anchor="w").pack(fill=tk.X, pady=(0, self.px(2)))
        text_input = RoundedTextArea(frame_input, font=self._get_code_font(), radius=self.px(8))
        text_input.pack(fill=tk.BOTH, expand=True)
        panel["input_frame"] = frame_input
        panel["text_input"] = text_input

        frame_btn = ttk.Frame(parent)
        frame_btn.pack(fill=tk.X, pady=(0, self.px(4)))
        button_texts = {"convert": "buttons.convert", "copy": "buttons.copy", "clear": "buttons.clear"}
        for key in ("convert", "copy", "clear"):
            bg, fg, active_bg = theme.BUTTON_COLORS[key]
            button = tk.Button(frame_btn, text=t(button_texts[key]), font=self.font_spec(10),
                               bg=bg, fg=fg, activebackground=active_bg, activeforeground=fg,
                               command=lambda k=key: self._trigger_with_sound(k))
            button.pack(side=tk.LEFT, padx=self.px(5))
            panel["buttons"]["btn_" + key] = button
        panel["frame_btn"] = frame_btn

        frame_output = ttk.Frame(parent)
        frame_output.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame_output, text=t("labels.output_json"), anchor="w").pack(fill=tk.X, pady=(0, self.px(2)))
        text_output = RoundedTextArea(frame_output, font=self._get_code_font(), radius=self.px(8))
        text_output.pack(fill=tk.BOTH, expand=True)
        panel["output_frame"] = frame_output
        panel["text_output"] = text_output

        return panel

    # ------------------------------------------------------------------
    # 当前标签页的输入/输出控件（对外仍按 text_input / text_output 使用）
    # ------------------------------------------------------------------
    def _current_key(self):
        try:
            return self.tab_order[self.notebook.index(self.notebook.select())]
        except Exception:
            return self.tab_order[0] if self.tab_order else None

    def _current_io(self):
        return self.tab_io.get(self._current_key(), {})

    @property
    def text_input(self):
        return self._current_io().get("text_input")

    @property
    def text_output(self):
        return self._current_io().get("text_output")

    @property
    def input_frame(self):
        return self._current_io().get("input_frame")

    @property
    def frame_btn(self):
        return self._current_io().get("frame_btn")

    @property
    def btn_convert(self):
        return self._current_io().get("buttons", {}).get("btn_convert")

    @property
    def btn_copy(self):
        return self._current_io().get("buttons", {}).get("btn_copy")

    @property
    def btn_clear(self):
        return self._current_io().get("buttons", {}).get("btn_clear")

    def all_text_areas(self):
        """所有标签页的文本区（主题换色时要全部套一遍）。"""
        for panel in self.tab_io.values():
            for attr in ("text_input", "text_output"):
                widget = panel.get(attr)
                if widget is not None:
                    yield widget

    def all_buttons(self):
        """所有标签页的三个按钮（(内部键, 按钮)）。"""
        for panel in self.tab_io.values():
            for attr, button in panel.get("buttons", {}).items():
                yield attr.replace("btn_", ""), button

    def _build_option_widgets(self):
        """各功能的选项控件（放进对应标签页）。"""
        # 功能 2 / 3：切割密度（两页各一份控件，共用同一个变量）
        self.density_rows = []
        for key in ("nonlinear_split", "polar_conversion"):
            self.density_rows.append(self._build_density_row(self.tab_frames[key]))

        # 功能 1：hold/事件首尾相接
        self.frame_hold_options = ttk.Frame(self.tab_frames["hold_notes_connect"])
        self.frame_hold_options.pack(fill=tk.X, pady=self.px(2))
        self.allow_shorten_check = ttk.Checkbutton(self.frame_hold_options, text=t("labels.allow_shorten"), variable=self.allow_shorten_var)
        self.allow_shorten_check.pack(side=tk.LEFT, padx=self.px(5))
        self.distinguish_track_check = ttk.Checkbutton(self.frame_hold_options, text=t("labels.distinguish_track"), variable=self.distinguish_track_var)
        self.distinguish_track_check.pack(side=tk.LEFT, padx=self.px(5))

        # 功能 4：事件类型转换（两列“输入选择框 → 文字”）
        self.frame_event_convert = ttk.Frame(self.tab_frames["event_type_convert"])
        self.frame_event_convert.pack(fill=tk.X, pady=self.px(2))
        self._create_event_convert_rows()

        # 功能 5：图片转音符画（5 行布局）
        self.frame_image_settings = ttk.Frame(self.tab_frames["image_to_notes"])
        self.frame_image_settings.pack(fill=tk.X, pady=self.px(2))

        row_path = ttk.Frame(self.frame_image_settings)
        row_path.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(row_path, text=t("labels.image_path")).pack(side=tk.LEFT, padx=self.px(5))
        self.image_path_var = tk.StringVar()
        self.entry_image_path = ttk.Entry(row_path, textvariable=self.image_path_var, width=55)
        self.entry_image_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=self.px(5))
        self.btn_select_image = ttk.Button(row_path, text=t("buttons.browse_image"), command=self.select_image_file)
        self.btn_select_image.pack(side=tk.LEFT, padx=self.px(5))

        # 第二行：音符类型 颜色处理 旧版染色标签
        row_type_color = ttk.Frame(self.frame_image_settings)
        row_type_color.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(row_type_color, text=t("labels.note_type")).pack(side=tk.LEFT, padx=self.px(5))
        self.note_type_var = tk.StringVar(value=i18n.option_display("note_type", "drag"))
        self.note_type_combo = ttk.Combobox(row_type_color, textvariable=self.note_type_var, values=i18n.option_values("note_type"), state="readonly", width=10)
        self.note_type_combo.pack(side=tk.LEFT, padx=self.px(5))

        ttk.Label(row_type_color, text=t("labels.color_mode")).pack(side=tk.LEFT, padx=self.px(5))
        self.color_mode_var = tk.StringVar(value=i18n.option_display("color_mode", "tint"))
        self.color_mode_combo = ttk.Combobox(row_type_color, textvariable=self.color_mode_var, values=i18n.option_values("color_mode"), state="readonly", width=14)
        self.color_mode_combo.pack(side=tk.LEFT, padx=self.px(5))

        self.legacy_tint_var = tk.BooleanVar(value=False)
        self.legacy_tint_check = ttk.Checkbutton(row_type_color, text=t("labels.legacy_tint"), variable=self.legacy_tint_var)
        self.legacy_tint_check.pack(side=tk.LEFT, padx=self.px(5))
        # 需求十二：颜色处理为“不透明度替代亮度”时隐藏旧版染色标签
        self.color_mode_var.trace_add("write", lambda *_: self._toggle_legacy_tint())
        self._toggle_legacy_tint()

        # 第三行：音符间隔（分音） 左右翻转 上下翻转 旋转度数
        row_opt3 = ttk.Frame(self.frame_image_settings)
        row_opt3.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(row_opt3, text=t("labels.note_interval")).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Entry(row_opt3, textvariable=self.density_var, width=10).pack(side=tk.LEFT, padx=self.px(5))
        self.flip_horizontal_var = tk.BooleanVar(value=False)
        self.flip_vertical_var = tk.BooleanVar(value=False)
        self.flip_horizontal_check = ttk.Checkbutton(row_opt3, text=t("labels.flip_horizontal"), variable=self.flip_horizontal_var)
        self.flip_horizontal_check.pack(side=tk.LEFT, padx=self.px(5))
        self.flip_vertical_check = ttk.Checkbutton(row_opt3, text=t("labels.flip_vertical"), variable=self.flip_vertical_var)
        self.flip_vertical_check.pack(side=tk.LEFT, padx=self.px(5))
        ttk.Label(row_opt3, text=t("labels.rotation")).pack(side=tk.LEFT, padx=self.px(5))
        self.rotation_combo = ttk.Combobox(row_opt3, textvariable=self.rotation_var, values=i18n.option_values("rotation"), state="readonly", width=8)
        self.rotation_combo.pack(side=tk.LEFT, padx=self.px(5))

        # 第四行：是否使用原图片大小 (x像素数 y像素数 锁定宽高比)
        row_size = ttk.Frame(self.frame_image_settings)
        row_size.pack(fill=tk.X, pady=self.px(2))
        self.use_original_size_var = tk.BooleanVar(value=False)
        self.use_original_size_check = ttk.Checkbutton(row_size, text=t("labels.use_original_size"), variable=self.use_original_size_var)
        self.use_original_size_check.pack(side=tk.LEFT, padx=self.px(5))
        self.use_original_size_var.trace_add("write", lambda *_: self._toggle_image_size_fields())

        self.frame_image_size_options = ttk.Frame(row_size)
        self.frame_image_size_options.pack(side=tk.LEFT, padx=self.px(5))
        ttk.Label(self.frame_image_size_options, text=t("labels.pixel_width")).pack(side=tk.LEFT, padx=self.px(5))
        self.pixel_width_var = tk.StringVar(value="65")
        self.pixel_width_var.trace_add("write", lambda *_: self._sync_image_dimension("x"))
        ttk.Entry(self.frame_image_size_options, textvariable=self.pixel_width_var, width=8).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Label(self.frame_image_size_options, text=t("labels.pixel_height")).pack(side=tk.LEFT, padx=self.px(5))
        self.pixel_height_var = tk.StringVar(value="65")
        self.pixel_height_var.trace_add("write", lambda *_: self._sync_image_dimension("y"))
        ttk.Entry(self.frame_image_size_options, textvariable=self.pixel_height_var, width=8).pack(side=tk.LEFT, padx=self.px(5))
        self.lock_aspect_check = ttk.Checkbutton(self.frame_image_size_options, text=t("labels.lock_aspect"), variable=self.lock_aspect_var)
        self.lock_aspect_check.pack(side=tk.LEFT, padx=self.px(5))

        # 第五行：是否自动调整音符宽度 (音符宽度)
        row_width = ttk.Frame(self.frame_image_settings)
        row_width.pack(fill=tk.X, pady=self.px(2))
        self.auto_adjust_width_var = tk.BooleanVar(value=True)
        self.auto_adjust_width_check = ttk.Checkbutton(row_width, text=t("labels.auto_adjust_width"), variable=self.auto_adjust_width_var)
        self.auto_adjust_width_check.pack(side=tk.LEFT, padx=self.px(5))
        self.auto_adjust_width_var.trace_add("write", lambda *_: self._toggle_image_width_fields())

        self.frame_image_width_options = ttk.Frame(row_width)
        self.frame_image_width_options.pack(side=tk.LEFT, padx=self.px(5))
        ttk.Label(self.frame_image_width_options, text=t("labels.note_width")).pack(side=tk.LEFT, padx=self.px(5))
        self.note_width_var = tk.StringVar(value="175")
        ttk.Entry(self.frame_image_width_options, textvariable=self.note_width_var, width=8).pack(side=tk.LEFT, padx=self.px(5))

        # 功能 6：时间间隔转 y 偏移
        self.frame_time_offset_settings = ttk.Frame(self.tab_frames["time_interval_to_yoffset"])
        self.frame_time_offset_settings.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(self.frame_time_offset_settings, text=t("labels.speed")).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Entry(self.frame_time_offset_settings, textvariable=self.time_offset_speed_var, width=8).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Label(self.frame_time_offset_settings, text=t("labels.bpm")).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Entry(self.frame_time_offset_settings, textvariable=self.time_offset_bpm_var, width=8).pack(side=tk.LEFT, padx=self.px(5))
        self.time_offset_unify_check = ttk.Checkbutton(self.frame_time_offset_settings, text=t("labels.unify_start_time"), variable=self.time_offset_unify_var)
        self.time_offset_unify_check.pack(side=tk.LEFT, padx=self.px(5))

        # 功能 7：倒序/拉伸
        self.frame_stretch_settings = ttk.Frame(self.tab_frames["reverse_data"])
        self.frame_stretch_settings.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(self.frame_stretch_settings, text=t("labels.stretch_ratio")).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Entry(self.frame_stretch_settings, textvariable=self.stretch_ratio_var, width=8).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Label(self.frame_stretch_settings, text=t("labels.stretch_ratio_hint"), style="Muted.TLabel").pack(side=tk.LEFT, padx=self.px(5))

        # 功能 8：MIDI BPM 提取
        self.frame_midi_settings = ttk.Frame(self.tab_frames["midi_bpm_extract"])
        self.frame_midi_settings.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(self.frame_midi_settings, text=t("labels.midi_path")).pack(side=tk.LEFT, padx=self.px(5))
        self.entry_midi_path = ttk.Entry(self.frame_midi_settings, textvariable=self.midi_path_var, width=55)
        self.entry_midi_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=self.px(5))
        self.btn_select_midi = ttk.Button(self.frame_midi_settings, text=t("buttons.browse_midi"), command=self.select_midi_file)
        self.btn_select_midi.pack(side=tk.LEFT, padx=self.px(5))

    def _build_density_row(self, parent):
        """切割密度输入行（非线性切割与极坐标转换两页各一份，共用 density_var）。"""
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=self.px(2))
        ttk.Label(row, text=t("labels.density")).pack(side=tk.LEFT, padx=self.px(5))
        ttk.Entry(row, textvariable=self.density_var, width=10).pack(side=tk.LEFT, padx=self.px(5))
        return row

    def _create_event_convert_rows(self):
        # 需求十一：两列布局，每行“输入选择框 → 文字”，速度更名为流速
        self.frame_event_convert_left = ttk.Frame(self.frame_event_convert)
        self.frame_event_convert_left.pack(side=tk.LEFT, fill=tk.X, padx=(self.px(5), self.px(25)), pady=self.px(2))
        self.frame_event_convert_right = ttk.Frame(self.frame_event_convert)
        self.frame_event_convert_right.pack(side=tk.LEFT, fill=tk.X, padx=(self.px(0), self.px(5)), pady=self.px(2))

        self.event_source_vars = []
        self.event_target_vars = []

        type_names = [name for name, _ in self.event_type_options]
        # 左列：X轴位移 Y轴位移 旋转 透明度 流速；右列：X轴缩放 Y轴缩放 定轨hold 曲线drag 音符间隔
        standard_keys = ["1", "2", "3", "4", "5", "6", "7"]
        for idx, type_key in enumerate(standard_keys):
            name = i18n.option_display("event_type", type_key)
            parent = self.frame_event_convert_left if idx < 5 else self.frame_event_convert_right
            row = idx if idx < 5 else idx - 5
            source_var = tk.StringVar(value=name)
            target_var = tk.StringVar(value=name)
            self.event_source_vars.append(source_var)
            self.event_target_vars.append(target_var)
            ttk.Combobox(parent, textvariable=source_var, values=type_names, state="readonly", width=14).grid(
                row=row, column=0, sticky="w", padx=self.px(2), pady=self.px(2))
            ttk.Label(parent, text=t("labels.arrow"), width=3, anchor="center").grid(
                row=row, column=1, sticky="w", padx=self.px(1), pady=self.px(2))
            ttk.Label(parent, text=name, width=11, anchor="w").grid(
                row=row, column=2, sticky="w", padx=self.px(2), pady=self.px(2))

        # 定轨hold：无/5k/7k，默认无
        self.hold_mode_var = tk.StringVar(value=i18n.option_display("hold_mode", "none"))
        ttk.Combobox(self.frame_event_convert_right, textvariable=self.hold_mode_var,
                     values=i18n.option_values("hold_mode"), state="readonly", width=14).grid(
            row=2, column=0, sticky="w", padx=self.px(2), pady=self.px(2))
        ttk.Label(self.frame_event_convert_right, text=t("labels.arrow"), width=3, anchor="center").grid(
            row=2, column=1, sticky="w", padx=self.px(1), pady=self.px(2))
        ttk.Label(self.frame_event_convert_right, text=t("labels.hold_track"), width=11, anchor="w").grid(
            row=2, column=2, sticky="w", padx=self.px(2), pady=self.px(2))

        # 曲线drag：无/X轴位移与缩放/y轴位移与缩放，默认无
        self.drag_mode_var = tk.StringVar(value=i18n.option_display("drag_mode", "none"))
        ttk.Combobox(self.frame_event_convert_right, textvariable=self.drag_mode_var,
                     values=i18n.option_values("drag_mode"), state="readonly", width=14).grid(
            row=3, column=0, sticky="w", padx=self.px(2), pady=self.px(2))
        ttk.Label(self.frame_event_convert_right, text=t("labels.arrow"), width=3, anchor="center").grid(
            row=3, column=1, sticky="w", padx=self.px(1), pady=self.px(2))
        ttk.Label(self.frame_event_convert_right, text=t("labels.drag_curve"), width=11, anchor="w").grid(
            row=3, column=2, sticky="w", padx=self.px(2), pady=self.px(2))

        # 音符间隔（输入框，仅曲线drag不为“无”时出现）
        self.frame_drag_interval = ttk.Frame(self.frame_event_convert_right)
        self.frame_drag_interval.grid(row=4, column=0, columnspan=3, sticky="w", padx=self.px(2), pady=self.px(2))
        self.drag_interval_var = tk.StringVar(value="16")
        ttk.Entry(self.frame_drag_interval, textvariable=self.drag_interval_var, width=8).pack(side=tk.LEFT, padx=self.px(2))
        ttk.Label(self.frame_drag_interval, text=t("labels.arrow"), width=3, anchor="center").pack(side=tk.LEFT, padx=self.px(1))
        ttk.Label(self.frame_drag_interval, text=t("labels.drag_interval"), width=11, anchor="w").pack(side=tk.LEFT, padx=self.px(2))
        self.frame_drag_interval.grid_remove()
        self.drag_mode_var.trace_add("write", lambda *_: self._toggle_drag_interval())

    def _toggle_drag_interval(self):
        if i18n.option_key("drag_mode", self.drag_mode_var.get()) != "none":
            self.frame_drag_interval.grid()
        else:
            self.frame_drag_interval.grid_remove()

    def _toggle_legacy_tint(self):
        if i18n.option_key("color_mode", self.color_mode_var.get()) == "alpha_as_luma":
            self.legacy_tint_check.pack_forget()
        else:
            self.legacy_tint_check.pack(side=tk.LEFT, padx=self.px(5))

    def _trigger_with_sound(self, kind):
        if kind == "convert":
            success = self.process_data()
            self._play_button_sound("convert" if success else "convert_error")
        elif kind == "copy":
            self._play_button_sound("copy")
            self.copy_result()
        elif kind == "clear":
            self._play_button_sound("clear")
            self.clear_io()

    def _toggle_image_size_fields(self):
        if self.use_original_size_var.get():
            self.frame_image_size_options.pack_forget()
        else:
            self.frame_image_size_options.pack(side=tk.LEFT, padx=self.px(5))

    def _toggle_image_width_fields(self):
        if self.auto_adjust_width_var.get():
            self.frame_image_width_options.pack_forget()
        else:
            self.frame_image_width_options.pack(side=tk.LEFT, padx=self.px(5))

    def _set_image_size_inputs(self, width, height):
        self._syncing_size_vars = True
        try:
            self.pixel_width_var.set(str(int(width)))
            self.pixel_height_var.set(str(int(height)))
        finally:
            self._syncing_size_vars = False

    def _sync_image_dimension(self, changed):
        if not self.lock_aspect_var.get() or not self.image_ratio or self._syncing_size_vars:
            return
        try:
            if changed == "x":
                width = float(self.pixel_width_var.get())
                if width <= 0:
                    return
                height = width / self.image_ratio
                self._syncing_size_vars = True
                self.pixel_height_var.set(str(int(round(height))))
            else:
                height = float(self.pixel_height_var.get())
                if height <= 0:
                    return
                width = height * self.image_ratio
                self._syncing_size_vars = True
                self.pixel_width_var.set(str(int(round(width))))
        except ValueError:
            return
        finally:
            self._syncing_size_vars = False

    def select_image_file(self):
        path = filedialog.askopenfilename(
            title=t("dialogs.choose_image_title"),
            filetypes=[(t("dialogs.filter_image"), "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp"), (t("dialogs.filter_all"), "*.*")]
        )
        if not path:
            return
        self.image_path_var.set(path)
        try:
            with Image.open(path) as img:
                orig = img.convert("RGBA")
                self.image_ratio = orig.width / max(orig.height, 1)
                self._set_image_size_inputs(orig.width, orig.height)
        except Exception:
            self.image_ratio = None

    def select_midi_file(self):
        path = filedialog.askopenfilename(
            title=t("dialogs.choose_midi_title"),
            filetypes=[(t("dialogs.filter_midi"), "*.mid;*.midi"), (t("dialogs.filter_all"), "*.*")]
        )
        if path:
            self.midi_path_var.set(path)

    def on_function_change(self, *args):
        label = self.current_function.get()
        func_data = self.functions.get(label, (None, ""))
        func_key = func_data[0]
        self.desc_label.config(text=func_data[1])

        if func_key:
            self._select_function_tab(func_key)

    def _select_function_tab(self, func_key):
        """把 Notebook 切到指定功能的标签页（已在该页时不动，避免事件回环）。"""
        if self._syncing_tab or func_key not in self.tab_frames:
            return
        try:
            index = self.tab_order.index(func_key)
            if self.notebook.index("current") == index:
                return
            self._syncing_tab = True
            self.notebook.select(index)
        except Exception:
            pass
        finally:
            self._syncing_tab = False

    def _on_tab_changed(self, event=None):
        """点击标签页 → 同步 current_function（进而触发 on_function_change）。"""
        if self._syncing_tab:
            return
        try:
            index = self.notebook.index(self.notebook.select())
            func_key = self.tab_order[index]
        except Exception:
            return
        item = i18n.function_by_key(func_key)
        if not item or self.current_function.get() == item["name"]:
            return
        self._syncing_tab = True
        try:
            self.current_function.set(item["name"])
        finally:
            self._syncing_tab = False

    def get_input_data(self):
        try:
            raw = self.text_input.get("1.0", tk.END).strip()
            if not raw:
                raise ValueError(t("errors.input_empty"))
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise Exception(t("errors.json_format", err=str(e)))

    def set_output_data(self, data):
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, json.dumps(data, indent=3, ensure_ascii=False))

    def show_error(self, msg):
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, t("app.error_prefix") + msg)
        self.text_output.config(fg=self.error_fg)
        # 恢复颜色以便下次正常输出
        self.root.after(3000, lambda: self.text_output.config(fg=self.text_fg))

    def process_data(self):
        try:
            label = self.current_function.get()
            func_data = self.functions.get(label, (None, None))
            func_key = func_data[0]
            data = {} if func_key in ["image_to_notes", "midi_bpm_extract"] else self.get_input_data()

            result = None
            if func_key == "hold_notes_connect":
                result = self.func_hold_connect(data)
            elif func_key == "nonlinear_split":
                density = int(self.density_var.get())
                result = self.func_nonlinear_split(data, density)
            elif func_key == "polar_conversion":
                density = int(self.density_var.get())
                result = self.func_polar_conversion(data, density)
            elif func_key == "event_type_convert":
                result = self.func_event_type_convert(data)
            elif func_key == "image_to_notes":
                result = self.func_image_to_notes(data)
            elif func_key == "time_interval_to_yoffset":
                result = self.func_time_interval_to_yoffset(data)
            elif func_key == "reverse_data":
                result = self.func_reverse_data(data)
            elif func_key == "midi_bpm_extract":
                result = self.func_extract_midi_bpm(data)
            else:
                raise Exception(t("errors.unknown_function"))

            self.set_output_data(result)
            return True

        except Exception as e:
            self.show_error(str(e))
            return False

    def clear_io(self):
        for widget in (self.text_input, self.text_output):
            if widget is not None:
                widget.delete("1.0", tk.END)

    def _get_event_type_number(self, label):
        for name, value in self.event_type_options:
            if name == label:
                return value
        return i18n.option_int_key("event_type", label, None)

    def copy_result(self):
        content = self.text_output.get("1.0", tk.END).strip()
        if content and not content.startswith(t("app.error_prefix")):
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
        else:
            messagebox.showwarning(t("dialogs.tip_title"), t("dialogs.no_result_to_copy"))
