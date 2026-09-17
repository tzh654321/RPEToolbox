# -*- coding: utf-8 -*-
"""RPEToolbox 主类：界面构建、输入输出与功能分发。

界面文字一律通过 i18n.t(...) 从 assets/lang/<语言>.json 读取，代码中不写死文案；
外观由 sv-ttk（sun-valley）主题统一，缺失该依赖时自动降级为 ttk 默认样式。
"""

import json
import os
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import traceback
from tkinter import filedialog, messagebox, ttk

from . import audio, config, dpi, i18n, mods_loader, resources, theme
from . import __version__ as APP_VERSION
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
    # 转换时进度条的最短可见时长（毫秒）：转换常常几毫秒就结束，不给个下限就完全看不见
    PROGRESS_MIN_MS = 700

    def __init__(self, root):
        self.root = root
        self.style = ttk.Style(root)
        # 语言先定下来（界面文字全部取自语言文件）
        i18n.set_language(config.resolve_language(i18n.DEFAULT_LANGUAGE))
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
        # 功能组 / 禁用的模组 / 标签页映射在 _rebuild_tabs() 里按当前模组重建
        groups = mods_loader.discover()
        saved_group = config.load_setting("group")
        self.current_group = saved_group if saved_group in groups else mods_loader.default_group(groups)
        self.disabled_keys = set(config.load_setting("disabled_mods", []) or [])
        self._disabled_vars = {}
        self.functions = {}
        self.function_names = []
        # 选项界面构建失败的模组：(MOD_KEY, traceback 文本)，供自检/测试断言
        self.mod_build_errors = []
        # 模组可以注册「提交未完成的就地编辑」；任何动作（转换/复制/清空…）之前统一调用，
        # 这样用户在输入框里改了数值后不按回车、直接去点按钮也不会丢
        self.pending_commits = []
        # 帮助窗口（可能同时开着多个）：换主题时统一重刷标题栏/配色/图标
        self._help_windows = []
        self._help_icon_handle = 0
        self.current_function = tk.StringVar(value="")
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
        # 菜单要跟着主题走：_sync_menus 会重画勾选标记并重新套用配色
        self._sync_menus()

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

        # 双保险：sv-ttk 载入主题时会执行 tk_setPalette，它把经典 tk 控件（按钮/菜单/文本框）
        # 重新着色的动作会**推迟到下一次空闲**（例如 pywinstyles 或别处触发的 update()），
        # 所以这里再排一次空闲回调，确保自定义配色是"最后生效"的那一次。
        def _recolor():
            palette_now = theme.palette(self.theme_name)
            self._apply_widget_colors(palette_now)
            self._style_menus(palette_now)

        try:
            self.root.after_idle(_recolor)
        except Exception:
            pass

    def _apply_widget_colors(self, palette=None):
        """自绘控件（经典 tk 按钮 / 圆角文本框）配色；所有标签页都要套一遍。"""
        if palette is None:
            palette = theme.palette(self.theme_name)
        outer_bg = self._outer_bg(palette)

        for key, button in self.all_buttons():
            bg, fg, active_bg = theme.button_colors(key, self.theme_name == "dark")
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
        self._style_window_titlebar(self.root)
        # 已经打开的帮助窗口也一起刷
        for win in list(getattr(self, "_help_windows", [])):
            try:
                if win.winfo_exists():
                    self._apply_help_theme(win)
            except Exception:
                pass

    def _on_dark_mode_toggle(self):
        if self._syncing_theme:
            return
        self._apply_theme("dark" if self.dark_mode_var.get() else "light", persist=True)

    def _icon_cache_files(self):
        """把图标 PNG 转成 .ico 并**长期缓存**（返回 [小图路径, 大图路径]）。

        刻意不写 %TEMP%、也刻意不删除：
        * 临时文件用完即删，而在装有「安全删除」类工具/策略的机器上，删除会把文件
          送进回收站 —— 每次启动都留下 2 个 .ico，用户会看到回收站被项目文件灌满；
        * 改为写 %LOCALAPPDATA%/RPEToolbox/cache 下的固定文件名，源图未变就直接复用，
          全程「只写不删」，不产生任何待清理的痕迹。
        """
        cached = getattr(self, "_icon_files", None)
        if cached:
            return cached
        import hashlib

        from PIL import Image

        full_icon = resources.find_full_icon()
        mini_icon = resources.find_icon()
        if not full_icon:
            return None
        small_src = mini_icon if mini_icon and os.path.exists(mini_icon) else full_icon

        cache_dir = resources.user_cache_dir()
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            return None

        # 记录「哪个源图生成的」，源图换了才重新生成（打包成 onefile 后解包路径每次不同，故用内容指纹）
        stamp_path = os.path.join(cache_dir, "icons.json")
        try:
            with open(stamp_path, "r", encoding="utf-8") as f:
                stamps = json.load(f)
            if not isinstance(stamps, dict):
                stamps = {}
        except Exception:
            stamps = {}

        def fingerprint(path):
            try:
                with open(path, "rb") as f:
                    return hashlib.md5(f.read()).hexdigest()
            except Exception:
                return None

        def ico_for(index, src_path, sizes):
            target = os.path.join(cache_dir, "icon%d.ico" % index)
            fp = fingerprint(src_path)
            if (fp and stamps.get(str(index)) == fp
                    and os.path.exists(target) and os.path.getsize(target) > 0):
                return target          # 命中缓存：不重写、不删除
            try:
                Image.open(src_path).convert("RGBA").save(target, format="ICO", sizes=sizes)
            except Exception:
                return target if os.path.exists(target) else None
            stamps[str(index)] = fp
            return target

        paths = [ico_for(0, small_src, [(16, 16)]), ico_for(1, full_icon, [(32, 32), (48, 48)])]
        try:
            with open(stamp_path, "w", encoding="utf-8") as f:
                json.dump(stamps, f)
        except Exception:
            pass
        paths = [p for p in paths if p]
        self._icon_files = paths
        return paths

    def _ensure_icons(self):
        """加载（并缓存）小/大图标句柄；重复调用不再产生任何临时文件。"""
        if getattr(self, "_icons_ready", False):
            return self._icon_small, self._icon_big
        paths = self._icon_cache_files()
        small = big = None
        if paths and len(paths) >= 2:
            try:
                import ctypes

                user32 = ctypes.windll.user32
                small = user32.LoadImageW(None, paths[0], 1, 16, 16, 0x0010)
                big = user32.LoadImageW(None, paths[1], 1, 32, 32, 0x0010)
            except Exception:
                small = big = None
        self._icon_small, self._icon_big = small, big
        self._icon_handles = [h for h in (small, big) if h]
        self._icons_ready = bool(self._icon_handles)
        return small, big

    def _release_icons(self):
        """退出时只释放图标句柄。缓存文件保留（删除它们只会在回收站留垃圾）。"""
        if os.name != "nt":
            self._icon_handles = []
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            for handle in getattr(self, "_icon_handles", []) or []:
                try:
                    user32.DestroyIcon(handle)
                except Exception:
                    pass
        except Exception:
            pass
        self._icon_handles = []
        self._icons_ready = False

    def _apply_taskbar_icon(self):
        """Windows：用 WM_SETICON 设置任务栏/标题栏图标。

        三管齐下：
        1. 打包环境（frozen）设置 AppUserModelID，任务栏直接使用 exe 资源图标（与 exe 一致）
        2. WM_SETICON 设置窗口小图标(16x16)/大图标(32x32)
        3. SetClassLong 设置类图标，覆盖任务栏/Alt-Tab 读取类图标的路径
        图标均取自 ico-z1.png（与 exe 文件图标同源）。

        注意：Tk 会不断把类图标重置回去，所以本函数会被 3 秒一次的检查反复调用；
        图标文件与句柄都做了缓存，重复调用不再产生临时文件（否则回收站会被 .ico 淹没，
        实测约 3 次/秒 × 2 个 ≈ 2.2 万个/小时）。
        """
        if os.name != "nt":
            return
        try:
            import ctypes

            small, big = self._ensure_icons()
            if not small and not big:
                return

            user32 = ctypes.windll.user32
            # 打包环境：绑定 AppUserModelID，任务栏显示 exe 图标（即 ico-z1.png）
            if getattr(sys, "frozen", False):
                try:
                    shell32 = ctypes.windll.shell32
                    shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.c_wchar_p]
                    shell32.SetCurrentProcessExplicitAppUserModelID("rpetoolbox")
                except Exception:
                    pass

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
            # 再发一次 WM_SETICON 刷新标题栏/任务栏（小图标 16x16、大图标 32x32）
            if small:
                user32.SendMessageW(hwnd, WM_SETICON, 0, small)
            if big:
                user32.SendMessageW(hwnd, WM_SETICON, 1, big)
            self._icon_retry = 0
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
        """定时检查任务栏大图标：若被 Tk 重置（如变回 16x16/羽毛），重新应用。

        Tk 会持续把类图标改回去，所以这里会频繁触发；_apply_taskbar_icon 已缓存图标文件与句柄，
        重复调用不产生临时文件。
        """
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
        # 释放图标句柄（.ico 缓存文件保留在用户目录，不删除——删除只会进回收站）
        try:
            self._release_icons()
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
        """播放按钮音效。

        走标准库 winsound（素材是 assets/audio/*.wav），不再依赖 pygame ——
        之前 pygame 只装在某个特定解释器里，换个 python 启动就变成全程静音。
        """
        try:
            audio.play(kind)
        except Exception:
            pass

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
        # 0. 菜单栏（深色兼容：颜色在 _apply_theme 里统一刷）
        self._build_menubar()

        # 1. 底边状态条：平时显示当前功能介绍，转换时换成进度条。
        #    必须**先于** Notebook pack：pack 是按调用顺序分配空间的，
        #    先 pack 一个 expand=True 的大块会把底边挤没。
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=self.px(10), pady=(0, self.px(6)))
        self.status_label = ttk.Label(self.status_bar, text="", style="Muted.TLabel",
                                      font=self.font_spec(9), anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.progress = ttk.Progressbar(self.status_bar, mode="indeterminate", length=self.px(160))

        # 2. 功能切换：Notebook；每个标签页里依次是「该功能的选项 → 输入JSON → 三个按钮 → 输出JSON」
        self.notebook_host = ttk.Frame(self.root)
        self.notebook_host.pack(fill=tk.BOTH, expand=True, padx=self.px(10), pady=(self.px(6), self.px(2)))
        self.notebook = ttk.Notebook(self.notebook_host)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._rebuild_tabs()

    # ------------------------------------------------------------------
    # 功能组 / 禁用 / 语言 / 状态条
    # ------------------------------------------------------------------
    def current_mods(self):
        """当前功能组里启用的模组（顺序决定标签页与序号）。"""
        mods = mods_loader.discover().get(self.current_group, [])
        return [m for m in mods if m.key not in self.disabled_keys]

    def group_names(self):
        return list(mods_loader.discover().keys())

    def switch_group(self, group):
        if not group or group == self.current_group:
            return
        self.current_group = group
        config.save_setting("group", group)
        self._rebuild_tabs()
        self._sync_menus()

    def toggle_mod_enabled(self, key):
        if key in self.disabled_keys:
            self.disabled_keys.discard(key)
        else:
            self.disabled_keys.add(key)
        config.save_setting("disabled_mods", sorted(self.disabled_keys))
        self._rebuild_tabs()
        self._sync_menus()

    def switch_language(self, code):
        if code == i18n.language():
            return
        i18n.set_language(code)
        config.save_setting("language", code)
        self._rebuild_tabs()
        # 顶层标题（功能/显示/关于）要跟着换语言，重建菜单即可（内含 _sync_menus）
        self._build_menubar()

    def _rebuild_tabs(self):
        """按当前功能组重建标签页（切换组 / 开关禁用 / 切换语言后都会调用）。"""
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        self.tab_frames = {}
        self.tab_io = {}
        self.tab_order = []
        self.functions = {}
        self.function_names = []
        del self.mod_build_errors[:]

        for index, mod in enumerate(self.current_mods()):
            item = i18n.function_by_key(mod.key) or {}
            title = i18n.function_title(index + 1, item.get("name", mod.key))
            tab = ttk.Frame(self.notebook, padding=self.px(6))
            self.notebook.add(tab, text=item.get("tab") or item.get("name") or mod.key)
            self.tab_frames[mod.key] = tab
            self.tab_order.append(mod.key)
            # 需求五顺序：该功能的选项 → 输入JSON → 三个按钮 → 输出JSON
            if callable(mod.build_options):
                try:
                    mod.build_options(self, tab)
                except Exception:
                    # 选项界面建失败不影响该功能可用，但要把真实异常留下来便于定位
                    detail = traceback.format_exc()
                    self.mod_build_errors.append((mod.key, detail))
                    try:
                        sys.stderr.write(detail)
                    except Exception:
                        pass
                    messagebox.showwarning(t("dialogs.tip_title"),
                                           t("dialogs.mod_options_failed", key=mod.key))
            self.tab_io[mod.key] = self._build_io_panel(
                tab, with_input=mod.key not in self.NO_INPUT_FUNCTIONS)
            self.functions[title] = (mod.key, item.get("desc", ""))
            self.function_names.append(title)

        self.current_function = tk.StringVar(
            value=self.function_names[0] if self.function_names else "")
        self.current_function.trace_add("write", self.on_function_change)
        self.on_function_change()

    def _update_status_text(self, text=None):
        """底边条文字：默认显示当前功能介绍。"""
        if text is None:
            label = self.current_function.get() if getattr(self, "current_function", None) else ""
            text = self._resolve_function(label)[1]
        try:
            self.status_label.config(text=text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 菜单栏
    # ------------------------------------------------------------------
    # 勾选标记自己画在文字前面：Tk 原生的菜单勾选框底色由系统决定，
    # 浅色/深色下都可能与菜单底色几乎同色（用户实测「勾看不到」），
    # 自绘的字符用的是菜单前景色，两种主题下都清晰，且宽度与两个空格完全一致。
    MENU_CHECK = "\u2714 "
    MENU_BLANK = "  "

    def _menu_mark(self, on):
        return self.MENU_CHECK if on else self.MENU_BLANK

    def _toggle_dark_mode(self):
        """菜单里的「深色模式」：切换主题（状态仍由 dark_mode_var 持有）。"""
        self.dark_mode_var.set(not self.dark_mode_var.get())

    def _build_menubar(self):
        """自绘菜单栏（Frame + 按钮 + 自绘下拉），**不用** tk 的原生 menubar 与原生弹出。

        原因：本机的 Tk 9.0.4 在 Windows 上把 menubar 那一条与弹出菜单都交给系统原生绘制，
        `-background`/`-foreground` 完全不生效（实测设成红色仍是纯白），深色主题下永远是白条。
        所以这里只把 tk.Menu 当**数据源**（条目/命令/勾选都在 `_sync_menus` 里维护），
        展示层用 tk.Button + 一个 overrideredirect 的 Toplevel 来渲染（`_open_dropdown`）。
        """
        # 换语言等场景会重建：先销毁上一条，避免旧 Frame 一直占着位置
        old = getattr(self, "menubar", None)
        if old is not None:
            try:
                old.destroy()
            except Exception:
                pass

        bar = tk.Frame(self.root, bd=0, highlightthickness=0)
        bar.pack(fill=tk.X, side=tk.TOP)
        self.menubar = bar

        func_menu = tk.Menu(bar, tearoff=0)
        self.group_menu = tk.Menu(func_menu, tearoff=0)
        func_menu.add_cascade(label=t("menu.switch_group"), menu=self.group_menu)
        self.enable_menu = tk.Menu(func_menu, tearoff=0)
        func_menu.add_cascade(label=t("menu.enable"), menu=self.enable_menu)

        view_menu = tk.Menu(bar, tearoff=0)
        self.view_menu = view_menu
        view_menu.add_command(label=self._menu_mark(False) + t("menu.dark_mode"),
                              command=self._toggle_dark_mode)
        self.lang_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(label=t("menu.language"), menu=self.lang_menu)

        help_menu = tk.Menu(bar, tearoff=0)
        self.help_menu = help_menu
        # 功能介绍排在关于上一行；文字随当前选中的功能变化
        help_menu.add_command(label=self._menu_mark(False) + t("menu.func_help", name=""),
                              command=self.show_function_help)
        help_menu.add_command(label=t("menu.about"), command=self.show_about)

        self._menu_buttons = {}
        self._menu_source = {}
        for text_key, menu in (("menu.function", func_menu), ("menu.view", view_menu),
                               ("menu.help", help_menu)):
            # 普通 tk.Button：点击后用 _open_dropdown 渲染自绘下拉（不依赖原生弹出）
            btn = tk.Button(bar, text=t(text_key), bd=0, relief=tk.FLAT,
                            font=self.font_spec(10), cursor="arrow",
                            command=lambda k=text_key: self._toggle_dropdown(k))
            btn.pack(side=tk.LEFT, padx=self.px(2), pady=self.px(3))
            self._menu_buttons[text_key] = btn
            self._menu_source[text_key] = menu

        # 底部一条 1px 分隔线：让菜单栏与下方内容拉开色差（颜色随主题在 _style_menus 里刷）
        palette = theme.palette(self.theme_name)
        bar._hp_line = tk.Frame(bar, height=self.px(1), bd=0,
                                bg=palette.get("menubar_border", palette["muted"]))
        bar._hp_line.pack(side=tk.BOTTOM, fill=tk.X)

        self._all_menus = [func_menu, self.group_menu, self.enable_menu,
                           view_menu, self.lang_menu, help_menu]
        self._sync_menus()

    def _sync_menus(self):
        """重建菜单条目：勾选标记（自绘）+ 功能组 / 禁用 / 语言 / 深色模式 的当前状态。"""
        mark = self._menu_mark
        try:
            # 深色模式
            self.view_menu.entryconfigure(
                0, label=mark(self.theme_name == "dark") + t("menu.dark_mode"))

            # 切换功能组：当前组前打勾
            self.group_menu.delete(0, tk.END)
            for name in self.group_names():
                self.group_menu.add_command(
                    label=mark(name == self.current_group) + name,
                    command=lambda n=name: self.switch_group(n))

            # 启用功能：**勾 = 启用**（没勾就是已禁用），再点一下即重新启用
            self.enable_menu.delete(0, tk.END)
            for mod in mods_loader.discover().get(self.current_group, []):
                item = i18n.function_by_key(mod.key) or {}
                enabled = mod.key not in self.disabled_keys
                key = mod.key
                self.enable_menu.add_command(
                    label=mark(enabled) + item.get("name", key),
                    command=lambda k=key: self.toggle_mod_enabled(k))

            # 语言：当前语言前打勾
            self.lang_menu.delete(0, tk.END)
            for code in i18n.available_languages():
                self.lang_menu.add_command(
                    label=mark(code == i18n.language()) + i18n.language_display(code),
                    command=lambda c=code: self.switch_language(c))

            # 帮助 / 功能介绍：<已选中功能的完整名称>
            self.help_menu.entryconfigure(
                0, label=mark(False) + t("menu.func_help", name=self._current_func_name()))
        except Exception:
            pass
        self._close_dropdown()          # 菜单内容变了，开着的下拉直接收起
        self._style_menus()

    def _current_func_name(self):
        """当前选中功能的完整名称（语言文件里的 name，不带序号）。"""
        key = self._resolve_function(self.current_function.get())[0] \
            if getattr(self, "current_function", None) else None
        item = i18n.function_by_key(key) if key else None
        return item.get("name", key or "")

    # ------------------------------------------------------------------
    # 自绘下拉菜单（tk.Menu 只当数据源，展示层完全自己画）
    # ------------------------------------------------------------------
    def _close_dropdown(self):
        for popup in getattr(self, "_dropdowns", []):
            try:
                popup.destroy()
            except Exception:
                pass
        self._dropdowns = []

    def _toggle_dropdown(self, text_key):
        """点击菜单栏按钮：已开就收起，否则展开。"""
        was_open = bool(getattr(self, "_dropdowns", [])) and \
            getattr(self, "_dropdown_key", None) == text_key
        self._close_dropdown()
        if not was_open:
            self._open_dropdown(text_key, level=0)
            self._start_dropdown_watch()

    def _dropdown_row(self, parent, label, command=None, cascade=False, hover=None):
        """下拉里的一行（经典 tk.Button，配色随主题，悬停有高亮）。

        行距刻意收紧（pady=2、左侧 12px 缩进），贴近原生菜单的排版。
        """
        palette = theme.palette(self.theme_name)
        text = label + ("  \u203a" if cascade else "")
        btn = tk.Button(parent, text=text, anchor="w", bd=0, relief=tk.FLAT,
                        font=self.font_spec(10), cursor="arrow",
                        bg=palette["bg"], fg=palette["fg"],
                        activebackground=palette["select_bg"] if self.theme_name == "dark"
                        else palette["accent"],
                        activeforeground="#ffffff",
                        padx=self.px(12), pady=self.px(2), command=command)
        if hover is not None:
            # 悬停级联项时像原生菜单一样弹出下一级
            btn.bind("<Enter>", lambda e, h=hover: h())
        return btn

    def _close_dropdown_from(self, level):
        """销毁 level 及更深层的所有下拉面板（切到别的级联/普通条目时用）。

        注意必须逐个 destroy —— 只从列表里裁掉的话，窗口还留在屏幕上
        （曾表现为：悬停「启用」弹出子菜单后移到「切换组」，启用面板不消失）。
        """
        idx = level
        while idx < len(self._dropdowns):
            p = self._dropdowns[idx]
            if p is not None:
                try:
                    p.destroy()
                except Exception:
                    pass
            idx += 1
        del self._dropdowns[level:]

    def _dropdown_entry(self, parent, menu, index, text_key, level, anchor_btn):
        kind = menu.type(index)
        if kind == "separator":
            palette = theme.palette(self.theme_name)
            tk.Frame(parent, bg=palette["muted"], height=self.px(1)).pack(
                fill=tk.X, padx=self.px(8), pady=self.px(2))
            return
        label = str(menu.entrycget(index, "label"))
        if kind == "cascade":
            submenu = menu.nametowidget(menu.entrycget(index, "menu"))

            def open_child(btn=parent):
                # 悬停/点击级联项：像原生菜单一样向右弹出下一级，
                # 同时销毁更深层的面板（避免旧面板残留在屏幕上）
                self._close_dropdown_from(level + 1)
                self._open_dropdown(text_key, level=level + 1, submenu=submenu,
                                    anchor=btn)
                self._start_dropdown_watch()

            btn = self._dropdown_row(parent, label, command=open_child,
                                     cascade=True, hover=open_child)
        else:
            def plain_hover():
                # 移到普通条目上时，收起更深层的手风琴（原生菜单也是这样）
                self._close_dropdown_from(level + 1)
                self._start_dropdown_watch()

            btn = self._dropdown_row(
                parent, label,
                command=lambda m=menu, i=index: self._run_menu_item(m, i),
                hover=plain_hover)
        btn.pack(fill=tk.X)

    def _open_dropdown(self, text_key, level=0, submenu=None, title="", anchor=None):
        """渲染一个下拉：条目来自 tk.Menu（数据源），外观全部自绘。

        level=0 是菜单栏按钮正下方的面板；level>=1 是级联子菜单，
        anchor 给出触发它的那一行（子面板出现在它右侧）。
        """
        palette = theme.palette(self.theme_name)
        menu = submenu if submenu is not None else getattr(self, "_menu_source", {}).get(text_key)
        if menu is None:
            return
        anchor_btn = self._menu_buttons.get(text_key)
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.transient(self.root)
        inner = tk.Frame(popup, bg=palette["bg"], bd=1,
                         highlightthickness=1,
                         highlightbackground=palette["menubar_border"])
        inner.pack(fill=tk.BOTH, expand=True)

        end = menu.index("end")
        if end is not None:
            for i in range(end + 1):
                self._dropdown_entry(inner, menu, i, text_key, level, anchor_btn)

        # 位置：一级在按钮正下方，级联子面板在触发行的右侧
        if level == 0 and anchor_btn is not None:
            x = anchor_btn.winfo_rootx()
            y = anchor_btn.winfo_rooty() + anchor_btn.winfo_height()
        elif anchor is not None:
            x = anchor.winfo_rootx() + anchor.winfo_width() - self.px(4)
            y = anchor.winfo_rooty()
        else:
            x = self.menubar.winfo_rootx() + self.menubar.winfo_width() // 3
            y = self.menubar.winfo_rooty() + self.px(30)
        popup.update_idletasks()
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        w = max(self.px(160), popup.winfo_reqwidth())
        h = popup.winfo_reqheight()
        x = min(max(0, x), max(0, sw - w - 8))
        y = min(max(0, y), max(0, sh - h - 8))
        # 注意：Tk9 的 overrideredirect 窗口在**映射前**设置的位置会被忽略（实测落在 +0+0），
        # 所以先带尺寸映射，映射完成后再定位一次。
        popup.geometry("%dx%d" % (w, h))
        popup.deiconify()
        popup.update_idletasks()
        popup.geometry("+%d+%d" % (x, y))
        popup.update_idletasks()

        popup.attributes("-topmost", True)
        popup.bind("<Escape>", lambda e: self._close_dropdown())
        popup.bind("<Button-1>", lambda e: self._close_dropdown()
                   if e.widget is popup else None)
        while len(self._dropdowns) <= level:
            self._dropdowns.append(None)
        self._dropdowns[level] = popup
        self._dropdown_key = text_key

    def _start_dropdown_watch(self):
        """鼠标移开所有菜单面板（且不在菜单栏上）时自动收起，模拟原生菜单。"""
        if getattr(self, "_dropdown_watch_running", False):
            return
        self._dropdown_watch_running = True

        def watch():
            self._dropdown_watch_running = False
            if not getattr(self, "_dropdowns", []):
                return
            try:
                px = self.root.winfo_pointerx()
                py = self.root.winfo_pointery()
            except Exception:
                return
            inside = False
            for p in list(self._dropdowns):
                if p is None:
                    continue
                try:
                    if not p.winfo_exists():
                        continue
                except Exception:
                    continue
                x, y = p.winfo_rootx(), p.winfo_rooty()
                if x - 2 <= px <= x + p.winfo_width() + 2 and \
                        y - 2 <= py <= y + p.winfo_height() + 2:
                    inside = True
                    break
            if not inside:
                bar = getattr(self, "menubar", None)
                if bar is not None:
                    bx, by = bar.winfo_rootx(), bar.winfo_rooty()
                    if bx - 2 <= px <= bx + bar.winfo_width() + 2 and \
                            by - 2 <= py <= by + bar.winfo_height() + 2:
                        inside = True          # 还在菜单栏上：先别收，可能要切换
            if inside:
                self._dropdown_outside = 0
                try:
                    self.root.after(150, watch)
                except Exception:
                    pass
            else:
                # 连续两次（约 300ms）都在外面才收起：避免指针恰好扫过空隙时误关
                self._dropdown_outside = getattr(self, "_dropdown_outside", 0) + 1
                if self._dropdown_outside >= 2:
                    self._dropdown_outside = 0
                    self._close_dropdown()
                else:
                    try:
                        self.root.after(150, watch)
                    except Exception:
                        pass

        try:
            self.root.after(200, watch)
        except Exception:
            self._dropdown_watch_running = False

    def _run_menu_item(self, menu, index):
        """执行下拉里选中的那一项，然后收起并重画勾选。"""
        self._close_dropdown()
        try:
            menu.invoke(index)
        finally:
            self._sync_menus()

    def _style_menus(self, palette=None):
        """菜单栏配色：自绘菜单栏（Frame + 按钮 + 底部分隔线）与下拉数据源都在这里刷。

        暗色下把 activebackground 也压暗一档，避免用亮蓝当高亮时“亮块+浅字”刺眼；
        selectcolor 一并设置，减少系统默认色在两种主题下与底色撞车的可能。
        """
        if palette is None:
            palette = theme.palette(self.theme_name)
        dark = self.theme_name == "dark"
        active_bg = palette["select_bg"] if dark else palette["accent"]
        active_fg = "#ffffff"
        bar_bg = palette.get("menubar_bg", palette["bg"])
        # 自绘菜单栏本身（Frame + 按钮 + 底部分隔线，与下方内容拉开色差）
        try:
            self.menubar.configure(bg=bar_bg)
        except Exception:
            pass
        for btn in getattr(self, "_menu_buttons", {}).values():
            try:
                btn.configure(bg=bar_bg, fg=palette["fg"],
                              activebackground=active_bg, activeforeground=active_fg)
            except Exception:
                pass
        line = getattr(self.menubar, "_hp_line", None)
        if line is not None:
            try:
                line.configure(bg=palette.get("menubar_border", palette["muted"]))
            except Exception:
                pass
        for menu in getattr(self, "_all_menus", []):
            try:
                menu.configure(bg=palette["bg"], fg=palette["fg"],
                               activebackground=active_bg, activeforeground=active_fg,
                               disabledforeground=palette["muted"],
                               selectcolor=palette["text_bg"],
                               bd=0, relief=tk.FLAT)
            except Exception:
                pass

    def show_about(self):
        # 文案里的 {version} 必须真的传值，否则界面会显示字面量 "{version}"
        messagebox.showinfo(t("dialogs.about_title"),
                            t("dialogs.about_text", version=APP_VERSION))

    def show_function_help(self):
        """帮助 / 功能介绍：弹窗显示当前功能的详细使用方法（含每个选项的作用）。"""
        key = self._resolve_function(self.current_function.get())[0] \
            if getattr(self, "current_function", None) else None
        body = None
        if key:
            try:
                node = i18n.load().get("help", {})
                body = node.get(key) if isinstance(node, dict) else None
            except Exception:
                body = None
        if not body:
            body = t("dialogs.func_help_missing", name=self._current_func_name())

        win = tk.Toplevel(self.root)
        win.title(t("dialogs.func_help_title", name=self._current_func_name()))
        win.transient(self.root)
        win.resizable(True, True)
        pad = self.px(8)
        palette = theme.palette(self.theme_name)
        win._hp_frame = tk.Frame(win, bg=palette["bg"])
        win._hp_frame.pack(fill=tk.BOTH, expand=True)
        win._hp_text = tk.Text(win._hp_frame, wrap="word", bd=0, highlightthickness=0,
                               font=self.font_spec(10), padx=pad, pady=pad,
                               bg=palette["text_bg"], fg=palette["text_fg"])
        bar = ttk.Scrollbar(win._hp_frame, orient=tk.VERTICAL, command=win._hp_text.yview)
        win._hp_text.configure(yscrollcommand=bar.set)
        bar.pack(side=tk.RIGHT, fill=tk.Y)
        win._hp_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        win._hp_text.insert("1.0", body)
        win._hp_text.configure(state=tk.DISABLED)          # 只读
        bg, fg, active_bg = theme.button_colors("clear", self.theme_name == "dark")
        win._hp_btn = tk.Button(win, text=t("dialogs.close"), command=win.destroy,
                                font=self.font_spec(10), bg=bg, fg=fg,
                                activebackground=active_bg, activeforeground=fg,
                                highlightbackground=bg, highlightcolor=bg)
        win._hp_btn.pack(fill=tk.X, padx=pad, pady=(0, pad))
        win.geometry("%dx%d" % (self.px(560), self.px(460)))

        # 标题栏/图标/配色都要跟着主题走
        self._apply_help_theme(win)
        self._help_windows.append(win)
        win.protocol("WM_DELETE_WINDOW", lambda: self._close_help_window(win))
        try:
            win.grab_set()                          # 模态：看完再回主窗口
            win.focus_set()
        except Exception:
            pass

    def _apply_help_theme(self, win):
        """帮助窗口的配色 + 标题栏深浅（与主窗口一致）。"""
        palette = theme.palette(self.theme_name)
        try:
            win.configure(bg=palette["bg"])
        except Exception:
            pass
        frame = getattr(win, "_hp_frame", None)
        text = getattr(win, "_hp_text", None)
        btn = getattr(win, "_hp_btn", None)
        if frame is not None:
            try:
                frame.configure(bg=palette["bg"])
            except Exception:
                pass
        if text is not None:
            try:
                text.configure(bg=palette["text_bg"], fg=palette["text_fg"],
                               insertbackground=palette["text_fg"])
            except Exception:
                pass
        if btn is not None:
            bg, fg, active_bg = theme.button_colors("clear", self.theme_name == "dark")
            try:
                btn.configure(bg=bg, fg=fg, activebackground=active_bg,
                              activeforeground=fg, highlightbackground=bg, highlightcolor=bg)
            except Exception:
                pass
        self._style_window_titlebar(win)
        self._set_window_icon(win, self._help_window_icon())
        # pywinstyles.apply_style 内部会 update()，把 sv-ttk 推迟的 tk_setPalette 跑掉，
        # 菜单栏（顶栏 + 所有子菜单）会被刷回浅色 —— 所以这里必须再补刷一次菜单。
        self._style_menus(palette)
        try:
            self.root.after_idle(lambda: self._style_menus(theme.palette(self.theme_name)))
        except Exception:
            pass

    def _close_help_window(self, win):
        try:
            self._help_windows.remove(win)
        except Exception:
            pass
        try:
            win.destroy()
        except Exception:
            pass

    def _window_hwnd(self, widget):
        """取「真正带标题栏」的窗口句柄（Tk 的 toplevel 外面还有一层 frame）。"""
        if os.name != "nt":
            return 0
        try:
            frame = widget.tk.call("wm", "frame", widget)
            if frame:
                return int(str(frame), 16)
        except Exception:
            pass
        try:
            import ctypes

            user32 = ctypes.windll.user32
            wid = widget.winfo_id()
            return user32.GetParent(wid) or wid
        except Exception:
            return 0

    def _style_window_titlebar(self, window):
        """任意窗口的标题栏跟随主题（主窗口与帮助窗口都用它）。"""
        if pywinstyles is None or os.name != "nt":
            return
        try:
            pywinstyles.apply_style(window, "dark" if self.theme_name == "dark" else "light")
        except Exception:
            pass

    def _help_window_icon(self):
        """Windows 自带的「帮助」图标（蓝底白问号），取一次并缓存。

        stock icon 编号要小心：77 是 SIID_SHIELD（UAC 盾牌/管理员），不是帮助！
        问号是 SIID_HELP=23（实测蓝底白问号，最贴合"帮助"），
        信息是 SIID_INFO=79；失败再退回 IDI_QUESTION(32514)。
        """
        if os.name != "nt":
            return 0
        cached = getattr(self, "_help_icon_handle", 0)
        if cached:
            return cached
        try:
            import ctypes
            from ctypes import wintypes

            class _SHSTOCKICONINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.ULONG),
                            ("hIcon", wintypes.HICON),
                            ("iSysImageIndex", ctypes.c_int),
                            ("iIcon", ctypes.c_int),
                            ("szPath", wintypes.WCHAR * 260)]

            sii = _SHSTOCKICONINFO()
            sii.cbSize = ctypes.sizeof(_SHSTOCKICONINFO)
            SIID_HELP = 23                       # 系统的「帮助/问号」图标
            SHGFI_ICON = 0x00000100
            if ctypes.windll.shell32.SHGetStockIconInfo(
                    SIID_HELP, SHGFI_ICON, ctypes.byref(sii)) == 0 and sii.hIcon:
                self._help_icon_handle = int(sii.hIcon)
                return self._help_icon_handle
        except Exception:
            pass
        try:
            import ctypes

            IMAGE_ICON, LR_SHARED = 1, 0x00008000
            h = ctypes.windll.user32.LoadImageW(None, ctypes.c_void_p(32514),   # IDI_QUESTION
                                                IMAGE_ICON, 0, 0, LR_SHARED)
            if h:
                self._help_icon_handle = int(h)
                return self._help_icon_handle
        except Exception:
            pass
        return 0

    def _set_window_icon(self, window, hicon):
        """给任意窗口设标题栏图标（WM_SETICON，小图标 + 大图标都用它）。"""
        if not hicon or os.name != "nt":
            return
        try:
            import ctypes

            hwnd = self._window_hwnd(window)
            if not hwnd:
                return
            user32 = ctypes.windll.user32
            user32.SendMessageW(hwnd, 0x0080, 0, hicon)     # WM_SETICON / ICON_SMALL
            user32.SendMessageW(hwnd, 0x0080, 1, hicon)     # WM_SETICON / ICON_BIG
        except Exception:
            pass

    def _set_busy(self, busy, text=""):
        """转换进行中：底边条换成进度条；结束后恢复介绍文字。"""
        try:
            if busy:
                self.status_label.config(text=text)
                self.progress.pack(side=tk.RIGHT, padx=self.px(5))
                self.progress.start(12)
            else:
                self.progress.stop()
                self.progress.pack_forget()
                self._update_status_text()
        except Exception:
            pass

    def _build_io_panel(self, parent, with_input=True):
        """在标签页内建一套 输入JSON / 转换·复制结果·清空输入输出 / 输出JSON。

        Tk 的控件不能同时属于多个容器，所以每个标签页各持有一套；这样切换功能时
        各自的输入输出也会分别保留。图片转音符画 / MIDI BPM 提取 不需要输入框。

        输入框与输出框**严格等高**：用 grid 里两个 weight=1 + uniform 的行来分剩余空间。
        用 pack 的 expand 只能做到「各自请求高度 + 平分余量」，两者会差出一大截。
        """
        panel = {"buttons": {}}

        holder = ttk.Frame(parent)
        holder.pack(fill=tk.BOTH, expand=True)
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1, uniform="io")
        holder.rowconfigure(2, weight=1, uniform="io")

        # 输入区始终建好，只是图片转音符画 / MIDI BPM 提取 两页不显示（保持结构一致）
        # 注意：输入框与输出框的**外层**不能有多余的 padx/pady，否则两个框会差出那几个像素
        frame_input = ttk.Frame(holder)
        if with_input:
            frame_input.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame_input, text=t("labels.input_json"), anchor="w").pack(fill=tk.X, pady=(0, self.px(2)))
        text_input = RoundedTextArea(frame_input, font=self._get_code_font(), radius=self.px(8))
        text_input.pack(fill=tk.BOTH, expand=True)
        panel["input_frame"] = frame_input
        panel["text_input"] = text_input

        frame_btn = ttk.Frame(holder)
        frame_btn.grid(row=1, column=0, sticky="ew", pady=self.px(4))
        button_texts = {"convert": "buttons.convert", "copy": "buttons.copy", "clear": "buttons.clear"}
        for key in ("convert", "copy", "clear"):
            bg, fg, active_bg = theme.button_colors(key, self.theme_name == "dark")
            button = tk.Button(frame_btn, text=t(button_texts[key]), font=self.font_spec(10),
                               bg=bg, fg=fg, activebackground=active_bg, activeforeground=fg,
                               command=lambda k=key: self._trigger_with_sound(k))
            button.pack(side=tk.LEFT, padx=self.px(5))
            panel["buttons"]["btn_" + key] = button
        panel["frame_btn"] = frame_btn

        frame_output = ttk.Frame(holder)
        frame_output.grid(row=2, column=0, sticky="nsew")
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

    def register_pending_commit(self, fn):
        """模组注册一个「提交未完成编辑」的回调（同一函数不会重复注册）。"""
        if fn not in self.pending_commits:
            self.pending_commits.append(fn)

    def commit_pending_edits(self):
        """把所有模组未提交的就地编辑落盘（按钮点击会先经过这里）。"""
        for fn in list(self.pending_commits):
            try:
                fn()
            except Exception:
                pass

    def _trigger_with_sound(self, kind):
        # 用户可能在就地编辑框里改了值却没按回车，先统一提交再执行动作
        self.commit_pending_edits()
        if kind == "convert":
            self._set_busy(True, t("status.converting"))
            self._convert_started = time.monotonic()
            # 先让界面把进度条画出来，再执行（转换是同步的）
            self.root.after(30, self._run_convert_with_sound)
        elif kind == "copy":
            self._play_button_sound("copy")
            self.copy_result()
        elif kind == "clear":
            self._play_button_sound("clear")
            self.clear_io()

    def _run_convert_with_sound(self):
        """转换 → 进度条至少显示 PROGRESS_MIN_MS → 播音效的同时切回功能介绍。

        转换本身常常只要几毫秒，进度条一闪而过等于看不见，所以给它一个最短可见时长。
        """
        started = getattr(self, "_convert_started", None)
        try:
            success = self.process_data()
        finally:
            elapsed_ms = (time.monotonic() - started) * 1000.0 if started else 0.0
            remain = int(max(0.0, self.PROGRESS_MIN_MS - elapsed_ms))
            kind = "convert" if success else "convert_error"

            def finish():
                # 恢复介绍文字与播放音效同时发生
                self._set_busy(False)
                self._play_button_sound(kind)

            if remain > 0:
                self.root.after(remain, finish)
            else:
                finish()

    def _resolve_function(self, label):
        """把 current_function 的值解析成 (模组键, 简介)。

        兼容三种写法：带序号的标题（界面实际用法）、不带序号的名称、模组 key，
        这样界面点击标签、菜单选择、以及外部按功能名赋值都能正确落到同一个模组。
        """
        if not label:
            return None, ""
        hit = self.functions.get(label)
        if hit:
            return hit
        for _title, (key, desc) in self.functions.items():
            if key == label:
                return key, desc
            item = i18n.function_by_key(key) or {}
            if item.get("name") == label:
                return key, desc
        return None, ""

    def on_function_change(self, *args):
        """当前功能变化：切到对应标签页，并刷新底边条上的功能简介。"""
        label = self.current_function.get()
        func_key = self._resolve_function(label)[0]
        if func_key:
            self._select_function_tab(func_key)
        self._update_status_text()

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
        except Exception:
            return
        # 必须写回「带序号的标题」，与 self.functions 的键一致，
        # 否则点过标签后状态条与「转换」都会找不到当前功能
        if not (0 <= index < len(self.function_names)):
            return
        title = self.function_names[index]
        if self.current_function.get() == title:
            return
        self._syncing_tab = True
        try:
            self.current_function.set(title)
        finally:
            self._syncing_tab = False
        # 帮助菜单里的「功能介绍: …」要跟着当前标签页走
        self._sync_menus()


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


    def process_data(self):
        """按当前标签页对应的模组执行转换。"""
        try:
            label = self.current_function.get()
            func_key = self._resolve_function(label)[0]
            mod = mods_loader.find(func_key) if func_key else None
            if mod is None:
                raise Exception(t("errors.unknown_function"))

            data = {} if func_key in self.NO_INPUT_FUNCTIONS else self.get_input_data()
            result = mod.process(self, data)

            self.set_output_data(result)
            return True

        except Exception as e:
            self.show_error(str(e))
            return False
