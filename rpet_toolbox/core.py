# -*- coding: utf-8 -*-
"""8 个功能的实现（原 RPET.py 中所有 func_* 与相关私有辅助方法）。

大段实现说明/推导注释已移至 Other File/大段注释整理.md，此处仅保留结论性注释。
"""

import copy
import math
import os

from .easing import EasingMixin
from .imglib import Image, ImageOps


class FunctionMixin(EasingMixin):
    # ------------------------------------------------------------------
    # 功能 6: 时间间隔转 y 偏移
    # ------------------------------------------------------------------
    def func_time_interval_to_yoffset(self, data):
        notes = data.get("notes", [])
        if not notes:
            return data

        try:
            flow_speed = float(self.time_offset_speed_var.get())
            bpm = float(self.time_offset_bpm_var.get())
        except ValueError:
            raise Exception("流速 / bpm 必须为数字")
        if bpm <= 0:
            raise Exception("bpm 必须大于 0")

        unify_start_time = self.time_offset_unify_var.get()
        first_start = self.time_to_float(notes[0].get("startTime", [0, 0, 1]))
        converted = []

        for idx, note in enumerate(notes):
            new_note = copy.deepcopy(note)
            original_start = self.time_to_float(new_note.get("startTime", [0, 0, 1]))
            if unify_start_time:
                new_note["startTime"] = self.float_to_time(first_start)
            else:
                new_note["startTime"] = new_note.get("startTime", [0, 0, 1])

            if idx == 0:
                new_note["yOffset"] = 0.0
            else:
                delta_beats = original_start - first_start
                delta_seconds = delta_beats * 60.0 / bpm
                y_offset = delta_seconds * flow_speed * 120.0
                new_note["yOffset"] = round(y_offset, 4)

            converted.append(new_note)

        data["notes"] = converted if converted else [copy.deepcopy(notes[0])]
        return data

    # ------------------------------------------------------------------
    # 功能 4: 事件类型转换
    # ------------------------------------------------------------------
    def func_event_type_convert(self, data):
        events = data.get("events", [])
        if not events:
            return data

        converted = []
        for event in events:
            new_event = copy.deepcopy(event)
            original_type = new_event.get("type")
            for idx in range(len(self.event_source_vars)):
                source_label = self.event_source_vars[idx].get()
                target_label = self.event_target_vars[idx].get()
                if source_label == target_label:
                    continue
                source_type = self._get_event_type_number(source_label)
                target_type = self._get_event_type_number(target_label)
                if source_type is not None and target_type is not None and original_type == source_type:
                    new_event["type"] = target_type
                    break
            converted.append(new_event)

        data["events"] = converted
        return data

    # ------------------------------------------------------------------
    # 功能 5: 图片转音符画（辅助：目标尺寸）
    # ------------------------------------------------------------------
    def _resolve_image_target_size(self, img):
        source_ratio = self.image_ratio or (img.width / max(img.height, 1))
        if self.use_original_size_var.get():
            return img.width, img.height

        try:
            target_w = int(self.pixel_width_var.get())
            target_h = int(self.pixel_height_var.get())
        except ValueError:
            raise Exception("x像素数 / y像素数必须为整数")

        if target_w <= 0 and target_h <= 0:
            target_w, target_h = 65, 65
        elif target_w <= 0:
            target_w = max(1, int(round(target_h * source_ratio)))
        elif target_h <= 0:
            target_h = max(1, int(round(target_w / source_ratio)))
        elif self.lock_aspect_var.get() and source_ratio > 0:
            if abs(target_w / max(target_h, 1) - source_ratio) > 1e-6:
                if abs(target_w - target_h * source_ratio) < abs(target_h - target_w / source_ratio):
                    target_h = max(1, int(round(target_w / source_ratio)))
                else:
                    target_w = max(1, int(round(target_h * source_ratio)))

        return max(1, target_w), max(1, target_h)

    def func_image_to_notes(self, data):
        if Image is None:
            raise Exception("缺少 Pillow 依赖，请先安装 pillow")

        image_path = self.image_path_var.get().strip()
        if not image_path or not os.path.exists(image_path):
            raise Exception("请选择有效图片文件")

        note_type = self.note_type_var.get()
        color_mode = self.color_mode_var.get()
        density = int(self.density_var.get()) if self.density_var.get().strip() else 16
        if density <= 0:
            raise Exception("切割密度必须大于 0")

        try:
            with Image.open(image_path) as src_img:
                img = src_img.convert("RGBA")
        except Exception as e:
            raise Exception(f"无法读取图片: {e}")

        resample = getattr(Image, "Resampling", Image).LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

        if self.flip_horizontal_var.get():
            img = ImageOps.mirror(img)
        # 上下翻转（默认否，但以其反义生成）：未勾选时按翻转后生成（底部行 → 最早时间）
        if not self.flip_vertical_var.get():
            img = ImageOps.flip(img)

        rotation_text = self.rotation_var.get().replace("°", "")
        try:
            rotation_angle = int(rotation_text)
        except ValueError:
            raise Exception("旋转度数必须为 0/90/180/270")
        if rotation_angle % 360 != 0:
            img = img.rotate(rotation_angle, resample=resample, expand=True)

        target_w, target_h = self._resolve_image_target_size(img)
        if not self.use_original_size_var.get():
            img = img.resize((target_w, target_h), resample)
        else:
            target_w, target_h = img.width, img.height

        pixels = list(img.getdata())
        notes = []
        note_type_map = {"tap": 1, "drag": 4, "flick": 2, "hold": 2}
        note_type_value = note_type_map.get(note_type, 1)

        width = img.width
        height = img.height
        if width <= 0 or height <= 0:
            raise Exception("图片尺寸无效")

        try:
            note_width = float(self.note_width_var.get())
        except ValueError:
            raise Exception("音符宽度必须为数字")

        if self.auto_adjust_width_var.get():
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

        total_duration = max(1.0, height * (4.0 / density))
        for y in range(height):
            for x in range(width):
                r, g, b, a = pixels[y * width + x]
                if a <= 0:
                    continue

                if color_mode == "不透明度替代亮度":
                    alpha = int(max(0, min(255, round((a / 255.0) * 255))))
                    color = [255, 255, 255]
                else:
                    alpha = 255
                    if color_mode == "矫正颜色染色":
                        color = self._corrected_color_from_rgb(r, g, b)
                    else:
                        color = [r, g, b]

                if width <= 1:
                    pos_x = 0.0
                elif self.auto_adjust_width_var.get():
                    pos_x = -675.0 + (x + 0.5) * step_x
                else:
                    pos_x = -675.0 + half_nw + x * step_x
                row_ratio = y / max(height - 1, 1)
                start_beat = row_ratio * total_duration
                end_beat = start_beat + (4.0 / density)

                color_key = "color" if self.legacy_tint_var.get() else "tint"
                note = {
                    "above": 1,
                    "alpha": alpha,
                    color_key: color,
                    "endTime": self.float_to_time(end_beat),
                    "isFake": 0,
                    "judgeArea": 1.0,
                    "line": 0,
                    "positionX": round(pos_x, 4),
                    "size": round(note_size, 4),
                    "speed": 1.0,
                    "startTime": self.float_to_time(start_beat),
                    "type": note_type_value,
                    "visibleTime": 999999.0,
                    "yOffset": 0.0,
                }
                notes.append(note)

        return {"notes": notes}

    def _corrected_color_from_rgb(self, r, g, b):
        base_colors = {
            "tap": [10, 195, 255],
            "drag": [240, 237, 105],
            "flick": [254, 67, 101],
            "hold": [154, 232, 253],
        }
        key = self.note_type_var.get()
        target = base_colors.get(key, [255, 255, 255])

        def multiply(a, b):
            return int(round(a * b / 255.0))

        r2 = multiply(r, target[0])
        g2 = multiply(g, target[1])
        b2 = multiply(b, target[2])
        return [r2, g2, b2]

    def _estimate_time_span(self, items):
        values = []
        for item in items:
            for key in ("startTime", "endTime"):
                if key in item:
                    values.append(self.time_to_float(item.get(key, [0, 0, 1])))
        if not values:
            return 0.0
        return max(values)

    # ------------------------------------------------------------------
    # 功能 7: 倒序 / 拉伸
    # ------------------------------------------------------------------
    def func_reverse_data(self, data):
        # 倒序/拉伸：t'[i] = t[0] + (t[i] - t[0]) * r
        # 保持第一个事件的开始时间与输入一致，不反转顺序
        try:
            ratio = float(self.stretch_ratio_var.get())
        except ValueError:
            raise Exception("拉伸比例必须为数字")

        if ratio == 0:
            raise Exception("拉伸比例不能为 0")

        negative = ratio < 0

        if "notes" in data and data.get("notes"):
            notes = copy.deepcopy(data["notes"])
            # 找到第一个（最早）开始时间
            first_start = min(self.time_to_float(n["startTime"]) for n in notes)
            stretched_notes = []
            for note in notes:
                new_note = copy.deepcopy(note)
                for key in ("startTime", "endTime"):
                    if key in new_note:
                        value = self.time_to_float(new_note[key])
                        new_note[key] = self.float_to_time(first_start + (value - first_start) * ratio)
                if negative:
                    if "yOffset" in new_note and isinstance(new_note.get("yOffset"), (int, float)):
                        new_note["yOffset"] = -float(new_note["yOffset"])
                    # 倒序时保证 hold 等音符的 startTime 早于 endTime
                    start_val = self.time_to_float(new_note.get("startTime", [0, 0, 1]))
                    end_val = self.time_to_float(new_note.get("endTime", new_note.get("startTime", [0, 0, 1])))
                    if end_val < start_val:
                        new_note["startTime"], new_note["endTime"] = new_note["endTime"], new_note["startTime"]
                stretched_notes.append(new_note)
            data["notes"] = stretched_notes
            return data

        if "events" in data and data.get("events"):
            events = copy.deepcopy(data["events"])
            first_start = min(self.time_to_float(e["startTime"]) for e in events)
            stretched_events = []
            for event in events:
                new_event = copy.deepcopy(event)
                for key in ("startTime", "endTime"):
                    if key in new_event:
                        value = self.time_to_float(new_event[key])
                        new_event[key] = self.float_to_time(first_start + (value - first_start) * ratio)
                if negative:
                    self._reverse_event_fields(new_event)
                stretched_events.append(new_event)
            data["events"] = stretched_events
            return data

        return data

    def _reverse_event_fields(self, event):
        """倒序拉伸适配：保证事件开始时间早于结束时间，
        并交换 start/end 值、in/out 缓动、缓动起始/结束值（先交换再被 1 减）、贝塞尔属性。"""
        start_val = self.time_to_float(event.get("startTime", [0, 0, 1]))
        end_val = self.time_to_float(event.get("endTime", event.get("startTime", [0, 0, 1])))
        if start_val <= end_val:
            return
        # 交换开始/结束时间
        event["startTime"], event["endTime"] = event["endTime"], event["startTime"]
        # 交换开始/结束值
        if "start" in event and "end" in event:
            event["start"], event["end"] = event["end"], event["start"]
        # in 与 out 缓动交换
        easing_type = event.get("easingType", 1)
        event["easingType"] = {2: 3, 3: 2, 4: 5, 5: 4, 8: 9, 9: 8, 10: 11, 11: 10,
                               14: 15, 15: 14, 16: 17, 17: 16, 18: 19, 19: 18,
                               20: 21, 21: 20, 24: 25, 25: 24, 26: 27, 27: 26}.get(easing_type, easing_type)
        # 缓动起始/结束值先交换再被 1 减
        if "easingLeft" in event and "easingRight" in event:
            left = event.get("easingLeft", 0.0)
            right = event.get("easingRight", 1.0)
            event["easingLeft"] = 1.0 - right
            event["easingRight"] = 1.0 - left
        # 贝塞尔属性适配
        if event.get("bezier") == 1 and isinstance(event.get("bezierPoints"), list) and len(event["bezierPoints"]) == 4:
            x1, y1, x2, y2 = event["bezierPoints"]
            event["bezierPoints"] = [1.0 - x2, 1.0 - y2, 1.0 - x1, 1.0 - y1]

    # ------------------------------------------------------------------
    # 功能 8: MIDI BPM 提取（辅助：可变长整数）
    # ------------------------------------------------------------------
    def _read_var_int(self, data, offset):
        value = 0
        while True:
            if offset >= len(data):
                raise Exception("MIDI 数据不完整")
            byte = data[offset]
            offset += 1
            value = (value << 7) | (byte & 0x7F)
            if byte < 0x80:
                break
        return value, offset

    def func_extract_midi_bpm(self, data):
        midi_path = self.midi_path_var.get().strip()
        if not midi_path or not os.path.exists(midi_path):
            raise Exception("请选择有效 MIDI 文件")

        with open(midi_path, "rb") as fh:
            raw = fh.read()

        if raw[:4] != b"MThd":
            raise Exception("不是标准 MIDI 文件")

        if len(raw) < 14:
            raise Exception("MIDI 文件过短")

        division = int.from_bytes(raw[12:14], byteorder="big", signed=True)
        if division == 0:
            raise Exception("MIDI 分辨率无效")

        offset = 14
        bpm_changes = []
        current_beat = 0.0
        running_status = None

        while offset < len(raw):
            if raw[offset:offset + 4] != b"MTrk":
                break
            track_len = int.from_bytes(raw[offset + 4:offset + 8], byteorder="big")
            track_data = raw[offset + 8:offset + 8 + track_len]
            offset += 8 + track_len

            cursor = 0
            delta = 0
            while cursor < len(track_data):
                delta, cursor = self._read_var_int(track_data, cursor)
                current_beat += delta / max(division, 1)

                if cursor >= len(track_data):
                    break

                status = track_data[cursor]
                if status < 0x80:
                    if running_status is None:
                        raise Exception("MIDI 运行状态缺失")
                    event_status = running_status
                    event_data = status
                else:
                    running_status = status
                    event_status = status
                    cursor += 1
                    if cursor >= len(track_data):
                        break
                    event_data = track_data[cursor]
                    cursor += 1

                if event_status == 0xFF:
                    meta_type = event_data
                    if cursor >= len(track_data):
                        break
                    meta_len, cursor = self._read_var_int(track_data, cursor)
                    meta_bytes = track_data[cursor:cursor + meta_len]
                    cursor += meta_len
                    if meta_type == 0x51 and len(meta_bytes) >= 3:
                        tempo = int.from_bytes(meta_bytes[:3], byteorder="big")
                        bpm = 60000000.0 / tempo
                        bpm_changes.append({
                            "bpm": round(bpm, 3),
                            "startTime": self.float_to_time(current_beat),
                        })
                elif event_status == 0xF0 or event_status == 0xF7:
                    if cursor >= len(track_data):
                        break
                    length, cursor = self._read_var_int(track_data, cursor)
                    cursor += length
                elif event_status == 0xC0 or event_status == 0xD0 or event_status == 0xE0 or event_status == 0x90 or event_status == 0x80 or event_status == 0xA0 or event_status == 0xB0:
                    cursor += 1
                    if event_status != 0xC0 and event_status != 0xD0:
                        cursor += 1

        if not bpm_changes:
            raise Exception("未在 MIDI 中找到 BPM 变化")

        # 需求九：输出格式为 BPMList（bpm + startTime），无需 midiPath
        return {"BPMList": bpm_changes}

    # ------------------------------------------------------------------
    # 功能 1: hold / 事件首尾相接
    # ------------------------------------------------------------------
    def func_hold_connect(self, data):
        distinguish = self.distinguish_track_var.get()

        if "notes" in data and data.get("notes"):
            notes = copy.deepcopy(data["notes"])
            if distinguish:
                # 区分轨道：按 x 坐标差距 < 175 分组，组内仅对 x 差距 < 175 的前后相邻 hold 首尾相接
                groups = self._group_notes_by_track(notes)
                for group in groups:
                    self._connect_group_notes(group)
            else:
                # 不区分轨道：沿用原逻辑（按唯一开始时间连接）
                unique_start_times = sorted(set(self.time_to_float(n["startTime"]) for n in notes))
                for note in notes:
                    if note.get("type") != 2:
                        continue
                    current_start = self.time_to_float(note["startTime"])
                    next_start_time_val = None
                    for t in unique_start_times:
                        if t > current_start:
                            next_start_time_val = t
                            break
                    if next_start_time_val is not None:
                        note["endTime"] = self.float_to_time(next_start_time_val)
            data["notes"] = notes
            return data

        if "events" in data and data.get("events"):
            events = copy.deepcopy(data["events"])
            if distinguish:
                # 区分轨道：按 line 字段分组，组内首尾相接
                groups = {}
                for ev in events:
                    groups.setdefault(ev.get("line", 0), []).append(ev)
                for group in groups.values():
                    self._connect_group_events(group)
            else:
                # 不区分轨道：按唯一开始时间连接
                unique_start_times = sorted(set(self.time_to_float(e["startTime"]) for e in events))
                for ev in events:
                    current_start = self.time_to_float(ev["startTime"])
                    next_start_time_val = None
                    for t in unique_start_times:
                        if t > current_start:
                            next_start_time_val = t
                            break
                    if next_start_time_val is not None:
                        ev["endTime"] = self.float_to_time(next_start_time_val)
            data["events"] = events
            return data

        return data

    def _group_notes_by_track(self, notes):
        """将 hold 音符按 x 坐标差距 < 175 分组（相邻差距 < 175 视为同一轨道）"""
        hold_notes = [n for n in notes if n.get("type") == 2]
        if not hold_notes:
            return []
        # 按 x 坐标排序
        hold_notes.sort(key=lambda n: n.get("positionX", 0.0))
        groups = []
        current_group = [hold_notes[0]]
        for note in hold_notes[1:]:
            prev_x = current_group[-1].get("positionX", 0.0)
            cur_x = note.get("positionX", 0.0)
            if abs(cur_x - prev_x) < 175:
                current_group.append(note)
            else:
                groups.append(current_group)
                current_group = [note]
        groups.append(current_group)
        return groups

    def _connect_group_notes(self, group):
        """组内 hold 按时间排序，仅当下一根 hold 的 x 坐标差距 < 175 时首尾相接；
        相同开始时间的 hold（双押）共同参考下一个不同开始时间。"""
        group.sort(key=lambda n: self.time_to_float(n["startTime"]))
        unique_times = sorted(set(self.time_to_float(n["startTime"]) for n in group))
        for note in group:
            cur_t = self.time_to_float(note["startTime"])
            cur_x = note.get("positionX", 0.0)
            next_time = None
            for t in unique_times:
                if t > cur_t + 1e-9:
                    next_time = t
                    break
            if next_time is None:
                continue
            candidates = [n for n in group
                          if abs(self.time_to_float(n["startTime"]) - next_time) < 1e-9
                          and abs(n.get("positionX", 0.0) - cur_x) < 175]
            if candidates:
                note["endTime"] = copy.deepcopy(candidates[0]["startTime"])
        # 最后一个（或后续无满足条件的）保持原样

    def _connect_group_events(self, group):
        """组内事件按时间排序，首尾相接（endTime = 下一个不同 startTime）"""
        group.sort(key=lambda e: self.time_to_float(e["startTime"]))
        unique_times = sorted(set(self.time_to_float(e["startTime"]) for e in group))
        for ev in group:
            cur_t = self.time_to_float(ev["startTime"])
            for t in unique_times:
                if t > cur_t + 1e-9:
                    ev["endTime"] = copy.deepcopy(self.float_to_time(t))
                    break
        # 最后一个保持原样

    # ------------------------------------------------------------------
    # 功能 2: 非线性切割
    # ------------------------------------------------------------------
    def func_nonlinear_split(self, data, density):
        events = data.get("events", [])
        new_events = []

        for event in events:
            # 获取起始和结束时间
            t_start = self.time_to_float(event["startTime"])
            t_end = self.time_to_float(event["endTime"])

            if t_start >= t_end:
                new_events.append(event)
                continue

            duration = t_end - t_start
            # 分音密度：16分音 = 1/4 拍，故 step = 4 / density（推导见 Other File/大段注释整理.md）
            step = 4.0 / density
            if step <= 0:
                step = 0.25  # fallback

            current_t = t_start
            easing_type = event.get("easingType", 1)
            easing_left = event.get("easingLeft", 0.0)
            easing_right = event.get("easingRight", 1.0)
            bezier_flag = event.get("bezier", 0)
            bezier_points = event.get("bezierPoints", [0.0, 0.0, 0.0, 0.0])

            while current_t < t_end - 1e-6:
                next_t = min(current_t + step, t_end)

                # 在原事件时长内计算每段的进度，并映射到缓动坐标
                seg_progress_start = (current_t - t_start) / duration
                seg_progress_end = (next_t - t_start) / duration

                cur_ease_l = easing_left + (easing_right - easing_left) * seg_progress_start
                cur_ease_r = easing_left + (easing_right - easing_left) * seg_progress_end

                # 按缓动类型或贝塞尔曲线计算段首尾值
                val_start = self.interpolate_value(event["start"], event["end"], seg_progress_start, easing_type, bezier_flag, bezier_points)
                val_end = self.interpolate_value(event["start"], event["end"], seg_progress_end, easing_type, bezier_flag, bezier_points)

                new_ev = copy.deepcopy(event)
                new_ev["startTime"] = self.float_to_time(current_t)
                new_ev["endTime"] = self.float_to_time(next_t)
                new_ev["start"] = val_start
                new_ev["end"] = val_end
                new_ev["easingLeft"] = cur_ease_l
                new_ev["easingRight"] = cur_ease_r
                # 保留原 easingType（与需求示例输出一致）
                new_events.append(new_ev)
                current_t = next_t

        data["events"] = new_events
        return data

    # ------------------------------------------------------------------
    # 功能 3: 旋转事件与距离生成普通事件（极坐标转换）
    # ------------------------------------------------------------------
    def func_polar_conversion(self, data, density):
        events = data.get("events", [])
        if not events:
            return data

        all_times = set()
        for e in events:
            all_times.add(self.time_to_float(e["startTime"]))
            all_times.add(self.time_to_float(e["endTime"]))

        if not all_times:
            return data

        min_t = min(all_times)
        max_t = max(all_times)

        # 按密度生成时间轴
        step = 4.0 / density
        if step <= 0:
            step = 0.25

        current_t = min_t
        timeline = []
        while current_t <= max_t + 1e-6:
            timeline.append(current_t)
            current_t += step

        # 取某 type 在时刻 t 的值：活动事件内插值，未定义段沿用上个事件结束值，否则用下一个事件起始值
        def get_val_at(t, target_type, evts):
            type_evts = [e for e in evts if e["type"] == target_type]
            if not type_evts:
                return 0.0

            type_evts.sort(key=lambda x: self.time_to_float(x["startTime"]))

            active = None
            for e in type_evts:
                s = self.time_to_float(e["startTime"])
                en = self.time_to_float(e["endTime"])
                if s <= t <= en:
                    active = e
                    break

            if active:
                s = self.time_to_float(active["startTime"])
                en = self.time_to_float(active["endTime"])
                dur = en - s
                if dur < 1e-6:
                    return active["start"]
                p = (t - s) / dur
                bezier_flag = active.get("bezier", 0)
                bezier_points = active.get("bezierPoints", [0.0, 0.0, 0.0, 0.0])
                easing_type = active.get("easingType", 1)
                eased = self.apply_easing(p, easing_type, bezier_flag, bezier_points)
                return active["start"] + (active["end"] - active["start"]) * eased

            prev_val = None
            for e in type_evts:
                en = self.time_to_float(e["endTime"])
                if en < t - 1e-6:
                    prev_val = e["end"]
                else:
                    break

            if prev_val is not None:
                return prev_val

            for e in type_evts:
                s = self.time_to_float(e["startTime"])
                if s > t + 1e-6:
                    return e["start"]

            return 0.0

        new_events = []

        # 实现思路：Type1=X、Type2=Y、Type3=旋转；极坐标换算见 Other File/大段注释整理.md
        prev_x = 0.0
        prev_y = 0.0
        prev_rot = 0.0

        temp_events_x = []
        temp_events_y = []
        temp_events_rot = []

        last_x = None
        last_y = None
        last_rot = None

        for t in timeline:
            raw_x = get_val_at(t, 1, events)
            raw_y = get_val_at(t, 2, events)
            raw_rot_deg = get_val_at(t, 3, events)

            # 计算与圆心距离，并根据旋转输出绝对坐标
            dist = math.sqrt(raw_x ** 2 + raw_y ** 2)
            rot_rad = math.radians(raw_rot_deg)
            new_x = dist * math.sin(rot_rad)
            new_y = dist * math.cos(rot_rad)

            if last_x is None:
                last_x = new_x
                last_y = new_y
                last_rot = raw_rot_deg
            else:
                if abs(new_x - last_x) < 1e-6 and abs(new_y - last_y) < 1e-6 and abs(raw_rot_deg - last_rot) < 1e-6:
                    last_x = new_x
                    last_y = new_y
                    last_rot = raw_rot_deg
                    continue

            if t > min_t:
                prev_t = t - step
                ev_x = {
                    "type": 1, "line": 0, "layer": 0, "linkgroup": 0, "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
                    "easingType": 1, "easingLeft": 0.0, "easingRight": 1.0,
                    "startTime": self.float_to_time(prev_t), "endTime": self.float_to_time(t),
                    "start": last_x, "end": new_x
                }
                temp_events_x.append(ev_x)

                ev_y = {
                    "type": 2, "line": 0, "layer": 0, "linkgroup": 0, "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
                    "easingType": 1, "easingLeft": 0.0, "easingRight": 1.0,
                    "startTime": self.float_to_time(prev_t), "endTime": self.float_to_time(t),
                    "start": last_y, "end": new_y
                }
                temp_events_y.append(ev_y)

                ev_r = {
                    "type": 3, "line": 0, "layer": 0, "linkgroup": 0, "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
                    "easingType": 1, "easingLeft": 0.0, "easingRight": 1.0,
                    "startTime": self.float_to_time(prev_t), "endTime": self.float_to_time(t),
                    "start": last_rot, "end": raw_rot_deg
                }
                temp_events_rot.append(ev_r)

            last_x = new_x
            last_y = new_y
            last_rot = raw_rot_deg

        new_events = temp_events_x + temp_events_y + temp_events_rot
        data["events"] = new_events
        return data
