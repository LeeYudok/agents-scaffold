// 인트로·장면 HTML 을 Chromium 으로 열어 webm 으로 녹화한다. mix.py 가 렌더 작업 폴더의 intro.webm·scene2.webm 을 1·2장에 끼운다.
// 사용: node tools/record_intro.mjs <page.html> <초> <출력 webm>   (Chromium 경로: PW_CHROMIUM, 없으면 playwright 기본 브라우저)
import { chromium } from "playwright-core";
import { existsSync, mkdirSync, renameSync } from "node:fs";
import { dirname, resolve } from "node:path";

const [page = "", sec = "10", out = ""] = process.argv.slice(2);
if (!page || !out) {
  console.error("사용: node tools/record_intro.mjs <page.html> <초> <출력 webm>");
  process.exit(2);
}
const target = resolve(out);
const dir = dirname(target);
mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.PW_CHROMIUM, args: ["--force-device-scale-factor=1"] });
const ctx = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  recordVideo: { dir, size: { width: 1920, height: 1080 } },
});
const tab = await ctx.newPage();
await tab.goto("file://" + resolve(page));
await tab.waitForTimeout(Number(sec) * 1000);
const video = tab.video();
await ctx.close();
const path = await video.path();
await browser.close();
if (existsSync(target)) renameSync(target, target + ".old");
renameSync(path, target);
console.log("recorded", target);
