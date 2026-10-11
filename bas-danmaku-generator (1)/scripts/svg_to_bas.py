#!/usr/bin/env python3
"""Convert basic SVG geometry and inline styles into BAS path objects."""
from __future__ import annotations

import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SUPPORTED = {"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"}
RESERVED_NAMES = {"def", "set", "then"}
COLOR_NAMES = {
    "black": "#000000", "white": "#ffffff", "red": "#ff0000", "green": "#008000",
    "blue": "#0000ff", "yellow": "#ffff00", "cyan": "#00ffff", "aqua": "#00ffff",
    "magenta": "#ff00ff", "fuchsia": "#ff00ff", "gray": "#808080", "grey": "#808080",
    "silver": "#c0c0c0", "orange": "#ffa500", "purple": "#800080", "navy": "#000080",
    "teal": "#008080", "lime": "#00ff00", "maroon": "#800000", "olive": "#808000",
}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def number(attrs: dict[str, str], key: str, default: float = 0.0) -> float:
    value = attrs.get(key)
    if value is None or value == "":
        return default
    match = re.fullmatch(r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(?:px)?\s*", value)
    if not match:
        raise ValueError(f"不支持 {key}={value!r}：仅接受无单位数值或 px")
    return float(match.group(1))


def fmt(n: float) -> str:
    if not math.isfinite(n):
        raise ValueError("SVG 坐标包含非有限数值")
    if abs(n) < 1e-10:
        n = 0
    return f"{n:g}"


def points_to_path(value: str, close: bool) -> str:
    numbers = re.findall(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value or "")
    if len(numbers) < 4 or len(numbers) % 2:
        raise ValueError("polyline/polygon 的 points 必须至少包含两组 x,y 坐标")
    pairs = list(zip(map(float, numbers[::2]), map(float, numbers[1::2])))
    result = [f"M{fmt(pairs[0][0])},{fmt(pairs[0][1])}"]
    result.extend(f"L{fmt(x)},{fmt(y)}" for x, y in pairs[1:])
    if close:
        result.append("Z")
    return " ".join(result)


def geometry_to_path(tag: str, attrs: dict[str, str]) -> str:
    if tag == "path":
        d = attrs.get("d", "").strip()
        if not d:
            raise ValueError("path 元素缺少 d 属性")
        return d
    if tag == "line":
        return f"M{fmt(number(attrs, 'x1'))},{fmt(number(attrs, 'y1'))} L{fmt(number(attrs, 'x2'))},{fmt(number(attrs, 'y2'))}"
    if tag in ("polyline", "polygon"):
        return points_to_path(attrs.get("points", ""), tag == "polygon")
    if tag == "rect":
        x, y = number(attrs, "x"), number(attrs, "y")
        w, h = number(attrs, "width"), number(attrs, "height")
        if w <= 0 or h <= 0:
            raise ValueError("rect 的 width/height 必须大于 0")
        if number(attrs, "rx") or number(attrs, "ry"):
            raise ValueError("暂不支持圆角 rect（rx/ry），请先在 SVG 编辑器中转为 path")
        return f"M{fmt(x)},{fmt(y)} H{fmt(x+w)} V{fmt(y+h)} H{fmt(x)} Z"
    if tag in ("circle", "ellipse"):
        cx, cy = number(attrs, "cx"), number(attrs, "cy")
        if tag == "circle":
            rx = ry = number(attrs, "r")
        else:
            rx, ry = number(attrs, "rx"), number(attrs, "ry")
        if rx <= 0 or ry <= 0:
            raise ValueError(f"{tag} 的半径必须大于 0")
        left, right, top, bottom = cx-rx, cx+rx, cy-ry, cy+ry
        return f"M{fmt(left)},{fmt(cy)} A{fmt(rx)},{fmt(ry)} 0 1 0 {fmt(right)},{fmt(cy)} A{fmt(rx)},{fmt(ry)} 0 1 0 {fmt(left)},{fmt(cy)} Z"
    raise ValueError(f"不支持的 SVG 图形：{tag}")


def parse_style(element: ET.Element) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("fill", "stroke", "stroke-width", "fill-opacity", "stroke-opacity", "opacity", "color"):
        if key in element.attrib:
            result[key] = element.attrib[key].strip()
    for item in element.attrib.get("style", "").split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            result[key.strip().lower()] = value.strip()
    return result


def color_and_alpha(raw: str | None, default: str) -> tuple[int, float]:
    value = (raw or default).strip().lower()
    if value == "none":
        return 0xffffff, 0.0
    value = COLOR_NAMES.get(value, value)
    if value.startswith("#"):
        code = value[1:]
        if len(code) == 3:
            code = "".join(ch * 2 for ch in code)
        if len(code) == 4:
            code = "".join(ch * 2 for ch in code)
        if len(code) == 6:
            return int(code, 16), 1.0
        if len(code) == 8:
            return int(code[:6], 16), int(code[6:8], 16) / 255
        raise ValueError(f"不支持的十六进制颜色：{raw}")
    match = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", value)
    if match:
        rgb = tuple(max(0, min(255, int(match.group(i)))) for i in (1, 2, 3))
        alpha = float(match.group(4)) if match.group(4) is not None else 1.0
        return (rgb[0] << 16) | (rgb[1] << 8) | rgb[2], max(0.0, min(1.0, alpha))
    raise ValueError(f"暂不支持 CSS 颜色 {raw!r}；请改用 #RGB/#RRGGBB/#RRGGBBAA、rgb()/rgba() 或常见颜色名")


def alpha_value(raw: str | None, default: float = 1.0) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"无效透明度：{raw}") from exc
    return max(0.0, min(1.0, value))


def bas_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def safe_name(raw: str, index: int, used: set[str]) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", raw or "")
    if not name or not re.match(r"[A-Za-z_]", name):
        name = f"svg_{index}_{name}" if name else f"svg_{index}"
    base = name
    if name.lower() in RESERVED_NAMES:
        name = f"svg_{name}"
        base = name
    suffix = 2
    while name in used:
        name = f"{base}_{suffix}"
        suffix += 1
    used.add(name)
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description="将 SVG 基础几何转换为 BAS path 定义")
    parser.add_argument("input", help="输入 SVG 文件")
    parser.add_argument("output", nargs="?", help="输出 BAS 文件（默认与输入同名）")
    parser.add_argument("--x", default="0", help="BAS 舞台 x 位置，例如 50%% 或 640（默认 0）")
    parser.add_argument("--y", default="0", help="BAS 舞台 y 位置，例如 50%% 或 360（默认 0）")
    parser.add_argument("--scale", type=float, default=1.0, help="图形缩放倍率（默认 1）")
    args = parser.parse_args()
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)%?", args.x) or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)%?", args.y):
        print("--x/--y 只接受数字或百分比，例如 240、50%", file=sys.stderr)
        return 2
    if not math.isfinite(args.scale) or args.scale <= 0:
        print("--scale 必须是大于 0 的有限数值。", file=sys.stderr)
        return 2

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else input_path.with_suffix(".bas")
    if not input_path.is_file():
        print(f"找不到 SVG 文件：{input_path}", file=sys.stderr)
        return 2
    try:
        root = ET.parse(input_path).getroot()
        if local_name(root.tag) != "svg":
            raise ValueError("输入文件根元素不是 <svg>")
        vb = root.attrib.get("viewBox")
        if not vb:
            width, height = number(root.attrib, "width"), number(root.attrib, "height")
            if width <= 0 or height <= 0:
                raise ValueError("SVG 缺少有效 viewBox；也未提供可读取的 width/height")
            vb = f"0 0 {fmt(width)} {fmt(height)}"
        view_box = " ".join(vb.replace(",", " ").split())
        try:
            if len(view_box.split()) != 4 or any(not math.isfinite(float(n)) for n in view_box.split()):
                raise ValueError
        except ValueError as exc:
            raise ValueError(f"viewBox 格式应为四个数值，实际为 {vb!r}") from exc

        objects: list[tuple[str, str, dict[str, str]]] = []
        warnings: list[str] = []
        used: set[str] = set()

        def walk(node: ET.Element, inherited: dict[str, str], opacity_product: float = 1.0, transforms: bool = False) -> None:
            tag = local_name(node.tag)
            if "class" in node.attrib:
                warnings.append("忽略了 SVG class；工具不加载外部样式表或 CSS 选择器")
            if "style" in node.attrib:
                style_keys = {item.split(":", 1)[0].strip().lower() for item in node.attrib["style"].split(";") if ":" in item}
                unsupported = style_keys - {"fill", "stroke", "stroke-width", "fill-opacity", "stroke-opacity", "opacity", "color"}
                if unsupported:
                    warnings.append("未映射 CSS 属性：" + ", ".join(sorted(unsupported)))
            style = dict(inherited)
            local_style = parse_style(node)
            style.update(local_style)
            own_opacity = alpha_value(local_style.get("opacity"), 1.0)
            opacity = opacity_product * own_opacity
            has_transform = transforms or "transform" in node.attrib
            if has_transform:
                raise ValueError("检测到 transform 属性：当前工具不会扁平化 SVG 变换，请先在绘图软件中应用/扁平化变换")
            if tag in SUPPORTED:
                d = geometry_to_path(tag, node.attrib)
                fill, fill_alpha = color_and_alpha(style.get("fill"), "#000000")
                stroke, stroke_alpha = color_and_alpha(style.get("stroke"), "none")
                fill_alpha *= opacity * alpha_value(style.get("fill-opacity"), 1.0)
                stroke_alpha *= opacity * alpha_value(style.get("stroke-opacity"), 1.0)
                stroke_width = number(node.attrib | {"stroke-width": style.get("stroke-width", "0")}, "stroke-width")
                name = safe_name(node.attrib.get("id", ""), len(objects) + 1, used)
                attrs = {
                    "d": d,
                    "fill": f"0x{fill:06x}",
                    "fillAlpha": fmt(fill_alpha),
                    "stroke": f"0x{stroke:06x}",
                    "strokeAlpha": fmt(stroke_alpha),
                    "strokeWidth": fmt(stroke_width),
                }
                objects.append((name, tag, attrs))
            elif tag not in {"svg", "g", "defs", "title", "desc", "metadata", "clippath", "mask", "symbol", "lineargradient", "radialgradient", "stop"}:
                warnings.append(f"跳过不支持的元素 <{tag}>")
            if tag in {"defs", "clippath", "mask", "symbol", "lineargradient", "radialgradient"}:
                if tag in {"clippath", "mask", "symbol", "lineargradient", "radialgradient"}:
                    warnings.append(f"未处理 <{tag}>（引用/滤镜资源不会自动映射到 BAS）")
                return
            for child in list(node):
                walk(child, style, opacity, has_transform)

        walk(root, {})
        if not objects:
            raise ValueError("SVG 中没有可转换的 path/rect/circle/ellipse/line/polyline/polygon 图形")

        lines: list[str] = []
        for name, tag, attrs in objects:
            lines.extend([
                f"def path {name} {{",
                f"  d = {bas_string(attrs['d'])}",
                f"  viewBox = {bas_string(view_box)}",
                f"  x = {args.x}",
                f"  y = {args.y}",
                f"  scale = {fmt(args.scale)}",
                f"  fillColor = {attrs['fill']}",
                f"  fillAlpha = {attrs['fillAlpha']}",
                f"  borderColor = {attrs['stroke']}",
                f"  borderAlpha = {attrs['strokeAlpha']}",
                f"  borderWidth = {attrs['strokeWidth']}",
                "}",
                "",
            ])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"已转换 {len(objects)} 个 SVG 图形：{output_path}")
        print("视图范围：" + view_box)
        for warning in dict.fromkeys(warnings):
            print("警告：" + warning, file=sys.stderr)
        return 0
    except (ET.ParseError, OSError, ValueError) as exc:
        print(f"SVG 转换失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
