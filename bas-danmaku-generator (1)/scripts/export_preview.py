#!/usr/bin/env python3
"""Render a BAS script with Bilibili's official renderer and export an MP4 preview."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

BAS_JS_URL = "https://raw.githubusercontent.com/bilibili/bas/gh-pages/bas.js"
JQUERY_URL = "https://code.jquery.com/jquery-3.7.1.min.js"
CACHE = Path.home() / ".cache" / "bas-danmaku-generator"


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "BAS-Danmaku-Preview/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as out:
        shutil.copyfileobj(response, out)


def find_chromium(explicit: str | None, bundled: str | None = None) -> str:
    candidates = [explicit] if explicit else []
    candidates += [shutil.which(name) for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")]
    candidates += [bundled]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RuntimeError("找不到 Chromium/Chrome。请安装浏览器，或通过 --chromium 指定可执行文件路径。")


def render_html(source: str, width: int, height: int, background: str) -> str:
    # Keep the BAS source out of inline JS to avoid quoting/injection errors.
    escaped = json.dumps(source, ensure_ascii=False)
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body,#player{{margin:0;width:100%;height:100%;overflow:hidden;background:{background}}}#player{{position:relative}}</style>
</head><body><div id="player"></div><script>
window.__startBAS = function(source) {{
  return new Promise((resolve, reject) => {{
    const started = performance.now();
    const player = document.getElementById('player');
    const engine = new window.BasDanmaku({{container: player, timeSyncFunc: () => performance.now() - started}}, null);
    engine.workerDisabled = true;
    engine.parse({{danmaku: {{text: source}}, success(parsed) {{
      try {{
        const animationTime = (node) => {{
          if (!node) return 0;
          if (node.type === 'Unit') return Number(node.duration) || 0;
          const children = node.items || [];
          const times = children.map(animationTime);
          return node.type === 'Serial' ? times.reduce((a,b) => a+b, 0) : Math.max(0, ...times);
        }};
        const objectTimes = parsed.defs.map(def => {{
          if (Number.isFinite(def.attrs.duration)) return def.attrs.duration;
          const attached = parsed.sets.filter(set => {{
            const units = set.items || [set];
            return units.some(unit => unit.targetName === def.name);
          }}).map(animationTime);
          return attached.length ? Math.max(...attached) : 4000;
        }});
        const durationMs = Math.max(1000, ...objectTimes);
        const dm = Object.assign({{}}, parsed, {{stime: 0, dmid: 'bas-preview', text: source}});
        engine.add({{dm, parsed: true}});
        engine.play();
        window.__basEngine = engine;
        resolve({{durationMs, defs: parsed.defs.length, sets: parsed.sets.length, width: {width}, height: {height}}});
      }} catch (error) {{ reject(error.message || String(error)); }}
    }}, error(message) {{ reject(message); }}}});
  }});
}};
window.__source = {escaped};
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Export BAS as a rendered MP4 preview using the official BAS renderer.")
    parser.add_argument("source", help="input BAS text file")
    parser.add_argument("output", help="output MP4 path")
    parser.add_argument("--duration", type=float, help="override preview duration in seconds; default: infer from BAS animations")
    parser.add_argument("--width", type=int, default=1280, help="video width (default: 1280)")
    parser.add_argument("--height", type=int, default=720, help="video height (default: 720)")
    parser.add_argument("--fps", type=int, default=30, help="output frame rate (default: 30)")
    parser.add_argument("--background", default="#161821", help="opaque stage background (default: #161821)")
    parser.add_argument("--chromium", help="Chromium/Chrome executable path")
    parser.add_argument("--keep-webm", action="store_true", help="keep intermediate WebM recording next to the MP4")
    args = parser.parse_args()

    source_path = Path(args.source).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not source_path.is_file():
        print(f"找不到 BAS 文件：{source_path}", file=sys.stderr)
        return 2
    if args.width < 320 or args.height < 180 or args.fps < 1 or args.fps > 60:
        print("画面至少 320×180，帧率范围为 1–60 fps。", file=sys.stderr)
        return 2
    if args.duration is not None and args.duration <= 0:
        print("--duration 必须大于 0。", file=sys.stderr)
        return 2
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("找不到 ffmpeg。请先安装 FFmpeg。", file=sys.stderr)
        return 2
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("缺少 Python Playwright。请安装：pip install playwright", file=sys.stderr)
        return 2

    try:
        with sync_playwright() as p:
            browser_path = find_chromium(args.chromium, p.chromium.executable_path)
        bas_js = CACHE / "bas.js"
        jquery_js = CACHE / "jquery-3.7.1.min.js"
        if not bas_js.is_file():
            print("首次运行：获取 Bilibili 官方 BAS 渲染器…", flush=True)
            download(BAS_JS_URL, bas_js)
        if not jquery_js.is_file():
            print("获取本地渲染依赖 jQuery…", flush=True)
            download(JQUERY_URL, jquery_js)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="bas-preview-") as tmp:
            video_dir = Path(tmp) / "recording"
            video_dir.mkdir()
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path=browser_path, args=["--no-sandbox"])
                context = browser.new_context(
                    viewport={"width": args.width, "height": args.height},
                    record_video_dir=str(video_dir),
                    record_video_size={"width": args.width, "height": args.height},
                    device_scale_factor=1,
                )
                recording_started = time.monotonic()
                page = context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda exc: page_errors.append(f"{exc}\n{getattr(exc, 'stack', '')}"))
                page.set_content(render_html(source_path.read_text(encoding="utf-8-sig"), args.width, args.height, args.background), wait_until="load")
                page.add_script_tag(path=str(jquery_js))
                page.add_script_tag(path=str(bas_js))
                try:
                    details = page.evaluate("source => window.__startBAS(source)", source_path.read_text(encoding="utf-8-sig"))
                except Exception as exc:
                    raise RuntimeError(f"BAS 解析或渲染初始化失败：{exc}") from exc
                lead_in = max(0.0, time.monotonic() - recording_started)
                duration = args.duration if args.duration is not None else details["durationMs"] / 1000
                print(f"开始录制：{args.width}×{args.height}，{args.fps} fps，约 {duration:.2f} 秒；对象 {details['defs']} 个，动画组 {details['sets']} 组。", flush=True)
                # Keep the page alive for real-time CSS animation recording.
                page.wait_for_timeout(max(100, round(duration * 1000)))
                video = page.video
                await_path = Path(tmp) / "preview.webm"
                page.close()
                video.save_as(str(await_path))
                context.close()
                browser.close()
                harmless_cleanup = [e for e in page_errors if "Cannot read properties of undefined (reading '" in e and ("animationCallback" in e or "transience" in e)]
                fatal_errors = [e for e in page_errors if e not in harmless_cleanup]
                if fatal_errors:
                    raise RuntimeError("浏览器渲染异常：" + "；".join(fatal_errors[:3]))
                if harmless_cleanup:
                    print(f"提示：BAS 旧版渲染器在动画结束清理阶段产生 {len(harmless_cleanup)} 条浏览器警告；录制仍已完成。", flush=True)
                if video is None:
                    raise RuntimeError("浏览器没有生成录制文件。")

            if args.keep_webm:
                webm_path = output_path.with_suffix(".webm")
                shutil.copy2(await_path, webm_path)
            command = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(await_path), "-ss", f"{lead_in:.3f}", "-t", f"{duration:.3f}", "-an", "-vf", f"fps={args.fps},scale={args.width}:{args.height}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-movflags", "+faststart", str(output_path)]
            subprocess.run(command, check=True)
        print(f"MP4 预览已导出：{output_path}")
        return 0
    except Exception as exc:
        print(f"导出失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
