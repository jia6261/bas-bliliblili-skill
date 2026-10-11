# BAS 语法参考（按需加载）

依据：Bilibili 的 [bilibili/bas](https://github.com/bilibili/bas) 解析器/前端源码（`bas.js`）及 [BAS 高级弹幕教程](https://diygod.cc/bas/)。官方编辑试验场：[BAS Playground](https://bilibili.github.io/bas/#/playground)。教程较早，客户端和投稿能力可能变化；输出应以用户实际播放器/试验场为准。

## 基本结构

```bas
def text demo {
  content = "BAS"
  x = 50%
  y = 50%
  anchorX = 0.5
  anchorY = 0.5
}
set demo {
  alpha = 0
} 5s
```

- `def text 名称 { 属性 = 值 ... }` 定义文本对象。
- `set 名称 { 属性 = 目标值 ... } 时长` 定义一个动画操作；初始值来自对象属性或类型默认值。
- `then` 将 set 串联；相邻 set 表示并行。
- 对象生命周期用 `duration` 指定；未指定时，教程说明生命周期通常由动画总时长决定，没有动画则默认 4 秒。若需可靠控制，显式写 `duration`。
- BAS 使用声明式语法，不能用 JS 语句、HTML 或 CSS 替代。

## 可确认的对象类型和属性

### `text`

源码中的默认属性包括：`content`、`alpha`、`color`、`anchorX`、`anchorY`、`fontSize`、`fontFamily`、`bold`、`textShadow`、`strokeWidth`、`strokeColor`、`rotateX`、`rotateY`、`rotateZ`、`parent`；通用位置/缩放属性包括 `x`、`y`、`zIndex`、`scale`、`duration`。

常用默认值：内容占位文字、alpha=1、白色、锚点 0/0、字号 25、SimHei、bold=1、textShadow=1、描边宽度 0。输出时不要依赖占位内容，显式写 `content`。

### `button`

源码默认属性包括 `text`、`fontSize`、`textColor`、`textAlpha`、`fillColor`、`fillAlpha`、`target`。教程列出的目标类型有 `seek`（跳转当前视频时间）、`av` 和 `bangumi`。仅在用户明确需要点击交互时使用；按需提供并核实目标 ID、页码和时间。

### `path`

源码默认属性包括 SVG `d`、`viewBox`、`borderColor`、`borderAlpha`、`borderWidth`、`fillColor`、`fillAlpha`。适合简单图形；`d` 为 SVG path 数据。不要未经验证构造过长复杂 SVG 路径。

## 单位、定位与动画

- 教程示例使用 `s`、`ms`、`m` 等时间单位（如 `5s`、`20.5s500ms`、`1m30s`）。按具体目标用清楚、可读的时长。
- `x`、`y`、`fontSize` 支持百分比；位置以舞台宽高的百分比计算，百分比字号以舞台宽度为基准。
- `anchorX`、`anchorY` 为锚点比例：0 表示左/上，1 表示右/下，0.5 表示中心。
- `alpha` 范围按透明度常规使用 0 到 1；颜色示例采用 `0xffffff`。
- 教程示例确认 `color`、`alpha` 等可做动画。不要把所有定义属性都假定为可动画；不确定的属性应查 Playground 或只作为静态属性。
- 并行 set 同一属性会冲突；实现中 `x/y/rotateX/rotateY/rotateZ/scale` 视为同一变换组，避免在同时段分别驱动它们。用 `then` 可表达先后阶段。

## 可靠示例

### 依次渐变文字颜色，再淡出

```bas
def text intro {
  content = "光会记得方向"
  x = 50%
  y = 50%
  anchorX = 0.5
  anchorY = 0.5
  fontSize = 5%
  color = 0xffffff
  duration = 4s
}
set intro {
  color = 0xffcc66
} 1s then set intro {
  alpha = 0
} 2s
```

### 两项独立属性同时动画

```bas
def text caption {
  content = "字幕内容"
  x = 50%
  y = 80%
  anchorX = 0.5
  fontSize = 4%
  color = 0xffffff
  duration = 3s
}
set caption {
  alpha = 0
} 3s
set caption {
  y = 70%
} 3s
```

以上用于说明并行形式；由于不同 BAS 版本/属性能力可能变化，提交前在 Playground 检查。若属性冲突，则改为串联动画或避免同时修改。

## 易错点

- 对象名字在定义和 set 中必须一致。
- 中文文本用双引号；代码块内只放 BAS 源码，不要混入解释注释（除非已确认注释语法）。
- `duration` 是对象总生命周期，不等同于各个动画时长。总生命周期应覆盖最后一个动画阶段。
- 需要保持可见时不要无意间把初始 `alpha` 设为 0；淡入应从 `alpha = 0` 定义，再 set 到 `alpha = 1`。
- 多个动画阶段用 `then` 明确连接；不要误以为换行本身代表串行。
- 投稿权限、是否显示发送入口与脚本语法是两回事。
