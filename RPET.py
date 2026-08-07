# -*- coding: utf-8 -*-
#  rpe 工具箱 —— 启动入口（模块化版；版本:2026.8.6 / tzh654321）
import os
import sys

# 保证从任意目录启动都能找到 rpe_toolbox 包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    import tkinter as tk

    from rpe_toolbox.app import RPEToolbox

    root = tk.Tk()
    app = RPEToolbox(root)
    try:
        root.mainloop()
    finally:
        # 退出清理：销毁 Tk 并等待音频线程，降低 onefile 临时目录清理失败的概率
        app.shutdown()


if __name__ == "__main__":
    from rpe_toolbox.launcher import relaunch_as_pythonw

    # Windows 下以 pythonw.exe 无窗口方式重启自身
    try:
        relaunch_as_pythonw(script_path=os.path.abspath(__file__))
        main()
    except Exception:
        # pythonw 无控制台，出错时写入日志便于排查（位于 Other File/启动错误.log）
        import traceback

        log_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "Other File",
            "启动错误.log",
        )
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        raise
