# -*- coding: utf-8 -*-
#  rpe 工具箱 —— 启动入口（模块化版；版本:2026.8.6 / tzh654321）
import os
import sys

# 保证从任意目录启动都能找到 rpet_toolbox 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import tkinter as tk

    from rpet_toolbox.app import RPEToolbox

    root = tk.Tk()
    app = RPEToolbox(root)
    root.mainloop()


if __name__ == "__main__":
    from rpet_toolbox.launcher import relaunch_as_pythonw

    # Windows 下以 pythonw.exe 无窗口方式重启自身
    relaunch_as_pythonw()
    main()
