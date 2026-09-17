# -*- coding: utf-8 -*-
"""模组加载：扫描 rpe_toolbox/mods/<功能组>/ 下的 *.py，登记为可切换的功能。

模组契约（示例见 mods/片段处理/polar_conversion.py）：
    MOD_KEY                      与 assets/lang/*.json 里 functions[].key 对应，
                                 功能的显示名/简介/标签短名都取自语言文件
    MOD_ORDER                    组内排序（可选，缺省 50）；序号由主程序按加载顺序生成，
                                 模组文件里不写序号，因此启用不同数量的模组时会自动重排
    build_options(app, parent)   可选：在标签页里创建该功能的选项控件
    process(app, data, *args)    必需：执行转换并返回结果

约束与容错：
  * 模组之间不互相调用；公共辅助放 rpe_toolbox/shared.py 等主程序模块
  * 加载失败的模组会被跳过并记进 LOAD_ERRORS，不影响其它模组（任意数量都能启动）
"""

import importlib.util
import os
import sys
import traceback

MODS_DIRNAME = "mods"
DEFAULT_ORDER = 50
LOAD_ERRORS = []

_cache = {}


class ModInfo(object):
    """一个模组的登记信息。"""

    def __init__(self, key, group, order, path, module):
        self.key = key
        self.group = group
        self.order = order
        self.path = path
        self.module = module
        self.build_options = getattr(module, "build_options", None)
        self.process = getattr(module, "process", None)

    def __repr__(self):
        return "<ModInfo %s (%s)>" % (self.key, self.group)


def mods_root():
    """模组根目录 rpe_toolbox/mods。

    打包成 exe 后模组的 .py 源文件不在 _MEIPASS 里（那里只有编译产物），
    所以冻结时若 **exe 同级**存在 rpe_toolbox/mods 目录就优先用它 —— 加模组不用重新打包。
    """
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), MODS_DIRNAME)
    if getattr(sys, "frozen", False) and not os.path.isdir(root):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidate = os.path.join(exe_dir, "rpe_toolbox", MODS_DIRNAME)
        if os.path.isdir(candidate):
            return candidate
    return root


def list_groups():
    """功能组名列表（= mods 下的文件夹名，忽略 _ / . 开头的）。"""
    root = mods_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        name for name in os.listdir(root)
        if not name.startswith(("_", ".")) and os.path.isdir(os.path.join(root, name))
    )


def _load_module(path, mod_name):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError("无法加载 %s" % path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_group_dir(group):
    """加载一个功能组目录下的全部模组（单个失败只跳过它）。"""
    group_dir = os.path.join(mods_root(), group)
    mods = []
    if not os.path.isdir(group_dir):
        return mods
    for file_name in sorted(os.listdir(group_dir)):
        if not file_name.endswith(".py") or file_name.startswith(("_", ".")):
            continue
        path = os.path.join(group_dir, file_name)
        try:
            module = _load_module(path, "rpe_toolbox_mod_%s_%s" % (group, file_name[:-3]))
        except Exception:
            LOAD_ERRORS.append((path, traceback.format_exc()))
            continue
        key = getattr(module, "MOD_KEY", None)
        process = getattr(module, "process", None)
        if not key or not callable(process):
            LOAD_ERRORS.append((path, "缺少 MOD_KEY 或 process()"))
            continue
        order = getattr(module, "MOD_ORDER", DEFAULT_ORDER)
        mods.append(ModInfo(key, group, order, path, module))
    mods.sort(key=lambda m: (m.order, os.path.basename(m.path)))
    return mods


def discover(force=False):
    """{功能组: [ModInfo, ...]}，结果缓存；force=True 时重新扫描。"""
    if _cache.get("groups") is not None and not force:
        return _cache["groups"]
    groups = {}
    del LOAD_ERRORS[:]
    for group in list_groups():
        groups[group] = load_group_dir(group)
    _cache["groups"] = groups
    return groups


def default_group(groups=None):
    """默认功能组：优先"片段处理"，否则第一个。"""
    groups = groups if groups is not None else discover()
    for name in ("片段处理",):
        if name in groups:
            return name
    return next(iter(groups), None)


def all_mods(force=False):
    """所有模组（按组顺序展开）。"""
    out = []
    for mods in discover(force).values():
        out.extend(mods)
    return out


def find(key, force=False):
    """按 MOD_KEY 找模组。"""
    for mod in all_mods(force):
        if mod.key == key:
            return mod
    return None


def install_legacy_methods(cls, force=False):
    """把每个模组的 process 挂成 cls 上的 func_<MOD_KEY>，兼容既有调用名。

    旧代码/测试里会写 app.func_polar_conversion(data, density)，
    这里生成的适配器允许额外的位置参数（多余参数原样转给 process）。
    """
    installed = []
    for mod in all_mods(force):
        name = "func_" + mod.key

        def make(mod=mod):
            def method(self, data, *args, **kwargs):
                return mod.process(self, data, *args, **kwargs)
            method.__name__ = "func_" + mod.key
            method.__doc__ = getattr(mod.process, "__doc__", None)
            return method

        setattr(cls, name, make())
        installed.append(name)
    return installed
