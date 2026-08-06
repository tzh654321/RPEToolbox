# rpe 工具箱（模块化版）

由单文件 `RPET.py`（约 1600 行）按“需求九：拆分文件并构建新目录”重构而来。

## 目录结构

```
RPET new/
├── RPET.py                     # 启动入口（双击 / python RPET.py）
├── rpet_toolbox/               # 源码包（拆分后的代码）
│   ├── launcher.py             # pythonw 无窗口重启
│   ├── imglib.py               # Pillow 可选导入
│   ├── easing.py               # 时间数组 / 缓动曲线数学
│   ├── core.py                 # 8 个功能的实现
│   ├── resources.py            # 资源路径解析
│   └── app.py                  # RPEToolbox 主类（UI 与流程）
├── assets/
│   ├── audio/                  # 按钮音效 click1-4.ogg
│   ├── icons/                  # 窗口图标 ico*.png
│   └── images/                 # 测试/示例图片（含多透明度 _test_img_alpha.png）
├── Other File/
│   ├── _上下文备忘.md           # 会话恢复用备忘
│   ├── 大段注释整理.md           # 从代码中移出的大段推导/说明注释
│   └── 染色矫正.py              # 染色矫正算法说明
├── docs/
│   └── 使用python和tkinter制作以下音游相关功能.txt   # 需求文档副本
└── tests/
    ├── _test_rpet.py           # 功能测试（20 项）
    ├── _test_ui.py             # UI 切换测试（12 项）
    └── _test_req9.py           # 需求九验证（BPMList / 音符宽度 / 上下翻转）
```

## 运行与测试

- 启动：`python RPET.py`（Windows 下自动切换 pythonw 无窗口运行）
- 功能测试：`python tests/_test_rpet.py`
- UI 测试：`python tests/_test_ui.py`
- 需求九验证：`python tests/_test_req9.py`

## 需求九要点

- MIDI BPM 提取输出 `BPMList`（`bpm` + `startTime`），不含 `midiPath`
- 自动调整音符宽度模式下同步输出 `size`（`size = 列间距 / 175`，平铺 1350 屏幕宽度）
- 非自动模式下 `size = 输入音符宽度 / 175`
- 上下翻转默认不勾选，但按其反义生成：图片底部一行最早出现（符合下落式音游）
- 大段实现注释与 `_上下文备忘.md` 位于 `Other File/`
