# -*- coding: utf-8 -*-
"""模组：图片转音符画

所属功能组：片段处理
MOD_KEY 与 assets/lang/*.json 里 functions[].key 对应；序号由主程序加载时决定，本文件不写序号。
"""

import os

from rpe_toolbox.imglib import Image, ImageOps

from rpe_toolbox import i18n
from rpe_toolbox.i18n import t

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from rpe_toolbox import i18n
from rpe_toolbox.i18n import t

MOD_KEY = "image_to_notes"
MOD_ORDER = 50

def process(app, data):
    if Image is None:
        raise Exception(t("errors.pillow_missing"))

    image_path = app.image_path_var.get().strip()
    if not image_path or not os.path.exists(image_path):
        raise Exception(t("errors.image_invalid"))

    note_type = i18n.option_key("note_type", app.note_type_var.get())
    color_mode = i18n.option_key("color_mode", app.color_mode_var.get())
    density = int(app.density_var.get()) if app.density_var.get().strip() else 16
    if density <= 0:
        raise Exception(t("errors.density_positive"))

    try:
        with Image.open(image_path) as src_img:
            img = src_img.convert("RGBA")
    except Exception as e:
        raise Exception(t("errors.image_read_failed", err=e))

    resample = getattr(Image, "Resampling", Image).LANCZOS

    if app.flip_horizontal_var.get():
        img = ImageOps.mirror(img)
    # 上下翻转（默认否，但以其反义生成）：未勾选时按翻转后生成（底部行 → 最早时间）
    if not app.flip_vertical_var.get():
        img = ImageOps.flip(img)

    rotation_angle = i18n.option_int_key("rotation", app.rotation_var.get())
    if rotation_angle is None:
        raise Exception(t("errors.rotation_invalid"))
    if rotation_angle % 360 != 0:
        img = img.rotate(rotation_angle, resample=resample, expand=True)

    target_w, target_h = _resolve_image_target_size(app, img)
    if not app.use_original_size_var.get():
        img = img.resize((target_w, target_h), resample)

    pixels = list(img.getdata())
    notes = []
    # RPE 音符类型：1=tap 2=hold 3=flick 4=drag
    # （与「hold/事件首尾相接」按 type==2 判定 hold 的约定一致）
    note_type_map = {"tap": 1, "hold": 2, "flick": 3, "drag": 4}
    note_type_value = note_type_map.get(note_type, 1)

    width = img.width
    height = img.height
    if width <= 0 or height <= 0:
        raise Exception(t("errors.image_size_invalid"))

    try:
        note_width = float(app.note_width_var.get())
    except ValueError:
        raise Exception(t("errors.note_width_number"))

    if app.auto_adjust_width_var.get():
        # 自动调整音符宽度：音符均匀铺满整个屏幕（1350 宽），并同步调整音符 size
        step_x = 1350.0 / max(width, 1) if width > 1 else 0.0
        half_nw = 0.0
        note_size = max(0.05, step_x / 175.0) if step_x > 0 else 1.0
    else:
        # 不调整音符宽度：外圈音符内缩半个音符宽度，均匀分布；size = 音符宽度 / 175
        nw = max(note_width, 1.0)
        half_nw = nw / 2.0
        step_x = (1350.0 - nw) / max(width - 1, 1) if width > 1 else 0.0
        note_size = nw / 175.0

    # 需求十一：每行间隔 = 音符间隔（16分音 → 1/4 拍），不按行数等比压缩
    step_beat = 4.0 / density
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[y * width + x]
            if a <= 0:
                continue

            # 需求十：透明度写入音符 alpha（所有颜色模式均保留图片透明度；0 透明度已在上方跳过）
            alpha = a
            if color_mode == "alpha_as_luma":
                color = [255, 255, 255]
            elif color_mode == "corrected_tint":
                color = _corrected_color_from_rgb(app, r, g, b)
            else:
                color = [r, g, b]

            if width <= 1:
                pos_x = 0.0
            elif app.auto_adjust_width_var.get():
                pos_x = -675.0 + (x + 0.5) * step_x
            else:
                pos_x = -675.0 + half_nw + x * step_x
            start_beat = y * step_beat
            end_beat = start_beat + step_beat

            color_key = "color" if app.legacy_tint_var.get() else "tint"
            note = {
                "above": 1,
                "alpha": alpha,
                color_key: color,
                "endTime": app.float_to_time(end_beat),
                "isFake": 0,
                "judgeArea": 1.0,
                "line": 0,
                "positionX": round(pos_x, 4),
                "size": round(note_size, 4),
                "speed": 1.0,
                "startTime": app.float_to_time(start_beat),
                "type": note_type_value,
                "visibleTime": 999999.0,
                "yOffset": 0.0,
            }
            notes.append(note)

    return {"notes": notes}


def _resolve_image_target_size(app, img):
    source_ratio = app.image_ratio or (img.width / max(img.height, 1))
    if app.use_original_size_var.get():
        return img.width, img.height

    try:
        target_w = int(app.pixel_width_var.get())
        target_h = int(app.pixel_height_var.get())
    except ValueError:
        raise Exception(t("errors.pixel_size_int"))

    if target_w <= 0 and target_h <= 0:
        target_w, target_h = 65, 65
    elif target_w <= 0:
        target_w = max(1, int(round(target_h * source_ratio)))
    elif target_h <= 0:
        target_h = max(1, int(round(target_w / source_ratio)))
    elif app.lock_aspect_var.get() and source_ratio > 0:
        if abs(target_w / max(target_h, 1) - source_ratio) > 1e-6:
            if abs(target_w - target_h * source_ratio) < abs(target_h - target_w / source_ratio):
                target_h = max(1, int(round(target_w / source_ratio)))
            else:
                target_w = max(1, int(round(target_h * source_ratio)))

    return max(1, target_w), max(1, target_h)


def _corrected_color_from_rgb(app, r, g, b):
    base_colors = {
        "tap": [10, 195, 255],
        "drag": [240, 237, 105],
        "flick": [254, 67, 101],
        "hold": [154, 232, 253],
    }
    key = i18n.option_key("note_type", app.note_type_var.get())
    fixed = base_colors.get(key, [255, 255, 255])
    # 需求十二：反推最接近结果的 tint（见 Other File/染色矫正.py）。
    # 游戏渲染 = 正片叠底(固定色, tint)；目标是让渲染结果最接近原图像素色。
    inferred = []
    target = (r, g, b)
    for i in range(3):
        f = fixed[i]
        t = target[i]
        if f == 0:
            inferred.append(255)
        elif t >= f:
            inferred.append(255)
        else:
            inferred.append(min(255, max(0, round(t * 255 / f))))
    return inferred


def build_options(app, parent):
    """在标签页里创建本功能的选项控件（由主程序在加载模组时调用）。"""
    # 功能 5：图片转音符画（5 行布局）
    app.frame_image_settings = ttk.Frame(app.tab_frames["image_to_notes"])
    app.frame_image_settings.pack(fill=tk.X, pady=app.px(2))

    row_path = ttk.Frame(app.frame_image_settings)
    row_path.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row_path, text=t("labels.image_path")).pack(side=tk.LEFT, padx=app.px(5))
    app.image_path_var = tk.StringVar()
    app.entry_image_path = ttk.Entry(row_path, textvariable=app.image_path_var, width=55)
    app.entry_image_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=app.px(5))
    # 回调指向本模组的模块级函数：select_image_file 只是本文件里的函数，app 上没有同名方法
    app.btn_select_image = ttk.Button(row_path, text=t("buttons.browse_image"),
                                      command=lambda: select_image_file(app))
    app.btn_select_image.pack(side=tk.LEFT, padx=app.px(5))

    # 第二行：音符类型 颜色处理 旧版染色标签
    row_type_color = ttk.Frame(app.frame_image_settings)
    row_type_color.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row_type_color, text=t("labels.note_type")).pack(side=tk.LEFT, padx=app.px(5))
    app.note_type_var = tk.StringVar(value=i18n.option_display("note_type", "drag"))
    app.note_type_combo = ttk.Combobox(row_type_color, textvariable=app.note_type_var, values=i18n.option_values("note_type"), state="readonly", width=10)
    app.note_type_combo.pack(side=tk.LEFT, padx=app.px(5))

    ttk.Label(row_type_color, text=t("labels.color_mode")).pack(side=tk.LEFT, padx=app.px(5))
    app.color_mode_var = tk.StringVar(value=i18n.option_display("color_mode", "tint"))
    app.color_mode_combo = ttk.Combobox(row_type_color, textvariable=app.color_mode_var, values=i18n.option_values("color_mode"), state="readonly", width=14)
    app.color_mode_combo.pack(side=tk.LEFT, padx=app.px(5))

    app.legacy_tint_var = tk.BooleanVar(value=False)
    app.legacy_tint_check = ttk.Checkbutton(row_type_color, text=t("labels.legacy_tint"), variable=app.legacy_tint_var)
    app.legacy_tint_check.pack(side=tk.LEFT, padx=app.px(5))
    # 需求十二：颜色处理为“不透明度替代亮度”时隐藏旧版染色标签
    app.color_mode_var.trace_add("write", lambda *_: _toggle_legacy_tint(app, ))
    _toggle_legacy_tint(app, )

    # 第三行：音符间隔（分音） 左右翻转 上下翻转 旋转度数
    row_opt3 = ttk.Frame(app.frame_image_settings)
    row_opt3.pack(fill=tk.X, pady=app.px(2))
    ttk.Label(row_opt3, text=t("labels.note_interval")).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Entry(row_opt3, textvariable=app.density_var, width=10).pack(side=tk.LEFT, padx=app.px(5))
    app.flip_horizontal_var = tk.BooleanVar(value=False)
    app.flip_vertical_var = tk.BooleanVar(value=False)
    app.flip_horizontal_check = ttk.Checkbutton(row_opt3, text=t("labels.flip_horizontal"), variable=app.flip_horizontal_var)
    app.flip_horizontal_check.pack(side=tk.LEFT, padx=app.px(5))
    app.flip_vertical_check = ttk.Checkbutton(row_opt3, text=t("labels.flip_vertical"), variable=app.flip_vertical_var)
    app.flip_vertical_check.pack(side=tk.LEFT, padx=app.px(5))
    ttk.Label(row_opt3, text=t("labels.rotation")).pack(side=tk.LEFT, padx=app.px(5))
    app.rotation_combo = ttk.Combobox(row_opt3, textvariable=app.rotation_var, values=i18n.option_values("rotation"), state="readonly", width=8)
    app.rotation_combo.pack(side=tk.LEFT, padx=app.px(5))

    # 第四行：是否使用原图片大小 (x像素数 y像素数 锁定宽高比)
    row_size = ttk.Frame(app.frame_image_settings)
    row_size.pack(fill=tk.X, pady=app.px(2))
    app.use_original_size_var = tk.BooleanVar(value=False)
    app.use_original_size_check = ttk.Checkbutton(row_size, text=t("labels.use_original_size"), variable=app.use_original_size_var)
    app.use_original_size_check.pack(side=tk.LEFT, padx=app.px(5))
    app.use_original_size_var.trace_add("write", lambda *_: _toggle_image_size_fields(app, ))

    app.frame_image_size_options = ttk.Frame(row_size)
    app.frame_image_size_options.pack(side=tk.LEFT, padx=app.px(5))
    ttk.Label(app.frame_image_size_options, text=t("labels.pixel_width")).pack(side=tk.LEFT, padx=app.px(5))
    app.pixel_width_var = tk.StringVar(value="65")
    app.pixel_width_var.trace_add("write", lambda *_: _sync_image_dimension(app, "x"))
    ttk.Entry(app.frame_image_size_options, textvariable=app.pixel_width_var, width=8).pack(side=tk.LEFT, padx=app.px(5))
    ttk.Label(app.frame_image_size_options, text=t("labels.pixel_height")).pack(side=tk.LEFT, padx=app.px(5))
    app.pixel_height_var = tk.StringVar(value="65")
    app.pixel_height_var.trace_add("write", lambda *_: _sync_image_dimension(app, "y"))
    ttk.Entry(app.frame_image_size_options, textvariable=app.pixel_height_var, width=8).pack(side=tk.LEFT, padx=app.px(5))
    app.lock_aspect_check = ttk.Checkbutton(app.frame_image_size_options, text=t("labels.lock_aspect"), variable=app.lock_aspect_var)
    app.lock_aspect_check.pack(side=tk.LEFT, padx=app.px(5))

    # 第五行：是否自动调整音符宽度 (音符宽度)
    row_width = ttk.Frame(app.frame_image_settings)
    row_width.pack(fill=tk.X, pady=app.px(2))
    app.auto_adjust_width_var = tk.BooleanVar(value=True)
    app.auto_adjust_width_check = ttk.Checkbutton(row_width, text=t("labels.auto_adjust_width"), variable=app.auto_adjust_width_var)
    app.auto_adjust_width_check.pack(side=tk.LEFT, padx=app.px(5))
    app.auto_adjust_width_var.trace_add("write", lambda *_: _toggle_image_width_fields(app, ))

    app.frame_image_width_options = ttk.Frame(row_width)
    app.frame_image_width_options.pack(side=tk.LEFT, padx=app.px(5))
    ttk.Label(app.frame_image_width_options, text=t("labels.note_width")).pack(side=tk.LEFT, padx=app.px(5))
    app.note_width_var = tk.StringVar(value="175")
    ttk.Entry(app.frame_image_width_options, textvariable=app.note_width_var, width=8).pack(side=tk.LEFT, padx=app.px(5))


def _toggle_legacy_tint(app):
    if i18n.option_key("color_mode", app.color_mode_var.get()) == "alpha_as_luma":
        app.legacy_tint_check.pack_forget()
    else:
        app.legacy_tint_check.pack(side=tk.LEFT, padx=app.px(5))


def _toggle_image_size_fields(app):
    if app.use_original_size_var.get():
        app.frame_image_size_options.pack_forget()
    else:
        app.frame_image_size_options.pack(side=tk.LEFT, padx=app.px(5))


def _toggle_image_width_fields(app):
    if app.auto_adjust_width_var.get():
        app.frame_image_width_options.pack_forget()
    else:
        app.frame_image_width_options.pack(side=tk.LEFT, padx=app.px(5))


def _set_image_size_inputs(app, width, height):
    app._syncing_size_vars = True
    try:
        app.pixel_width_var.set(str(int(width)))
        app.pixel_height_var.set(str(int(height)))
    finally:
        app._syncing_size_vars = False


def _sync_image_dimension(app, changed):
    if not app.lock_aspect_var.get() or not app.image_ratio or app._syncing_size_vars:
        return
    try:
        if changed == "x":
            width = float(app.pixel_width_var.get())
            if width <= 0:
                return
            height = width / app.image_ratio
            app._syncing_size_vars = True
            app.pixel_height_var.set(str(int(round(height))))
        else:
            height = float(app.pixel_height_var.get())
            if height <= 0:
                return
            width = height * app.image_ratio
            app._syncing_size_vars = True
            app.pixel_width_var.set(str(int(round(width))))
    except ValueError:
        return
    finally:
        app._syncing_size_vars = False


def select_image_file(app):
    path = filedialog.askopenfilename(
        title=t("dialogs.choose_image_title"),
        filetypes=[(t("dialogs.filter_image"), "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp"), (t("dialogs.filter_all"), "*.*")]
    )
    if not path:
        return
    app.image_path_var.set(path)
    try:
        with Image.open(path) as img:
            orig = img.convert("RGBA")
            app.image_ratio = orig.width / max(orig.height, 1)
            _set_image_size_inputs(app, orig.width, orig.height)
    except Exception:
        app.image_ratio = None
