# -*- coding: utf-8 -*-
"""8 个功能的实现（原 RPET.py 中所有 func_* 与相关私有辅助方法）。

大段实现说明/推导注释已移至 Other File/大段注释整理.md，此处仅保留结论性注释。
"""

import copy
import math
import os

from . import i18n
from .easing import EasingMixin
from .i18n import t
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
            raise Exception(t("errors.speed_bpm_number"))
        if bpm <= 0:
            raise Exception(t("errors.bpm_positive"))

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

        data["notes"] = converted
        return data

    # ------------------------------------------------------------------
    # 功能 4: 事件类型转换
    # ------------------------------------------------------------------
    def func_event_type_convert(self, data):
        events = data.get("events", [])
        if not events:
            return data

        # 1. 常规行（输入选择框 → 文字）：按行把源类型转换为目标类型
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

        # 2. 定轨hold：把事件当作五/七列 hold
        notes = []
        hold_mode = i18n.option_key("hold_mode", self.hold_mode_var.get())
        if hold_mode in ("5k", "7k"):
            k = 5 if hold_mode == "5k" else 7
            notes.extend(self._events_to_hold_notes(converted, k))

        # 3. 曲线drag：把位移与缩放按音符间隔转换成一系列 drag
        drag_mode = i18n.option_key("drag_mode", self.drag_mode_var.get())
        if drag_mode != "none":
            try:
                density = int(self.drag_interval_var.get())
            except ValueError:
                raise Exception(t("errors.drag_interval_int"))
            if density <= 0:
                raise Exception(t("errors.drag_interval_positive"))
            axis = "x" if drag_mode == "x" else "y"
            notes.extend(self._events_to_drag_notes(converted, axis, density))

        if notes:
            # 相同时间+位置的音符去重（后生成的覆盖先生成的，边界处取后一段事件）
            seen = {}
            for n in notes:
                seen[(tuple(n["startTime"]), n["positionX"])] = n
            result_notes = sorted(
                seen.values(),
                key=lambda n: (self.time_to_float(n["startTime"]), n["positionX"]),
            )
            return {"notes": result_notes}

        data["events"] = converted
        return data

    def _make_base_note(self, type, positionX, startTime, endTime=None, size=1.0, judgeArea=None):
        """生成统一格式的 note（与图片转音符画输出格式一致）。"""
        return {
            "above": 1,
            "alpha": 255,
            "endTime": copy.deepcopy(endTime) if endTime is not None else copy.deepcopy(startTime),
            "isFake": 0,
            "judgeArea": judgeArea if judgeArea is not None else size,
            "line": 0,
            "positionX": positionX,
            "size": size,
            "speed": 1.0,
            "startTime": copy.deepcopy(startTime),
            "tint": [255, 255, 255],
            "type": type,
            "visibleTime": 999999.0,
            "yOffset": 0.0,
        }

    def _events_to_hold_notes(self, events, k):
        """定轨hold：事件类型 1..k 分别映射到 k 列固定轨道，生成 hold 音符。
        5k 列位：-540/-270/0/270/540；7k 列位：-578.57/-385.71/-192.86/0/192.86/385.71/578.57。"""
        positions = [round((i - (k - 1) / 2.0) * 1350.0 / k, 2) for i in range(k)]
        notes = []
        for ev in events:
            t = ev.get("type")
            if not isinstance(t, int) or not (1 <= t <= k):
                continue
            start_time = ev.get("startTime", [0, 0, 1])
            end_time = ev.get("endTime", start_time)
            notes.append(self._make_base_note(
                type=2,
                positionX=positions[t - 1],
                startTime=start_time,
                endTime=end_time,
            ))
        return notes

    def _events_to_drag_notes(self, events, axis, density):
        """曲线drag：把位移事件（x→type1 / y→type2）与缩放事件（x→type6 / y→type7）
        按音符间隔采样成一系列 drag 音符；无缩放事件覆盖时 size/judgeArea 取 1.0。"""
        move_type = 1 if axis == "x" else 2
        scale_type = 6 if axis == "x" else 7
        step = 4.0 / density
        if step <= 0:
            step = 0.25

        move_events = [e for e in events if e.get("type") == move_type]
        scale_events = [e for e in events if e.get("type") == scale_type]
        scale_events.sort(key=lambda e: self.time_to_float(e.get("startTime", [0, 0, 1])))

        def scale_at(t):
            # 覆盖 t 的活动缩放事件内插值；否则沿用上一个事件的结束值；再否则 1.0
            active = None
            for e in scale_events:
                s = self.time_to_float(e["startTime"])
                en = self.time_to_float(e.get("endTime", e["startTime"]))
                if s - 1e-9 <= t <= en + 1e-9:
                    active = e
                    break
            if active:
                s = self.time_to_float(active["startTime"])
                en = self.time_to_float(active.get("endTime", active["startTime"]))
                dur = en - s
                if dur < 1e-6:
                    return active.get("end", 1.0)
                p = (t - s) / dur
                return self.interpolate_value(
                    active.get("start", 1.0),
                    active.get("end", 1.0),
                    p,
                    active.get("easingType", 1),
                    active.get("bezier", 0),
                    active.get("bezierPoints", [0.0, 0.0, 0.0, 0.0]),
                )
            prev = None
            for e in scale_events:
                en = self.time_to_float(e.get("endTime", e["startTime"]))
                if en < t - 1e-9:
                    prev = e.get("end", 1.0)
                else:
                    break
            return prev if prev is not None else 1.0

        notes = []
        for ev in move_events:
            t0 = self.time_to_float(ev.get("startTime", [0, 0, 1]))
            t1 = self.time_to_float(ev.get("endTime", ev.get("startTime", [0, 0, 1])))
            start_val = ev.get("start", 0.0)
            end_val = ev.get("end", start_val)

            if t1 <= t0 + 1e-9:
                size = round(max(0.05, scale_at(t0)), 4)
                notes.append(self._make_base_note(
                    type=4,
                    positionX=start_val,
                    startTime=self.float_to_time(t0),
                    size=size,
                ))
                continue

            t = t0
            while t <= t1 + 1e-6:
                p = (t - t0) / (t1 - t0)
                val = self.interpolate_value(
                    start_val, end_val, p,
                    ev.get("easingType", 1),
                    ev.get("bezier", 0),
                    ev.get("bezierPoints", [0.0, 0.0, 0.0, 0.0]),
                )
                size = round(max(0.05, scale_at(t)), 4)
                notes.append(self._make_base_note(
                    type=4,
                    positionX=val,
                    startTime=self.float_to_time(t),
                    size=size,
                ))
                t += step
        return notes

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
            raise Exception(t("errors.pixel_size_int"))

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
            raise Exception(t("errors.pillow_missing"))

        image_path = self.image_path_var.get().strip()
        if not image_path or not os.path.exists(image_path):
            raise Exception(t("errors.image_invalid"))

        note_type = i18n.option_key("note_type", self.note_type_var.get())
        color_mode = i18n.option_key("color_mode", self.color_mode_var.get())
        density = int(self.density_var.get()) if self.density_var.get().strip() else 16
        if density <= 0:
            raise Exception(t("errors.density_positive"))

        try:
            with Image.open(image_path) as src_img:
                img = src_img.convert("RGBA")
        except Exception as e:
            raise Exception(t("errors.image_read_failed", err=e))

        resample = getattr(Image, "Resampling", Image).LANCZOS

        if self.flip_horizontal_var.get():
            img = ImageOps.mirror(img)
        # 上下翻转（默认否，但以其反义生成）：未勾选时按翻转后生成（底部行 → 最早时间）
        if not self.flip_vertical_var.get():
            img = ImageOps.flip(img)

        rotation_angle = i18n.option_int_key("rotation", self.rotation_var.get())
        if rotation_angle is None:
            raise Exception(t("errors.rotation_invalid"))
        if rotation_angle % 360 != 0:
            img = img.rotate(rotation_angle, resample=resample, expand=True)

        target_w, target_h = self._resolve_image_target_size(img)
        if not self.use_original_size_var.get():
            img = img.resize((target_w, target_h), resample)

        pixels = list(img.getdata())
        notes = []
        note_type_map = {"tap": 1, "drag": 4, "flick": 2, "hold": 2}
        note_type_value = note_type_map.get(note_type, 1)

        width = img.width
        height = img.height
        if width <= 0 or height <= 0:
            raise Exception(t("errors.image_size_invalid"))

        try:
            note_width = float(self.note_width_var.get())
        except ValueError:
            raise Exception(t("errors.note_width_number"))

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
                    color = self._corrected_color_from_rgb(r, g, b)
                else:
                    color = [r, g, b]

                if width <= 1:
                    pos_x = 0.0
                elif self.auto_adjust_width_var.get():
                    pos_x = -675.0 + (x + 0.5) * step_x
                else:
                    pos_x = -675.0 + half_nw + x * step_x
                start_beat = y * step_beat
                end_beat = start_beat + step_beat

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
        key = i18n.option_key("note_type", self.note_type_var.get())
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

    # ------------------------------------------------------------------
    # 功能 7: 倒序 / 拉伸
    # ------------------------------------------------------------------
    def func_reverse_data(self, data):
        # 倒序/拉伸：t'[i] = t[0] + (t[i] - t[0]) * r
        # 保持第一个事件的开始时间与输入一致，不反转顺序
        try:
            ratio = float(self.stretch_ratio_var.get())
        except ValueError:
            raise Exception(t("errors.stretch_ratio_number"))

        if ratio == 0:
            raise Exception(t("errors.stretch_ratio_zero"))

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
                raise Exception(t("errors.midi_incomplete"))
            byte = data[offset]
            offset += 1
            value = (value << 7) | (byte & 0x7F)
            if byte < 0x80:
                break
        return value, offset

    def func_extract_midi_bpm(self, data):
        midi_path = self.midi_path_var.get().strip()
        if not midi_path or not os.path.exists(midi_path):
            raise Exception(t("errors.midi_invalid"))

        with open(midi_path, "rb") as fh:
            raw = fh.read()

        if raw[:4] != b"MThd":
            raise Exception(t("errors.midi_not_standard"))

        if len(raw) < 14:
            raise Exception(t("errors.midi_too_short"))

        division = int.from_bytes(raw[12:14], byteorder="big", signed=True)
        if division == 0:
            raise Exception(t("errors.midi_resolution_invalid"))

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
                        raise Exception(t("errors.midi_running_status_missing"))
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
                elif event_status < 0xF0:
                    # 普通通道消息（0x80~0xEF）：仅跳过数据字节（C0/D0 一个，其余两个）
                    cursor += 1
                    if event_status not in (0xC0, 0xD0):
                        cursor += 1

        if not bpm_changes:
            raise Exception(t("errors.midi_no_bpm"))

        # 需求九：输出格式为 BPMList（bpm + startTime），无需 midiPath
        return {"BPMList": bpm_changes}

    # ------------------------------------------------------------------
    # 功能 1: hold / 事件首尾相接
    # ------------------------------------------------------------------
    def func_hold_connect(self, data):
        distinguish = self.distinguish_track_var.get()
        allow_shorten = self.allow_shorten_var.get()

        if "notes" in data and data.get("notes"):
            notes = copy.deepcopy(data["notes"])
            if distinguish:
                # 区分轨道：按 x 坐标差距 < 175 分组，组内仅对 x 差距 < 175 的前后相邻 hold 首尾相接
                groups = self._group_notes_by_track(notes)
                for group in groups:
                    self._connect_group_notes(group, allow_shorten)
            else:
                # 不区分轨道：按唯一开始时间连接
                unique_start_times = sorted(set(self.time_to_float(n["startTime"]) for n in notes))
                for note in notes:
                    if note.get("type") != 2:
                        continue
                    current_start = self.time_to_float(note["startTime"])
                    current_end = self.time_to_float(note.get("endTime", note["startTime"]))
                    next_start_time_val = self._next_unique_time(unique_start_times, current_start)
                    if next_start_time_val is None:
                        continue
                    if allow_shorten or next_start_time_val > current_end + 1e-9:
                        note["endTime"] = self.float_to_time(next_start_time_val)
                    elif next_start_time_val < current_end - 1e-9:
                        # 不允许缩短：本会被缩短的长条改为从其结束时间起
                        # 寻找下一个音符开始时间来延长；找不到则保持原样
                        extend_time = self._next_unique_time(unique_start_times, current_end)
                        if extend_time is not None:
                            note["endTime"] = self.float_to_time(extend_time)
                    # next_start ≈ current_end：已首尾相接，保持不变
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
                    self._connect_group_events(group, allow_shorten)
            else:
                # 不区分轨道：按唯一开始时间连接
                unique_start_times = sorted(set(self.time_to_float(e["startTime"]) for e in events))
                for ev in events:
                    current_start = self.time_to_float(ev["startTime"])
                    current_end = self.time_to_float(ev.get("endTime", ev["startTime"]))
                    next_start_time_val = self._next_unique_time(unique_start_times, current_start)
                    if next_start_time_val is None:
                        continue
                    if allow_shorten or next_start_time_val > current_end + 1e-9:
                        ev["endTime"] = self.float_to_time(next_start_time_val)
                    elif next_start_time_val < current_end - 1e-9:
                        # 不允许缩短：本会被缩短的事件改为从其结束时间起延长
                        extend_time = self._next_unique_time(unique_start_times, current_end)
                        if extend_time is not None:
                            ev["endTime"] = self.float_to_time(extend_time)
                    # next_start ≈ current_end：已首尾相接，保持不变
            data["events"] = events
            return data

        return data

    @staticmethod
    def _next_unique_time(sorted_times, after_t):
        """返回 sorted_times 中第一个严格晚于 after_t（留 1e-9 容差）的时间，没有则 None"""
        for t in sorted_times:
            if t > after_t + 1e-9:
                return t
        return None

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

    def _connect_group_notes(self, group, allow_shorten=True):
        """组内 hold 按时间排序，仅当下一根 hold 的 x 坐标差距 < 175 时首尾相接；
        相同开始时间的 hold（双押）共同参考下一个不同开始时间。
        不允许缩短时，本会被缩短的 hold 改为从其结束时间起寻找下一个满足轨道条件的开始时间。"""
        group.sort(key=lambda n: self.time_to_float(n["startTime"]))
        unique_times = sorted(set(self.time_to_float(n["startTime"]) for n in group))
        for note in group:
            cur_t = self.time_to_float(note["startTime"])
            cur_x = note.get("positionX", 0.0)
            cur_end = self.time_to_float(note.get("endTime", note["startTime"]))
            next_time = self._next_unique_time(unique_times, cur_t)
            if next_time is None:
                continue
            candidates = [n for n in group
                          if abs(self.time_to_float(n["startTime"]) - next_time) < 1e-9
                          and abs(n.get("positionX", 0.0) - cur_x) < 175]
            if not candidates:
                continue
            if allow_shorten or next_time > cur_end + 1e-9:
                note["endTime"] = copy.deepcopy(candidates[0]["startTime"])
            elif next_time < cur_end - 1e-9:
                # 不允许缩短：从结束时间起寻找下一个满足轨道条件的开始时间来延长
                extend_time = self._next_unique_time(unique_times, cur_end)
                if extend_time is not None:
                    ext_candidates = [n for n in group
                                      if abs(self.time_to_float(n["startTime"]) - extend_time) < 1e-9
                                      and abs(n.get("positionX", 0.0) - cur_x) < 175]
                    if ext_candidates:
                        note["endTime"] = copy.deepcopy(ext_candidates[0]["startTime"])
            # next_time ≈ cur_end：已首尾相接，保持不变
        # 最后一个（或后续无满足条件的）保持原样

    def _connect_group_events(self, group, allow_shorten=True):
        """组内事件按时间排序，首尾相接（endTime = 下一个不同 startTime）。
        不允许缩短时，本会被缩短的事件改为从其结束时间起寻找下一个开始时间。"""
        group.sort(key=lambda e: self.time_to_float(e["startTime"]))
        unique_times = sorted(set(self.time_to_float(e["startTime"]) for e in group))
        for ev in group:
            cur_t = self.time_to_float(ev["startTime"])
            cur_end = self.time_to_float(ev.get("endTime", ev["startTime"]))
            next_time = self._next_unique_time(unique_times, cur_t)
            if next_time is None:
                continue
            if allow_shorten or next_time > cur_end + 1e-9:
                ev["endTime"] = copy.deepcopy(self.float_to_time(next_time))
            elif next_time < cur_end - 1e-9:
                # 不允许缩短：从结束时间起寻找下一个开始时间来延长
                extend_time = self._next_unique_time(unique_times, cur_end)
                if extend_time is not None:
                    ev["endTime"] = copy.deepcopy(self.float_to_time(extend_time))
            # next_time ≈ cur_end：已首尾相接，保持不变
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
                # 需求十一：三次贝塞尔改为按数学公式（de Casteljau 细分）推导每一小段的控制点
                if bezier_flag == 1 and isinstance(bezier_points, list) and len(bezier_points) == 4:
                    sub_points = self._subdivide_bezier(
                        bezier_points[0], bezier_points[1],
                        bezier_points[2], bezier_points[3],
                        seg_progress_start, seg_progress_end,
                    )
                    if sub_points is not None:
                        new_ev["bezierPoints"] = sub_points
                # 保留原 easingType（与需求示例输出一致）
                new_events.append(new_ev)
                current_t = next_t

        data["events"] = new_events
        return data

    # ------------------------------------------------------------------
    # 功能 3: 旋转事件与距离生成普通事件（极坐标转换）
    #   X/Y 事件按密度切割成线性段并换算为绝对坐标；旋转事件原样复制输入，不参与切割
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

        # 按密度生成时间轴，并合并所有事件的边界时刻（跳变时刻必须被精确采样）
        step = 4.0 / density
        if step <= 0:
            step = 0.25

        grid_times = []
        current_t = min_t
        while current_t <= max_t + 1e-6:
            grid_times.append(current_t)
            current_t += step

        timeline = sorted(t for t in (set(grid_times) | all_times)
                          if min_t - 1e-9 <= t <= max_t + 1e-9)

        # 按 type 预分组，避免每次采样都重新过滤/排序
        events_by_type = {}
        for e in events:
            events_by_type.setdefault(e["type"], []).append(e)
        for type_evts in events_by_type.values():
            type_evts.sort(key=lambda x: self.time_to_float(x["startTime"]))

        def _event_value_at(active, t):
            """按 easingLeft/easingRight 窗口计算事件在时刻 t 的值，窗口外钳位到 start/end"""
            s = self.time_to_float(active["startTime"])
            en = self.time_to_float(active["endTime"])
            start_v = active["start"]
            end_v = active["end"]
            dur = en - s
            if dur < 1e-9:
                # 零时长事件视为瞬时跳变
                return end_v
            p = (t - s) / dur
            easing_left = active.get("easingLeft", 0.0)
            easing_right = active.get("easingRight", 1.0)
            if easing_right < easing_left:
                easing_left, easing_right = easing_right, easing_left
            if p <= easing_left:
                return start_v
            if p >= easing_right:
                return end_v
            span = easing_right - easing_left
            if span < 1e-9:
                return end_v
            norm = (p - easing_left) / span
            eased = self.apply_easing(norm, active.get("easingType", 1),
                                      active.get("bezier", 0),
                                      active.get("bezierPoints", [0.0, 0.0, 0.0, 0.0]))
            return start_v + (end_v - start_v) * eased

        def sample(t, target_type, side):
            """取某类型事件在时刻 t 的值；side='right' 取右极限（新开始的事件优先），
            side='left' 取左极限（旧事件优先）。未定义段沿用上个事件结束值，否则用下一个事件起始值。"""
            type_evts = events_by_type.get(target_type)
            if not type_evts:
                return 0.0

            best = None
            best_s = None
            for e in type_evts:
                s = self.time_to_float(e["startTime"])
                en = self.time_to_float(e["endTime"])
                started = s <= t + 1e-9 if side == "right" else s < t - 1e-9
                if started and en >= t - 1e-9:
                    if best is None or s >= best_s:
                        best = e
                        best_s = s
            if best is not None:
                return _event_value_at(best, t)

            prev_val = None
            for e in type_evts:
                if self.time_to_float(e["endTime"]) < t - 1e-9:
                    prev_val = e["end"]
                else:
                    break
            if prev_val is not None:
                return prev_val

            for e in type_evts:
                if self.time_to_float(e["startTime"]) > t + 1e-9:
                    return e["start"]

            return 0.0

        EPS = 1e-6
        temp_events_x = []
        temp_events_y = []
        last_x = None
        last_y = None

        def make_ev(ttype, t0, t1, v0, v1):
            return {
                "type": ttype, "line": 0, "layer": 0, "linkgroup": 0,
                "bezier": 0, "bezierPoints": [0.0, 0.0, 0.0, 0.0],
                "easingType": 1, "easingLeft": 0.0, "easingRight": 1.0,
                "startTime": self.float_to_time(t0), "endTime": self.float_to_time(t1),
                "start": v0, "end": v1,
            }

        def emit(evt_list, v0, v1, last_val, ttype, t0, t1, force=False):
            """输出一个线性段；区间起点相对上一输出发生跳变时也必须输出以锚定新值"""
            changed = abs(v1 - v0) > EPS
            jumped = last_val is not None and abs(v0 - last_val) > EPS
            if not changed and not jumped and not force:
                return last_val
            evt_list.append(make_ev(ttype, t0, t1, v0, v1))
            return v1

        has_xy = 1 in events_by_type or 2 in events_by_type

        # 逐区间输出：区间起点取右极限（跳变后的新值），终点取左极限（跳变前的旧值），
        # 再各自做极坐标换算。输入事件在某时刻数值突变时，输出拆成
        # "上一段以旧值结束 + 下一段以新值开始" 两段，而不是用一段时间做平滑过渡。
        for i in range(len(timeline) - 1):
            t0 = timeline[i]
            t1 = timeline[i + 1]

            x0 = sample(t0, 1, "right"); x1 = sample(t1, 1, "left")
            y0 = sample(t0, 2, "right"); y1 = sample(t1, 2, "left")
            r0 = sample(t0, 3, "right"); r1 = sample(t1, 3, "left")

            d0 = math.sqrt(x0 ** 2 + y0 ** 2)
            d1 = math.sqrt(x1 ** 2 + y1 ** 2)
            v0x = d0 * math.sin(math.radians(r0)); v1x = d1 * math.sin(math.radians(r1))
            v0y = d0 * math.cos(math.radians(r0)); v1y = d1 * math.cos(math.radians(r1))

            # 首个区间强制输出一次，锚定各通道初始值，保证后续任何跳变都有明确的"前值"可对照
            last_x = emit(temp_events_x, v0x, v1x, last_x, 1, t0, t1, force=(i == 0 and has_xy))
            last_y = emit(temp_events_y, v0y, v1y, last_y, 2, t0, t1, force=(i == 0 and has_xy))

        # 旋转事件不切割：直接复制输入的旋转事件（旋转仍参与 r/θ 换算，只是输出保持输入原貌）
        copied_rotations = [copy.deepcopy(e) for e in events if e.get("type") == 3]

        new_events = temp_events_x + temp_events_y + copied_rotations
        data["events"] = new_events
        return data
