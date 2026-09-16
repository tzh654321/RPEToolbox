# -*- coding: utf-8 -*-
"""音效播放与音频合成。

设计取舍：**不依赖第三方库**。
原先用 pygame 播 .ogg，但 pygame 只装在某个特定解释器里（换一个 python 启动就静默无声），
所以改为：
  * 素材统一用 WAV（assets/audio/*.wav，由同名 .ogg 转换而来），
    用标准库 `winsound` 异步播放 —— 任何 Python 3 在 Windows 上都有；
  * 需要即时合成的音（纵连音高的锯齿波试听）在 Python 里生成 PCM，
    写进用户缓存目录里的固定文件再播（**只写不删**，避免污染回收站）。

非 Windows 平台退化为静默（可选回退 pygame），绝不影响主功能。
"""

import array
import os
import wave

from . import resources

# 按钮音效：内部键 → 文件名
SOUND_FILES = {
    "convert": "click1.wav",
    "copy": "click2.wav",
    "clear": "click3.wav",
    "convert_error": "click4.wav",
}

# 试听用的轮转文件名：同一时刻不会去覆盖正在播放的那一个
_PREVIEW_SLOTS = 4
_preview_index = 0

_warned = False


def _winsound():
    try:
        import winsound
        return winsound
    except Exception:
        return None


def available():
    """当前环境能否播放声音（供测试与界面判断）。"""
    if os.name == "nt" and _winsound() is not None:
        return True
    try:
        import pygame  # noqa: F401
        return True
    except Exception:
        return False


def _play_file_winsound(path):
    ws = _winsound()
    if ws is None:
        return False
    flags = getattr(ws, "SND_FILENAME", 0x00020000) | getattr(ws, "SND_ASYNC", 0x0001) \
        | getattr(ws, "SND_NODEFAULT", 0x0002)
    try:
        ws.PlaySound(path, flags)
        return True
    except Exception:
        return False


def _play_file_pygame(path):
    try:
        import pygame
        pygame.mixer.init()
        sound = pygame.mixer.Sound(path)
        sound.play()
        return True
    except Exception:
        return False


def play(name, path=None):
    """播放一个音效。name 是 SOUND_FILES 的内部键；path 可直接指定文件。

    返回是否成功播出（无音频后端时返回 False，调用方无需关心）。
    """
    target = path
    if target is None:
        file_name = SOUND_FILES.get(name)
        if not file_name:
            return False
        target = resources.audio_path(file_name)
        # 优先用 WAV（标准库可播）；只有 .ogg 时回退 pygame
        if not os.path.exists(target):
            ogg = resources.audio_path(os.path.splitext(file_name)[0] + ".ogg")
            if os.path.exists(ogg):
                return _play_file_pygame(ogg)
            return False
    if not os.path.exists(target):
        return False
    if _play_file_winsound(target):
        return True
    return _play_file_pygame(target)


def peak_amplitude():
    """试听音量（0..1）。留成函数便于以后接到界面设置。"""
    return 0.35


# ----------------------------------------------------------------------
# 合成：锯齿波（高频率重复同一波形即可听出音高）
# ----------------------------------------------------------------------
def sawtooth(freq, seconds, sample_rate=44100, amplitude=None):
    """生成一段锯齿波 PCM 样本（list[int]）。

    锯齿波的谐波最丰富，用它可以清楚听出基频（=音高）。
    """
    if amplitude is None:
        amplitude = peak_amplitude()
    peak = int(32767 * max(0.0, min(1.0, amplitude)))
    if freq <= 0 or seconds <= 0 or peak <= 0:
        return []
    total = int(sample_rate * seconds)
    period = max(2, int(round(sample_rate / float(freq))))
    # 一个周期内均匀上升再瞬间回落
    ramp = [int(-peak + 2.0 * peak * i / (period - 1)) for i in range(period)]
    if total <= period:
        return ramp[:total]
    repeats = total // period
    samples = ramp * repeats
    samples.extend(ramp[:total - len(samples)])
    return samples


def write_wav(path, samples, sample_rate=44100):
    """把样本写入 16bit 单声道 WAV；失败返回 False。"""
    try:
        directory = os.path.dirname(path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        data = array.array("h", samples)
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(data.tobytes())
        return True
    except Exception:
        return False


def _next_preview_path():
    """返回下一个轮转的试听文件路径（固定的一组文件名，只写不删）。"""
    global _preview_index
    path = os.path.join(resources.user_cache_dir(), "preview%d.wav" % _preview_index)
    _preview_index = (_preview_index + 1) % _PREVIEW_SLOTS
    return path


def render_wav(samples, sample_rate=44100):
    """把一段合成样本写成 WAV（轮转文件名），返回路径；失败返回 None。

    与 `play_samples` 分开是为了让调用方能**缓存**渲染结果：同一段内容再播一次时
    直接用上次的文件，不必重新逐样本合成（纯 Python 循环，长片段会比较慢）。
    """
    if not samples:
        return None
    path = _next_preview_path()
    return path if write_wav(path, samples, sample_rate) else None


def play_samples(samples, sample_rate=44100):
    """把一段合成样本写成 WAV 并异步播放（供音高试听用）。"""
    path = render_wav(samples, sample_rate)
    if not path:
        return False
    if _play_file_winsound(path):
        return True
    return _play_file_pygame(path)


def stop():
    """停止当前异步播放（winsound 支持）。"""
    ws = _winsound()
    if ws is None:
        return
    try:
        ws.PlaySound(None, getattr(ws, "SND_PURGE", 0x0040))
    except Exception:
        try:
            ws.PlaySound(None, 0)
        except Exception:
            pass
