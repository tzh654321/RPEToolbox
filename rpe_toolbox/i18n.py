# -*- coding: utf-8 -*-
"""界面文案（多语言）加载与查询。

所有会被用户在界面上看到的文字都存放在 assets/lang/<语言代码>.json 中
（该文件是纯数据，不含任何代码）。本模块只负责读取与查询：

    from .i18n import t, option_values, option_key, function_list

    t("labels.input_json")               -> "输入JSON:"
    t("errors.json_format", err="...")   -> "JSON格式错误: ..."
    option_values("hold_mode")           -> ["无", "5k(常规事件)", "7k(包括缩放)"]
    option_key("hold_mode", "5k(常规事件)") -> "5k"

语言选择优先级：环境变量 RPET_LANG > 默认语言（zh-CN）。
新增语言只需复制一份 json 并翻译其中的值，键名不可修改。
"""

import json
import os
import threading

DEFAULT_LANGUAGE = "zh-CN"

_lock = threading.RLock()
_cache = {}
_language = None


def _candidate_paths(language):
    """语言文件候选路径（打包后 assets 位于 _MEIPASS 解包目录）。"""
    paths = []
    try:
        from . import resources
        paths.append(resources.lang_path(language))
        paths.append(os.path.join(resources.PROJECT_ROOT, "assets", "lang", language + ".json"))
    except Exception:
        pass
    # 未打包时按包路径回溯（rpe_toolbox/../assets/lang）
    here = os.path.dirname(os.path.abspath(__file__))
    paths.append(os.path.join(os.path.dirname(here), "assets", "lang", language + ".json"))
    seen = []
    for p in paths:
        if p and p not in seen:
            seen.append(p)
    return seen


def language():
    """当前语言代码。"""
    return _language or os.environ.get("RPET_LANG") or DEFAULT_LANGUAGE


def set_language(code):
    """切换界面语言（加载失败会抛错，由调用方处理）。"""
    global _language
    _read(code)
    _language = code
    return _language


def available_languages():
    """可用语言代码列表（assets/lang/*.json，默认语言排最前）。"""
    codes = []
    try:
        from . import resources
        directory = resources.LANG_DIR
        if os.path.isdir(directory):
            codes = sorted(f[:-5] for f in os.listdir(directory) if f.endswith(".json"))
    except Exception:
        codes = []
    if DEFAULT_LANGUAGE in codes:
        codes.remove(DEFAULT_LANGUAGE)
        codes.insert(0, DEFAULT_LANGUAGE)
    return codes or [DEFAULT_LANGUAGE]


def language_display(code):
    """语言的显示名（取语言文件里的 _meta.display_name）。"""
    try:
        meta = _dig(load(code), "_meta") or {}
        return meta.get("display_name") or code
    except Exception:
        return code


def function_title(index, name):
    """功能显示名："序号. 名称"——序号由主程序按加载顺序生成，模组文件里不写序号。"""
    return t("app.function_title_format", n=index, name=name)


def _read(language_code):
    """读取某个语言文件的文案字典（按语言代码缓存）。

    只负责「读」，绝不改动当前语言 —— 否则像 language_display() 这种
    「查另一个语言」的调用会把当前语言顺手改掉。
    """
    code = language_code or DEFAULT_LANGUAGE
    with _lock:
        if code in _cache:
            return _cache[code]
        tried = _candidate_paths(code)
        for path in tried:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 功能介绍拆分在 assets/lang/mods/<语言>/<模组key>.json（{"text": ...}），
                # 逐个合并进 help 块；目录缺失或单个文件损坏都不影响主文案。
                try:
                    from . import resources
                    mods_dir = resources.lang_mods_dir(code)
                    if os.path.isdir(mods_dir):
                        help_map = data.setdefault("help", {})
                        for fn in sorted(os.listdir(mods_dir)):
                            if not fn.endswith(".json"):
                                continue
                            try:
                                with open(os.path.join(mods_dir, fn),
                                          "r", encoding="utf-8") as hf:
                                    obj = json.load(hf)
                            except Exception:
                                continue
                            if isinstance(obj, dict) and isinstance(obj.get("text"), str):
                                help_map[fn[:-5]] = obj["text"]
                except Exception:
                    pass
                _cache[code] = data
                return _cache[code]
        raise RuntimeError(
            "未找到界面文案文件（{0}.json），已尝试：\n  {1}\n"
            "请确认 assets/lang 目录随程序一起分发/打包。".format(code, "\n  ".join(tried))
        )


def load(language_code=None):
    """返回指定语言（缺省为当前语言）的文案字典。只读，不改变当前语言。"""
    return _read(language_code or language())


def _dig(data, key):
    node = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def t(text_key, **fmt):
    """取一条文案；缺失时返回键名本身（便于发现未翻译项）。

    参数名不叫 key，避免与文案里的 {key} 占位符冲突（如 dialogs.mod_options_failed）。
    """
    value = _dig(load(), text_key)
    if not isinstance(value, str):
        return text_key
    if fmt:
        try:
            return value.format(**fmt)
        except (KeyError, IndexError, ValueError):
            return value
    return value


def _options(group):
    return _dig(load(), "options." + group) or {}


def option_groups():
    """全部选项组名。"""
    return list((_dig(load(), "options") or {}).keys())


def option_items(group):
    """[(内部键, 显示文字)]，顺序与语言文件一致。"""
    return [(key, text) for key, text in _options(group).items()]


def option_values(group):
    """下拉框可选项（显示文字，按语言文件顺序）。"""
    return [text for _, text in option_items(group)]


def option_key(group, value):
    """把「内部键」或「显示文字」统一解析为内部键；无法识别时原样返回。

    这样调用方既能用内部键（推荐，与语言无关），也兼容历史写法/测试里直接传显示文字。
    """
    if value is None:
        return None
    items = option_items(group)
    for key, text in items:
        if value == key:
            return key
    for key, text in items:
        if value == text:
            return key
    return value


def option_display(group, key):
    """内部键 -> 显示文字；找不到时返回键本身。"""
    for k, text in option_items(group):
        if k == key:
            return text
    return key


def option_int_key(group, value, default=None):
    """数值型内部键（如 rotation / event_type）解析为 int。"""
    key = option_key(group, value)
    try:
        return int(key)
    except (TypeError, ValueError):
        return default


def function_list():
    """功能列表 [{'key':..., 'name':..., 'desc':...}]，顺序即下拉框顺序。"""
    items = _dig(load(), "functions")
    return items if isinstance(items, list) else []


def function_by_name(name):
    """按显示名找功能条目。"""
    for item in function_list():
        if item.get("name") == name:
            return item
    return None


def function_by_key(key):
    """按内部键找功能条目。"""
    for item in function_list():
        if item.get("key") == key:
            return item
    return None


def function_names():
    return [item.get("name", "") for item in function_list()]
