import { chromium } from "playwright";
const b = await chromium.launch({ args:["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport:{width:1600,height:900}, deviceScaleFactor:1 });
const errs=[]; p.on("pageerror",e=>errs.push(e.message)); p.on("console",m=>{if(m.type()==="error")errs.push("CON:"+m.text());});
const net=[]; p.on("response",r=>{ const u=r.url(); if(u.includes("8000")) net.push(r.status()+" "+u); });
await p.goto("http://localhost:3000/",{waitUntil:"networkidle",timeout:60000});
await p.waitForTimeout(5000);
await p.screenshot({path:"/tmp/integration_home.png"});
// has canvas?
const hasCanvas = await p.evaluate(()=>!!document.querySelector("canvas"));
console.log("HAS_CANVAS:", hasCanvas);
console.log("ERRORS:", errs.length?errs.slice(0,5).join(" | "):"none");
console.log("BACKEND_CALLS:", net.length?net.slice(0,8).join(" ; "):"none on load (expected — command bar is on submit)");
await b.close();
