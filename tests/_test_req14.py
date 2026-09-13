# -*- coding: utf-8 -*-
"""需求十四验证：极坐标旋转事件不切割 + 界面文案全量外置 + DPI/主题基建。

覆盖点
  A 极坐标转换：旋转事件原样复制输入（不再按密度切割），且仍参与 r/θ 换算
  B 文案文件：键齐全、取值正确、未知键降级返回键名
  C 代码中不再残留界面文案（AST 扫描中文字符串字面量，仅允许字体名等白名单）
  D DPI 模块：导入不引入 tkinter、可三级回退启用、缩放换算正确
  E 主题与配置：主题名归一化、环境变量/配置文件优先级、切换不报错
"""
import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 隔离用户配置：主题切换会写 %APPDATA%/RPEToolbox/config.json，测试期间重定向到临时目录，
# 结束时还原，避免污染本机真实配置（否则下次启动会继承测试选择的主题）。
_CFG_TMP = tempfile.mkdtemp(prefix="rpet_cfg_")
_OLD_APPDATA = os.environ.get("APPDATA")
os.environ["APPDATA"] = _CFG_TMP


def cleanup_config():
    if _OLD_APPDATA is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _OLD_APPDATA
    shutil.rmtree(_CFG_TMP, ignore_errors=True)


from rpe_toolbox import config, dpi, i18n, resources, theme  # noqa: E402
from rpe_toolbox.core import FunctionMixin  # noqa: E402

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


app = object.__new__(FunctionMixin)


def mk(start_t, end_t, s, e, typ, **kw):
    d = {"type": typ, "line": 1, "layer": 0, "linkgroup": 0, "bezier": 0,
         "bezierPoints": [0.0, 0.0, 0.0, 0.0], "easingType": 1,
         "easingLeft": 0.0, "easingRight": 1.0,
         "startTime": start_t, "endTime": end_t, "start": s, "end": e}
    d.update(kw)
    return d


# ======================================================================
# A 极坐标转换：旋转事件不切割
# ======================================================================
print("---- A 极坐标转换：旋转事件原样复制 ----")

rot_long = mk([0, 0, 1], [8, 0, 1], 90.0, 270.0, 3,
              easingType=5, easingLeft=0.25, easingRight=0.75, line=3, layer=2)
x_ev = mk([0, 0, 1], [4, 0, 1], 0.0, 100.0, 1)

for density in (4, 16):
    out = app.func_polar_conversion({"events": [dict(x_ev), dict(rot_long)]}, density)
    rots = [e for e in out["events"] if e["type"] == 3]
    xs = [e for e in out["events"] if e["type"] in (1, 2)]
    check("A 密度%d 旋转事件数量与输入一致(1)" % density, len(rots) == 1, "got %d" % len(rots))
    check("A 密度%d 旋转事件内容与输入完全一致" % density, rots[0] == rot_long, str(rots[0])[:80])
    check("A 密度%d X/Y 仍按密度切割" % density, len(xs) >= 2, "got %d" % len(xs))

rots_out = out["events"][len(out["events"]) - 1]
check("A 旋转事件保留 easingType/easingLeft/Right/line/layer",
      (rots_out["easingType"], rots_out["easingLeft"], rots_out["easingRight"],
       rots_out["line"], rots_out["layer"]) == (5, 0.25, 0.75, 3, 2),
      str(rots_out))

# 旋转仍参与换算：旋转恒为 90°，X 事件 0->100 线性，则输出 X 段应等于 |X|（90° ⇒ sin=1）
out2 = app.func_polar_conversion({"events": [
    mk([0, 0, 1], [4, 0, 1], 0.0, 100.0, 1),
    mk([0, 0, 1], [4, 0, 1], 90.0, 90.0, 3),
]}, 4)
x_segs = [e for e in out2["events"] if e["type"] == 1 and abs(e["end"] - e["start"]) > 1e-6]
check("A 旋转仍参与换算（90° ⇒ 输出 X = |距离|）",
      len(x_segs) >= 1 and abs(x_segs[-1]["end"] - 100.0) < 1e-6,
      str([(e["start"], e["end"]) for e in x_segs]))

# 输入中没有旋转事件时，输出也不应凭空产生
out3 = app.func_polar_conversion({"events": [mk([0, 0, 1], [4, 0, 1], 100.0, 100.0, 1)]}, 4)
check("A 无旋转输入时输出无旋转事件", [e for e in out3["events"] if e["type"] == 3] == [])


# ======================================================================
# B 文案文件完整性
# ======================================================================
print("---- B 界面文案文件 ----")

lang_file = resources.lang_path("zh-CN")
check("B 文案文件位于 assets/lang/zh-CN.json", os.path.exists(lang_file), lang_file)
with io.open(lang_file, encoding="utf-8") as f:
    raw = f.read()
parsed = None
try:
    parsed = json.loads(raw)
except Exception as e:  # pragma: no cover
    pass
check("B 文案文件是合法 JSON", parsed is not None)
check("B 文案文件不含代码（无 import/def/函数调用）",
      parsed is not None and not re.search(r"\b(import|def|lambda|return)\b", raw))

check("B t() 取窗口标题", i18n.t("app.title") == "rpe工具箱", i18n.t("app.title"))
check("B t() 取标签", i18n.t("labels.input_json") == "输入JSON:", i18n.t("labels.input_json"))
check("B t() 支持占位符", i18n.t("errors.json_format", err="X") == "JSON格式错误: X",
      i18n.t("errors.json_format", err="X"))
check("B 未知键降级为键名", i18n.t("not.exists.key") == "not.exists.key")
check("B 错误前缀", i18n.t("app.error_prefix").startswith("【错误】"), i18n.t("app.error_prefix"))

funcs = i18n.function_list()
check("B 功能列表 8 项", len(funcs) == 8, "got %d" % len(funcs))
check("B 功能 key 唯一且非空",
      len({f["key"] for f in funcs}) == len(funcs) and all(f.get("key") for f in funcs))
check("B 功能均有名称与说明", all(f.get("name") and f.get("desc") for f in funcs))
check("B function_by_key 可反查",
      (i18n.function_by_key("polar_conversion") or {}).get("key") == "polar_conversion")

check("B 事件类型选项 1~7 齐全",
      [k for k, _ in i18n.option_items("event_type")] == ["1", "2", "3", "4", "5", "6", "7"],
      str([k for k, _ in i18n.option_items("event_type")]))
check("B option_key 接受显示文字", i18n.option_key("hold_mode", "5k(常规事件)") == "5k")
check("B option_key 接受内部键", i18n.option_key("hold_mode", "5k") == "5k")
check("B option_key 接受颜色模式显示文字", i18n.option_key("color_mode", "染色") == "tint")
check("B option_int_key 解析旋转度数", i18n.option_int_key("rotation", "90°") == 90)
check("B option_key 未知值原样返回", i18n.option_key("hold_mode", "???") == "???")
check("B option_display 内部键转显示", i18n.option_display("drag_mode", "x") == "X轴位移与缩放")

# 所有文案叶子节点必须是非空字符串
leaves = []


def collect(node, path=""):
    if isinstance(node, dict):
        for k, v in node.items():
            if str(k).startswith("_"):
                continue
            collect(v, path + "/" + str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect(v, path + "/%d" % i)
    else:
        leaves.append((path, node))


collect(parsed)
bad = [p for p, v in leaves if not isinstance(v, str) or not v.strip()]
check("B 文案叶子均为非空字符串", not bad, str(bad[:5]))

# 界面实际用到的键必须都能取到（避免漏抽）；(?<![\w.]) 避免误匹配 data.get("events") 之类
used_keys = set()
for name in ("app.py", "core.py"):
    with io.open(os.path.join(BASE, "rpe_toolbox", name), encoding="utf-8") as f:
        used_keys |= set(re.findall(r'(?<![\w.])t\("([a-zA-Z0-9_.]+)"', f.read()))
missing = sorted(k for k in used_keys if i18n.t(k) == k)
check("B 代码引用的文案键均存在", not missing, "missing=%s" % missing)
check("B 事件类型转换的行文字符存在", i18n.t("labels.arrow") == "→", i18n.t("labels.arrow"))


# ======================================================================
# C 代码中不再残留界面文案
# ======================================================================
print("---- C 代码内无残留文案 ----")

MODULES = ["app.py", "core.py", "dpi.py", "theme.py", "config.py",
           "resources.py", "easing.py", "imglib.py", "__init__.py", "launcher.py"]
# 允许的非界面文字：字体族名。launcher/RPET.py 属启动脚本，不在检查范围
ALLOWED = {"微软雅黑"}


def cjk_literals(path):
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            if re.search(r"[一-鿿]", node.value) and node.value not in ALLOWED:
                hits.append((node.lineno, node.value[:60]))
    return hits


leftover = {}
for name in MODULES:
    hits = cjk_literals(os.path.join(BASE, "rpe_toolbox", name))
    if hits:
        leftover[name] = hits
check("C rpe_toolbox 各模块无残留界面文案", not leftover, str(leftover))

# i18n.py 自身只允许一条“文案文件缺失”的引导性报错（该文件缺失时无法从语言文件取文案）
i18n_hits = cjk_literals(os.path.join(BASE, "rpe_toolbox", "i18n.py"))
check("C i18n.py 仅保留文案文件缺失报错", len(i18n_hits) == 1, str(i18n_hits))


# ======================================================================
# D DPI 模块
# ======================================================================
print("---- D DPI 模块 ----")

probe = (
    "import sys;"
    "import rpe_toolbox;"
    "a = 'tkinter' in sys.modules;"
    "from rpe_toolbox import dpi;"
    "b = 'tkinter' in sys.modules;"
    "print(a, b)"
)
result = subprocess.run([sys.executable, "-c", probe], cwd=BASE,
                        capture_output=True, text=True, encoding="utf-8")
check("D 导入 rpe_toolbox / dpi 不会引入 tkinter（DPI 感知可先行启用）",
      result.returncode == 0 and result.stdout.strip() == "False False",
      "rc=%s out=%r err=%r" % (result.returncode, result.stdout, result.stderr[-200:]))

lazy = subprocess.run(
    [sys.executable, "-c",
     "import sys; import rpe_toolbox; _ = rpe_toolbox.RPEToolbox; print('tkinter' in sys.modules)"],
    cwd=BASE, capture_output=True, text=True, encoding="utf-8")
check("D 惰性属性 rpe_toolbox.RPEToolbox 仍可用", lazy.returncode == 0 and lazy.stdout.strip() == "True",
      "rc=%s out=%r err=%r" % (lazy.returncode, lazy.stdout, lazy.stderr[-200:]))

check("D system_dpi 返回合理值", dpi.system_dpi() >= 96, str(dpi.system_dpi()))
check("D dpi_scale 与 system_dpi 一致", abs(dpi.dpi_scale() - dpi.system_dpi() / 96.0) < 1e-9)
check("D enable_dpi_awareness 返回布尔不抛异常", isinstance(dpi.enable_dpi_awareness(), bool))


# ======================================================================
# E 主题与配置
# ======================================================================
print("---- E 主题与配置 ----")

check("E 主题名归一化", theme.normalize("sun-valley-dark") == "dark"
      and theme.normalize("LIGHT") == "light" and theme.normalize("???") == theme.DEFAULT_THEME)
check("E 默认主题为浅色", theme.DEFAULT_THEME == "light", theme.DEFAULT_THEME)
check("E 两套配色不同", theme.palette("light")["text_bg"] != theme.palette("dark")["text_bg"])
check("E other() 互为反向", theme.other("light") == "dark" and theme.other("dark") == "light")
check("E 配色键齐全",
      all(k in theme.palette(n) for n in theme.THEMES
          for k in ("bg", "fg", "muted", "text_bg", "text_fg", "error")))

old_env = os.environ.get("RPET_THEME")
os.environ["RPET_THEME"] = "dark"
check("E 环境变量 RPET_THEME 优先", config.resolve_theme() == "dark", config.resolve_theme())

# 配置持久化（APPDATA 已在文件顶部重定向到临时目录）
os.environ.pop("RPET_THEME", None)
try:
    check("E 无配置时默认浅色", config.resolve_theme() == "light", config.resolve_theme())
    check("E 保存主题成功", config.save_theme("dark"))
    check("E 读取到已保存主题", config.load_config().get("theme") == "dark", str(config.load_config()))
    check("E 配置生效", config.resolve_theme() == "dark", config.resolve_theme())
    os.environ["RPET_THEME"] = "light"
    check("E 环境变量仍覆盖配置", config.resolve_theme() == "light", config.resolve_theme())
finally:
    os.environ.pop("RPET_THEME", None)
    if old_env is not None:
        os.environ["RPET_THEME"] = old_env


# ======================================================================
# F 界面：主题切换
# ======================================================================
print("---- F 界面主题切换 ----")
try:
    import tkinter as tk

    from rpe_toolbox.app import RPEToolbox

    config.save_theme("light")  # 复位配置，验证"默认浅色启动"
    root = tk.Tk()
    root.withdraw()
    ui = RPEToolbox(root)
    check("F 启动主题读自配置（浅色）", ui.theme_name == "light", ui.theme_name)
    light_bg = ui.text_input.cget("bg")
    ui.dark_mode_var.set(True)
    check("F 切到深色", ui.theme_name == "dark", ui.theme_name)
    dark_bg = ui.text_input.cget("bg")
    check("F 文本框配色随主题变化", light_bg != dark_bg, "%s -> %s" % (light_bg, dark_bg))
    check("F 深色下错误色为浅红", ui.error_fg == theme.palette("dark")["error"], ui.error_fg)
    ui.dark_mode_var.set(False)
    check("F 切回浅色", ui.theme_name == "light" and ui.text_input.cget("bg") == light_bg)
    check("F 主题选择已持久化到配置", config.load_config().get("theme") == "light", str(config.load_config()))
    check("F 主题开关与勾选框状态同步", ui.dark_mode_check.cget("text") == i18n.t("labels.dark_mode"))
    check("F 定轨hold默认显示文字为“无”",
          ui.hold_mode_var.get() == i18n.option_display("hold_mode", "none"), ui.hold_mode_var.get())
    check("F UI 内部键解析：曲线drag默认 none",
          i18n.option_key("drag_mode", ui.drag_mode_var.get()) == "none")
    # 高分屏：窗口与内边距按 DPI 缩放，且不超出屏幕
    check("F 窗口尺寸按 DPI 缩放",
          ui.px(680) == int(round(680 * ui.ui_scale)) and ui.px(0) == 0, str(ui.ui_scale))
    check("F 窗口不超过屏幕",
          root.winfo_width() <= root.winfo_screenwidth() and root.winfo_height() <= root.winfo_screenheight(),
          "%dx%d" % (root.winfo_width(), root.winfo_height()))
    root.destroy()
except Exception as e:  # pragma: no cover
    check("F 界面主题切换", False, repr(e))

cleanup_config()

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
sys.exit(1 if fail else 0)
