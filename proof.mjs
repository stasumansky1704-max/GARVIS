import { chromium } from "playwright";
const b = await chromium.launch({ args:["--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"] });
const p = await b.newPage({ viewport:{width:1280,height:720} });
let cmdStatus=null; p.on("response",async r=>{ if(r.url().includes("/runtime/command")){ cmdStatus=r.status(); } });
await p.goto("http://localhost:3000/",{waitUntil:"networkidle",timeout:60000});
await p.waitForTimeout(5000);
// measure max brightness (not area) at exact center 80x80 — reacts to glow intensity regardless of DPR
const peak=async()=>p.evaluate(()=>{const c=document.querySelector("canvas");const gl=c.getContext("webgl2")||c.getContext("webgl");const W=c.width,H=c.height;const s=120;const buf=new Uint8Array(s*s*4);gl.readPixels(Math.floor(W/2-s/2),Math.floor(H/2-s/2),s,s,gl.RGBA,gl.UNSIGNED_BYTE,buf);let sum=0;for(let i=0;i<buf.length;i+=4)sum+=buf[i]+buf[i+1]+buf[i+2];return Math.round(sum/(s*s*3));});
let idle=0; for(let i=0;i<8;i++){idle=Math.max(idle,await peak());await p.waitForTimeout(140);}
await p.screenshot({path:"main_idle.png"});
const inp=await p.$("input"); await inp.click(); await inp.type("Give a long detailed multi sentence status report now please");
await p.keyboard.press("Enter");
let speak=0; for(let i=0;i<30;i++){speak=Math.max(speak,await peak());await p.waitForTimeout(160);}
await p.screenshot({path:"main_speaking.png"});
console.log("CMD_STATUS:",cmdStatus);
console.log("CENTER_BRIGHTNESS idle:",idle," speak:",speak," delta:",speak-idle);
await b.close();
