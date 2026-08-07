# -*- coding: utf-8 -*-
"""RPEToolbox 主类：界面构建、输入输出与功能分发。"""

import json
import os
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from . import resources
from .core import FunctionMixin
from .imglib import Image


class RPEToolbox(FunctionMixin):
    def __init__(self, root):
        self.root = root
        self.root.title("rpe工具箱")
        self.root.geometry("680x760")
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
        self.root.option_add("*Font", f"{self.ui_font_family} 10")
        self.root.option_add("*Label.Font", f"{self.ui_font_family} 10")
        self.root.option_add("*Button.Font", f"{self.ui_font_family} 10")
        self.root.option_add("*Combobox.Font", f"{self.ui_font_family} 10")

        # 状态变量
        self.current_function = tk.StringVar(value="1. hold/事件首尾相接")
        self.density_var = tk.StringVar(value="16")
        self.allow_shorten_var = tk.BooleanVar(value=False)
        self.distinguish_track_var = tk.BooleanVar(value=False)
        self.stretch_ratio_var = tk.StringVar(value="-1")
        self.time_offset_speed_var = tk.StringVar(value="10")
        self.time_offset_bpm_var = tk.StringVar(value="120")
        self.time_offset_unify_var = tk.BooleanVar(value=True)
        self.lock_aspect_var = tk.BooleanVar(value=True)
        self.rotation_var = tk.StringVar(value="0°")
        self.midi_path_var = tk.StringVar()
        self.event_type_options = [
            ("X轴位移", 1),
            ("Y轴位移", 2),
            ("旋转", 3),
            ("透明度", 4),
            ("流速", 5),
            ("X轴缩放", 6),
            ("Y轴缩放", 7),
        ]
        self.event_source_vars = []
        self.event_target_vars = []
        self.easing_type_map = {
            1: "Linear",
            2: "Out Sine",
            3: "In Sine",
            4: "Out Quad",
            5: "In Quad",
            6: "In Out Sine",
            7: "In Out Quad",
            8: "Out Cubic",
            9: "In Cubic",
            10: "Out Quart",
            11: "In Quart",
            12: "In Out Cubic",
            13: "In Out Quart",
            14: "Out Quint",
            15: "In Quint",
            16: "Out Expo",
            17: "In Expo",
            18: "Out Circ",
            19: "In Circ",
            20: "Out Back",
            21: "In Back",
            22: "In Out Circ",
            23: "In Out Back",
            24: "Out Elastic",
            25: "In Elastic",
            26: "Out Bounce",
            27: "In Bounce",
            28: "In Out Bounce",
            29: "In Out Elastic"
        }
        self.image_ratio = None
        self._syncing_size_vars = False
        self._audio_threads = []
        self._icon_retry = 0

        # 构建界面
        self.create_widgets()

        # 绑定事件
        self.current_function.trace_add("write", self.on_function_change)
        self.on_function_change()  # 初始化显示状态

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
        for t in getattr(self, "_audio_threads", []):
            try:
                t.join(timeout=2)
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

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        try:
            self._audio_threads.append(t)
        except AttributeError:
            self._audio_threads = [t]

    def _get_available_font_family(self):
        available = set(tkfont.families())
        for family in ["Sarasa Gothic SC", "Microsoft YaHei Mono", "monospace", "微软雅黑", "Microsoft YaHei", "Arial"]:
            if family in available:
                return family
        return "Arial"

    def _get_code_font(self):
        return (self.ui_font_family, 9)

    def create_widgets(self):
        # 1. 顶部功能区
        frame_top = tk.Frame(self.root, pady=5)
        frame_top.pack(fill=tk.X, padx=10)

        tk.Label(frame_top, text="选择功能:").pack(side=tk.LEFT)

        self.functions = {
            "1. hold/事件首尾相接": ("hold_notes_connect", "将 Hold 音符或事件的 endTime 连接到下一个不同的 startTime，可区分轨道"),
            "2. 非线性切割": ("nonlinear_split", "按指定密度切分事件，并能自动处理缓动左右端点与贝塞尔控制点"),
            "3. 极坐标转换": ("polar_conversion", "将输入的 (X,Y) 到原点距离作为 r，旋转角度作为 θ，组成极坐标并转换为笛卡尔坐标"),
            "4. 事件类型转换": ("event_type_convert", "修改事件种类 ，支持常规属性和 X/Y 缩放"),
            "5. 图片转音符画": ("image_to_notes", "使用图片生成音符画，支持 JPG/PNG 导入"),
            "6. 时间间隔转y偏移": ("time_interval_to_yoffset", "把音符按时间间隔和流速处理成 yOffset"),
            "7. 倒序/拉伸": ("reverse_data", "将音符或事件按比例拉伸/压缩时间，负比例表示倒序"),
            "8. MIDI BPM 提取": ("midi_bpm_extract", "从 MIDI 文件中提取 BPM 变化列表")
        }

        self.combo = ttk.Combobox(frame_top, textvariable=self.current_function, values=list(self.functions.keys()), state="readonly")
        self.combo.pack(side=tk.LEFT, padx=5)

        self.desc_label = tk.Label(frame_top, text="", fg="gray", font=(self.ui_font_family, 8), wraplength=500, justify=tk.LEFT)
        self.desc_label.pack(side=tk.RIGHT, padx=5)

        # 2. 额外输入区（密度、事件转换、图片转换、时间间隔）
        self.frame_extra = tk.Frame(self.root, pady=5)
        self.frame_extra.pack(fill=tk.X, padx=10)

        # 3. 文本输入区（保持在选项之后）
        self.input_frame = tk.Frame(self.root, pady=5)
        self.input_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        tk.Label(self.input_frame, text="输入JSON:", anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.text_input = tk.Text(self.input_frame, height=10, font=self._get_code_font())
        self.text_input.pack(fill=tk.BOTH, expand=True)

        self.frame_density = tk.Frame(self.frame_extra)
        self.frame_density.pack(fill=tk.X, padx=5, pady=2)
        tk.Label(self.frame_density, text="切割密度 / 音符间隔 (分音):").pack(side=tk.LEFT, padx=5)
        self.entry_density = tk.Entry(self.frame_density, textvariable=self.density_var, width=10)
        self.entry_density.pack(side=tk.LEFT, padx=5)

        self.frame_hold_options = tk.Frame(self.frame_extra)
        self.frame_hold_options.pack(fill=tk.X, padx=5, pady=2)
        self.frame_hold_options.pack_forget()
        self.allow_shorten_check = tk.Checkbutton(self.frame_hold_options, text="是否允许长度缩短", variable=self.allow_shorten_var)
        self.allow_shorten_check.pack(side=tk.LEFT, padx=5)

        self.distinguish_track_check = tk.Checkbutton(self.frame_hold_options, text="是否区分轨道", variable=self.distinguish_track_var)
        self.distinguish_track_check.pack(side=tk.LEFT, padx=5)

        self.frame_event_convert = tk.Frame(self.frame_extra)
        self.frame_event_convert.pack(fill=tk.X, padx=5, pady=5)
        self.frame_event_convert.pack_forget()
        self._create_event_convert_rows()

        self.frame_image_settings = tk.Frame(self.frame_extra)
        self.frame_image_settings.pack(fill=tk.X, padx=5, pady=5)
        self.frame_image_settings.pack_forget()

        row_path = tk.Frame(self.frame_image_settings)
        row_path.pack(fill=tk.X, pady=2)
        tk.Label(row_path, text="图片文件路径:").pack(side=tk.LEFT, padx=5)
        self.image_path_var = tk.StringVar()
        self.entry_image_path = tk.Entry(row_path, textvariable=self.image_path_var, width=55)
        self.entry_image_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.btn_select_image = tk.Button(row_path, text="选择图片", command=self.select_image_file)
        self.btn_select_image.pack(side=tk.LEFT, padx=5)

        # 图片转音符画设置项：5 行布局
        # 第二行：音符类型 颜色处理 旧版染色标签
        row_type_color = tk.Frame(self.frame_image_settings)
        row_type_color.pack(fill=tk.X, pady=2)
        tk.Label(row_type_color, text="音符类型:").pack(side=tk.LEFT, padx=5)
        self.note_type_var = tk.StringVar(value="drag")
        self.note_type_combo = ttk.Combobox(row_type_color, textvariable=self.note_type_var, values=["tap", "drag", "flick", "hold"], state="readonly", width=10)
        self.note_type_combo.pack(side=tk.LEFT, padx=5)

        tk.Label(row_type_color, text="颜色处理:").pack(side=tk.LEFT, padx=5)
        self.color_mode_var = tk.StringVar(value="染色")
        self.color_mode_combo = ttk.Combobox(row_type_color, textvariable=self.color_mode_var, values=["染色", "矫正颜色染色", "不透明度替代亮度"], state="readonly", width=14)
        self.color_mode_combo.pack(side=tk.LEFT, padx=5)

        self.legacy_tint_var = tk.BooleanVar(value=False)
        self.legacy_tint_check = tk.Checkbutton(row_type_color, text="旧版染色标签", variable=self.legacy_tint_var)
        self.legacy_tint_check.pack(side=tk.LEFT, padx=5)
        # 需求十二：颜色处理为“不透明度替代亮度”时隐藏旧版染色标签
        self.color_mode_var.trace_add("write", lambda *_: self._toggle_legacy_tint())
        self._toggle_legacy_tint()

        # 第三行：音符间隔（分音） 左右翻转 上下翻转 旋转度数
        row_opt3 = tk.Frame(self.frame_image_settings)
        row_opt3.pack(fill=tk.X, pady=2)
        tk.Label(row_opt3, text="音符间隔(分音):").pack(side=tk.LEFT, padx=5)
        tk.Entry(row_opt3, textvariable=self.density_var, width=10).pack(side=tk.LEFT, padx=5)
        self.flip_horizontal_var = tk.BooleanVar(value=False)
        self.flip_vertical_var = tk.BooleanVar(value=False)
        self.flip_horizontal_check = tk.Checkbutton(row_opt3, text="左右翻转", variable=self.flip_horizontal_var)
        self.flip_horizontal_check.pack(side=tk.LEFT, padx=5)
        self.flip_vertical_check = tk.Checkbutton(row_opt3, text="上下翻转", variable=self.flip_vertical_var)
        self.flip_vertical_check.pack(side=tk.LEFT, padx=5)
        tk.Label(row_opt3, text="旋转度数:").pack(side=tk.LEFT, padx=5)
        self.rotation_combo = ttk.Combobox(row_opt3, textvariable=self.rotation_var, values=["0°", "90°", "180°", "270°"], state="readonly", width=8)
        self.rotation_combo.pack(side=tk.LEFT, padx=5)

        # 第四行：是否使用原图片大小 (x像素数 y像素数 锁定宽高比)
        row_size = tk.Frame(self.frame_image_settings)
        row_size.pack(fill=tk.X, pady=2)
        self.use_original_size_var = tk.BooleanVar(value=False)
        self.use_original_size_check = tk.Checkbutton(row_size, text="使用原图片大小", variable=self.use_original_size_var)
        self.use_original_size_check.pack(side=tk.LEFT, padx=5)
        self.use_original_size_var.trace_add("write", lambda *_: self._toggle_image_size_fields())

        self.frame_image_size_options = tk.Frame(row_size)
        self.frame_image_size_options.pack(side=tk.LEFT, padx=5)
        tk.Label(self.frame_image_size_options, text="x像素数:").pack(side=tk.LEFT, padx=5)
        self.pixel_width_var = tk.StringVar(value="65")
        self.pixel_width_var.trace_add("write", lambda *_: self._sync_image_dimension("x"))
        tk.Entry(self.frame_image_size_options, textvariable=self.pixel_width_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Label(self.frame_image_size_options, text="y像素数:").pack(side=tk.LEFT, padx=5)
        self.pixel_height_var = tk.StringVar(value="65")
        self.pixel_height_var.trace_add("write", lambda *_: self._sync_image_dimension("y"))
        tk.Entry(self.frame_image_size_options, textvariable=self.pixel_height_var, width=8).pack(side=tk.LEFT, padx=5)
        self.lock_aspect_check = tk.Checkbutton(self.frame_image_size_options, text="锁定宽高比", variable=self.lock_aspect_var)
        self.lock_aspect_check.pack(side=tk.LEFT, padx=5)

        # 第五行：是否自动调整音符宽度 (音符宽度)
        row_width = tk.Frame(self.frame_image_settings)
        row_width.pack(fill=tk.X, pady=2)
        self.auto_adjust_width_var = tk.BooleanVar(value=True)
        self.auto_adjust_width_check = tk.Checkbutton(row_width, text="自动调整音符宽度", variable=self.auto_adjust_width_var)
        self.auto_adjust_width_check.pack(side=tk.LEFT, padx=5)
        self.auto_adjust_width_var.trace_add("write", lambda *_: self._toggle_image_width_fields())

        self.frame_image_width_options = tk.Frame(row_width)
        self.frame_image_width_options.pack(side=tk.LEFT, padx=5)
        tk.Label(self.frame_image_width_options, text="音符宽度:").pack(side=tk.LEFT, padx=5)
        self.note_width_var = tk.StringVar(value="175")
        tk.Entry(self.frame_image_width_options, textvariable=self.note_width_var, width=8).pack(side=tk.LEFT, padx=5)

        self.frame_time_offset_settings = tk.Frame(self.frame_extra)
        self.frame_time_offset_settings.pack(fill=tk.X, padx=5, pady=5)
        self.frame_time_offset_settings.pack_forget()
        tk.Label(self.frame_time_offset_settings, text="流速:").pack(side=tk.LEFT, padx=5)
        tk.Entry(self.frame_time_offset_settings, textvariable=self.time_offset_speed_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Label(self.frame_time_offset_settings, text="bpm:").pack(side=tk.LEFT, padx=5)
        tk.Entry(self.frame_time_offset_settings, textvariable=self.time_offset_bpm_var, width=8).pack(side=tk.LEFT, padx=5)
        self.time_offset_unify_check = tk.Checkbutton(self.frame_time_offset_settings, text="是否统一起始时间", variable=self.time_offset_unify_var)
        self.time_offset_unify_check.pack(side=tk.LEFT, padx=5)

        self.frame_midi_settings = tk.Frame(self.frame_extra)
        self.frame_midi_settings.pack(fill=tk.X, padx=5, pady=5)
        self.frame_midi_settings.pack_forget()
        tk.Label(self.frame_midi_settings, text="MIDI 文件路径:").pack(side=tk.LEFT, padx=5)
        self.entry_midi_path = tk.Entry(self.frame_midi_settings, textvariable=self.midi_path_var, width=55)
        self.entry_midi_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.btn_select_midi = tk.Button(self.frame_midi_settings, text="选择 MIDI", command=self.select_midi_file)
        self.btn_select_midi.pack(side=tk.LEFT, padx=5)

        self.frame_stretch_settings = tk.Frame(self.frame_extra)
        self.frame_stretch_settings.pack(fill=tk.X, padx=5, pady=5)
        self.frame_stretch_settings.pack_forget()
        tk.Label(self.frame_stretch_settings, text="拉伸比例:").pack(side=tk.LEFT, padx=5)
        tk.Entry(self.frame_stretch_settings, textvariable=self.stretch_ratio_var, width=8).pack(side=tk.LEFT, padx=5)
        tk.Label(self.frame_stretch_settings, text="(负值表示倒序，默认 -1)", fg="gray").pack(side=tk.LEFT, padx=5)

        # 4. 按钮区
        self.frame_btn = tk.Frame(self.root, pady=5)
        self.frame_btn.pack(fill=tk.X, padx=10)

        self.btn_convert = tk.Button(self.frame_btn, text="转换", command=lambda: self._trigger_with_sound("convert"), bg="#8EC990", fg="#0C4E1A")
        self.btn_convert.pack(side=tk.LEFT, padx=5)

        self.btn_copy = tk.Button(self.frame_btn, text="复制结果", command=lambda: self._trigger_with_sound("copy"), bg="#E6E7AB", fg="#5A550E")
        self.btn_copy.pack(side=tk.LEFT, padx=5)

        self.btn_clear = tk.Button(self.frame_btn, text="清空输入/输出", command=lambda: self._trigger_with_sound("clear"), bg="#e6766e", fg="#EEDFE5")
        self.btn_clear.pack(side=tk.LEFT, padx=5)

        # 5. 文本输出区
        tk.Label(self.root, text="输出JSON:", anchor="w").pack(fill=tk.X, padx=10, pady=(5, 0))
        self.text_output = tk.Text(self.root, height=10, font=self._get_code_font())
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _create_event_convert_rows(self):
        # 需求十一：两列布局，每行“输入选择框 → 文字”，速度更名为流速
        self.frame_event_convert_left = tk.Frame(self.frame_event_convert)
        self.frame_event_convert_left.pack(side=tk.LEFT, fill=tk.X, padx=(5, 25), pady=2)
        self.frame_event_convert_right = tk.Frame(self.frame_event_convert)
        self.frame_event_convert_right.pack(side=tk.LEFT, fill=tk.X, padx=(0, 5), pady=2)

        self.event_source_vars = []
        self.event_target_vars = []

        type_names = [name for name, _ in self.event_type_options]
        # 左列：X轴位移 Y轴位移 旋转 透明度 流速；右列：X轴缩放 Y轴缩放 定轨hold 曲线drag 音符间隔
        standard_names = ["X轴位移", "Y轴位移", "旋转", "透明度", "流速", "X轴缩放", "Y轴缩放"]
        for idx, name in enumerate(standard_names):
            parent = self.frame_event_convert_left if idx < 5 else self.frame_event_convert_right
            row = idx if idx < 5 else idx - 5
            source_var = tk.StringVar(value=name)
            target_var = tk.StringVar(value=name)
            self.event_source_vars.append(source_var)
            self.event_target_vars.append(target_var)
            ttk.Combobox(parent, textvariable=source_var, values=type_names, state="readonly", width=14).grid(
                row=row, column=0, sticky="w", padx=2, pady=2)
            tk.Label(parent, text="→", width=3, anchor="center").grid(
                row=row, column=1, sticky="w", padx=1, pady=2)
            tk.Label(parent, text=name, width=11, anchor="w").grid(
                row=row, column=2, sticky="w", padx=2, pady=2)

        # 定轨hold：无/5k/7k，默认无
        self.hold_mode_var = tk.StringVar(value="无")
        ttk.Combobox(self.frame_event_convert_right, textvariable=self.hold_mode_var,
                     values=["无", "5k(常规事件)", "7k(包括缩放)"], state="readonly", width=14).grid(
            row=2, column=0, sticky="w", padx=2, pady=2)
        tk.Label(self.frame_event_convert_right, text="→", width=3, anchor="center").grid(
            row=2, column=1, sticky="w", padx=1, pady=2)
        tk.Label(self.frame_event_convert_right, text="定轨hold", width=11, anchor="w").grid(
            row=2, column=2, sticky="w", padx=2, pady=2)

        # 曲线drag：无/X轴位移与缩放/y轴位移与缩放，默认无
        self.drag_mode_var = tk.StringVar(value="无")
        ttk.Combobox(self.frame_event_convert_right, textvariable=self.drag_mode_var,
                     values=["无", "X轴位移与缩放", "y轴位移与缩放"], state="readonly", width=14).grid(
            row=3, column=0, sticky="w", padx=2, pady=2)
        tk.Label(self.frame_event_convert_right, text="→", width=3, anchor="center").grid(
            row=3, column=1, sticky="w", padx=1, pady=2)
        tk.Label(self.frame_event_convert_right, text="曲线drag", width=11, anchor="w").grid(
            row=3, column=2, sticky="w", padx=2, pady=2)

        # 音符间隔（输入框，仅曲线drag不为“无”时出现）
        self.frame_drag_interval = tk.Frame(self.frame_event_convert_right)
        self.frame_drag_interval.grid(row=4, column=0, columnspan=3, sticky="w", padx=2, pady=2)
        self.drag_interval_var = tk.StringVar(value="16")
        tk.Entry(self.frame_drag_interval, textvariable=self.drag_interval_var, width=8).pack(side=tk.LEFT, padx=2)
        tk.Label(self.frame_drag_interval, text="→", width=3, anchor="center").pack(side=tk.LEFT, padx=1)
        tk.Label(self.frame_drag_interval, text="音符间隔（分音）", width=11, anchor="w").pack(side=tk.LEFT, padx=2)
        self.frame_drag_interval.grid_remove()
        self.drag_mode_var.trace_add("write", lambda *_: self._toggle_drag_interval())

    def _toggle_drag_interval(self):
        if self.drag_mode_var.get() != "无":
            self.frame_drag_interval.grid()
        else:
            self.frame_drag_interval.grid_remove()

    def _toggle_legacy_tint(self):
        if self.color_mode_var.get() == "不透明度替代亮度":
            self.legacy_tint_check.pack_forget()
        else:
            self.legacy_tint_check.pack(side=tk.LEFT, padx=5)

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
            self.frame_image_size_options.pack(side=tk.LEFT, padx=5)

    def _toggle_image_width_fields(self):
        if self.auto_adjust_width_var.get():
            self.frame_image_width_options.pack_forget()
        else:
            self.frame_image_width_options.pack(side=tk.LEFT, padx=5)

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
            title="选择图片",
            filetypes=[("图片文件", "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp"), ("所有文件", "*.*")]
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
        path = filedialog.askopenfilename(title="选择 MIDI", filetypes=[("MIDI 文件", "*.mid;*.midi"), ("所有文件", "*.*")])
        if path:
            self.midi_path_var.set(path)

    def on_image_drop(self, event):
        data = event.data or ""
        if data.startswith("{") and data.endswith("}"):
            data = data[1:-1]
        path = data.strip().strip("{}")
        if path:
            self.image_path_var.set(path)
        return "break"

    def on_function_change(self, *args):
        label = self.current_function.get()
        func_data = self.functions.get(label, (None, ""))
        desc = func_data[1]
        self.desc_label.config(text=desc)

        func_key = func_data[0]
        if func_key in ["nonlinear_split", "polar_conversion", "event_type_convert", "image_to_notes", "hold_notes_connect", "time_interval_to_yoffset", "reverse_data", "midi_bpm_extract"]:
            self.frame_extra.pack(fill=tk.X, padx=10, pady=5)
        else:
            self.frame_extra.pack_forget()

        if func_key in ["nonlinear_split", "polar_conversion"]:
            self.frame_density.pack(fill=tk.X, padx=5, pady=2)
        else:
            self.frame_density.pack_forget()

        if func_key == "hold_notes_connect":
            self.frame_hold_options.pack(fill=tk.X, padx=5, pady=2)
        else:
            self.frame_hold_options.pack_forget()

        if func_key == "event_type_convert":
            self.frame_event_convert.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.frame_event_convert.pack_forget()

        if func_key == "image_to_notes":
            self.frame_image_settings.pack(fill=tk.X, padx=5, pady=5)
            self._toggle_image_size_fields()
            self._toggle_image_width_fields()
        else:
            self.frame_image_settings.pack_forget()

        if func_key == "time_interval_to_yoffset":
            self.frame_time_offset_settings.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.frame_time_offset_settings.pack_forget()

        if func_key == "midi_bpm_extract":
            self.frame_midi_settings.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.frame_midi_settings.pack_forget()

        if func_key == "reverse_data":
            self.frame_stretch_settings.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.frame_stretch_settings.pack_forget()

        # 图片转音符画 / MIDI BPM 提取：无需显示“输入JSON”及其输入框
        if func_key in ["image_to_notes", "midi_bpm_extract"]:
            self.input_frame.pack_forget()
        else:
            self.input_frame.pack(fill=tk.BOTH, expand=True, padx=10, before=self.frame_btn)

    def get_input_data(self):
        try:
            raw = self.text_input.get("1.0", tk.END).strip()
            if not raw:
                raise ValueError("输入为空")
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise Exception(f"JSON格式错误: {str(e)}")

    def set_output_data(self, data):
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, json.dumps(data, indent=3, ensure_ascii=False))

    def show_error(self, msg):
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, f"【错误】: {msg}")
        self.text_output.config(fg="red")
        # 恢复颜色以便下次正常输出
        self.root.after(3000, lambda: self.text_output.config(fg="black"))

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
                raise Exception("未知功能")

            self.set_output_data(result)
            return True

        except Exception as e:
            self.show_error(str(e))
            return False

    def clear_io(self):
        self.text_input.delete("1.0", tk.END)
        self.text_output.delete("1.0", tk.END)

    def _get_event_type_number(self, label):
        for name, value in self.event_type_options:
            if name == label:
                return value
        return None

    def _get_event_type_label(self, value):
        for name, v in self.event_type_options:
            if v == value:
                return name
        return str(value)

    def copy_result(self):
        content = self.text_output.get("1.0", tk.END).strip()
        if content and not content.startswith("【错误】"):
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
        else:
            messagebox.showwarning("提示", "没有有效结果可复制")
