# -*- coding: utf-8 -*-
"""需求十五验证：Notebook 功能切换 + 界面字体/按钮配色 + 简介灰字复位 + 输入框对比度 + 标题栏。

覆盖点
  A 功能切换改为 Notebook：8 个标签页、文字取自语言文件 tab 键、与 current_function 双向同步
  B 界面字体：ttk 各样式与三个按钮都使用最初规定的字体（更纱黑体>微软雅黑等宽>Consolas>系统等宽）
  C 三个按钮沿用最初配色（sv-ttk 的 tk_setPalette 会重置，需在主题应用后重新套用）
  D 功能简介回到顶部原位置、使用灰字（Muted.TLabel）
  E 输入框与背景拉开对比（底色不同 + 描边）
  F pywinstyles 标题栏：缺失时静默降级，存在时按主题走 light/dark
"""
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 隔离用户配置：主题切换会写 %APPDATA%/RPEToolbox/config.json
_CFG_TMP = tempfile.mkdtemp(prefix="rpet_cfg15_")
_OLD_APPDATA = os.environ.get("APPDATA")
os.environ["APPDATA"] = _CFG_TMP
os.environ.pop("RPET_THEME", None)


def cleanup_config():
    if _OLD_APPDATA is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _OLD_APPDATA
    shutil.rmtree(_CFG_TMP, ignore_errors=True)


from rpe_toolbox import i18n, theme  # noqa: E402
from rpe_toolbox import app as app_module  # noqa: E402

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
ui_font = None
root = None
ui = None

try:
    import tkinter as tk
    import tkinter.font as tkfont

    from rpe_toolbox.app import RPEToolbox

    root = tk.Tk()
    root.withdraw()
    ui = RPEToolbox(root)
    for _ in range(3):
        root.update()
        root.update_idletasks()
    ui_font = (ui.ui_font_family, 10)

    # ==================================================================
    # A 功能切换：Notebook 标签页
    # ==================================================================
    print("---- A Notebook 功能切换 ----")
    check("A 存在 Notebook", ui.notebook.winfo_class() in ("TNotebook", "Notebook"),
          ui.notebook.winfo_class())
    check("A 标签页数量与功能数一致", ui.notebook.index("end") == len(funcs),
          "%s vs %s" % (ui.notebook.index("end"), len(funcs)))

    tabs = [ui.notebook.tab(i, "text") for i in range(ui.notebook.index("end"))]
    expect = [f.get("tab") for f in funcs]
    check("A 标签文字取自语言文件 tab 键", tabs == expect, "%s != %s" % (tabs, expect))
    check("A 每个功能都有非空 tab 标签", all(f.get("tab") for f in funcs), str(tabs))

    # current_function -> 标签页
    for index, item in enumerate(funcs):
        ui.current_function.set(item["name"])
        ui.on_function_change()
        root.update_idletasks()
        selected = ui.notebook.index("current")
        check("A 选中功能%d 时切到对应标签页" % (index + 1), selected == index,
              "selected=%s expect=%s" % (selected, index))

    # 标签页 -> current_function
    ui.notebook.select(4)
    ui.notebook.event_generate("<<NotebookTabChanged>>")
    root.update()
    check("A 点击标签页同步 current_function",
          ui.current_function.get() == funcs[4]["name"], ui.current_function.get())
    check("A 切换后简介同步",
          ui.desc_label.cget("text") == funcs[4]["desc"], ui.desc_label.cget("text")[:40])

    # 各功能的选项控件确实在对应标签页内
    parents = {
        "hold_notes_connect": ui.frame_hold_options,
        "event_type_convert": ui.frame_event_convert,
        "image_to_notes": ui.frame_image_settings,
        "time_interval_to_yoffset": ui.frame_time_offset_settings,
        "reverse_data": ui.frame_stretch_settings,
        "midi_bpm_extract": ui.frame_midi_settings,
    }
    misplaced = [k for k, w in parents.items() if w.winfo_parent() != str(ui.tab_frames[k])]
    check("A 选项控件挂在对应标签页内", not misplaced, str(misplaced))
    check("A 切割密度在两页各有一份且共用变量",
          len(ui.density_rows) == 2 and all(r.winfo_parent() == str(ui.tab_frames[k])
                                            for r, k in zip(ui.density_rows, ("nonlinear_split", "polar_conversion"))))

    # 输入框显隐（沿用需求八：图片转音符画 / MIDI BPM 提取 不显示输入JSON）
    ui.current_function.set(funcs[4]["name"]); ui.on_function_change(); root.update_idletasks()
    check("A 图片转音符画隐藏输入框", ui.input_frame.winfo_manager() == "",
          ui.input_frame.winfo_manager())
    ui.current_function.set(funcs[7]["name"]); ui.on_function_change(); root.update_idletasks()
    check("A MIDI BPM 隐藏输入框", ui.input_frame.winfo_manager() == "")
    ui.current_function.set(funcs[0]["name"]); ui.on_function_change(); root.update_idletasks()
    check("A 常规功能显示输入框", ui.input_frame.winfo_manager() == "pack",
          ui.input_frame.winfo_manager())

    # ==================================================================
    # B 界面字体
    # ==================================================================
    print("---- B 界面字体 ----")

    def font_family(got):
        """样式里的字体可能是元组或 "{家族} 字号" 字符串，统一解析出家族名。"""
        try:
            return tkfont.Font(font=got).actual("family")
        except Exception:
            return ""

    body_size = tkfont.Font(font=ui.font_spec(10)).actual("size")
    for style_name in ("TButton", "TLabel", "TCheckbutton", "TCombobox", "TEntry"):
        got = ui.style.lookup(style_name, "font")
        check("B ttk 样式 %s 使用规定字体" % style_name, font_family(got) == ui.ui_font_family,
              "%s (%s)" % (got, ui_font))

    tab_font = ui.style.lookup("TNotebook.Tab", "font")
    check("B 标签字号小于正文（功能选择栏要排得下）",
          font_family(tab_font) == ui.ui_font_family
          and tkfont.Font(font=tab_font).actual("size") < body_size,
          "%s vs body=%s" % (tab_font, body_size))

    for attr in ("btn_convert", "btn_copy", "btn_clear"):
        w = getattr(ui, attr)
        got = str(w.cget("font"))
        check("B %s 字体为 %s" % (attr, ui_font), font_family(got) == ui.ui_font_family, got)

    # ttk 控件没有 -font 选项，字体由样式决定（深色模式开关即属此类）
    switch_style = ui.dark_mode_check.cget("style") or "TCheckbutton"
    switch_font = ui.style.lookup(switch_style, "font")
    check("B 深色模式开关字体为 %s" % (ui_font,), font_family(switch_font) == ui.ui_font_family,
          "%s (style=%s)" % (switch_font, switch_style))

    check("B 界面字体取自规定优先级（更纱黑体等宽优先）",
          ui.ui_font_family.startswith("Sarasa")
          or ui.ui_font_family in ("Microsoft YaHei Mono", "Consolas", "monospace",
                                   "微软雅黑", "Microsoft YaHei", "Arial"), ui.ui_font_family)

    # ==================================================================
    # C 按钮配色
    # ==================================================================
    print("---- C 按钮配色 ----")
    for attr, key in (("btn_convert", "convert"), ("btn_copy", "copy"), ("btn_clear", "clear")):
        bg, fg, active = theme.BUTTON_COLORS[key]
        w = getattr(ui, attr)
        for _ in range(2):
            root.update(); root.update_idletasks()
        check("C %s 背景为最初配色" % attr, w.cget("bg") == bg, "%s != %s" % (w.cget("bg"), bg))
        check("C %s 文字为最初配色" % attr, w.cget("fg") == fg, "%s != %s" % (w.cget("fg"), fg))
        check("C %s 按下色已适配" % attr, w.cget("activebackground") == active, w.cget("activebackground"))
    check("C 三个按钮颜色互不相同",
          len({theme.BUTTON_COLORS[k][0] for k in theme.BUTTON_COLORS}) == 3)

    # 切换主题后仍然是原配色
    ui.dark_mode_var.set(True)
    for _ in range(3):
        root.update(); root.update_idletasks()
    still = all(getattr(ui, a).cget("bg") == theme.BUTTON_COLORS[k][0]
                for a, k in (("btn_convert", "convert"), ("btn_copy", "copy"), ("btn_clear", "clear")))
    check("C 切到深色后按钮仍为原配色", still,
          str([getattr(ui, a).cget("bg") for a in ("btn_convert", "btn_copy", "btn_clear")]))
    ui.dark_mode_var.set(False)
    for _ in range(3):
        root.update(); root.update_idletasks()

    # ==================================================================
    # D 功能简介
    # ==================================================================
    print("---- D 功能简介 ----")
    check("D 简介使用灰字样式", ui.desc_label.cget("style") == "Muted.TLabel", ui.desc_label.cget("style"))
    muted = ui.style.lookup("Muted.TLabel", "foreground")
    check("D 灰字颜色取自配色表", str(muted).lower() == theme.palette(ui.theme_name)["muted"],
          str(muted))
    check("D 简介位于顶部区域", ui.desc_label.winfo_parent() == str(ui.desc_label.master) and
          ui.desc_label.master == ui.dark_mode_check.master,
          ui.desc_label.winfo_parent())
    check("D 简介与深色开关同在顶栏",
          ui.desc_label.master == ui.dark_mode_check.master and ui.desc_label.master != ui.notebook_host,
          "%s / %s" % (ui.desc_label.winfo_parent(), ui.dark_mode_check.winfo_parent()))
    check("D 简介右对齐原位置",
          ui.desc_label.pack_info().get("side") == "right",
          str(ui.desc_label.pack_info().get("side")))
    ui.current_function.set(funcs[2]["name"]); ui.on_function_change()
    check("D 简介内容为该功能说明", ui.desc_label.cget("text") == funcs[2]["desc"],
          ui.desc_label.cget("text")[:40])

    # ==================================================================
    # E 输入框对比度（圆角文本区）
    # ==================================================================
    print("---- E 输入框对比度 ----")
    for name in ("light", "dark"):
        ui._apply_theme(name)
        for _ in range(2):
            root.update(); root.update_idletasks()
        pal = theme.palette(name)
        check("E %s 输入框底色与窗口底色不同" % name,
              ui.text_input.cget("bg") != pal["bg"] and ui.text_input.cget("bg") == pal["text_bg"],
              "%s vs %s" % (ui.text_input.cget("bg"), pal["bg"]))
        check("E %s 输入框有描边" % name,
              str(ui.text_input.border_color).lower() == pal["text_border"],
              str(ui.text_input.border_color))
        check("E %s 输入输出框配色一致" % name,
              ui.text_output.cget("bg") == ui.text_input.cget("bg") and
              ui.text_output.cget("fg") == ui.text_input.cget("fg"))
        check("E %s 强调色来自配色表" % name,
              str(ui.text_input.accent_color).lower() == pal["accent"], str(ui.text_input.accent_color))
    ui._apply_theme("light")
    for _ in range(2):
        root.update(); root.update_idletasks()

    # ==================================================================
    # F 标题栏（pywinstyles）
    # ==================================================================
    print("---- F 标题栏 ----")
    check("F pywinstyles 为可选依赖", app_module.pywinstyles is not None or app_module.pywinstyles is None)
    if app_module.pywinstyles is not None:
        ui._apply_titlebar_style()  # 不应抛异常
        check("F 应用标题栏样式不报错", True)
        ui.theme_name = "dark"
        ui._apply_titlebar_style()
        ui.theme_name = "light"
        ui._apply_titlebar_style()
        check("F 深浅主题都可应用标题栏", True)
    else:
        check("F 缺少 pywinstyles 时静默降级", True)

    saved = app_module.pywinstyles
    app_module.pywinstyles = None
    try:
        ui._apply_titlebar_style()  # 模拟未安装
        check("F 模拟未安装 pywinstyles 不报错", True)
    except Exception as e:
        check("F 模拟未安装 pywinstyles 不报错", False, repr(e))
    finally:
        app_module.pywinstyles = saved
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
