# RPEToolbox 项目约定

## 模组化架构（第十五轮起）
- 功能都在 `rpe_toolbox/mods/<功能组>/*.py`（当前两组：`片段处理`、`全谱处理`），由 `mods_loader.discover()` 扫描。
  模组契约：`MOD_KEY`（对应语言文件 `functions[].key`）、`MOD_ORDER`（组内排序）、`build_options(app, parent)`、`process(app, data)`。
- **标签页顺序由各模组 `MOD_ORDER` 决定，不是语言文件 `functions[]` 的顺序**；`functions[]` 只是「key → tab/name/desc」的翻译表。
  新增模组必须同时在 `assets/lang/*.json` 的 `functions[]` 里加条目，否则标签会显示原始 key。
- 模组内的辅助函数是**模块级 `def fn(app, ...)`**，回调必须写 `command=lambda: fn(app)`。
  ✗ 禁止写 `app.fn`——自动切分容易把旧的 `self.fn` 机械改写成 `app.fn`，而 app 上并没有这个方法，
  结果是运行时 AttributeError、选项界面建不出来（曾表现为启动弹窗「模组 xxx 的选项界面创建失败」）。
- `build_options` 抛错时主程序**弹窗 + 打印 traceback**，并记进 `app.mod_build_errors`（可被测试断言）；失败不影响功能可用。
- 功能标识：界面里 `current_function` 存的是 `app.function_names` 里的**「序号. 名称」**；
  `app._resolve_function(label)` 兼容「序号. 名称 / 纯名称 / 模组 key」三种写法（外部按功能名赋值也能落到同一模组）。

## 文案与语言（i18n）
- `i18n.load(code)` 是**只读**的（按语言代码缓存，不会改当前语言）；切换语言只能用 `i18n.set_language(code)`。
  曾经的 bug：`load()` 无参时按「环境变量 > 默认」取，且 `language_display()` 内部调 `load(别的code)` 会顺手改掉当前语言
  → 结果是菜单切语言后立刻被拉回中文，等于切换失效。`tests/_test_mods.py` B2 段守着这条。

## 工程结构（需求九起）
- 入口 `RPET.py`（仅启动：DPI 感知 → Tk → mainloop → shutdown）；核心在 `rpe_toolbox/`；资源在 `assets/`；`Other File/`、`tests/` 不参与程序逻辑。
- 用户可见文字**一律**走 `i18n.t("组.键")`，文案数据在 `assets/lang/<语言>.json`，代码里不写死文案（`RPET_THEME`/`RPET_LANG` 环境变量可覆盖行为）。
- 下拉框选项用「内部键 → 显示文字」结构（`options.*`）：代码只比较内部键（`i18n.option_key`），显示文字可翻译。切勿再用显示文字做逻辑判断。
- `assets/lang/*.json` 打包时必须随 exe 一并带上。

## 运行与打包
- 运行：`python RPET.py`。打包脚本在用户另一台机器（`...\temp\RPET\`），本仓库不含。
- 依赖：`pillow` 必需；`sv-ttk`（外观）、`pygame`（音效）可选，缺失时静默降级。

## 文件归属（重要）
- **`docs/ai提示词历史.txt` 是用户的文件，AI 不要修改**（文件末尾用户也写了"AI不要动这个文件"）。
  只有 `docs/ai提示词历史.md` 是整理产物：用 `prompt-history-to-md` 转换器的输出**增量追加/替换轮次小节**，
  绝不整份重新生成（会丢手工润色的表格），也绝不回写 txt。
- **`README.md` 末尾写了「> AI不要擅自修改此文件」，同样不要改**。
- 回收站 / %TEMP% / 用户目录里的东西不擅自清理，只报告数量与位置。

## 文件与临时文件纪律（重要）
- **一切派生物都写 `resources.user_cache_dir()`（`%APPDATA%/RPEToolbox/cache`），并且只写不删。**
  本机的删除动作（`os.remove` / `rm` / `shutil.rmtree`）会被安全删除接管 → **进回收站**，
  所以「用完即删的临时文件」本身就是污染源（曾把回收站灌到当天 687 条）。
  图标 `.ico`、试听 `.wav` 都按固定文件名原地覆盖，源图未变就直接复用（`icons.json` 存指纹）。
- 同理：**不要用 `rm` 处理项目文件**，要改内容就原地覆盖写。
- 测试不再 `mkdtemp`+`rmtree`，改为每个测试一个固定目录 `%TEMP%/rpet_test_<名字>`，
  开头重写一份基线配置 `{"theme":"light","language":"zh-CN"}`（隔离 + 零新增零删除）。

## 音效
- `rpe_toolbox/audio.py`：素材是 `assets/audio/click*.wav`（由同名 .ogg 用 ffmpeg 转过），
  用标准库 `winsound` 异步播放，**不再依赖 pygame**（pygame 只装在 Python38，换解释器就静音）。
- 合成音（纵连音高试听）用 `wave`+`array` 写 WAV 到缓存目录再播；非 Windows 可回退 pygame。

## 菜单栏
- 勾选**自己画在文字前面**：`MENU_CHECK="\u2714 "` / `MENU_BLANK="  "`（等宽字体下等宽，完全对齐）。
  Tk 原生勾选框底色由系统 `selectcolor` 决定，与菜单底色撞车 → 用户看不到勾。
- `_sync_menus()` 是「重建条目 + 重画勾 + 刷配色」的唯一入口，`_build_menubar` 与主题应用都走它。
- 禁用功能语义：**勾 = 启用**，没勾即已禁用（不加载到标签栏），再点一下勾回来。
- 菜单前景色/底色会被 sv-ttk 的 `tk_setPalette` 推迟到 idle 重着色 → 必须和自绘控件一起在
  `_apply_theme` 的 `after_idle` 回调里再刷一次。

## 状态条与进度条
- `status_bar` **必须早于 Notebook pack**（先 `side=BOTTOM` 占位），否则被 `expand=True` 的 Notebook 挤没。
- 转换时进度条有最短可见时长 `PROGRESS_MIN_MS = 700`；到点后**同时**恢复介绍文字与播放音效。

## 输入框 / 输出框等高
- 每页那套「输入JSON / 三按钮 / 输出JSON」放在一个 `holder` 里，用 **grid 两行 `weight=1 + uniform="io"`**
  才能严格等高（`pack(expand=True)` 只会「各自请求高度 + 平分余量」，实测能差到 396 vs 107）。
- 两个框的**外层不能再加 padx/pady**，否则又差那几个像素；间距给中间那行按钮框。
- 模组自己的选项控件用 `fill=X` 固定高度，别用 `expand=True` 抢空间。

## 音符类型编号（RPE）
- `1=tap 2=hold 3=flick 4=drag`（用户需求 txt 第 9 行明确「hold = type 2」）。
  颜色：tap `#0AC3FF` / drag `#F0ED69` / flick `#FE4365` / hold `#9AE8FD`。
- `easing.MAX_TIME_DENOMINATOR = 4096`：纵连间隔可以细到 1/220 拍，原来 192 存不下。

## 纵连音高（vertical_pitch）
- 数量规则：`单音符时值 = 1/音高频率`（音高 0 退回 16 分音），hold 数量 = `时长 × 频率`；
  滑音（音高 A→B）总数 = `时长 × (fA+fB)/2`，时间点由 `∫f = k` 反解 → 疏密随音高变化。
- hold 拆出的每一段必须**首尾相接**（第 i 个 endTime = 第 i+1 个 startTime）；`marks` 一律用「拍」，别再乘一次 bpm。
- 预览画布：**下方较早、上方较晚**，横轴 = positionX（±675、音符宽度 175），时间刻度用**拍**，
  上下各留 `TIME_PAD_BEATS=1`；音高·数量标在音符**上方**（放右边会跑出框）。
- 改数值用**画布内嵌 Entry**（`create_window` + 全选），不弹窗；语法 `0` / `C4` / `C4→E4` / 数字。
  编辑框按用途分流：左键=音高（`main`）、右键非 hold=数量（`count`）、右键 hold=结束音调（`tail`，**留空即非滑音**）。
- **「点别处也保存」的三段式**：① 画布点击先 `_commit_editor()`；② `app.root.bind("<Button-1>", …, add="+")` 兜底
  （但要 `vp_editor_fresh` + `after_idle` 跳过"打开编辑框的那一下点击"，否则刚开就被提交）；
  ③ 按钮的 command 属类绑定、跑在 toplevel 之前，所以 app 提供 `register_pending_commit()`，
  `_trigger_with_sound()` 进来先 `commit_pending_edits()`（否则"改了数直接点转换"会用旧值）。
- `effective_count()` 只在 `glide` 为真时把 `pitch2` 计入频率平均——否则关掉滑音后数量仍是两端平均值。

## 菜单栏（结构 + 自绘）
- **必须自绘**：本机 Tk 9.0.4 在 Windows 上 menubar 那一条是原生绘制的，`-background/-foreground`
  完全无效（`bg='#ff0000'` 仍是纯白），深色主题下永远是白条。
  现在是 `tk.Frame` + 经典 `tk.Menubutton`（ttk.Menubutton 自带主题底色压不平），下拉仍是 `tk.Menu`。
  重建时先 `destroy()` 上一条 Frame；不再 `root.config(menu=...)`。
- 顶级：功能 / 显示 / **帮助**；帮助下：**功能介绍: <当前功能完整名>**（排在关于上一行）→ 关于。
- `_on_tab_changed` 末尾要调 `_sync_menus()`，否则功能介绍菜单里的功能名不跟着标签页变。
- **任何 `pywinstyles.apply_style`（比如弹新窗口）内部都会 `update()`**，会把 sv-ttk 推迟的
  `tk_setPalette` 跑掉、把刚刷好的菜单刷回浅色 → 弹窗/标题栏样式应用完要**再补刷一次菜单**。
- 帮助窗口：`_style_window_titlebar`（pywinstyles 深浅）+ `_window_hwnd`（用 `wm frame` 取真句柄）+
  `_help_window_icon()`（`SHGetStockIconInfo(SIID_HELP=77)`，取一次缓存，失败退回 IDI_QUESTION），
  `WM_SETICON` 小/大图标各发一次；开着的帮助窗口登记在 `app._help_windows`，换主题时统一重刷。
- 各功能的详细使用说明（作用/每个选项的作用/操作方法）在 `assets/lang/*.json` 顶层 `help` 块，
  代码里只 `i18n.load().get("help", {}).get(mod_key)`，不写死文字。
- **自绘下拉**：tk.Menu 只当数据源，展示用 `Toplevel(overrideredirect=True)` + 一列 tk.Button；
  行距紧凑（pady=2），级联项悬停即向右弹出二级面板（无「返回」行），`_dropdowns` 按层级下标存；
  级联/普通条目切换时用 `_close_dropdown_from(level)` **destroy** 旧面板（只裁列表会残留屏幕上）；
  `_start_dropdown_watch` 轮询指针位置，连续两次（约 300ms）在外才自动收起（不用 grab）。
  坑①：overrideredirect 窗口映射前 geometry("+x+y") 被忽略，要先带尺寸 deiconify 再定位。
  坑②：grab_set 会拦截不在 grab 树里的子面板点击，多级面板别用。
- 菜单栏底色用 `palette["menubar_bg"]`（与窗口底色拉开色差）+ 底部 1px `menubar_border` 分隔线。
- 三个彩色按钮配色走 `theme.button_colors(key, dark)`：暗色查独立常数表 `BUTTON_COLORS_DARK`
  （底色/字色与浅色表互换后的色号，两张表互相独立、不再调用时互换）。
- **i18n 文案里的占位符调用时必须传参**：`t()` 只在传了 kwargs 时才 format，
  漏传就会在界面显示 "{xxx}" 字面量（曾在关于弹窗的 {version} 上踩过）；
  版本号在 `rpe_toolbox/__init__.py` 的 `__version__`。
- **功能介绍拆分**：`assets/lang/mods/<语言>/<模组key>.json`（`{"text": ...}`），
  `resources.lang_mods_dir()` + `i18n._read` 合并进 help 块；主语言文件不再含 help。
- **打包在仓库外**：`C:\Users\tzh\Documents\code\og\build_exe.py`（PyInstaller onefile+windowed，
  assets 整目录 --add-data）；版本号 `__version__`（YYYY.M.D）。

## 测试
- 测试都在 `tests/`，直接 `python tests/_test_*.py` 跑，各自打印 `TOTAL: n PASS, m FAIL` 并用退出码表示结果。
- 测试用 `object.__new__(FunctionMixin)` 起无界面实例测核心逻辑；UI 测试直接 `tk.Tk()` + `RPEToolbox(root)`。
- 要求：改动后把 `tests/` 全部跑一遍（`_test_rpet/_req9/_req11/_req12/_polar_fix/_allow_shorten/_req14/_req15/_req16/_req17/_icons/_mods`，
  `_test_ui` 已删——断言被 _test_mods/_test_req15/16/_test_req11/_test_req9 覆盖，图标优先级断言并入了 _test_icons）。
  共 436 项断言 + `_test_polar_fix` 的 ALL PASSED。
- 测试图片在 `tests/images/`（`assets/images` 已移除，`resources.IMAGES_DIR` 已删）。
- 进度条/进度线这类"带时序"的断言**不要用采样法**（机器繁忙时一次 update() 会吃掉整段计时窗口），
  改成同步断言 + 临时放大延时（如把 PROGRESS_MIN_MS 设 1500ms 再断言 900ms 时仍在）。
- `requirements.txt` 在仓库根目录，列了 Pillow/sv-ttk/pywinstyles/pygame（后三者可选，pygame 带 win32 标记）。
- 跑 UI 测试前先把 `messagebox.showwarning/showerror/showinfo` 打桩：模态框无人点确定会**永久阻塞**。
- 写涉及主题/配置的测试时，必须把 `APPDATA` 重定向到固定测试目录，否则会写坏真实用户配置。
- 提示词历史（`docs/ai提示词历史.txt`→`.md`）由 skill `prompt-history-to-md` 的 convert.py 负责转换；
  **不要整份重新生成 md**（会丢掉手工润色的表格），新轮次用转换器生成对应小节后追加，并同步目录。
- 定时器/看门狗里的资源（临时文件、GDI 句柄）必须缓存复用，别每次重建再删除——
  曾因任务栏图标每 3 秒重建 .ico（约 2.2 万个/小时）把用户回收站灌满，`tests/_test_icons.py` 守着这条。

## 交互与视觉约定
- 功能切换用 Notebook 标签页（当前功能组每页一个）：**每页各有一套「输入JSON / 三个按钮 / 输出JSON」**，与该功能选项同页（需求五顺序在页内成立）；
  `text_input`/`text_output`/`input_frame`/`frame_btn`/`btn_*` 是**属性**，返回当前页那份；`self.tab_io[key]` 存各页面板。
- 图片转音符画 / MIDI BPM 两页的输入区**照建但不 pack**（`winfo_manager()` 为 ""）。
- 输入/输出框是 `widgets.RoundedTextArea`（Canvas 圆角底 + 聚焦时底部 accent 蓝线）；配色在 `theme.PALETTES`（含 `accent`）。
  **它必须覆写 config/configure/cget**——Frame 上本来就有的方法不走 `__getattr__` 转发。
- 标签文字取语言文件 `functions[].tab`（短标签），字号 9（正文 10）。
- 控件顺序（需求五）：该功能选项 → 输入JSON → 三个按钮 → 输出JSON。
- 菜单栏（`tk.Menu`）：功能（切换功能组 / 禁用模组）、显示（深色模式 / 语言）、关于。
  **深色模式开关与语言切换都在菜单里**（不再是顶栏勾选框），`_style_menus()` 负责暗色下菜单配色。
- 功能介绍显示在**底边状态条**（`status_label`，Muted.TLabel 灰字，贴窗口底部）；转换时状态条换成进度条。
- 主题：默认浅色，菜单可切深色，选择存 `%APPDATA%/RPEToolbox/config.json`；标题栏用 pywinstyles 跟随暗/亮色。
- 三个按钮（转换/复制结果/清空输入输出）颜色固定在 `theme.BUTTON_COLORS`，**每次应用主题后必须重新套用**
  （sv-ttk 的 tk_setPalette 会推迟重着色）；界面字体必须显式配到 ttk 样式上（ttk 不读 option_add）。
- 界面字体：等宽中文，优先更纱黑体（Sarasa，简体 SC 优先）；**家族名带空格时字体规格必须写 `"{家族} 字号"`**
  （`self.font_spec(size)`），否则 Tk 按列表解析报 `expected integer but got "…"`。
- 所有固定像素尺寸用 `self.px()` 换算，保证高分屏下与字号同步（DPI 感知后 Tk 单位=物理像素）。
- 测试断言配色时先 `update()`；涉及主题/配置的测试把 `APPDATA` 重定向到临时目录。
- 截图核对界面时要 `deiconify() + attributes('-topmost', True) + lift()`，否则 ImageGrab 会抓到别的窗口。
- 每批需求都要给出可复现路径与量化验证（用户偏好表格化根因 + 验证用例数），改动后全量复跑 tests/。
