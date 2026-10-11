---
name: bas-danmaku-generator
description: Generate, explain, and revise Bilibili Animation Script (BAS) danmaku, convert SVG artwork to BAS paths, validate it with Bilibili's parser, and export rendered preview videos. Use when a user wants BAS source code for subtitles, animated text, timed visual effects, SVG conversion, interactive BAS elements, or a quick video preview of BAS.
---

# BAS 弹幕生成

把用户的创意转成可粘贴到 Bilibili BAS Playground 的 BAS 脚本；优先生成语法克制、可读、易调试的代码。BAS 是声明式脚本，不是 JavaScript，也不是普通 XML。

## 工作流程

1. **确认最低必要需求**：确定画面内容、出现时间/持续时间、位置、颜色/字号、动画方向与节奏。用户没给细节时，采用合理默认值并说明；只有缺失信息会实质改变结果时才追问。默认目标为视频舞台、居中或不遮挡主体、文本清晰、动画简短。
2. **规划时间线**：把每个对象及其动画起点、时长和先后/并行关系写清。区分对象 `duration`（生命周期）与每个 `set` 后的动画时长；需要串行动画时使用 `then`，并行动画使用相邻的 `set`。
3. **生成或转换脚本**：使用 `def text 名称 { ... }` 定义对象，`set 名称 { ... } 时长` 设置动画。若用户提供 SVG 文件并要求转换，优先运行下方 `svg_to_bas.py`，检查输出警告，并用 BAS 官方解析器验证结果；只用 BAS 支持的对象、属性与表达式，细节见 [references/syntax.md](references/syntax.md)。
4. **快速验证**：若当前环境可运行 Node.js 且依赖可安装，将生成的代码保存为 `.bas` 文件，运行 `node /home/ubuntu/skills/bas-danmaku-generator/scripts/validate_bas.js <file.bas>`，用 Bilibili 官方解析器检查语法。首次运行会从官方 GitHub 下载解析器；需要 `jsdom` 和 `jquery`（缺少时执行 `npm install jsdom jquery`）。也可通过 `--bas-js <path>` 使用已下载的解析器。验证失败时依据报错修复并重试；不能运行脚本时做人工检查，并明确告知尚未用解析器验证。
5. **导出预览视频（用户提出时）**：按下方“预览视频导出”操作，使用官方 BAS 渲染器录制实际弹幕动画；默认根据脚本生命周期自动决定时长，默认输出 1280×720、30 fps MP4。播放预览通过后再交付代码和视频。
6. **自检**：检查对象名一致、花括号/字符串完整、时间单位正确、百分比仅用于适合的舞台尺寸属性、属性值类型合理；不要把 JS/CSS 语法塞进脚本。并行 set 里避免重复改同一属性；空间变换属性 `x/y/rotateX/rotateY/rotateZ/scale` 可能互相冲突。语法通过不代表画面效果、客户端兼容性或投稿权限已验证。
7. **交付**：先给完整 BAS 代码块，再给用户要求的预览视频和关键参数/时间线说明。建议在官方 [BAS Playground](https://bilibili.github.io/bas/#/playground) 粘贴预览；明确区分解析器语法验证与视频渲染验证。

## 生成原则

- 默认用简单文本对象完成需求；只有明确需要时才用 button 或 path。交互按钮应只在用户要求交互时生成，并说明目标参数需要用户提供及在客户端检查。
- 可用 `0xffffff` 形式表示十六进制颜色。文本默认属性包含白色、25px、SimHei、粗体、文字阴影；需要稳定观感时显式设置关键属性。
- `x`、`y`、`fontSize` 可使用百分比以适配播放器大小。位置由 `x/y` 与 `anchorX/anchorY` 共同决定；中心锚点常用 `0.5`。
- `duration` 和动画时长用 BAS 时间值，例如 `2s`、`500ms`；可按参考文档中的合法时间单位书写，不要把毫秒数当成裸数字。
- 不声称 BAS 脚本可绕过 Bilibili 弹幕投稿权限、审核或客户端能力限制。

## 最小模板

```bas
def text title {
  content = "示例文字"
  x = 50%
  y = 50%
  anchorX = 0.5
  anchorY = 0.5
  fontSize = 5%
  color = 0xffffff
  duration = 4s
}
set title {
  alpha = 0
} 4s
```

这段展示了居中、响应式字号与淡出；BAS 的动画属性通常由定义时默认状态向 set 目标值变化。生成其他效果时应按需求调整初态和 set 目标，避免描述动画方向与代码相反。

## 预览视频导出

用 `scripts/export_preview.py` 调用官方 `bas.js` 解析并渲染脚本，在 Chromium 中录制后用 FFmpeg 转成 MP4。先保存脚本为 UTF-8 `.bas` 文件，再执行：

```bash
python3 /home/ubuntu/skills/bas-danmaku-generator/scripts/export_preview.py input.bas preview.mp4
```

常用选项：

```bash
python3 /home/ubuntu/skills/bas-danmaku-generator/scripts/export_preview.py input.bas preview.mp4 \
  --duration 8 --width 1920 --height 1080 --fps 30 --background '#161821'
```

默认根据 BAS 对象的显式 `duration` 或相关动画时长自动选取视频长度；无动画对象采用 BAS 默认生命周期。`--duration` 可覆盖长度（秒），适合要多留/少留片尾时使用；`--keep-webm` 可保留浏览器原始录制。首次使用会下载官方 BAS JS 与 jQuery 并缓存在用户缓存目录；运行需要 Python Playwright、Chromium/Chrome（或 `python3 -m playwright install chromium`）、Playwright 录制所需的 FFmpeg（`python3 -m playwright install ffmpeg`）以及系统 FFmpeg。脚本输出为不含音频、实色背景的 H.264 MP4；它用于快速检查动画，不保留透明通道，也不等同于 Bilibili 投稿或移动端兼容性测试。若环境缺少依赖，不要用静态截图冒充预览视频，应报告具体缺失项。


## SVG 转 BAS

用户要把 SVG 图形/图标转换为 BAS 时，使用 `scripts/svg_to_bas.py`：

```bash
python3 /home/ubuntu/skills/bas-danmaku-generator/scripts/svg_to_bas.py input.svg output.bas
```

省略 `output.bas` 时默认在 SVG 同目录生成同名 `.bas`。可用 `--x 50% --y 50% --scale 2` 指定整体舞台位置和缩放；默认 `x=0`、`y=0`、`scale=1`。工具使用 Python 标准库，无额外依赖。支持 `path`、直角 `rect`、`circle`、`ellipse`、`line`、`polyline`、`polygon`，并映射 `viewBox`、内联/继承的基础填充色、描边和透明度。转换后运行 `validate_bas.js` 检查 BAS 语法；有条件时再运行 `export_preview.py` 检查实际图形位置与样式。

明确告知工具限制：不执行 SVG/脚本、不读取外部样式表；目前不会扁平化 `transform`，不支持圆角矩形、文字、渐变、滤镜、裁剪/遮罩、图片嵌入和 CSS class。遇到转换失败时，不要静默删除这些效果；说明如何在 SVG 编辑器中将变换应用、文字转路径、复杂效果栅格化或简化后再转换。转换器对颜色和尺寸格式有明确限制，命令输出的警告必须一并检查。
