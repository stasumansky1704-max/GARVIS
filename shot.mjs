import { chromium } from "playwright";

const out = process.argv[2] || "shot.png";
const browser = await chromium.launch({
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--enable-unsafe-swiftshader",
  ],
});
const page = await browser.newPage({
  viewport: { width: 1920, height: 1080 }, // 16:9
  deviceScaleFactor: 2, // -> 3840x2160 (4K) crisp capture
});
const errs = [];
page.on("pageerror", (e) => errs.push("PAGEERR " + e.message));
page.on("console", (m) => { if (m.type() === "error") errs.push("CONSOLE " + m.text()); });

await page.goto("http://localhost:5173/", { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(5000);
await page.screenshot({ path: out, timeout: 120000 });
console.log("SHOT_OK " + out);
console.log("ERRS " + (errs.length ? errs.join(" | ") : "none"));
await browser.close();
