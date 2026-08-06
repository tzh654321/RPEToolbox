# -*- coding: utf-8 -*-
"""RPEToolbox 主类：界面构建、输入输出与功能分发。"""

import json
import os
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
        self.root.geometry("1000x760")
        # 设置窗口图标（PNG 格式，使用 PhotoImage）
        try:
            icon_path = resources.find_icon()
            if icon_path:
                self._window_icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, self._window_icon)
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
            ("速度", 5),
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

        # 构建界面
        self.create_widgets()

        # 绑定事件
        self.current_function.trace_add("write", self.on_function_change)
        self.on_function_change()  # 初始化显示状态

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
                pygame.mixer.init()
                sound = pygame.mixer.Sound(audio_path)
                sound.play()
            except Exception:
                return

        threading.Thread(target=worker, daemon=True).start()

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
            "2. 非线性切割": ("nonlinear_split", "按指定密度切分事件，并保留缓动左右端点和贝塞尔相关信息"),
            "3. 极坐标转换": ("polar_conversion", "将输入的 X/Y/旋转事件组合成极坐标并转换为绝对 X/Y 位置"),
            "4. 事件类型转换": ("event_type_convert", "修改事件 type ，支持常规属性和 X/Y 缩放"),
            "5. 图片转音符画": ("image_to_notes", "使用图片生成音符画，支持 JPG/PNG 导入"),
            "6. 时间间隔转y偏移": ("time_interval_to_yoffset", "把 note 的时间间隔按流速变成 yOffset"),
            "7. 倒序/拉伸": ("reverse_data", "将 notes 或 events 按比例拉伸/压缩时间，负比例表示倒序"),
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
        self.use_original_size_check = tk.Checkbutton(row_size, text="是否使用原图片大小", variable=self.use_original_size_var)
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
        self.auto_adjust_width_check = tk.Checkbutton(row_width, text="是否自动调整音符宽度", variable=self.auto_adjust_width_var)
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

        self.btn_convert = tk.Button(self.frame_btn, text="转换", command=lambda: self._trigger_with_sound("convert"), bg="#4CAF50", fg="white")
        self.btn_convert.pack(side=tk.LEFT, padx=5)

        self.btn_copy = tk.Button(self.frame_btn, text="复制结果", command=lambda: self._trigger_with_sound("copy"))
        self.btn_copy.pack(side=tk.LEFT, padx=5)

        self.btn_clear = tk.Button(self.frame_btn, text="清空输入/输出", command=lambda: self._trigger_with_sound("clear"), bg="#f44336", fg="white")
        self.btn_clear.pack(side=tk.LEFT, padx=5)

        # 5. 文本输出区
        tk.Label(self.root, text="输出JSON:", anchor="w").pack(fill=tk.X, padx=10, pady=(5, 0))
        self.text_output = tk.Text(self.root, height=10, font=self._get_code_font())
        self.text_output.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    def _create_event_convert_rows(self):
        for label, _ in self.event_type_options:
            row = tk.Frame(self.frame_event_convert)
            row.pack(fill=tk.X, padx=5, pady=2)
            tk.Label(row, text=label).pack(side=tk.LEFT, padx=5)

            source_var = tk.StringVar(value=label)
            target_var = tk.StringVar(value=label)
            self.event_source_vars.append(source_var)
            self.event_target_vars.append(target_var)

            source_box = ttk.Combobox(row, textvariable=source_var, values=[name for name, _ in self.event_type_options], state="readonly", width=12)
            source_box.pack(side=tk.LEFT, padx=5)
            tk.Label(row, text="→").pack(side=tk.LEFT, padx=3)
            target_box = ttk.Combobox(row, textvariable=target_var, values=[name for name, _ in self.event_type_options], state="readonly", width=12)
            target_box.pack(side=tk.LEFT, padx=5)

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
