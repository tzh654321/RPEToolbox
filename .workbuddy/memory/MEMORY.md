# RPEToolbox 项目约定

## 工程结构（需求九起）
- 入口 `RPET.py`（仅启动：DPI 感知 → Tk → mainloop → shutdown）；核心在 `rpe_toolbox/`；资源在 `assets/`；`Other File/`、`tests/` 不参与程序逻辑。
- 用户可见文字**一律**走 `i18n.t("组.键")`，文案数据在 `assets/lang/<语言>.json`，代码里不写死文案（`RPET_THEME`/`RPET_LANG` 环境变量可覆盖行为）。
- 下拉框选项用「内部键 → 显示文字」结构（`options.*`）：代码只比较内部键（`i18n.option_key`），显示文字可翻译。切勿再用显示文字做逻辑判断。
- `assets/lang/*.json` 打包时必须随 exe 一并带上。

## 运行与打包
- 运行：`python RPET.py`。打包脚本在用户另一台机器（`...\temp\RPET\`），本仓库不含。
- 依赖：`pillow` 必需；`sv-ttk`（外观）、`pygame`（音效）可选，缺失时静默降级。

## 测试
- 测试都在 `tests/`，直接 `python tests/_test_*.py` 跑，各自打印 `TOTAL: n PASS, m FAIL` 并用退出码表示结果。
- 测试用 `object.__new__(FunctionMixin)` 起无界面实例测核心逻辑；UI 测试直接 `tk.Tk()` + `RPEToolbox(root)`。
- 要求：改动后把 `tests/` 全部跑一遍（`_test_rpet/_req9/_req11/_req12/_polar_fix/_allow_shorten/_ui/_req14/_req15/_req16` 均应全绿）。
- 写涉及主题/配置的测试时，必须把 `APPDATA` 重定向到临时目录，否则会写坏真实用户配置。
- 提示词历史（`docs/ai提示词历史.txt`→`.md`）由 skill `prompt-history-to-md` 的 convert.py 负责转换；
  **不要整份重新生成 md**（会丢掉手工润色的表格），新轮次用转换器生成对应小节后追加，并同步目录。

## 交互与视觉约定
- 功能切换用 Notebook 标签页（8 页）：**每页各有一套「输入JSON / 三个按钮 / 输出JSON」**，与该功能选项同页（需求五顺序在页内成立）；
  `text_input`/`text_output`/`input_frame`/`frame_btn`/`btn_*` 是**属性**，返回当前页那份；`self.tab_io[key]` 存各页面板。
- 图片转音符画 / MIDI BPM 两页的输入区**照建但不 pack**（`winfo_manager()` 为 ""）。
- 输入/输出框是 `widgets.RoundedTextArea`（Canvas 圆角底 + 聚焦时底部 accent 蓝线）；配色在 `theme.PALETTES`（含 `accent`）。
  **它必须覆写 config/configure/cget**——Frame 上本来就有的方法不走 `__getattr__` 转发。
- 标签文字取语言文件 `functions[].tab`（短标签），字号 9（正文 10）。
- 控件顺序（需求五）：选择功能 → 该功能选项 → 输入JSON → 三个按钮 → 输出JSON。
- 主题：默认浅色，右上角开关可切深色，选择存 `%APPDATA%/RPEToolbox/config.json`；标题栏用 pywinstyles 跟随暗/亮色。
- 三个按钮（转换/复制结果/清空输入输出）颜色固定在 `theme.BUTTON_COLORS`，**每次应用主题后必须重新套用**
  （sv-ttk 的 tk_setPalette 会推迟重着色）；界面字体必须显式配到 ttk 样式上（ttk 不读 option_add）。
- 界面字体：等宽中文，优先更纱黑体（Sarasa，简体 SC 优先）；**家族名带空格时字体规格必须写 `"{家族} 字号"`**
  （`self.font_spec(size)`），否则 Tk 按列表解析报 `expected integer but got "…"`。
- 功能介绍：灰字（Muted.TLabel），放顶栏右侧、深色开关左边。
- 所有固定像素尺寸用 `self.px()` 换算，保证高分屏下与字号同步（DPI 感知后 Tk 单位=物理像素）。
- 测试断言配色时先 `update()`；涉及主题/配置的测试把 `APPDATA` 重定向到临时目录。
- 每批需求都要给出可复现路径与量化验证（用户偏好表格化根因 + 验证用例数），改动后全量复跑 tests/。
