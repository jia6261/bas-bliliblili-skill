#!/usr/bin/env node
'use strict';

/** Validate a BAS source file with Bilibili's official bas.js parser. */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const https = require('node:https');
const { URL } = require('node:url');
const { createRequire } = require('node:module');

const BAS_URL = 'https://raw.githubusercontent.com/bilibili/bas/gh-pages/bas.js';
const BAS_CACHE = path.join(os.tmpdir(), 'bas-danmaku-generator-bas.js');

function usage() {
  console.error('用法: node validate_bas.js <file.bas> [--bas-js /path/to/bas.js]');
  console.error('依赖: npm install jsdom jquery');
  process.exit(2);
}

function download(url, dest, redirects = 5) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        if (redirects <= 0) return reject(new Error('重定向次数过多'));
        return resolve(download(new URL(res.headers.location, url).toString(), dest, redirects - 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`下载官方解析器失败：HTTP ${res.statusCode}`));
      }
      const out = fs.createWriteStream(dest);
      res.pipe(out);
      out.on('finish', () => out.close(resolve));
      out.on('error', reject);
    }).on('error', reject);
  });
}

async function main() {
  const args = process.argv.slice(2);
  if (!args.length || args[0].startsWith('--')) usage();
  const sourcePath = path.resolve(args[0]);
  let parserPath = process.env.BAS_JS || '';
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--bas-js' && args[i + 1]) parserPath = args[++i];
    else usage();
  }
  if (!fs.existsSync(sourcePath)) {
    console.error(`找不到 BAS 文件：${sourcePath}`);
    process.exit(2);
  }

  let JSDOM, jquery;
  let dom;
  try {
    // Resolve from the caller's project as well as this skill's own directory.
    const fromCwd = createRequire(path.join(process.cwd(), 'package.json'));
    ({ JSDOM } = fromCwd('jsdom'));
    dom = new JSDOM('<!doctype html><html><head></head><body><div id="player"></div></body></html>', { url: 'http://localhost/' });
    global.window = dom.window;
    global.document = dom.window.document;
    jquery = fromCwd('jquery');
  } catch (error) {
    console.error(`无法加载 jsdom/jquery（${error.message}）。请在当前目录运行：npm install jsdom jquery`);
    process.exit(2);
  }

  if (parserPath) {
    parserPath = path.resolve(parserPath);
    if (!fs.existsSync(parserPath)) {
      console.error(`找不到 BAS 解析器：${parserPath}`);
      process.exit(2);
    }
  } else {
    parserPath = BAS_CACHE;
    if (!fs.existsSync(parserPath)) {
      console.error('首次运行：正在下载 Bilibili 官方 BAS 解析器…');
      await download(BAS_URL, parserPath);
    }
  }

  const source = fs.readFileSync(sourcePath, 'utf8');
  global.window = dom.window;
  global.document = dom.window.document;
  Object.defineProperty(global, 'navigator', { value: dom.window.navigator, configurable: true });
  global.Worker = undefined; // Use the library's synchronous parser path in Node.
  global.$ = jquery(dom.window);
  global.jQuery = global.$;

  try {
    const BasDanmaku = require(parserPath);
    const parser = new BasDanmaku({}, null);
    parser.workerDisabled = true;
    parser.parse({
      danmaku: { text: source },
      success(result) {
        console.log(`BAS 语法通过：${path.basename(sourcePath)}（${result.defs.length} 个对象定义，${result.sets.length} 组动画）`);
        dom.window.close();
      },
      error(message) {
        console.error(`BAS 语法错误：${message}`);
        dom.window.close();
        process.exitCode = 1;
      },
    });
  } catch (error) {
    console.error(`验证失败：${error.message}`);
    dom.window.close();
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(`验证器错误：${error.message}`);
  process.exit(2);
});
