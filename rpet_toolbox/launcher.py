# -*- coding: utf-8 -*-
"""以 pythonw.exe 无窗口方式重启自身（Windows）。"""

import os
import subprocess
import sys


def relaunch_as_pythonw():
    if os.name != "nt":
        return
    if os.environ.get("RPET_NO_RELAUNCH"):
        return
    if "pythonw" in sys.executable.lower():
        return

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
            [pythonw_path, os.path.abspath(__file__)],
            creationflags=creationflags,
            env=env,
        )
        raise SystemExit(0)
