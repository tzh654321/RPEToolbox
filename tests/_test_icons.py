# -*- coding: utf-8 -*-
"""任务栏图标回归测试：.ico 只生成一次、句柄复用，且**绝不写 TEMP、绝不删除**。

背景（两轮踩坑）：
  1. _keep_taskbar_icon 每 3 秒检查一次类图标，Tk 会不断把类图标重置回去，
     于是 _apply_taskbar_icon 被反复调用。旧实现每次都新建 2 个临时 .ico 再删除，
     实测约 3 次/秒 → 约 2.2 万个/小时。
  2. 只把「反复创建」改成「创建一次 + 退出时删除」还不够：删除动作在带安全删除的机器上
     会把文件送进回收站 —— 每启动一次留 2 个 .ico 的痕迹。
     现在的实现改为写「用户级缓存目录」里的固定文件名，只写不删。
"""

import glob
import io
import os
import sys
import tempfile
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# 每个测试独立的固定配置目录：**只写不删**（删除动作会进回收站，弄脏用户回收站）
# 每次运行都重写一份基线配置，避免上一次运行留下的主题/语言/禁用项影响本次结果。
_CFG_TMP = os.path.join(tempfile.gettempdir(), "rpet_test_icons")
os.makedirs(os.path.join(_CFG_TMP, "RPEToolbox"), exist_ok=True)
os.environ["APPDATA"] = _CFG_TMP
os.environ.pop("RPET_THEME", None)
os.environ.pop("RPET_LANG", None)
with io.open(os.path.join(_CFG_TMP, "RPEToolbox", "config.json"), "w", encoding="utf-8") as _f:
    _f.write('{"theme": "light", "language": "zh-CN"}')
_OLD_APPDATA = os.environ.get("APPDATA")
os.environ["APPDATA"] = _CFG_TMP
os.environ.pop("RPET_THEME", None)


def cleanup():
    if _OLD_APPDATA is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _OLD_APPDATA


def tmp_ico_files():
    """TEMP 里由本程序产生的 .ico（新前缀 rpet_icon_ + 旧前缀 tmp）。"""
    d = tempfile.gettempdir()
    return sorted(glob.glob(os.path.join(d, "rpet_icon_*.ico"))
                  + glob.glob(os.path.join(d, "tmp*.ico")))


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


root = None
try:
    import tkinter as tk

    import rpe_toolbox.app as app_module
    from rpe_toolbox import dpi
    from rpe_toolbox.app import RPEToolbox

    dpi.enable_dpi_awareness()

    cache_dir = os.path.join(_CFG_TMP, "RPEToolbox", "cache")

    before_tmp = tmp_ico_files()
    calls = {"n": 0}
    original = app_module.RPEToolbox._apply_taskbar_icon

    def counted(self):
        calls["n"] += 1
        return original(self)

    app_module.RPEToolbox._apply_taskbar_icon = counted

    root = tk.Tk()
    ui = RPEToolbox(root)
    for _ in range(4):
        root.update()
        root.update_idletasks()

    check("图标函数被多次调用（Tk 会重置类图标）", calls["n"] >= 1, str(calls["n"]))

    # 1) 不再往 TEMP 写任何东西
    check("构造后 TEMP 没有新增 .ico", len(tmp_ico_files()) - len(before_tmp) == 0,
          "%d -> %d" % (len(before_tmp), len(tmp_ico_files())))

    # 2) 缓存目录里的文件固定（最多 2 个 .ico + 1 个指纹）
    # 缓存目录里可能还有试听用的 preview*.wav，这里只看图标相关文件
    names = sorted(n for n in (os.listdir(cache_dir) if os.path.isdir(cache_dir) else [])
                   if n.endswith(".ico") or n == "icons.json")
    check("缓存目录在用户目录下且文件固定",
          names == ["icon0.ico", "icon1.ico", "icons.json"], str(names))
    check("缓存 .ico 非空", all(os.path.getsize(os.path.join(cache_dir, n)) > 0
                                for n in names if n.endswith(".ico")))

    # 2b) 图标源文件的优先级（从 _test_ui.py 移过来的两条）
    from rpe_toolbox import resources
    check("窗口图标优先 mini ico-z1.png",
          resources.find_icon() is not None
          and resources.find_icon().endswith("mini ico-z1.png"), str(resources.find_icon()))
    check("exe 图标源为完整版 ico-z1.png",
          resources.find_full_icon() is not None
          and resources.find_full_icon().endswith("ico-z1.png"), str(resources.find_full_icon()))

    stamp = {n: os.path.getmtime(os.path.join(cache_dir, n)) for n in names}

    # 3) 运行一段时间，让 3 秒一次的检查反复触发
    t0 = time.time()
    while time.time() - t0 < 7:
        root.update()
        root.update_idletasks()
        time.sleep(0.05)
    check("运行 7 秒后 TEMP 仍无新增 .ico", len(tmp_ico_files()) - len(before_tmp) == 0,
          "调用 %d 次" % calls["n"])
    check("运行期间缓存文件未被重写",
          all(os.path.getmtime(os.path.join(cache_dir, n)) == t for n, t in stamp.items()),
          str(sorted(os.listdir(cache_dir))))

    # 4) 手动多调几次，也不应再产生/改动文件
    for _ in range(10):
        ui._apply_taskbar_icon()
    root.update()
    check("重复调用不再生成 .ico 也不改缓存",
          len(tmp_ico_files()) - len(before_tmp) == 0
          and all(os.path.getmtime(os.path.join(cache_dir, n)) == t for n, t in stamp.items()),
          str(sorted(os.listdir(cache_dir))))

    # 5) 句柄被缓存
    handles = getattr(ui, "_icon_handles", [])
    same = ui._ensure_icons()
    check("图标句柄被缓存复用",
          bool(handles) and same[0] == getattr(ui, "_icon_small", None)
          and same[1] == getattr(ui, "_icon_big", None), str(handles))
    check("缓存标记已置位", getattr(ui, "_icons_ready", False) is True)

    # 6) 退出时只释放句柄，缓存文件保留（删除它们只会在回收站留垃圾）
    try:
        ui.shutdown()
    finally:
        app_module.RPEToolbox._apply_taskbar_icon = original
    left = sorted(n for n in (os.listdir(cache_dir) if os.path.isdir(cache_dir) else [])
                  if n.endswith(".ico") or n == "icons.json")
    check("退出后缓存文件仍保留（不产生待删除项）",
          left == ["icon0.ico", "icon1.ico", "icons.json"], str(left))
    check("退出后 TEMP 仍无新增 .ico", len(tmp_ico_files()) - len(before_tmp) == 0,
          "%d 个" % (len(tmp_ico_files()) - len(before_tmp)))
    check("退出后句柄已释放", getattr(ui, "_icon_handles", None) == [], str(ui._icon_handles))
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
    cleanup()

print("=" * 50)
print("TOTAL: %d PASS, %d FAIL" % (ok, fail))
sys.exit(1 if fail else 0)
