# -*- coding: utf-8 -*-
"""以 pythonw.exe 无窗口方式重启自身（Windows）。"""

import os
import subprocess
import sys


def relaunch_as_pythonw(script_path=None):
    """以 pythonw.exe 无窗口方式重启入口脚本。

    script_path: 入口脚本的绝对路径。默认取项目根目录下的 RPET.py
    （launcher.py 自身不是入口，不能使用其 __file__）。
    """
    if os.name != "nt":
        return
    if getattr(sys, "frozen", False):
        # 打包成 exe（--windowed）后没有控制台可藏，重启自身反而会让
        # PyInstaller 6.22+ 的 onefile 父进程安全校验失败：
        # 新进程继承了 _MEIPASS2，而启动它的应用实例随即退出，
        # 校验父进程可执行文件路径时就会报 "Security validation failure"。
        return
    if os.environ.get("RPET_NO_RELAUNCH"):
        return
    if "pythonw" in sys.executable.lower():
        return

    if script_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path = os.path.join(project_root, "RPET.py")
    target = os.path.abspath(script_path)

    pythonw_candidates = [
        os.path.join(os.path.dirname(sys.executable), "pythonw.exe"),
        sys.executable.replace("python.exe", "pythonw.exe").replace("python3.exe", "pythonw.exe"),
    ]
    pythonw_path = next((p for p in pythonw_candidates if os.path.exists(p)), None)
    if pythonw_path:
        env = os.environ.copy()
        env["RPET_NO_RELAUNCH"] = "1"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            [pythonw_path, target],
            creationflags=creationflags,
            env=env,
        )
        raise SystemExit(0)
