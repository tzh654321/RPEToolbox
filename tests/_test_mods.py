# -*- coding: utf-8 -*-
"""模组系统回归测试（第十五轮模组化）。

守住两类问题：
  A 静态：模组里把「本文件内的模块级函数」当成 app 的方法调用（app.xxx）。
    这类写法在旧 app.py 里是 self.xxx，自动切分后必然留下 app.xxx，
    但 app 上没有同名方法 —— 运行到就 AttributeError，选项界面建不出来。
  B 运行：真正把界面建起来，确认每个模组的 build_options 都没抛异常
    （曾出现「模组 image_to_notes 的选项界面创建失败」启动弹窗）。

直接跑：python tests/_test_mods.py
"""

import io
import os
import re
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 配置/语言相关写入重定向到临时目录，避免污染真实用户配置
# 每个测试独立的固定配置目录：**只写不删**（删除动作会进回收站，弄脏用户回收站）
# 每次运行都重写一份基线配置，避免上一次运行留下的主题/语言/禁用项影响本次结果。
_TMP = os.path.join(tempfile.gettempdir(), "rpet_test_mods")
os.makedirs(os.path.join(_TMP, "RPEToolbox"), exist_ok=True)
os.environ["APPDATA"] = _TMP
os.environ.pop("RPET_THEME", None)
os.environ.pop("RPET_LANG", None)
with io.open(os.path.join(_TMP, "RPEToolbox", "config.json"), "w", encoding="utf-8") as _f:
    _f.write('{"theme": "light", "language": "zh-CN"}')
os.environ["APPDATA"] = _TMP
os.environ.pop("RPET_THEME", None)
os.environ.pop("RPET_LANG", None)

from rpe_toolbox import i18n, mods_loader  # noqa: E402

ok = 0
fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print("  PASS  %s" % name)
    else:
        fail += 1
        print("  FAIL  %s  %s" % (name, detail))


# ======================================================================
# A 静态：模组里不得把「本模组的模块级函数」当作 app 的方法使用
# ======================================================================
print("---- A 模组内函数调用写法 ----")

# RPEToolbox 类上真实存在的方法/属性
import rpe_toolbox.app as app_module  # noqa: E402

class_attrs = set(dir(app_module.RPEToolbox))

mod_files = []
for group in mods_loader.list_groups():
    group_dir = os.path.join(mods_loader.mods_root(), group)
    for name in sorted(os.listdir(group_dir)):
        if name.endswith(".py") and not name.startswith(("_", ".")):
            mod_files.append((group, name, os.path.join(group_dir, name)))

check("发现模组文件", len(mod_files) >= 9, "只找到 %d 个" % len(mod_files))

for group, name, path in mod_files:
    src = io.open(path, encoding="utf-8").read()
    # 本文件里定义为 def X(app, ...) 的模块级函数
    mod_funcs = set(re.findall(r"^def (\w+)\(app", src, re.M))
    # 被写成 app.X 的引用
    refs = set(re.findall(r"\bapp\.(\w+)", src))
    bad = sorted((refs & mod_funcs) - class_attrs)
    check("A %s 不把本模组函数当 app 方法用" % name, not bad,
          "这些应写成 fn(app)：%s" % bad)

# 需要文件对话框按钮的模组，回调必须能取到
print("---- A2 文件选择回调可用 ----")
IMAGE_MOD = os.path.join(mods_loader.mods_root(), "片段处理", "image_to_notes.py")
MIDI_MOD = os.path.join(mods_loader.mods_root(), "片段处理", "midi_bpm.py")
for path, func_name in ((IMAGE_MOD, "select_image_file"), (MIDI_MOD, "select_midi_file")):
    src = io.open(path, encoding="utf-8").read()
    check("%s 定义了 %s" % (os.path.basename(path), func_name),
          re.search(r"^def %s\(app" % func_name, src, re.M) is not None)
    # 不允许直接写 command=app.xxx（app 上没这个方法）
    check("%s 的回调不写 app.%s" % (os.path.basename(path), func_name),
          not re.search(r"command=app\.%s\b" % func_name, src))


# ======================================================================
# B 运行：全部模组的选项界面都要能建起来
# ======================================================================
print("---- B 选项界面构建 ----")

try:
    import tkinter as tk

    from rpe_toolbox import dpi

    dpi.enable_dpi_awareness()
    root = tk.Tk()
    root.withdraw()
    ui = app_module.RPEToolbox(root)
    for _ in range(3):
        root.update()
        root.update_idletasks()

    check("B 启动时无模组选项界面构建失败", not ui.mod_build_errors,
          "；".join("%s: %s" % (k, d.splitlines()[-1]) for k, d in ui.mod_build_errors))

    # 逐个功能组、每个标签页都切一遍，确保构建期异常不藏在别的组里
    for group in ui.group_names():
        ui.switch_group(group)
        for _ in range(3):
            root.update()
            root.update_idletasks()
        check("B %s 组无构建失败" % group, not ui.mod_build_errors,
              "；".join("%s: %s" % (k, d.splitlines()[-1]) for k, d in ui.mod_build_errors))

    # 切语言会重建全部标签页，同样不能失败
    ui.switch_group(mods_loader.default_group())
    for code in ("en-US", "zh-CN"):
        ui.switch_language(code)
        for _ in range(2):
            root.update()
            root.update_idletasks()
        check("B 切到 %s 后无构建失败" % code, not ui.mod_build_errors,
              "；".join("%s: %s" % (k, d.splitlines()[-1]) for k, d in ui.mod_build_errors))

    # ==================================================================
    # B2 语言切换真的生效（曾出现「切了立刻被拉回中文」）
    # ==================================================================
    print("---- B2 语言切换 ----")
    zh = i18n.t("labels.input_json")
    ui.switch_language("zh-CN")
    for _ in range(2):
        root.update(); root.update_idletasks()
    zh_tabs = [ui.notebook.tab(i, "text") for i in range(ui.notebook.index("end"))]

    ui.switch_language("en-US")
    for _ in range(2):
        root.update(); root.update_idletasks()
    en_tabs = [ui.notebook.tab(i, "text") for i in range(ui.notebook.index("end"))]
    check("B2 切语言后当前语言变了", i18n.language() == "en-US", i18n.language())
    check("B2 切语言后文案跟着变", i18n.t("labels.input_json") != zh,
          "%r vs %r" % (i18n.t("labels.input_json"), zh))
    check("B2 切语言后标签文字跟着变", en_tabs != zh_tabs,
          "%s vs %s" % (en_tabs, zh_tabs))

    # 查别的语言（菜单里列语言名）不能把当前语言改掉
    for code in i18n.available_languages():
        i18n.language_display(code)
    check("B2 查其它语言名不会改变当前语言", i18n.language() == "en-US", i18n.language())

    ui.switch_language("zh-CN")
    for _ in range(2):
        root.update(); root.update_idletasks()
    check("B2 切回中文恢复", [ui.notebook.tab(i, "text")
                              for i in range(ui.notebook.index("end"))] == zh_tabs,
          str([ui.notebook.tab(i, "text") for i in range(ui.notebook.index("end"))]))
    check("B2 切回中文后语言正确", i18n.language() == "zh-CN", i18n.language())

    # 文件选择按钮确实能点开对话框（原来这里指向不存在的 app 方法，一点就 AttributeError）
    import tkinter.filedialog as _fd

    _orig_askopen = _fd.askopenfilename
    _calls = []
    _fd.askopenfilename = lambda **kw: (_calls.append(kw), "")[1]
    try:
        for key, attr in (("image_to_notes", "btn_select_image"),
                          ("midi_bpm_extract", "btn_select_midi")):
            btn = getattr(ui, attr, None)
            check("B %s 的 %s 已创建" % (key, attr), btn is not None, repr(btn))
            if btn is None:
                continue
            before = len(_calls)
            try:
                btn.invoke()
                root.update_idletasks()
                err = ""
            except Exception as e:  # 回调内部炸了
                err = repr(e)
            check("B %s 的 %s 点击可打开对话框" % (key, attr),
                  not err and len(_calls) == before + 1,
                  "err=%s calls=%s->%s" % (err, before, len(_calls)))
    finally:
        _fd.askopenfilename = _orig_askopen

    # 每个模组的 process 都必须存在且可调用
    for mod in mods_loader.all_mods():
        check("B 模组 %s 有 process" % mod.key, callable(mod.process))

    # 标签页数量与当前组的模组数一致（禁用项除外）
    ui.switch_group(mods_loader.default_group())
    for _ in range(2):
        root.update()
        root.update_idletasks()
    expected = len([m for m in mods_loader.discover()[mods_loader.default_group()]
                    if m.key not in ui.disabled_keys])
    check("B 标签页数与模组数一致", ui.notebook.index("end") == expected,
          "%s vs %s" % (ui.notebook.index("end"), expected))

    root.destroy()
except Exception as e:  # pragma: no cover
    import traceback as _tb
    _tb.print_exc()
    check("B 界面构建", False, repr(e))


print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
sys.exit(1 if fail else 0)
