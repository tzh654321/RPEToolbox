# -*- coding: utf-8 -*-
"""需求十六验证：输入/按钮/输出移入标签页 + 圆角与聚焦蓝线 + 标签栏字号 + 更纱黑体等宽。

覆盖点
  A 每个功能标签页各持一套「输入JSON / 转换·复制结果·清空 / 输出JSON」
  B 各页输入输出互相独立，text_input/text_output 指向当前页
  C 页内顺序仍是：该功能选项 → 输入JSON → 三个按钮 → 输出JSON
  D 圆角文本区：平滑多边形圆角底 + 聚焦时多一条 accent 蓝线，失焦后消失
  E 功能选择栏字号小于正文（8 个标签排得下）
  F 界面字体使用更纱黑体等宽（本机 Sarasa Fixed SC），字体规格用 "{家族} 字号" 形式
"""
import io
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 每个测试独立的固定配置目录：**只写不删**（删除动作会进回收站，弄脏用户回收站）
# 每次运行都重写一份基线配置，避免上一次运行留下的主题/语言/禁用项影响本次结果。
_CFG_TMP = os.path.join(tempfile.gettempdir(), "rpet_test_req16")
os.makedirs(os.path.join(_CFG_TMP, "RPEToolbox"), exist_ok=True)
os.environ["APPDATA"] = _CFG_TMP
os.environ.pop("RPET_THEME", None)
os.environ.pop("RPET_LANG", None)
with io.open(os.path.join(_CFG_TMP, "RPEToolbox", "config.json"), "w", encoding="utf-8") as _f:
    _f.write('{"theme": "light", "language": "zh-CN"}')
_OLD_APPDATA = os.environ.get("APPDATA")
os.environ["APPDATA"] = _CFG_TMP
os.environ.pop("RPET_THEME", None)


def cleanup_config():
    if _OLD_APPDATA is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _OLD_APPDATA


from rpe_toolbox import i18n, theme  # noqa: E402
from rpe_toolbox.app import RPEToolbox  # noqa: E402

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


funcs = i18n.function_list()
NO_INPUT = ("image_to_notes", "midi_bpm_extract")
root = None

try:
    import tkinter as tk
    import tkinter.font as tkfont

    root = tk.Tk()
    root.withdraw()
    ui = RPEToolbox(root)
    for _ in range(3):
        root.update()
        root.update_idletasks()

    # ==================================================================
    # A 每页一套输入/按钮/输出
    # ==================================================================
    print("---- A 每页一套输入/按钮/输出 ----")
    check("A 标签页数=功能数", ui.notebook.index("end") == len(ui.current_mods()))
    check("A 每页都有 IO 面板", len(ui.tab_io) == len(ui.current_mods()), "%d vs %d" % (len(ui.tab_io), len(ui.current_mods())))

    keys = ui.tab_order

    missing_in = [k for k in keys if "text_input" not in ui.tab_io.get(k, {})]
    check("A 每页都有输入文本区（未使用的页只是不显示）", not missing_in, str(missing_in))

    missing_out = [k for k in keys if "text_output" not in ui.tab_io.get(k, {})]
    check("A 每页都有输出文本区", not missing_out, str(missing_out))

    bad_buttons = []
    for k in keys:
        buttons = ui.tab_io[k].get("buttons", {})
        if set(buttons) != {"btn_convert", "btn_copy", "btn_clear"}:
            bad_buttons.append((k, sorted(buttons)))
    check("A 每页都有三个按钮", not bad_buttons, str(bad_buttons))

    check("A 按钮总数 = 页数 × 3", len(list(ui.all_buttons())) == len(ui.current_mods()) * 3,
          str(len(list(ui.all_buttons()))))
    check("A 文本区总数 = 页数 × 2", len(list(ui.all_text_areas())) == len(ui.current_mods()) * 2,
          str(len(list(ui.all_text_areas()))))

    # 输入框显示与否：图片转音符画 / MIDI 两页不显示
    hidden = []
    shown = []
    for k in keys:
        frame = ui.tab_io[k].get("input_frame")
        manager = frame.winfo_manager() if frame is not None else None
        if k in NO_INPUT:
            hidden.append(manager)
        else:
            shown.append(manager)
    check("A 图片/MIDI 页的输入框不显示", all(m == "" for m in hidden), str(hidden))
    check("A 其余页显示输入框", all(m in ("pack", "grid") for m in shown), str(shown))

    # 按当前页取控件
    ui.current_function.set(ui.function_names[0]); ui.on_function_change(); root.update_idletasks()
    first_in = ui.text_input
    ui.current_function.set(ui.function_names[1]); ui.on_function_change(); root.update_idletasks()
    check("B text_input 指向当前页", ui.text_input is not first_in and ui.text_input is ui.tab_io["nonlinear_split"]["text_input"],
          str(ui.text_input))

    # ==================================================================
    # B 各页输入输出互相独立
    # ==================================================================
    print("---- B 各页输入输出独立 ----")
    # 第 1 页写入输入/输出
    ui.current_function.set(ui.function_names[0]); ui.on_function_change(); root.update_idletasks()
    ui.text_input.delete("1.0", tk.END)
    ui.text_input.insert("1.0", '{"page": 1}')
    ui.text_output.insert("1.0", "out1")

    # 切到第 2 页：应当是干净的，且各自写入
    ui.current_function.set(ui.function_names[1]); ui.on_function_change(); root.update_idletasks()
    check("B 切页后输入框内容不串页", ui.text_input.get("1.0", tk.END).strip() != '{"page": 1}',
          repr(ui.text_input.get("1.0", tk.END).strip()))
    check("B 输出框也各页独立", ui.text_output.get("1.0", tk.END).strip() == "",
          repr(ui.text_output.get("1.0", tk.END).strip()))
    ui.text_input.insert("1.0", '{"page": 2}')
    ui.text_output.insert("1.0", "out2")

    # 切回第 1 页：内容仍在
    ui.current_function.set(ui.function_names[0]); ui.on_function_change(); root.update_idletasks()
    check("B 切回原页内容仍在", ui.text_input.get("1.0", tk.END).strip() == '{"page": 1}',
          repr(ui.text_input.get("1.0", tk.END).strip()))
    check("B 切回后输出框内容仍在", ui.text_output.get("1.0", tk.END).strip() == "out1",
          repr(ui.text_output.get("1.0", tk.END).strip()))

    # 在第 1 页清空：只影响本页
    ui.clear_io()
    check("B 清空只清当前页", ui.text_output.get("1.0", tk.END).strip() == ""
          and ui.text_input.get("1.0", tk.END).strip() == "")
    ui.current_function.set(ui.function_names[1]); ui.on_function_change(); root.update_idletasks()
    check("B 清空不影响其它页", ui.text_input.get("1.0", tk.END).strip() == '{"page": 2}'
          and ui.text_output.get("1.0", tk.END).strip() == "out2",
          repr(ui.text_input.get("1.0", tk.END).strip()) + " / " + repr(ui.text_output.get("1.0", tk.END).strip()))
    ui.clear_io()

    # 转换功能在当前页生效
    ui.current_function.set(ui.function_names[0]); ui.on_function_change(); root.update_idletasks()
    ui.text_input.insert("1.0", '{"notes": [{"type": 2, "startTime": [1,0,1], "endTime": [1,0,1], "positionX": 0},'
                                ' {"type": 1, "startTime": [2,0,1], "endTime": [2,0,1], "positionX": 0}]}')
    ui.process_data()
    check("B 转换结果写入当前页输出框",
          ui.text_output.get("1.0", tk.END).strip().startswith("{") and '"notes"' in ui.text_output.get("1.0", tk.END),
          ui.text_output.get("1.0", tk.END).strip()[:60])
    ui.clear_io()

    # ==================================================================
    # C 页内顺序
    # ==================================================================
    print("---- C 页内顺序 ----")
    for key in ("hold_notes_connect", "nonlinear_split", "event_type_convert"):
        tab = ui.tab_frames[key]
        panel = ui.tab_io[key]
        holder = panel["input_frame"].master
        # 选项控件直接挂在标签页上；输入/按钮/输出三块在同一个 grid 容器里（为了输入输出框等高）
        order = ["io" if w is holder else "options" for w in tab.pack_slaves()]
        check("C %s 页内顺序 = 选项 → 输入→按钮→输出" % key,
              order[-1] == "io" and order.count("io") == 1, str(order))

        check("C %s 输入/按钮/输出在同一容器内" % key,
              panel["frame_btn"].master is holder and panel["output_frame"].master is holder,
              "%s / %s" % (panel["frame_btn"].master, panel["output_frame"].master))
        rows = (int(panel["input_frame"].grid_info().get("row", -1)),
                int(panel["frame_btn"].grid_info().get("row", -1)),
                int(panel["output_frame"].grid_info().get("row", -1)))
        check("C %s 行号依次为 输入→按钮→输出" % key, rows[0] < rows[1] < rows[2], str(rows))
        check("C %s 输入框与输出框等权（等高）" % key,
              holder.rowconfigure(rows[0])["weight"] == holder.rowconfigure(rows[2])["weight"]
              and holder.rowconfigure(rows[0])["uniform"] == holder.rowconfigure(rows[2])["uniform"],
              str(holder.rowconfigure(rows[0])) + " vs " + str(holder.rowconfigure(rows[2])))

    # ==================================================================
    # D 圆角 + 聚焦蓝线
    # ==================================================================
    print("---- D 圆角与聚焦蓝线 ----")
    area = ui.text_input
    for _ in range(3):
        root.update(); root.update_idletasks()

    def canvas_items():
        return area.canvas.find_all()

    def kinds():
        return [area.canvas.type(i) for i in canvas_items()]

    def chrome_fills():
        return [str(area.canvas.itemcget(i, "fill")).lower() for i in canvas_items()
                if area.canvas.type(i) in ("polygon", "line")]

    check("D 有圆角底（平滑多边形）",
          any(area.canvas.type(i) == "polygon" and str(area.canvas.itemcget(i, "smooth")) not in ("0", "false", "")
              for i in canvas_items()), str(kinds()))
    check("D 未聚焦时没有蓝线",
          not area.focused and str(area.accent_color).lower() not in chrome_fills(),
          str(chrome_fills()))

    area.text.event_generate("<FocusIn>")
    for _ in range(2):
        root.update(); root.update_idletasks()
    lines = [i for i in canvas_items() if area.canvas.type(i) == "line"]
    accent = str(area.accent_color).lower()
    check("D 聚焦后有底部蓝线",
          area.focused and len(lines) == 1 and str(area.canvas.itemcget(lines[0], "fill")).lower() == accent,
          "focused=%s lines=%d fills=%s" % (area.focused, len(lines), chrome_fills()))
    if lines:
        check("D 蓝线颜色取自主题强调色", str(area.canvas.itemcget(lines[0], "fill")).lower() == accent,
              str(area.canvas.itemcget(lines[0], "fill")))

    area.text.event_generate("<FocusOut>")
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("D 失焦后蓝线消失",
          not area.focused and not [i for i in canvas_items() if area.canvas.type(i) == "line"],
          str(chrome_fills()))

    check("D 空格子也画了圆角底（输出框）",
          any(ui.text_output.canvas.type(i) == "polygon" for i in ui.text_output.canvas.find_all())
          if ui.text_output is not None else False)

    # ==================================================================
    # E 标签栏字号
    # ==================================================================
    print("---- E 标签栏字号 ----")
    body = ui.font_spec(10)
    tab_font = str(ui.style.lookup("TNotebook.Tab", "font"))
    body_size = tkfont.Font(font=body).actual("size")
    tab_size = tkfont.Font(font=tab_font).actual("size")
    check("E 标签字号小于正文字号", tab_size < body_size, "tab=%s body=%s" % (tab_size, body_size))
    width = ui.notebook.winfo_width()
    last = None
    for i in range(ui.notebook.index("end")):
        bbox = ui.notebook.bbox(i)
        if bbox:
            last = bbox[0] + bbox[2]
    check("E 标签栏未溢出笔记本宽度", last is None or last <= width,
          "last=%s width=%s" % (last, width))

    # ==================================================================
    # F 更纱黑体等宽 + 字体规格
    # ==================================================================
    print("---- F 字体 ----")
    family = ui.ui_font_family
    check("F 使用更纱黑体（本机为 Sarasa Fixed SC）", family.startswith("Sarasa"),
          "%s（若本机未装更纱黑体则按回退链选择）" % family)
    check("F 使用简体等宽变体", family.endswith("SC") and ("Mono" in family or "Fixed" in family or "Term" in family),
          family)
    spec = ui.font_spec(10)
    check("F 字体规格为 {家族} 字号 形式", spec == "{%s} 10" % family, spec)
    actual = tkfont.Font(font=spec).actual()
    check("F 字体规格可被 Tk 解析出正确家族", actual.get("family") == family, str(actual))
    check("F 等宽：两个 ASCII 宽 = 一个汉字宽",
          tkfont.Font(font=spec).measure("aa") == tkfont.Font(font=spec).measure("汉"),
          "%d vs %d" % (tkfont.Font(font=spec).measure("aa"), tkfont.Font(font=spec).measure("汉")))
except Exception as e:
    import traceback
    traceback.print_exc()
    check("界面测试执行", False, repr(e))
finally:
    if root is not None:
        try:
            root.destroy()
        except Exception:
            pass
    cleanup_config()

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
sys.exit(1 if fail else 0)
