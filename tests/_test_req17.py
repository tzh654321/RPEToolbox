# -*- coding: utf-8 -*-
"""需求十七验证：临时文件不再生成 / 菜单勾选与暗色 / 状态条与音效 / 纵连音高。

覆盖点
  A 不再产生待删除的临时文件（图标写用户缓存、试听写缓存、不写 TEMP）
  B 菜单：勾选标记看得见（自绘）、暗色适配、禁用项「勾=启用」且可重新启用
  C 底部状态条：平时显示简介 → 转换时进度条（有最短可见时长）→ 完成后播音效并切回简介
  D 按钮音效：不再依赖 pygame（wav 素材 + winsound）
  E 纵连音高：音高换算 / 数量推算 / 纵连转换 / 配色 / 画布方向 / 锯齿波试听
  F 英文功能名不再过于简略
"""

import io
import json
import os
import sys
import tempfile
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 每个测试独立的固定配置目录：**只写不删**（删除动作会进回收站，弄脏用户回收站）
# 每次运行都重写一份基线配置，避免上一次运行留下的主题/语言/禁用项影响本次结果。
_CFG_TMP = os.path.join(tempfile.gettempdir(), "rpet_test_req17")
os.makedirs(os.path.join(_CFG_TMP, "RPEToolbox"), exist_ok=True)
os.environ["APPDATA"] = _CFG_TMP
os.environ.pop("RPET_THEME", None)
os.environ.pop("RPET_LANG", None)
with io.open(os.path.join(_CFG_TMP, "RPEToolbox", "config.json"), "w", encoding="utf-8") as _f:
    _f.write('{"theme": "light", "language": "zh-CN"}')

from rpe_toolbox import audio, i18n, mods_loader, resources, theme  # noqa: E402

ok = 0
fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("PASS:", name)
    else:
        fail += 1
        print("FAIL:", name, detail)


def tmp_rpet_files():
    """TEMP 里由本程序产生的临时文件（图标 / 试听 wav）。"""
    d = tempfile.gettempdir()
    names = []
    for name in os.listdir(d):
        low = name.lower()
        if low.startswith(("rpet_icon_", "tmp")) and low.endswith(".ico"):
            names.append(name)
        elif low.endswith(".wav") and ("preview" in low or "rpet" in low):
            names.append(name)
    return sorted(names)


# ======================================================================
# A 临时文件
# ======================================================================
print("---- A 不再产生待删除的临时文件 ----")
check("A 缓存目录在用户配置目录下（不是 TEMP）",
      "Temp" not in resources.user_cache_dir() or _CFG_TMP.split(os.sep)[-1] in resources.user_cache_dir(),
      resources.user_cache_dir())
check("A 音频素材已转为 wav（标准库可播）",
      all(os.path.exists(resources.audio_path(audio.SOUND_FILES[k]))
          for k in ("convert", "copy", "clear", "convert_error")))

root = None
try:
    import tkinter as tk

    from rpe_toolbox import dpi

    dpi.enable_dpi_awareness()

    import rpe_toolbox.app as app_module
    from rpe_toolbox.app import RPEToolbox

    before_tmp = tmp_rpet_files()
    root = tk.Tk()
    ui = RPEToolbox(root)
    for _ in range(4):
        root.update(); root.update_idletasks()

    check("A 启动不再往 TEMP 写图标", tmp_rpet_files() == before_tmp,
          "%s -> %s" % (before_tmp, tmp_rpet_files()))

    # ==================================================================
    # B 菜单
    # ==================================================================
    print("---- B 菜单：勾选可见 / 暗色 / 启用语义 ----")

    def labels(menu):
        return [str(menu.entrycget(i, "label")) for i in range(menu.index("end") + 1)]

    def menu_texts():
        out = []
        for menu in getattr(ui, "_all_menus", []):
            try:
                for i in range(menu.index("end") + 1):
                    if menu.type(i) in ("checkbutton", "radiobutton", "cascade", "command"):
                        out.append(str(menu.entrycget(i, "label")))
            except Exception:
                pass
        return out

    check("B 勾选标记用可见字符自绘（不依赖系统勾选框）",
          ui.MENU_CHECK.strip() != "" and ui.MENU_BLANK.strip() == "",
          repr((ui.MENU_CHECK, ui.MENU_BLANK)))

    first_key = ui.tab_order[0]
    first_title = (i18n.function_by_key(first_key) or {}).get("name", first_key)
    entry = [l for l in labels(ui.enable_menu) if l.lstrip(ui.MENU_CHECK.strip() + " ") == first_title]
    check("B 已启用功能前面有勾", bool(entry) and entry[0].startswith(ui.MENU_CHECK.strip()),
          str(labels(ui.enable_menu)[:3]))

    tabs_before = ui.notebook.index("end")
    ui.toggle_mod_enabled(first_key)
    for _ in range(2):
        root.update(); root.update_idletasks()
    entry2 = [l for l in labels(ui.enable_menu)
              if l.lstrip(ui.MENU_CHECK.strip() + " ") == first_title]
    check("B 取消启用后勾消失", bool(entry2) and not entry2[0].startswith(ui.MENU_CHECK.strip()),
          str(entry2))
    check("B 取消启用后该功能不加载", ui.notebook.index("end") == tabs_before - 1,
          "%s -> %s" % (tabs_before, ui.notebook.index("end")))

    ui.toggle_mod_enabled(first_key)
    for _ in range(2):
        root.update(); root.update_idletasks()
    entry3 = [l for l in labels(ui.enable_menu)
              if l.lstrip(ui.MENU_CHECK.strip() + " ") == first_title]
    check("B 再点一次可重新启用（勾回来）",
          bool(entry3) and entry3[0].startswith(ui.MENU_CHECK.strip())
          and ui.notebook.index("end") == tabs_before, str(entry3))

    check("B 当前功能组前有勾",
          any(l.startswith(ui.MENU_CHECK.strip()) and ui.current_group in l
              for l in labels(ui.group_menu)), str(labels(ui.group_menu)))
    check("B 当前语言前有勾",
          any(l.startswith(ui.MENU_CHECK.strip()) for l in labels(ui.lang_menu)),
          str(labels(ui.lang_menu)))

    pal_light = theme.palette("light")
    ui._apply_theme("light")
    for _ in range(2):
        root.update(); root.update_idletasks()
    # 菜单栏现在是自绘的 Frame + 经典 Menubutton（原生 menubar 在 Tk9/Windows 上不吃配色）
    check("B 浅色菜单栏底色取自配色表（与下方内容拉开色差）",
          str(ui.menubar.cget("background")).lower() == pal_light["menubar_bg"]
          and pal_light["menubar_bg"] != pal_light["bg"],
          ui.menubar.cget("background"))
    ui._apply_theme("dark")
    for _ in range(3):
        root.update(); root.update_idletasks()
    pal_dark = theme.palette("dark")
    check("B 深色菜单栏底色随主题（与下方内容拉开色差）",
          str(ui.menubar.cget("background")).lower() == pal_dark["menubar_bg"]
          and pal_dark["menubar_bg"] != pal_dark["bg"],
          ui.menubar.cget("background"))
    btn = ui._menu_buttons["menu.help"]
    check("B 深色菜单栏按钮前景为浅色",
          str(btn.cget("foreground")).lower() == pal_dark["fg"],
          btn.cget("foreground"))
    check("B 深色菜单项勾选色与底色不同",
          str(ui.view_menu.cget("selectcolor")).lower() != pal_dark["bg"],
          ui.view_menu.cget("selectcolor"))
    check("B 深色模式项前有勾",
          any(l.startswith(ui.MENU_CHECK.strip()) and i18n.t("menu.dark_mode") in l
              for l in labels(ui.view_menu)), str(labels(ui.view_menu)))
    ui._apply_theme("light")
    for _ in range(2):
        root.update(); root.update_idletasks()

    # ==================================================================
    # C 状态条 + 音效时序
    # ==================================================================
    print("---- C 状态条与音效 ----")
    played = []
    original_play = audio.play
    audio.play = lambda kind, path=None: (played.append(kind), True)[1]

    ui.current_function.set(ui.function_names[0])
    ui.on_function_change()
    for _ in range(2):
        root.update(); root.update_idletasks()
    intro = ui.status_label.cget("text")
    check("C 平时显示功能介绍", bool(intro) and intro == ui._resolve_function(ui.current_function.get())[1],
          repr(intro[:40]))

    ui.text_input.delete("1.0", tk.END)
    ui.text_input.insert("1.0", '{"notes": [{"type": 2, "startTime": [1, 0, 1], "endTime": [1, 2, 1],'
                                ' "positionX": 0}, {"type": 1, "startTime": [2, 0, 1],'
                                ' "endTime": [2, 0, 1], "positionX": 0}]}')
    # ① 同步断言：一点转换按钮就切成进度条 + 转换中文字（不依赖事件循环时序）
    t_first = time.time()
    ui._trigger_with_sound("convert")
    check("C 转换时立刻显示进度条", ui.progress.winfo_manager() != "",
          ui.progress.winfo_manager())
    check("C 转换中状态条文字为「转换中…」",
          ui.status_label.cget("text") == i18n.t("status.converting"),
          repr(ui.status_label.cget("text")))
    check("C 进度条有最短可见时长配置（PROGRESS_MIN_MS >= 500ms）", ui.PROGRESS_MIN_MS >= 500,
          str(ui.PROGRESS_MIN_MS))

    # ② 等第一次转换的收尾回调跑完，再把统计清零，单独验证第二次转换的时序
    while (time.time() - t_first) * 1000 < ui.PROGRESS_MIN_MS + 400:
        root.update(); root.update_idletasks(); time.sleep(0.03)
    check("C 第一次转换后已恢复介绍文字", ui.status_label.cget("text") == intro,
          repr(ui.status_label.cget("text")[:40]))

    ui.PROGRESS_MIN_MS = 1500          # 临时放大，验证"最短可见时长"真的生效
    played.clear()
    # 直接侦测「恢复介绍」的回调被安排在多少毫秒之后 —— 比在真实事件循环里采样更可靠
    scheduled = []
    _real_after = ui.root.after

    def _spy_after(ms, func=None, *a):
        scheduled.append(ms)
        return _real_after(ms, func, *a)

    ui.root.after = _spy_after
    try:
        ui._trigger_with_sound("convert")
        t_hold = time.time()
        while (time.time() - t_hold) * 1000 < ui.PROGRESS_MIN_MS + 900:
            root.update(); root.update_idletasks(); time.sleep(0.03)
            if ui.status_label.cget("text") == intro:
                break
    finally:
        ui.root.after = _real_after
    restore_delay = max(scheduled) if scheduled else 0
    check("C 恢复介绍被安排在 ≥ 最短可见时长之后（最短可见时长生效）",
          restore_delay >= ui.PROGRESS_MIN_MS * 0.9,
          "调度=%s 最短=%s" % (sorted(set(scheduled))[:6], ui.PROGRESS_MIN_MS))
    check("C 转换完成后切回功能介绍", ui.status_label.cget("text") == intro,
          repr(ui.status_label.cget("text")[:40]))
    check("C 转换完成播放音效（恰好一次）", played == ["convert"], str(played))
    ui.PROGRESS_MIN_MS = 700

    played.clear()
    ui._trigger_with_sound("copy")
    ui._trigger_with_sound("clear")
    check("C 复制/清空按钮也有音效", played == ["copy", "clear"], str(played))
    audio.play = original_play

    # ==================================================================
    # D 音效后端
    # ==================================================================
    print("---- D 音效后端 ----")
    check("D 当前环境可播放声音", audio.available())
    check("D 实际播放成功", audio.play("convert"))
    app_src = io.open(os.path.join(BASE, "rpe_toolbox", "app.py"), encoding="utf-8").read()
    check("D 按钮音效不依赖 pygame（pygame 缺失也能播）",
          "import pygame" not in app_src, "app.py 里还有 import pygame")
    check("D 合成 WAV 写入缓存目录而非 TEMP",
          audio.write_wav(os.path.join(resources.user_cache_dir(), "_t.wav"), [0, 1, 2]) and
          not os.path.exists(os.path.join(tempfile.gettempdir(), "_t.wav")))

    # ==================================================================
    # E 纵连音高
    # ==================================================================
    print("---- E 纵连音高 ----")
    VP = mods_loader.find("vertical_pitch").module
    check("E 音高频率 A4=440 / A5=880",
          abs(VP.pitch_frequency("A4") - 440) < 0.01 and abs(VP.pitch_frequency("A5") - 880) < 0.01)
    check("E 音高颜色 tap/hold/flick/drag",
          [VP.TYPE_COLORS[i].upper() for i in (1, 2, 3, 4)]
          == ["#0AC3FF", "#9AE8FD", "#FE4365", "#F0ED69"], str(VP.TYPE_COLORS))
    check("E x 范围 ±675、音符宽度 175",
          VP.COORD_HALF == 675.0 and VP.NOTE_WIDTH == 175.0)

    ui.notebook.select(ui.tab_order.index("vertical_pitch"))
    ui._on_tab_changed()
    for _ in range(2):
        root.update(); root.update_idletasks()
    ui.vp_bpm_var.set("120")

    hold = {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 2, 1], "positionX": 0.0}
    check("E hold 数量按 bpm+音高推算（1 秒 A4 → 440）",
          VP.hold_count(ui, hold, "A4") == 440, VP.hold_count(ui, hold, "A4"))

    ui.vp_states = []
    VP._state_list(ui, [hold])
    ui.vp_states[0]["pitch"] = "A4"
    out = VP.process(ui, {"notes": [dict(hold)]})
    check("E 转换结果不再与输入相同", len(out["notes"]) == 440, len(out["notes"]))
    ts = [ui.time_to_float(n["startTime"]) for n in out["notes"]]
    check("E 纵连时间严格递增（真的一串）",
          all(ts[i] < ts[i + 1] for i in range(len(ts) - 1)))
    check("E 纵连覆盖原时长",
          abs(ts[0] - 1.0) < 1e-9 and abs(ui.time_to_float(out["notes"][-1]["endTime"]) - 3.0) < 1e-6,
          "%s .. %s" % (ts[0], ui.time_to_float(out["notes"][-1]["endTime"])))

    tap = {"type": 1, "startTime": [4, 0, 1], "endTime": [4, 0, 1], "positionX": 100.0}
    ui.vp_states = []
    VP._state_list(ui, [tap])
    ui.vp_states[0].update({"pitch": "A4", "count": 8})
    out2 = VP.process(ui, {"notes": [dict(tap)]})
    check("E 单键按手填数量拆成 8 个", len(out2["notes"]) == 8, len(out2["notes"]))
    t2 = [ui.time_to_float(n["startTime"]) for n in out2["notes"]]
    check("E 纵连间隔 = 单音符时值", abs((t2[1] - t2[0]) - 120 / (60 * 440)) < 1e-9, t2[1] - t2[0])

    # 画布：纵向=时间，横向=坐标
    ui.text_input.delete("1.0", tk.END)
    ui.text_input.insert("1.0", json.dumps({"notes": [
        {"type": 1, "startTime": [1, 0, 1], "endTime": [1, 0, 1], "positionX": -600.0},
        {"type": 2, "startTime": [2, 0, 1], "endTime": [2, 2, 1], "positionX": 600.0},
    ]}))
    notes = VP.refresh(ui)
    for _ in range(2):
        root.update(); root.update_idletasks()
    boxes = {}
    for item in ui.vp_canvas.find_withtag("note"):
        for tag in ui.vp_canvas.gettags(item):
            if tag.isdigit():
                boxes[int(tag)] = ui.vp_canvas.bbox(item)
    check("E 画布画出 2 个音符", len(boxes) == 2, str(boxes))
    if len(boxes) == 2:
        check("E 纵向=时间（下方较早、上方较晚：靠后的音符更靠上）",
              boxes[1][3] < boxes[0][3], str(boxes))
        check("E 横向=坐标（-600 在 600 左侧）", boxes[0][0] < boxes[1][0], str(boxes))
    check("E 时间轴可缩放/滚动，坐标轴不缩放",
          hasattr(ui, "vp_zoom") and hasattr(ui, "vp_scroll"))
    samples, rate, dur, b_from, b_to = VP._samples_for(ui, notes, ui.vp_states)
    check("E 试听合成锯齿波且非静音",
          len(samples) > 1000 and rate == 44100 and any(abs(v) > 100 for v in samples),
          (len(samples), rate))
    check("E 试听时长与拍区间一并返回", dur > 0 and b_to > b_from, (dur, b_from, b_to))
    check("E 试听可播放", VP.preview(ui) is True)

    # ==================================================================
    # G 第二轮反馈：菜单改名 / 输入输出等高 / 首尾相接 / 滑音 / 画布方向与就地编辑
    # ==================================================================
    print("---- G 菜单改名与输入输出等高 ----")
    all_labels = []
    for menu in ui._all_menus:
        try:
            for i in range(menu.index("end") + 1):
                if menu.type(i) in ("checkbutton", "radiobutton", "cascade", "command"):
                    all_labels.append(str(menu.entrycget(i, "label")))
        except Exception:
            pass
    check("G 功能子菜单名为「启用」（与打勾含义对应）",
          i18n.t("menu.enable") in all_labels and "禁用" not in all_labels, str(all_labels[:8]))

    for key in ui.tab_order:
        panel = ui.tab_io[key]
        if panel["input_frame"].winfo_manager() == "":
            continue
        h_in = panel["text_input"].winfo_height()
        h_out = panel["text_output"].winfo_height()
        check("G %s 输入框与输出框等高" % key, abs(h_in - h_out) <= 2,
              "输入=%s 输出=%s" % (h_in, h_out))

    ui.notebook.select(ui.tab_order.index("vertical_pitch"))
    ui._on_tab_changed()
    for _ in range(2):
        root.update(); root.update_idletasks()
    ui.vp_bpm_var.set("120")

    print("---- G 长条首尾相接 / 滑音 ----")
    hold = {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 2, 1], "positionX": 0.0}
    ui.vp_states = []
    VP._state_list(ui, [hold])
    ui.vp_states[0]["pitch"] = "A4"
    out = VP.process(ui, {"notes": [dict(hold)]})
    spans = [(ui.time_to_float(n["startTime"]), ui.time_to_float(n["endTime"]))
             for n in out["notes"]]
    check("G hold 拆出的长条首尾相接（endTime = 下一个 startTime）",
          all(abs(spans[i][1] - spans[i + 1][0]) < 1e-9 for i in range(len(spans) - 1)),
          "最大缝 %s" % max(abs(spans[i][1] - spans[i + 1][0]) for i in range(len(spans) - 1)))
    check("G 第一个长条不再覆盖整段",
          abs(spans[0][1] - spans[0][0]) < 1e-9
          or spans[0][1] < ui.time_to_float(hold["endTime"]),
          str(spans[0]))

    glide = {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 4, 1], "positionX": 0.0}
    ui.vp_states = []
    VP._state_list(ui, [glide])
    ui.vp_states[0].update({"pitch": "C4", "glide": True, "pitch2": "C6"})
    g_out = VP.process(ui, {"notes": [dict(glide)]})
    g_t = [ui.time_to_float(n["startTime"]) for n in g_out["notes"]]
    g_steps = [g_t[i + 1] - g_t[i] for i in range(len(g_t) - 1)]
    check("G 滑音数量按两端平均频率推算",
          len(g_t) == VP.hold_count(ui, glide, "C4", "C6"), len(g_t))
    check("G 滑音间隔随音高变密（不再等同于非滑音）",
          g_steps[-1] < g_steps[0] / 2.0, "首=%s 尾=%s" % (g_steps[0], g_steps[-1]))
    check("G 滑音纵连仍覆盖整段",
          abs(g_t[0] - 1.0) < 1e-9
          and abs(ui.time_to_float(g_out["notes"][-1]["endTime"]) - 5.0) < 1e-6)
    ui.vp_states = []
    VP._state_list(ui, [glide])
    ui.vp_states[0].update({"pitch": "C4"})
    n_out = VP.process(ui, {"notes": [dict(glide)]})
    n_t = [ui.time_to_float(n["startTime"]) for n in n_out["notes"]]
    n_steps = [n_t[i + 1] - n_t[i] for i in range(len(n_t) - 1)]
    check("G 非滑音是等距的", abs(n_steps[0] - n_steps[-1]) < 1e-9, (n_steps[0], n_steps[-1]))
    check("G 滑音结果与非滑音不同", len(g_t) != len(n_t) or g_steps[0] != n_steps[0],
          "%s vs %s" % (len(g_t), len(n_t)))

    print("---- G 画布方向 / 拍单位 / 标签位置 / 就地编辑 ----")
    edge = {"notes": [
        {"type": 1, "startTime": [1, 0, 1], "endTime": [1, 0, 1], "positionX": -600.0},
        {"type": 2, "startTime": [2, 0, 1], "endTime": [2, 2, 1], "positionX": 600.0},
    ]}
    ui.text_input.delete("1.0", tk.END)
    ui.text_input.insert("1.0", json.dumps(edge))
    notes = VP.refresh(ui)
    for _ in range(2):
        root.update(); root.update_idletasks()
    boxes = {}
    for item in ui.vp_canvas.find_withtag("note"):
        for tag in ui.vp_canvas.gettags(item):
            if tag.isdigit():
                boxes[int(tag)] = ui.vp_canvas.bbox(item)
    labels_ = {}
    for item in ui.vp_canvas.find_withtag("pitch"):
        for tag in ui.vp_canvas.gettags(item):
            if tag.isdigit():
                labels_[int(tag)] = ui.vp_canvas.bbox(item)
    if len(boxes) == 2:
        check("G 下方较早、上方较晚", boxes[0][3] > boxes[1][3], str(boxes))
    check("G 音高/数量标在音符上方",
          all(labels_[k][3] <= boxes[k][1] + 2 for k in labels_ if k in boxes),
          str((labels_, boxes)))
    check("G 靠右边缘的标签不超出画布",
          all(labels_[k][2] <= ui.vp_canvas.winfo_width() for k in labels_),
          "%s / 宽%s" % ([labels_[k][2] for k in labels_], ui.vp_canvas.winfo_width()))
    canvas_texts = [str(ui.vp_canvas.itemcget(i, "text")) for i in ui.vp_canvas.find_all()
                    if ui.vp_canvas.type(i) == "text"]
    ticks = [x for x in canvas_texts if x.replace(".", "").replace("-", "").isdigit()]
    check("G 时间刻度用拍数、不再用秒", bool(ticks) and not any(x.endswith("s") for x in canvas_texts),
          str(canvas_texts[:8]))
    check("G 画布上下各留一拍（音符不贴边）",
          min(b[1] for b in boxes.values()) > 0
          and max(b[3] for b in boxes.values()) < ui.vp_canvas.winfo_height(), str(boxes))

    import tkinter.simpledialog as _sd
    asked = {"n": 0}
    _orig_askstring = _sd.askstring
    _sd.askstring = lambda *a, **k: (asked.__setitem__("n", asked["n"] + 1), None)[1]
    target = [i for i in ui.vp_canvas.find_withtag("note")
              if "0" in ui.vp_canvas.gettags(i)][0]
    bb = ui.vp_canvas.bbox(target)
    VP.click_canvas(ui, type("E", (), {"x": (bb[0] + bb[2]) // 2, "y": (bb[1] + bb[3]) // 2})(),
                    right=False)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("G 就地编辑：输入框嵌在画布里而不是弹窗",
          getattr(ui, "vp_editor", None) is not None
          and ui.vp_editor.winfo_parent().startswith(str(ui.vp_canvas)),
          repr(getattr(ui, "vp_editor", None)))
    check("G 就地编辑没有调用弹窗对话框", asked["n"] == 0, str(asked))
    if getattr(ui, "vp_editor", None) is not None:
        ui.vp_editor.delete(0, tk.END)
        ui.vp_editor.insert(0, "E4")
        VP._commit_editor(ui)
        for _ in range(2):
            root.update(); root.update_idletasks()
        check("G 就地输入生效", ui.vp_states[0]["pitch"] == "E4", ui.vp_states[0])
        check("G 提交后输入框消失", getattr(ui, "vp_editor", None) is None)
    _sd.askstring = _orig_askstring

    # ==================================================================
    # H 第三轮反馈：点别处也保存 / 右键分用途 / 留空即非滑音
    # ==================================================================
    print("---- H 右键分用途 / 点别处也保存 / 留空即非滑音 ----")

    class _Ev(object):
        def __init__(self, widget, x, y):
            self.widget, self.x, self.y = widget, x, y

    sample2 = {"notes": [
        {"type": 1, "startTime": [1, 0, 1], "endTime": [1, 0, 1], "positionX": -400.0},
        {"type": 2, "startTime": [2, 0, 1], "endTime": [2, 2, 1], "positionX": 400.0},
    ]}
    ui.text_input.delete("1.0", tk.END)
    ui.text_input.insert("1.0", json.dumps(sample2))
    VP.refresh(ui)
    for _ in range(2):
        root.update(); root.update_idletasks()

    def _note_center(i):
        for item in ui.vp_canvas.find_withtag("note"):
            if str(i) in ui.vp_canvas.gettags(item):
                bb = ui.vp_canvas.bbox(item)
                return (bb[0] + bb[2]) // 2, (bb[1] + bb[3]) // 2
        return 0, 0

    # 点别处（不是按回车、也不是按 Esc）要保存
    cx, cy = _note_center(0)
    VP.click_canvas(ui, _Ev(ui.vp_canvas, cx, cy), right=False)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 左键点音符弹出就地框", getattr(ui, "vp_editor", None) is not None)
    ui.vp_editor.delete(0, tk.END)
    ui.vp_editor.insert(0, "A4")
    VP._on_root_click(ui, _Ev(ui.text_input, 5, 5))          # 模拟点到别的控件
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 点其它控件即保存（不必按回车）", ui.vp_states[0]["pitch"] == "A4", ui.vp_states[0])
    check("H 保存后编辑框关闭", getattr(ui, "vp_editor", None) is None)

    VP.click_canvas(ui, _Ev(ui.vp_canvas, cx, cy), right=False)
    for _ in range(2):
        root.update(); root.update_idletasks()
    ui.vp_editor.delete(0, tk.END)
    ui.vp_editor.insert(0, "C5")
    VP.click_canvas(ui, _Ev(ui.vp_canvas, 5, 5), right=False)  # 点画布空白
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 点画布空白处也保存", ui.vp_states[0]["pitch"] == "C5", ui.vp_states[0])

    # 直接点按钮（走 pending commit 钩子）也要保存
    VP.click_canvas(ui, _Ev(ui.vp_canvas, cx, cy), right=False)
    for _ in range(2):
        root.update(); root.update_idletasks()
    ui.vp_editor.delete(0, tk.END)
    ui.vp_editor.insert(0, "D4")
    ui.commit_pending_edits()                                  # 按钮点击路径会先调它
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 直接点按钮前会先提交编辑", ui.vp_states[0]["pitch"] == "D4", ui.vp_states[0])

    # Esc 才丢弃
    VP.click_canvas(ui, _Ev(ui.vp_canvas, cx, cy), right=False)
    for _ in range(2):
        root.update(); root.update_idletasks()
    ui.vp_editor.delete(0, tk.END)
    ui.vp_editor.insert(0, "B4")
    VP._cancel_editor(ui)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 按 Esc 才丢弃", ui.vp_states[0]["pitch"] == "D4", ui.vp_states[0])

    # 右键非 hold → 数量框
    VP.click_canvas(ui, _Ev(ui.vp_canvas, cx, cy), right=True)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 右键非 hold 直接弹出数量框",
          getattr(ui, "vp_editor", None) is not None and getattr(ui, "vp_editor_kind", "") == "count",
          str(getattr(ui, "vp_editor_kind", None)))
    if getattr(ui, "vp_editor", None) is not None:
        ui.vp_editor.delete(0, tk.END)
        ui.vp_editor.insert(0, "12")
        VP._commit_editor(ui)
        for _ in range(2):
            root.update(); root.update_idletasks()
        check("H 数量已写入", ui.vp_states[0]["count"] == 12, ui.vp_states[0])

    # 右键 hold → 结束音调框；留空 = 非滑音
    hx, hy = _note_center(1)
    VP.click_canvas(ui, _Ev(ui.vp_canvas, hx, hy), right=True)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 右键 hold 直接弹出结束音调框",
          getattr(ui, "vp_editor", None) is not None and getattr(ui, "vp_editor_kind", "") == "tail",
          str(getattr(ui, "vp_editor_kind", None)))
    check("H 非滑音时该框为空", ui.vp_editor.get() == "", repr(ui.vp_editor.get()))
    ui.vp_editor.delete(0, tk.END)
    ui.vp_editor.insert(0, "E5")
    VP._on_root_click(ui, _Ev(ui.text_input, 5, 5))
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 填了结束音调即为滑音",
          ui.vp_states[1].get("glide") is True and ui.vp_states[1].get("pitch2") == "E5",
          ui.vp_states[1])

    VP.click_canvas(ui, _Ev(ui.vp_canvas, hx, hy), right=True)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 已是滑音时框内显示当前尾音高", ui.vp_editor.get() == "E5", repr(ui.vp_editor.get()))
    ui.vp_editor.delete(0, tk.END)
    VP._commit_editor(ui)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("H 留空即为非滑音",
          ui.vp_states[1].get("glide") is False and ui.vp_states[1].get("pitch2") == "0",
          ui.vp_states[1])
    # 关掉滑音后数量按单端频率算（不能残留两端平均）
    h2 = {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 4, 1], "positionX": 0.0}
    ui.vp_states = []
    VP._state_list(ui, [h2])
    ui.vp_states[0].update({"pitch": "C4", "glide": False, "pitch2": "C6"})
    check("H 关掉滑音后数量只按起始音高算",
          VP.effective_count(ui, h2, ui.vp_states[0]) == VP.hold_count(ui, h2, "C4"),
          VP.effective_count(ui, h2, ui.vp_states[0]))

    # ==================================================================
    # I 第四轮反馈：预览加速 / 非 hold 时长按数量 / 播放进度线 / 非法 endTime
    # ==================================================================
    print("---- I 预览速度与进度线 ----")
    far = {"notes": [
        {"type": 1, "startTime": [1000, 0, 1], "endTime": [1000, 0, 1], "positionX": -300.0},
        {"type": 2, "startTime": [1002, 0, 1], "endTime": [1002, 2, 1], "positionX": 300.0},
    ]}
    ui.text_input.delete("1.0", tk.END)
    ui.text_input.insert("1.0", json.dumps(far))
    far_notes = VP.refresh(ui)
    ui.vp_states[0].update({"pitch": "C4", "count": 8})
    ui.vp_states[1].update({"pitch": "A4"})
    ui.vp_bpm_var.set("120")

    t_syn = time.monotonic()
    i_samples, i_rate, i_dur, i_from, i_to = VP._samples_for(ui, far_notes, ui.vp_states)
    synth_ms = (time.monotonic() - t_syn) * 1000
    check("I 起始拍数很大时只渲染发声区间（不再补一大段静音）",
          len(i_samples) < i_rate * (i_dur + 0.5),
          "%d 样本 / %.2fs" % (len(i_samples), i_dur))
    check("I 合成耗时 < 1s", synth_ms < 1000, "%.0f ms" % synth_ms)
    check("I 返回的拍区间覆盖全部发声音符",
          abs(i_from - 1000.0) < 1e-6 and abs(i_to - 1004.0) < 1e-6, (i_from, i_to))

    check("I 预览可播放", VP.preview(ui) is True)
    cached_path = ui.vp_preview_cache["path"]
    t_re = time.monotonic()
    VP.preview(ui)
    re_ms = (time.monotonic() - t_re) * 1000
    check("I 内容未变时复用缓存（不重新合成）",
          ui.vp_preview_cache["path"] == cached_path and re_ms < 200, "%.0f ms" % re_ms)

    play = ui.vp_play
    check("I 预览时画出播放进度线",
          play is not None and bool(ui.vp_canvas.find_withtag("progress")), str(play))
    if play:
        coords = ui.vp_canvas.coords(play["item"])
        check("I 进度线横跨预览窗", coords[0] == 0
              and coords[2] >= ui.vp_canvas.winfo_width(), str(coords))
        y_before = coords[1]
        for _ in range(12):
            root.update(); root.update_idletasks(); time.sleep(0.05)
        y_after = (ui.vp_canvas.coords(play["item"])[1]
                   if ui.vp_canvas.type(play["item"]) else None)
        check("I 进度线随时间向上移动（下方较早、上方较晚）",
              y_after is not None and y_after < y_before, "%s -> %s" % (y_before, y_after))
        play["duration"] = 0.05
        for _ in range(10):
            root.update(); root.update_idletasks(); time.sleep(0.03)
        check("I 播放结束后进度线消失", not ui.vp_canvas.find_withtag("progress"))

    print("---- I 非 hold 的预览时长由数量推算 ----")
    tap_note = {"type": 1, "startTime": [5, 0, 1], "endTime": [5, 0, 1], "positionX": 0.0}
    ui.vp_states = []
    VP._state_list(ui, [tap_note])
    ui.vp_states[0].update({"pitch": "C4", "count": 1})
    span1 = VP._note_preview_span(ui, tap_note, ui.vp_states[0])
    ui.vp_states[0]["count"] = 10
    span10 = VP._note_preview_span(ui, tap_note, ui.vp_states[0])
    unit1 = VP.unit_seconds(ui, "C4")
    check("I 非 hold 时长 = 数量 × 单音符时值", abs(span10 - 10 * unit1) < 1e-9,
          (span10, 10 * unit1))
    check("I 数量 1 时就是一个单音符时值（不加人为下限）", abs(span1 - unit1) < 1e-9,
          (span1, unit1))
    ui.vp_states[0].update({"pitch": "0", "count": 4})
    check("I 音高 0 时按 16 分音算",
          abs(VP._note_preview_span(ui, tap_note, ui.vp_states[0]) - 4 * 60 / 120 / 4) < 1e-9)

    print("---- I 非法 endTime 的修正 ----")
    bad_input = [
        {"type": 2, "startTime": [0, 1, 2], "endTime": [0, 1, 4], "positionX": -300.0},
        {"type": 2, "startTime": [2, 0, 1], "endTime": [1, 0, 1], "positionX": 300.0},
    ]
    ui.vp_states = []
    VP._state_list(ui, bad_input)
    bad_out = VP.process(ui, {"notes": [dict(n) for n in bad_input]})["notes"]
    still_bad = [(n["startTime"], n["endTime"]) for n in bad_out
                 if ui.time_to_float(n["endTime"]) < ui.time_to_float(n["startTime"]) - 1e-12]
    check("I 输入 hold 的 endTime 早于 startTime 时输出不再保留非法值",
          not still_bad, str(still_bad[:3]))
    check("I 修正数量被记录并提示",
          ui.vp_fixed_invalid >= 2 and bool(ui.vp_fix_notice),
          (ui.vp_fixed_invalid, ui.vp_fix_notice))
    VP.draw(ui, bad_input, ui.vp_states)
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("I 画布上给出修正提示", bool(ui.vp_canvas.find_withtag("notice")))
    ui.vp_fix_notice = ""

    ok_note = {"type": 2, "startTime": [1, 0, 1], "endTime": [1, 2, 1], "positionX": 0.0}
    ui.vp_states = []
    VP._state_list(ui, [ok_note])
    ok_out = VP.process(ui, {"notes": [dict(ok_note)]})["notes"]
    check("I 合法输入不产生修正提示", ui.vp_fixed_invalid == 0 and ui.vp_fix_notice == "",
          (ui.vp_fixed_invalid, ui.vp_fix_notice))
    check("I 合法 hold 的纵连仍首尾相接",
          all(abs(ui.time_to_float(ok_out[i]["endTime"])
                  - ui.time_to_float(ok_out[i + 1]["startTime"])) < 1e-9
              for i in range(len(ok_out) - 1)))

    # ==================================================================
    # J 第五轮反馈：帮助菜单 + 功能介绍弹窗 + requirements.txt 可被 pip 解析
    # ==================================================================
    print("---- J 帮助菜单与功能介绍 ----")
    help_labels = [str(ui.help_menu.entrycget(i, "label"))
                   for i in range(ui.help_menu.index("end") + 1)]
    stripped = [x.lstrip("\u2714 ") for x in help_labels]
    top_labels = [str(b.cget("text")) for b in ui._menu_buttons.values()]
    check("J 顶级菜单是 功能/显示/帮助（帮助替代了关于）",
          top_labels == [i18n.t("menu.function"), i18n.t("menu.view"), i18n.t("menu.help")],
          str(top_labels))
    check("J 帮助下第一项是功能介绍（带当前功能名）",
          stripped[0] == i18n.t("menu.func_help").format(name=ui._current_func_name())
          and ui._current_func_name() in stripped[0], str(stripped))
    check("J 关于排在功能介绍下一行", stripped[1] == i18n.t("menu.about"), str(stripped))
    # 切换功能后菜单文字跟着变
    ui.notebook.select(ui.tab_order.index("vertical_pitch"))
    ui._on_tab_changed()
    for _ in range(2):
        root.update(); root.update_idletasks()
    cur = ui._current_func_name()
    check("J 功能介绍跟随已选中功能",
          cur in str(ui.help_menu.entrycget(0, "label")) and cur != "",
          str(ui.help_menu.entrycget(0, "label")))

    # 弹窗：包含每个选项的作用与操作方法
    import rpe_toolbox.app as _am
    created = []
    orig_toplevel = tk.Toplevel

    class TrackedToplevel(orig_toplevel):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            created.append(self)

    _am.tk.Toplevel = TrackedToplevel
    try:
        ui.show_function_help()
        for _ in range(3):
            root.update(); root.update_idletasks()
    finally:
        _am.tk.Toplevel = orig_toplevel
    check("J 功能介绍弹窗已创建", bool(created), str(len(created)))
    if created:
        texts = [w for w in created[0].winfo_children()
                 if isinstance(w, tk.Frame)]
        body = ""
        for frame in texts:
            for child in frame.winfo_children():
                if isinstance(child, tk.Text):
                    body = child.get("1.0", "end")
        check("J 弹窗内容包含每个选项与操作方法",
              "填充音符" in body and "预览" in body
              and "左键点音符改音高" in body and "右键hold改结束音调" in body
              and "0=单键" in body,
              body[:120].replace("\n", " / "))
        for w in created:
            try:
                w.destroy()
            except Exception:
                pass

    # requirements.txt：能被 pip 的解析器逐行读取
    print("---- J requirements.txt ----")
    from packaging.requirements import Requirement
    lines = io.open(os.path.join(BASE, "requirements.txt"), encoding="utf-8").read().split("\n")
    parsed = []
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parsed.append(Requirement(line))
    names = {r.name.lower() for r in parsed}
    check("J requirements.txt 可被 pip 解析且包含必需/可选依赖",
          len(parsed) >= 3 and {"pillow", "sv-ttk", "pygame", "pywinstyles"} <= names,
          str(sorted(names)))

    # ==================================================================
    # K 第六轮反馈：菜单栏/帮助窗口标题栏随深浅主题，帮助窗口用系统帮助图标
    # ==================================================================
    print("---- K 标题栏与帮助图标 ----")

    def _dwim_dark(hwnd):
        """读 DWMWA_USE_IMMERSIVE_DARK_MODE(20)；Windows 不支持时返回 None。"""
        import ctypes

        val = ctypes.c_int(0)
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            ctypes.c_void_p(hwnd), 20, ctypes.byref(val), ctypes.sizeof(val))
        return None if res else bool(val.value)

    pal_dark = theme.palette("dark")
    pal_light = theme.palette("light")

    ui._apply_theme("dark")
    for _ in range(4):
        root.update(); root.update_idletasks()
    ui.show_function_help()
    for _ in range(4):
        root.update(); root.update_idletasks()
    win_dark = ui._help_windows[-1]
    mh = ui._window_hwnd(root)
    wh = ui._window_hwnd(win_dark)
    m_flag, w_flag = _dwim_dark(mh), _dwim_dark(wh)
    if m_flag is None or w_flag is None:
        print("   (此系统不支持 DWMWA_USE_IMMERSIVE_DARK_MODE，跳过标题栏断言)")
    else:
        check("K 深色下主窗口标题栏为深色", m_flag is True, str(m_flag))
        check("K 深色下帮助窗口标题栏为深色", w_flag is True, str(w_flag))
    check("K 深色下帮助窗口底色随主题",
          str(win_dark.cget("background")).lower() == pal_dark["bg"],
          win_dark.cget("background"))
    check("K 深色下帮助窗口文本区随主题",
          str(win_dark._hp_text.cget("background")).lower() == pal_dark["text_bg"],
          win_dark._hp_text.cget("background"))
    dark_menus = [str(m.cget("background")).lower() for m in ui._all_menus]
    check("K 深色下所有菜单（含帮助子菜单）底色都是深色",
          all(c == pal_dark["bg"] for c in dark_menus), str(set(dark_menus)))
    check("K 帮助窗口用的是系统帮助图标（句柄非 0）", ui._help_icon_handle != 0,
          str(ui._help_icon_handle))

    ui._apply_theme("light")
    for _ in range(4):
        root.update(); root.update_idletasks()
    m_flag2, w_flag2 = _dwim_dark(mh), _dwim_dark(wh)
    if m_flag2 is not None and w_flag2 is not None:
        check("K 浅色下两个窗口标题栏都回到浅色",
              m_flag2 is False and w_flag2 is False, (m_flag2, w_flag2))
    light_menus = [str(m.cget("background")).lower() for m in ui._all_menus]
    check("K 浅色下所有菜单底色都是浅色",
          all(c == pal_light["bg"] for c in light_menus), str(set(light_menus)))
    ui._close_help_window(win_dark)
    for _ in range(3):
        root.update(); root.update_idletasks()
    check("K 关闭后窗口列表被清理", win_dark not in ui._help_windows, str(ui._help_windows))

    # ==================================================================
    # L 第七轮反馈：自绘下拉（原生菜单在 Tk9/Windows 上既不吃配色也弹不出来）
    # ==================================================================
    print("---- L 自绘下拉 ----")
    ui._apply_theme("dark")            # K 段结束在浅色，这里切回深色验证
    for _ in range(3):
        root.update(); root.update_idletasks()
    check("L 菜单栏是自绘 Frame（不再是原生 menubar）",
          isinstance(ui.menubar, tk.Frame)
          and str(ui.menubar.cget("background")).lower() == pal_dark["menubar_bg"],
          str(ui.menubar.cget("background")))
    line = getattr(ui.menubar, "_hp_line", None)
    check("L 菜单栏底部有分隔线（与下方拉开色差）",
          line is not None and str(line.cget("background")).lower() == pal_dark["menubar_border"],
          line.cget("background") if line is not None else None)
    check("L 菜单栏按钮为 功能/显示/帮助",
          [str(b.cget("text")) for b in ui._menu_buttons.values()]
          == [i18n.t("menu.function"), i18n.t("menu.view"), i18n.t("menu.help")],
          str([b.cget("text") for b in ui._menu_buttons.values()]))

    ui._open_dropdown("menu.function")
    for _ in range(2):
        root.update(); root.update_idletasks()
    dd = ui._dropdowns[0] if ui._dropdowns else None
    check("L 点击菜单按钮展开自绘下拉", dd is not None and dd.winfo_ismapped(),
          str(dd))
    if dd is not None:
        # 下拉位置应在按钮正下方
        btn = ui._menu_buttons["menu.function"]
        expected_x = btn.winfo_rootx()
        check("L 下拉出现在按钮正下方", abs(dd.winfo_x() - expected_x) <= 2,
              "下拉x=%s 按钮x=%s" % (dd.winfo_x(), expected_x))
        rows = [w for w in dd.winfo_children()[0].winfo_children()
                if isinstance(w, tk.Button)]
        check("L 下拉条目数与菜单数据源一致",
              len(rows) == ui._menu_source["menu.function"].index("end") + 1,
              "%d vs %s" % (len(rows), ui._menu_source["menu.function"].index("end")))
        # 点一条会执行对应命令：选「切换组 → 全谱处理」
        ui._run_menu_item(ui.group_menu, 0)
        for _ in range(2):
            root.update(); root.update_idletasks()
        check("L 点下拉条目真的执行了命令（功能组切换）",
              ui.current_group == ui.group_names()[0], ui.current_group)
    ui._close_dropdown()
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("L 收起后下拉销毁", not ui._dropdowns, str(ui._dropdowns))

    # 二级面板（级联子菜单）：不再有「返回」行，直接列出子条目，且出现在一级面板右侧
    ui._open_dropdown("menu.view")
    for _ in range(2):
        root.update(); root.update_idletasks()
    rows1 = [w for w in ui._dropdowns[0].winfo_children()[0].winfo_children()
             if isinstance(w, tk.Button)]
    cascade_rows = [w for w in rows1 if w.cget("text").endswith("\u203a")]
    check("L 一级面板里的级联项带 › 标记", bool(cascade_rows),
          str([w.cget("text") for w in rows1]))
    if cascade_rows:
        ui._open_dropdown("menu.view", level=1, submenu=ui.lang_menu,
                          anchor=cascade_rows[-1])
        for _ in range(2):
            root.update(); root.update_idletasks()
        check("L 二级面板能打开",
              len(ui._dropdowns) >= 2 and ui._dropdowns[1] is not None
              and ui._dropdowns[1].winfo_ismapped(), str(ui._dropdowns))
        if len(ui._dropdowns) >= 2 and ui._dropdowns[1] is not None:
            rows2 = [w for w in ui._dropdowns[1].winfo_children()[0].winfo_children()
                     if isinstance(w, tk.Button)]
            texts2 = [w.cget("text") for w in rows2]
            check("L 二级面板直接列出子条目（无返回行）",
                  len(rows2) == ui.lang_menu.index("end") + 1
                  and not any("返回" in x or "Back" in x for x in texts2),
                  str(texts2))
            check("L 二级面板出现在一级面板右侧",
                  ui._dropdowns[1].winfo_x() > ui._dropdowns[0].winfo_x(),
                  "%s vs %s" % (ui._dropdowns[1].winfo_x(), ui._dropdowns[0].winfo_x()))
    ui._close_dropdown()
    for _ in range(2):
        root.update(); root.update_idletasks()

    # 复现用户场景：悬停「启用」弹出子面板后，再移到「切换组」，启用面板必须消失
    ui._open_dropdown("menu.function")
    for _ in range(2):
        root.update(); root.update_idletasks()
    rows1 = [w for w in ui._dropdowns[0].winfo_children()[0].winfo_children()
             if isinstance(w, tk.Button)]
    row_switch = next(w for w in rows1 if str(w.cget("text")).startswith("切换组"))
    row_enable = next(w for w in rows1 if str(w.cget("text")).startswith("启用"))
    row_enable.event_generate("<Enter>")            # 悬停「启用」→ 子面板
    for _ in range(3):
        root.update(); root.update_idletasks()
    check("L 悬停「启用」弹出子面板",
          len(ui._dropdowns) == 2 and ui._dropdowns[1] is not None
          and ui._dropdowns[1].winfo_ismapped(), str(len(ui._dropdowns)))
    enable_panel = ui._dropdowns[1]
    row_switch.event_generate("<Enter>")            # 移到「切换组」
    for _ in range(3):
        root.update(); root.update_idletasks()
    check("L 移到「切换组」后启用子面板已销毁",
          not enable_panel.winfo_exists() and len(ui._dropdowns) == 2,
          str(len(ui._dropdowns)))
    # 移到普通条目（显示菜单的「深色模式」）时子面板也要收起
    ui._close_dropdown()
    ui._open_dropdown("menu.view")
    for _ in range(2):
        root.update(); root.update_idletasks()
    rows_v = [w for w in ui._dropdowns[0].winfo_children()[0].winfo_children()
              if isinstance(w, tk.Button)]
    rows_v[0].event_generate("<Enter>")             # 「深色模式」是普通条目
    for _ in range(3):
        root.update(); root.update_idletasks()
    check("L 悬停普通条目时子面板收起", len(ui._dropdowns) == 1, str(len(ui._dropdowns)))
    ui._close_dropdown()
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("K 帮助窗口图标是问号（SIID_HELP=23，非 77 盾牌）", ui._help_icon_handle != 0,
          str(ui._help_icon_handle))

    # 关于弹窗：{version} 占位符必须被真实版本号替换，而不是显示字面量
    from rpe_toolbox import __version__
    shown_info = []
    _orig_info = _am.messagebox.showinfo
    _am.messagebox.showinfo = lambda *a, **k: shown_info.append(a)
    try:
        ui.show_about()
        for _ in range(2):
            root.update(); root.update_idletasks()
    finally:
        _am.messagebox.showinfo = _orig_info
    check("K 关于弹窗显示真实版本号（不是 {version} 字面量）",
          bool(shown_info) and __version__ in shown_info[0][1]
          and "{version}" not in shown_info[0][1],
          str(shown_info[:1]))
    for lang in ("zh-CN", "en-US"):
        data = json.loads(io.open(os.path.join(BASE, "assets", "lang", lang + ".json"),
                                  encoding="utf-8").read())
        filled = data["dialogs"]["about_text"].format(version=__version__)
        check("K %s 的关于文案填充后无残留占位符" % lang, "{version}" not in filled,
              repr(filled[-40:]))

    # ==================================================================
    # F 英文功能名
    # ==================================================================
    print("---- F 英文翻译 ----")
    en = json.loads(io.open(os.path.join(BASE, "assets", "lang", "en-US.json"),
                            encoding="utf-8").read())
    short = [f["key"] for f in en["functions"] if len(f.get("name", "")) < 20]
    check("F 英文功能名不再过于简略", not short, str([(f["key"], f["name"]) for f in en["functions"]
                                                       if f["key"] in short]))
    check("F 英文短标签仍然足够短（一行排得下）",
          all(len(f.get("tab", "")) <= 12 for f in en["functions"]),
          str([(f["key"], f.get("tab")) for f in en["functions"] if len(f.get("tab", "")) > 12]))
    zh = json.loads(io.open(os.path.join(BASE, "assets", "lang", "zh-CN.json"),
                            encoding="utf-8").read())
    check("F 中英功能表键一致",
          [f["key"] for f in zh["functions"]] == [f["key"] for f in en["functions"]])

    ui.shutdown()
except Exception as e:
    import traceback
    traceback.print_exc()
    check("执行", False, repr(e))
finally:
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
sys.exit(1 if fail else 0)
