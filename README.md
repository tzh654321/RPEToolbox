# RPEToolbox

这是一个主要通过`Re:Phiedit`的`“导出至系统剪贴板”`和`“导入谱面片段”`功能进行辅助谱面编辑的程序

### 现有功能
- hold/事件首尾相接
- 非线性切割
- 极坐标转换
- 事件类型转换
- 图片转音符画
- 时间间隔转y偏移
- 倒序/拉伸
- MIDI BPM 提取

### 界面文案、主题与高分屏

- 功能切换使用标签页（Notebook），**每个功能一页，页内依次是该功能的选项、输入JSON、三个按钮、输出JSON**
  （各页的输入输出互相独立，切换功能不会串内容；图片转音符画 / MIDI BPM 提取两页没有输入框）。
  顶部灰字是当前功能的简介。
- 输入/输出框为圆角外观，获得焦点时底部显示主题强调色的横线（`rpe_toolbox/widgets.py`）。
- 所有界面文字集中在 `assets/lang/zh-CN.json`（纯数据文件，不含任何代码）。
  复制该文件为同目录的 `<语言代码>.json` 并翻译其中的值，用环境变量 `RPET_LANG=<语言代码>` 启动即可切换语言；
  键名（key）决定程序行为，不可修改（`functions[].tab` 是标签页上的短标题）。
- 界面字体为等宽中文字体，优先已安装的更纱黑体（Sarasa，简体 SC 依次取 Mono / Fixed / Term），
  再回退 微软雅黑等宽 / Consolas / 系统等宽 / 微软雅黑。
- 外观使用 `sv-ttk`（sun-valley 主题），默认浅色，界面右上角「深色模式」开关可实时切换，
  选择记录在 `%APPDATA%/RPEToolbox/config.json`；也可用环境变量 `RPET_THEME=light|dark` 强制指定。
  未安装 sv-ttk 时自动降级为 ttk 默认样式，功能不受影响。
- 标题栏用 `pywinstyles` 跟随暗/亮色（Win11 风格），未安装该库时保持系统默认标题栏。
- 高分屏：程序在 `import tkinter` 之前启用进程级 DPI 感知，并按系统 DPI 缩放窗口与内边距
  （见 `rpe_toolbox/dpi.py`），避免 150% 等缩放下界面发虚、字体模糊。

依赖：`pillow`（图片转音符画）、`sv-ttk`（可选，界面样式）、`pywinstyles`（可选，标题栏暗/亮色）、`pygame`（可选，按钮音效）。

> 入口为 `RPET.py`，核心实现在 `rpe_toolbox/`；`Other File`、`tests` 目录中的文件均不参与程序逻辑。
> 打包 exe 时需一并打包 `assets` 目录（含 `assets/lang`）与 `sv_ttk` 包，否则界面文字或样式会缺失。
