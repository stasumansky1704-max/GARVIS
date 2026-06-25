import { chromium } from "playwright";

const out = process.argv[2] || "shot_8k.png";
const browser = await chromium.launch({
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--enable-unsafe-swiftshader",
    "--max-active-webgl-contexts=16",
  ],
});
// 3840x2160 viewport @ deviceScaleFactor 2 -> 7680x4320 (8K UHD)
const page = await browser.newPage({
  viewport: { width: 3840, height: 2160 },
  deviceScaleFactor: 2,
});
const errs = [];
page.on("pageerror", (e) => errs.push("PAGEERR " + e.message));
page.on("console", (m) => { if (m.type() === "error") errs.push("CONSOLE " + m.text()); });

await page.goto("http://localhost:5173/", { waitUntil: "networkidle", timeout: 90000 });
await page.waitForTimeout(7000);
await page.screenshot({ path: out, timeout: 300000 });
console.log("SHOT_8K_OK " + out);
console.log("ERRS " + (errs.length ? errs.join(" | ") : "none"));
await browser.close();
