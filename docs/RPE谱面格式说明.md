# RPE 谱面格式

> **警告：** 以下所有内容从编写开始时间（2024.7.25）最新 RPE 版本 1.4.1 开始编写，更早的加入版本等信息全部待补充。

## 5.1.1 谱面根目录

### BPMList

`BPMList` 是一个 `JsonArray` 类型字段，包含若干个 `JsonObject`。每个 JsonObject 包含以下字段：

| 字段名 | 类型 | 说明 | 加入版本 |
| --- | --- | --- | --- |
| bpm | float | BPM 值 | - |
| startTime | [beat](#beat) | BPM 开始时间 | - |

### META

`META` 是一个 `JsonObject` 类型字段，包含以下字段：

| 字段名 | 类型 | 说明 | 加入版本 |
| --- | --- | --- | --- |
| RPEVersion | int | RPE 版本，100~160 | - |
| background | string | 背景图片相对于谱面根目录路径 | - |
| charter | string | 谱师名义 | - |
| composer | string | 曲师 | - |
| id | string | 谱面 ID，在 RPE 中用于识别谱面 | - |
| illustration | string | 曲绘画师 | 141 |
| level | string | 谱面等级 | - |
| name | string | 谱面名称 | - |
| offset | int | 音乐偏移，单位为毫秒 | - |
| song | string | 音乐文件相对于谱面根目录路径 | - |

- `offset` 字段为负数时，音乐应该在谱面开始前 `-offset` 毫秒时播放；为正数时，音乐应该在谱面开始后 `offset` 毫秒时播放。
- `id` 字段在 RPE 自动生成时为 `long`，实际上这个值可以随便篡改为任何字符，所以在实际谱面中存储方式为 `string` 类型。
- **RPE 1.5.0 ~ RPE 1.6.0 之间的版本（不含 RPE 1.6.0，含 Alpha 版本），META 中的 `RPEVersion` 字段保持为 `150`，没有被更改。**
- **RPE 1.6.1 版本，META 中的 `RPEVersion` 字段的值保持为 `160`，没有被更改。**

### chartTime

*模拟器不需要本属性。*

- `chartTime` 是一个 `double` 类型字段，值的时间单位是秒，表示谱面编辑时长，在 `141` 版本加入。
- 在 RPE 中，如果谱师在 30 秒内没有编辑谱面，则该值将不再变动，下次开始编辑后继续计时。（特性被移除）
- 如果 RPE 失去焦点，RPE 仍会继续计时，若 RPE 重新获得焦点，计时将回溯至失去焦点时的时间。

### judgeLineGroup

*模拟器不需要本属性。*

- `judgeLineGroup` 是一个 `string[]` 类型字段；
- 每一个 `string` 为一个判定线组。
- *实际行为待补充。*

### judgeLineList

- `judgeLineList` 是一个 `JsonArray` 类型字段，包含若干个 [JudgeLine](#judgeline)。

### multiLineString

*模拟器不需要本属性。*

- `multiLineString` 是一个 `string` 类型字段，在 RPE 中多线编辑时使用，以空格分割，每个数字代表一个判定线。
- `multiLineString` 中也可能含有 `:`，`1:20` 将选中 `1` 到 `20` 号的所有判定线。
- `multiLineString` 若为 `all`，则表示选中所有判定线。（RPE 1.6.4）

### multiScale

*模拟器不需要本属性。*

- `multiScale` 是一个 `float`，在 RPE 中用于缩放多线编辑页面的大小。

### timeTags

*模拟器不需要本属性。*

`timeTags` 是一个 `JsonArray` 类型字段，包含若干个 `JsonObject`，每个 `JsonObject` 包含以下字段：

| 字段名 | 类型 | 说明 | 加入版本 |
| --- | --- | --- | --- |
| name | string | 标记名称 | 130 |
| time | [beat](#beat) | 标记拍 | 130 |

### xybind

*模拟器不需要本属性。*

- `xybind` 是一个 `bool`，用于指示本谱面是否启用了 XY 绑定。
- 若为 `true`，则表示启用了 XY 绑定，则每一个 `XEvent` 一定有一个对应同等长度的 `YEvent`。

---

## 5.1.2 判定线

每一个 JudgeLine（判定线）都含有以下字段：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| Group | int | 判定线所属[组](#judgelinegroup) | 0 | - |
| Name | string | 判定线名称 | Untitled | - |
| Texture | string | 判定线纹理，若非默认值，则为相对于谱面根目录的路径，详见 [Texture](#texture) | line.png | - |
| anchor | float[2] | 判定线纹理锚点，详见 [anchor](#anchor) | [0.5, 0.5] | 142 |
| eventLayers | [EventLayer](#eventlayer)\[\]? | 事件层级，默认包含至少一个层级，最大有五个 | - | - |
| extended | [JsonObject](#extended) | 特殊事件层，详见 [特殊事件](#extended) | - | - |
| father | int | 父线索引，`-1` 表示无父线 | - | - |
| isCover | int | 是否遮罩 | 1 | - |
| notes | [Note](#note)\[\] | 线上所有的音符 | - | - |
| numOfNotes | int | 音符总数量（包含 FakeNote，不包含 Hold） | 0 | - |
| zOrder | int | 线 z 轴（即图层），范围为 ±100 | 0 | - |
| attachUI | string? | UI 绑定，详见 [attachUI](#attachui)；无绑定情况下不存在本字段 | - | - |
| isGif | bool | 纹理是否为 GIF，若为 `true` 则 Texture 为一个 GIF 文件 | false | 150 |
| posControl | JsonArray | 详见 [Controls](#controls) | - | - |
| sizeControl | JsonArray | 详见 [Controls](#controls) | - | - |
| skewControl | JsonArray | 详见 [Controls](#controls) | - | - |
| yControl | JsonArray | 详见 [Controls](#controls) | - | - |
| alphaControl | JsonArray | 详见 [Controls](#controls) | - | - |
| bpmfactor | float | BPM 因子 *此字段无法在 RPE 中编辑* | 1.0 | - |
| rotateWithFather | bool | 子线是否继承父线的旋转角度 | true | 163 |

- 若层级为空，在某个版本之前字段为 `null`，在某个版本及以后空层级无字段。（当前已知至少在 `143` 版本时无字段）
  - 若某个层级中的某个事件不存在，则该事件字段不会出现。
  - 若所有层级都为空，`eventLayers` 字段不会出现。
- 判定线的当前 BPM 为 `nowBpm / bpmfactor`，而非 `nowBpm * bpmfactor`。
- 父线允许嵌套，父线是否影响子线的旋转角度取决于 `rotateWithFather` 是否为 `true`，若不存在此字段应视为 `false`（兼容 163 以前的版本）。
- `isCover` 字段在 RPE 中为 `1` 时表示遮罩，其他值为不遮罩；遮罩时，位于判定线背面的音符（如果音符 `Above` 不为 1 则为正面）不会渲染，反之则渲染（除非已被打击，则不渲染）。
- 在RPE中，判定线的实际长度为`4000`（对应x坐标 -2000 ~ 2000）

### EventLayer

事件层级。每个判定线可以有多个事件层级。

### Extended

特殊事件层，详见 [特殊事件](#extended-events)。

---

## 5.1.3 beat

`beat` 是 RPE 所有事件的时间单位，它是一个 `int[3]`，在 RPE 中显示为 `[0]:[1]/[2]`。

单 BPM 计算方式为：

```csharp
double beat = RPEBeat[1] / RPEBeat[2] + RPEBeat[0];
double seconds = 60 / BPM * beat;
```

多 BPM 计算方式见下方 Python 示例。

### Python 示例

```python
def sec2beat(self, t: float, bpmfactor: float):
    beat = 0.0
    for i, e in enumerate(self.BPMList):
        bpmv = e.bpm / bpmfactor
        if i != len(self.BPMList) - 1:
            et_beat = self.BPMList[i + 1].startTime.value - e.startTime.value
            et_sec = et_beat * (60 / bpmv)

            if t >= et_sec:
                beat += et_beat
                t -= et_sec
            else:
                beat += t / (60 / bpmv)
                break
        else:
            beat += t / (60 / bpmv)
    return beat

def beat2sec(self, t: float, bpmfactor: float):
    sec = 0.0
    for i, e in enumerate(self.BPMList):
        bpmv = e.bpm / bpmfactor
        if i != len(self.BPMList) - 1:
            et_beat = self.BPMList[i + 1].startTime.value - e.startTime.value

            if t >= et_beat:
                sec += et_beat * (60 / bpmv)
                t -= et_beat
            else:
                sec += t * (60 / bpmv)
                break
        else:
            sec += t * (60 / bpmv)
    return sec
```

其中 `BPMEvent` 定义为：

```python
@dataclass
class BPMEvent:
    startTime: Beat
    bpm: float
```

---

## 5.1.4 音符

Note，即音符，是谱面的主要构成之一，每个音符都应该含有以下参数：

| 字段 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| above | int | `1` 为从线的正面下落，其他数字为从线的背面下落 | 1 | - |
| alpha | int | 音符不透明度，0 为完全透明，255 为完全不透明 | 255 | - |
| endTime | [beat](#beat) | 音符结束时间，若 `type` 为 `2` 则此值为 Hold 的结束时间，否则与 startTime 一致 | - | - |
| startTime | [beat](#beat) | 音符开始时间，若 `type` 为 `2` 则此值为 Hold 的开始时间，否则与 endTime 一致 | - | - |
| isFake | int | 音符真值，`1` 为假，其他数为真 | 0 | - |
| positionX | float | 音符相对于判定线中心点的 X 坐标 | - | - |
| size | float | 音符大小倍率 | 1.0 | - |
| speed | float | 流速倍率 | 1.0 | - |
| type | int | 音符类型，详见[对照表](#note类型对照) | - | - |
| visibleTime | float | 音符可见时间，单位为秒 | 999999.0000 | - |
| yOffset | float | 音符的 Y 轴偏移，正数向上偏移，负数向下偏移 | 0 | - |
| hitsound | string? | 音符自定义打击音文件相对于谱面文件根目录路径 | - | 142 |
| judgeArea | float | 判定区域宽度倍率 | 1.0 | 170 |
| tint 或 color | int[3] | 音符颜色，格式为 `[R, G, B]`，范围为 0-255 | [255, 255, 255] | 170 |
| tintHitEffects | int[3]? | 音符打击特效颜色，格式为 `[R, G, B]`，范围为 0-255 | [255, 255, 255] | 170 |

- `size` 字段实际上在 RPE 中显示为宽度，即只能控制音符的宽度而不是音符的整个大小。
- `above` 字段在为 `1` 时，音符从判定线的正面下落，其他数值时从判定线的背面下落。
- `hitsound` 字段在没有自定义音效时不存在。
- 假音符没有判定，没有打击特效与音效，不计分，不计物量，若为 Hold 则始终显示为未打击样式。
- `color` 字段用于给音符染色，染色方式为顶点颜色乘法，即 `noteColor = noteColor * color`。
  - color 字段修改过字段名称，由于 color 版本被公测，后续版本更换为 tint，所以这两个字段可能都有被使用，定义不变，请注意兼容。
- `tintHitEffects` 字段用于给音符的打击特效染色，当此字段出现时，无论判定是 Good 还是 Perfect，打击特效均使用此颜色，不需要额外计算。
- `yOffset` 并非相对于判定线位置的绝对偏移，偏移量为 `yOffset * speed`。若 `speed` 为 `0`，则 `yOffset` 设置为任何数偏移量都为 `0`。

### Note 类型对照

| 字段值 | 描述 |
| --- | --- |
| 1 | Tap |
| 2 | Hold |
| 3 | Flick |
| 4 | Drag |

---

## 5.1.5 普通事件

本节介绍判定线事件层级下的**普通事件**。

RPE 中一共有五种普通事件：`moveXEvents`（X 轴移动事件）、`moveYEvents`（Y 轴移动事件）、`rotateEvents`（旋转事件）、`alphaEvents`（不透明度事件）、`speedEvents`（音符流速事件）。

在层级下，这些字段都对应一个 `JsonArray`，每一个元素代表一个事件。当前判定线无某一个事件时，无对应字段而非空数组。

除了**流速事件**外的每个普通事件都应该含有以下字段：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| bezier | int | 缓动是否为贝塞尔曲线，`0` 为不是，`1` 为是 | 0 | - |
| bezierPoints | float[4] | 贝塞尔曲线控制点，当 `bezier` 为 `1` 时生效 | [0.0, 0.0, 0.0, 0.0] | - |
| easingLeft | float | 缓动的左边界位置，最小为 `0.0`，最大为 `1.0` | 0.0 | - |
| easingRight | float | 缓动的右边界位置，最小为 `0.0`，最大为 `1.0` | 1.0 | - |
| easingType | int | 缓动类型，详见 [easingType](#easingtype) | 1 | - |
| linkgroup | int | - | - | - |
| start | float | 事件开始时数值 | - | - |
| startTime | [beat](#beat) | 事件开始的时间 | - | - |
| end | float | 事件结束时数值 | - | - |
| endTime | [beat](#beat) | 事件结束的时间 | - | - |

- 坐标系锚点位于屏幕中心，X 轴范围为 `-675 ~ 675`，Y 轴范围为 `-450 ~ 450`。
- `Alpha` 不透明度事件的正常范围为 `0 ~ 255`，`0` 为完全透明，`255` 为完全不透明。
  - 若 `Alpha` 事件数值为负数，则会在隐藏判定线的同时隐藏这条判定线上的所有 Note。（此功能是废弃的非法功能，但它仍然有效）
- 速度事件只有上述的 `startTime`、`endTime`、`start`、`end`、`linkgroup` 字段。
  - 速度事件在 `162` 版本支持了所有缓动字段，但是仍然不支持贝塞尔曲线缓动。
  - RPE 作者原文：速度事件缓动不为 1 时，实际的速度变化与缓动的导函数形状相同，从而 floorposition 的变化遵循缓动曲线。为了兼容性，缓动为 1 时我们保持原含义不变，也即缓动为 `1` 和缓动为 `5` 都代表二次型的 floorposition 变化。
  - RPE 1.7.0 版本，速度事件缓动回归最原始的逻辑，使用缓动函数缓动速度的数值，效果有待考证。
  - 音符流速事件**不支持缓动**，即只有线性变化。
  - 流速为负数时，音符会向上飞，若音符为 Hold，在 Hold 尾出现时整个音符都会出现（即使 Hold 还没完全回到判定线正面）。（此行为与本家行为不符，请酌情选择）

### Python 示例（不支持 bezier）

```python
def easing_interpolation(
    t: float, st: float,
    et: float, sv: float,
    ev: float, f: typing.Callable[[float], float]
):
    if t == st: return sv
    return f((t - st) / (et - st)) * (ev - sv) + sv

def GetEventValue(t: float, es: list[LineEvent], default):
    for e in es:
        if e.startTime.value <= t <= e.endTime.value:
            if isinstance(e.start, float|int):
                return easing_interpolation(t, e.startTime.value, e.endTime.value, e.start, e.end, e.easingFunc)
            elif isinstance(e.start, str):
                return e.start
            elif isinstance(e.start, list):
                r = easing_interpolation(t, e.startTime.value, e.endTime.value, e.start[0], e.end[0], e.easingFunc)
                g = easing_interpolation(t, e.startTime.value, e.endTime.value, e.start[1], e.end[1], e.easingFunc)
                b = easing_interpolation(t, e.startTime.value, e.endTime.value, e.start[2], e.end[2], e.easingFunc)
                return (r, g, b)
    return default
```

---

## 5.1.6 特殊事件

本节讲解 RPE 的特殊事件，俗称故事板，位于事件编辑的第五个层级。每一个事件字段都对应一个 `JsonArray`，每一个元素对应一个事件。**除了 `inclineEvents`（倾斜事件），其他事件在没有使用时都没有对应字段。**

### colorEvents

颜色事件，可以控制判定线或纹理的颜色：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| bezier | int | 缓动是否为贝塞尔曲线，`0` 为不是，`1` 为是 | 0 | - |
| bezierPoints | float[4] | 贝塞尔曲线控制点，当 `bezier` 为 `1` 时生效 | [0.0, 0.0, 0.0, 0.0] | - |
| easingLeft | float | 缓动的左边界位置，最小为 `0.0`，最大为 `1.0` | 0.0 | - |
| easingRight | float | 缓动的右边界位置，最小为 `0.0`，最大为 `1.0` | 1.0 | - |
| easingType | int | 缓动类型，详见 [easingType](#easingtype) | 1 | - |
| linkgroup | int | - | - | - |
| start | int[3] | 事件开始时颜色，格式为 `[R, G, B]`，范围 0-255 | - | - |
| startTime | [beat](#beat) | 事件开始的时间 | - | - |
| end | int[3] | 事件结束时颜色，格式为 `[R, G, B]`，范围 0-255 | - | - |
| endTime | [beat](#beat) | 事件结束的时间 | - | - |

### scaleXEvents

X 轴缩放事件，可以控制判定线、纹理或文字的宽度缩放：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| bezier | int | 缓动是否为贝塞尔曲线，`0` 为不是，`1` 为是 | 0 | - |
| bezierPoints | float[4] | 贝塞尔曲线控制点 | [0.0, 0.0, 0.0, 0.0] | - |
| easingLeft | float | 缓动的左边界位置 | 0.0 | - |
| easingRight | float | 缓动的右边界位置 | 1.0 | - |
| easingType | int | 缓动类型，详见 [easingType](#easingtype) | 1 | - |
| linkgroup | int | - | - | - |
| start | float | 事件开始时缩放 | 1 | - |
| startTime | [beat](#beat) | 事件开始的时间 | - | - |
| end | float | 事件结束时缩放 | 1 | - |
| endTime | [beat](#beat) | 事件结束的时间 | - | - |

### scaleYEvents

Y 轴缩放事件，可以控制判定线、纹理或文字的高度缩放：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| bezier | int | 缓动是否为贝塞尔曲线，`0` 为不是，`1` 为是 | 0 | - |
| bezierPoints | float[4] | 贝塞尔曲线控制点 | [0.0, 0.0, 0.0, 0.0] | - |
| easingLeft | float | 缓动的左边界位置 | 0.0 | - |
| easingRight | float | 缓动的右边界位置 | 1.0 | - |
| easingType | int | 缓动类型，详见 [easingType](#easingtype) | 1 | - |
| linkgroup | int | - | - | - |
| start | float | 事件开始时缩放 | 1 | - |
| startTime | [beat](#beat) | 事件开始的时间 | - | - |
| end | float | 事件结束时缩放 | 1 | - |
| endTime | [beat](#beat) | 事件结束的时间 | - | - |

### textEvents

文字事件，可以控制文字的显示：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| bezier | int | 缓动是否为贝塞尔曲线，`0` 为不是，`1` 为是 | 0 | - |
| bezierPoints | float[4] | 贝塞尔曲线控制点 | [0.0, 0.0, 0.0, 0.0] | - |
| easingLeft | float | 缓动的左边界位置 | 0.0 | - |
| easingRight | float | 缓动的右边界位置 | 1.0 | - |
| easingType | int | 缓动类型，详见 [easingType](#easingtype) | 1 | - |
| linkgroup | int | - | - | - |
| start | string | 事件开始时字符 | - | - |
| startTime | [beat](#beat) | 事件开始的时间 | - | - |
| end | string | 事件结束时字符 | - | - |
| endTime | [beat](#beat) | 事件结束的时间 | - | - |
| font | string | 文字字体（见下方解释） | 请看下方解释 | - |

- 从 `152` 版本开始，`font` 字段在为默认字体时不会有本字段，只有有自定义字体时才会存在本字段。
- 在 `152` 版本之前，`font` 字段默认存在且默认为 `cmdysj`。
- 此事件设置缓动可能不会有效，也可能会出现未定义的错误导致模拟器崩溃。
- 文字事件的文字中含有 `%P%` 时，可以让文本中的数字在事件播放过程中根据缓动动态变化。
- 有文字事件的判定线会始终隐藏，只显示文字（即使播放的地方没有文字事件），也会清除自定义纹理。
- 有文字事件但是没有颜色事件时，文字的颜色会始终为白色。
- 从 `153` 版本开始，文字事件中的文字可以包含 `\n` 换行符且有效（其他的不可用）。

### paintEvents

画笔事件，此事件在 `143` 版本被 shader 编辑功能取代，故无法编辑：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 | 移除版本 |
| --- | --- | --- | --- | --- | --- |
| bezier | int | 缓动是否为贝塞尔曲线 | 0 | - | 143 |
| bezierPoints | float[4] | 贝塞尔曲线控制点 | [0.0, 0.0, 0.0, 0.0] | - | 143 |
| easingLeft | float | 缓动的左边界位置 | 0.0 | - | 143 |
| easingRight | float | 缓动的右边界位置 | 1.0 | - | 143 |
| easingType | int | 缓动类型 | 1 | - | 143 |
| linkgroup | int | - | - | - | 143 |
| start | float | 事件开始时画笔大小 | 0 | - | 143 |
| startTime | [beat](#beat) | 事件开始的时间 | - | - | 143 |
| end | float | 事件结束时画笔大小 | 0 | - | 143 |
| endTime | [beat](#beat) | 事件结束的时间 | - | - | 143 |

### gifEvents

GIF 播放进度事件，在 `150` 版本与 GIF 判定线纹理一同加入，用于控制 GIF 的播放进度：

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| easingType | int | 缓动类型，详见 [easingType](#easingtype) | 1 | - |
| linkgroup | int | - | - | - |
| start | float | 事件开始时 GIF 的播放进度 | - | - |
| startTime | [beat](#beat) | 事件开始的时间 | - | - |
| end | float | 事件结束时 GIF 的播放进度 | - | - |
| endTime | [beat](#beat) | 事件结束的时间 | - | - |

- 若判定线纹理是 GIF 但是没有 `gifEvents` 时，GIF 会自动循环播放。
- GIF 的第一帧为 `0.0`，最后一帧为 `1.0`，若播放进度超出此范围，GIF 将会自动循环播放。
- 若当前播放进度没有 `gifEvents` 时，GIF 会自动循环播放。
- 文字事件同样会将此纹理清除。
- 超过 `15MB` 大小的 GIF 会使 RPE 在加载谱面时弹出解码失败。
- 纹理为 GIF 以后，流速事件会被替换为此事件的编辑，所以理论上此事件不可能与流速事件同时出现。
- 位于其他层级的 `gifEvents` 会被忽略，且 RPE 纠错会标红。

### inclineEvents

倾斜事件，疑似已被弃用，但是默认会在 `extended` 字段下留一个垫底事件。*此事件无法在 RPE 中编辑。*

- 倾斜事件开始结束数值为判定线 Z 轴倾斜角度。
- 具体行为需要补充。

---

## 5.1.7 扩展特性

### attachUI

`attachUI` 是 RPE 独有特性，它允许你使用判定线绑定 UI 元素，使你可以控制 UI 的位置、透明度、大小等。

属性对应 UI 元素列表：

| 值 | 对应 UI 元素 | RPE 设置中对应数字 | 锚点 | 注 |
| --- | --- | --- | --- | --- |
| pause | 暂停按钮 | 1 | 左上角 | - |
| combonumber | 连击数 | 2 | 中心 | 绑定此 UI 会使此 UI 透明度受到 Alpha 事件影响，默认连击大于等于 3 时才会显示 |
| combo | 连击数下的 combo 文字 | 3 | 中心 | 同上 |
| score | 分数 | 4 | 右上角 | - |
| bar | 进度条 | 5 | 左侧中心 | RPE 1.4.0 及以前，此属性绑定的为曲名左侧的白色竖条 |
| name | 谱面名称 | 6 | 左下角 | - |
| level | 谱面等级 | 7 | 右下角 | - |

- 在 UI 被绑定后，判定线将会自动隐藏，UI 可以通过类似于子线的方式进行操作，不同的是可以操作 UI 角度和透明度；判定线实际位置仍然不变。

### anchor

`anchor` 是 RPE 独有特性，它允许你设置判定线的锚点，它的设计是为文字事件服务的。

- 在 RPE 中，此设置在顶栏工具栏第二页中，两个数值用空格分割。
- 它是一个 `float[2]`，两个值对应材质的 `x` 和 `y` 坐标。
- `x` 默认为 `0.5`，即中心，`1` 时判定线纹理向左移，`0` 时判定线纹理向右移。
- `y` 默认为 `0.5`，即中心，`1` 时判定线纹理向下移，`0` 时判定线纹理向上移。
- 此字段同样可以影响自定义纹理的位置。

### Texture

RPE 允许设置判定线的 `Texture` 字段来修改判定线的纹理，当判定线的纹理被修改后，判定线颜色不再受到 AP/FC 判定线颜色指示影响。

- 若不使用 scaleXEvents 和 scaleYEvents 修改判定线纹理大小，则默认缩放为 `1`。
- 纹理的显示方式为：每个像素对应一个 RPE 坐标系单位，忽略宽高比。
- 若纹理为一个 GIF 动图，则会受到 gifEvents 的影响。（`150` 版本开始支持）

### easingType

`easingType` 是 RPE 用于对应缓动的数字标识，对照表如下：

| 值 | 对应缓动 | 注 |
| --- | --- | --- |
| 1 | Linear | - |
| 2 | Out Sine | - |
| 3 | In Sine | - |
| 4 | Out Quad | - |
| 5 | In Quad | - |
| 6 | In Out Sine | - |
| 7 | In Out Quad | - |
| 8 | Out Cubic | - |
| 9 | In Cubic | - |
| 10 | Out Quart | - |
| 11 | In Quart | - |
| 12 | In Out Cubic | - |
| 13 | In Out Quart | - |
| 14 | Out Quint | - |
| 15 | In Quint | - |
| 16 | Out Expo | - |
| 17 | In Expo | - |
| 18 | Out Circ | - |
| 19 | In Circ | - |
| 20 | Out Back | - |
| 21 | In Back | - |
| 22 | In Out Circ | - |
| 23 | In Out Back | - |
| 24 | Out Elastic | - |
| 25 | In Elastic | - |
| 26 | Out Bounce | - |
| 27 | In Bounce | - |
| 28 | In Out Bounce | - |
| 29 | In Out Elastic | 无法在速度事件使用（RPE 1.7.0 恢复了 29 号缓动的使用） |

你可以在 [easings.net](https://easings.net/zh-cn) 查看它们的函数等信息。

### Python 缓动示例

```python
import math
import typing

ease_funcs: list[typing.Callable[[float], float]] = [
    lambda t: t,  # linear - 1
    lambda t: math.sin((t * math.pi) / 2),  # out sine - 2
    lambda t: 1 - math.cos((t * math.pi) / 2),  # in sine - 3
    lambda t: 1 - (1 - t) * (1 - t),  # out quad - 4
    lambda t: t ** 2,  # in quad - 5
    lambda t: -(math.cos(math.pi * t) - 1) / 2,  # io sine - 6
    lambda t: 2 * (t ** 2) if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2,  # io quad - 7
    lambda t: 1 - (1 - t) ** 3,  # out cubic - 8
    lambda t: t ** 3,  # in cubic - 9
    lambda t: 1 - (1 - t) ** 4,  # out quart - 10
    lambda t: t ** 4,  # in quart - 11
    lambda t: 4 * (t ** 3) if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2,  # io cubic - 12
    lambda t: 8 * (t ** 4) if t < 0.5 else 1 - (-2 * t + 2) ** 4 / 2,  # io quart - 13
    lambda t: 1 - (1 - t) ** 5,  # out quint - 14
    lambda t: t ** 5,  # in quint - 15
    lambda t: 1 if t == 1 else 1 - 2 ** (-10 * t),  # out expo - 16
    lambda t: 0 if t == 0 else 2 ** (10 * t - 10),  # in expo - 17
    lambda t: (1 - (t - 1) ** 2) ** 0.5,  # out circ - 18
    lambda t: 1 - (1 - t ** 2) ** 0.5,  # in circ - 19
    lambda t: 1 + 2.70158 * ((t - 1) ** 3) + 1.70158 * ((t - 1) ** 2),  # out back - 20
    lambda t: 2.70158 * (t ** 3) - 1.70158 * (t ** 2),  # in back - 21
    lambda t: (1 - (1 - (2 * t) ** 2) ** 0.5) / 2 if t < 0.5 else (((1 - (-2 * t + 2) ** 2) ** 0.5) + 1) / 2,  # io circ - 22
    lambda t: ((2 * t) ** 2 * ((2.5949095 + 1) * 2 * t - 2.5949095)) / 2 if t < 0.5 else ((2 * t - 2) ** 2 * ((2.5949095 + 1) * (t * 2 - 2) + 2.5949095) + 2) / 2,  # io back - 23
    lambda t: 0 if t == 0 else (1 if t == 1 else 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1),  # out elastic - 24
    lambda t: 0 if t == 0 else (1 if t == 1 else - 2 ** (10 * t - 10) * math.sin((t * 10 - 10.75) * (2 * math.pi / 3))),  # in elastic - 25
    lambda t: 7.5625 * (t ** 2) if (t < 1 / 2.75) else (7.5625 * (t - (1.5 / 2.75)) * (t - (1.5 / 2.75)) + 0.75 if (t < 2 / 2.75) else (7.5625 * (t - (2.25 / 2.75)) * (t - (2.25 / 2.75)) + 0.9375 if (t < 2.5 / 2.75) else (7.5625 * (t - (2.625 / 2.75)) * (t - (2.625 / 2.75)) + 0.984375))),  # out bounce - 26
    lambda t: 1 - (7.5625 * ((1 - t) ** 2) if ((1 - t) < 1 / 2.75) else (7.5625 * ((1 - t) - (1.5 / 2.75)) * ((1 - t) - (1.5 / 2.75)) + 0.75 if ((1 - t) < 2 / 2.75) else (7.5625 * ((1 - t) - (2.25 / 2.75)) * ((1 - t) - (2.25 / 2.75)) + 0.9375 if ((1 - t) < 2.5 / 2.75) else (7.5625 * ((1 - t) - (2.625 / 2.75)) * ((1 - t) - (2.625 / 2.75)) + 0.984375)))),  # in bounce - 27
    lambda t: (1 - (7.5625 * ((1 - 2 * t) ** 2) if ((1 - 2 * t) < 1 / 2.75) else (7.5625 * ((1 - 2 * t) - (1.5 / 2.75)) * ((1 - 2 * t) - (1.5 / 2.75)) + 0.75 if ((1 - 2 * t) < 2 / 2.75) else (7.5625 * ((1 - 2 * t) - (2.25 / 2.75)) * ((1 - 2 * t) - (2.25 / 2.75)) + 0.9375 if ((1 - 2 * t) < 2.5 / 2.75) else (7.5625 * ((1 - 2 * t) - (2.625 / 2.75)) * ((1 - 2 * t) - (2.625 / 2.75)) + 0.984375))))) / 2 if t < 0.5 else (1 + (7.5625 * ((2 * t - 1) ** 2) if ((2 * t - 1) < 1 / 2.75) else (7.5625 * ((2 * t - 1) - (1.5 / 2.75)) * ((2 * t - 1) - (1.5 / 2.75)) + 0.75 if ((2 * t - 1) < 2 / 2.75) else (7.5625 * ((2 * t - 1) - (2.25 / 2.75)) * ((2 * t - 1) - (2.25 / 2.75)) + 0.9375 if ((2 * t - 1) < 2.5 / 2.75) else (7.5625 * ((2 * t - 1) - (2.625 / 2.75)) * ((2 * t - 1) - (2.625 / 2.75)) + 0.984375))))) / 2,  # io bounce - 28
    lambda t: 0 if t == 0 else (1 if t == 0 else (-2 ** (20 * t - 10) * math.sin((20 * t - 11.125) * ((2 * math.pi) / 4.5))) / 2 if t < 0.5 else (2 ** (-20 * t + 10) * math.sin((20 * t - 11.125) * ((2 * math.pi) / 4.5))) / 2 + 1)  # io elastic - 29
]
```

---

## 5.1.8 Controls

Control 是以关键帧形式控制 note 各项参数的一个 RPE 特性。

### Alpha Control

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| easing | int | 到下一个关键帧数值的缓动类型，详见 [easingType](#easingtype) | - | - |
| alpha | float | note 不透明度 | 1.0 | - |
| x | float | note 与判定线的纵向距离 | - | - |

- `alpha control` 可以控制 note 的不透明度。
- 可以与 note 的 `alpha` 字段结合使用，不冲突，混合公式为 `noteAlpha = noteAlpha * nowAlpha`（先从 0\~255 转换为 0\~1 后再计算）。

#### 行为示例

当 `alpha control` 如下时：

```json
{
  "alphaControl": [
    { "alpha": 1.0, "easing": 1, "x": 0.0 },
    { "alpha": 0.5, "easing": 2, "x": 100.0 },
    { "alpha": 1.0, "easing": 1, "x": 9999999.0 }
  ]
}
```

note 在距离判定线 `100` 个 y 坐标单位前不透明度为 `0.5`，在 `100` 个 y 坐标单位后以 Out Sine 缓动函数缓动到 `1.0` 不透明度到与判定线重合。

### Size Control

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| easing | int | 到下一个关键帧数值的缓动类型，详见 [easingType](#easingtype) | 1 | - |
| size | float | note 大小倍率 | 1.0 | - |
| x | float | note 与判定线的纵向距离 | - | - |

- `size control` 可以真正地控制 note 的大小，而不仅仅控制宽度。
- 可以与 note 的宽度字段结合使用，不冲突。
- 无法影响 Hold 类型的 note 大小。

#### 行为示例

当 `size control` 如下时：

```json
{
  "sizeControl": [
    { "easing": 1, "size": 1.0, "x": 0.0 },
    { "easing": 2, "size": 1.5, "x": 200.0 },
    { "easing": 1, "size": 1.0, "x": 9999999.0 }
  ]
}
```

note 在距离判定线 `200` 个 y 坐标前大小为原先的 `1.5` 倍，在 `200` 个 y 坐标单位后以 Out Sine 缓动函数缓动到 `1.0` 倍大小到与判定线重合。

### pos Control（X Control）

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| easing | int | 到下一个关键帧数值的缓动类型，详见 [easingType](#easingtype) | 1 | - |
| pos | float | note 的 `positionX` 参数倍率 | - | - |
| x | float | note 与判定线的纵向距离 | - | - |

- `pos control` 可以动态控制 note 的 `positionX` 倍率。
- 不能控制 Hold 类型的 note。

#### 行为示例

当 `pos control` 如下时：

```json
{
  "posControl": [
    { "easing": 1, "pos": 2.0, "x": 0.0 },
    { "easing": 2, "pos": 1.0, "x": 100.0 },
    { "easing": 1, "pos": 1.0, "x": 9999999.0 }
  ]
}
```

note 在距离判定线 `100` 个 y 坐标单位前 note 的 `positionX` 为原先的 `2.0` 倍，在 `100` 个 y 坐标单位后以 Out Sine 缓动函数缓动 note 的 `positionX` 为 `1.0` 倍到与判定线重合。

### y Control

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| easing | int | 到下一个关键帧数值的缓动类型，详见 [easingType](#easingtype) | 1 | - |
| y | float | （待补充） | - | - |
| x | float | note 与判定线的纵向距离 | - | - |

- 行为描述待补充。

### Skew Control

| 字段名 | 类型 | 描述 | 默认值 | 加入版本 |
| --- | --- | --- | --- | --- |
| easing | int | 到下一个关键帧数值的缓动类型，详见 [easingType](#easingtype) | 1 | - |
| skew | float | （待补充） | - | - |
| x | float | note 与判定线的纵向距离 | - | - |

- 对 Hold 类型的 note 无效。
- 行为描述待补充。
