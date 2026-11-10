const { chromium } = require('/tmp/openrouter-draw-preview/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname,'../experiments/web2d-comparison');
(async()=>{
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const results=fs.existsSync(path.join(root,'variant-render-results.json'))?JSON.parse(fs.readFileSync(path.join(root,'variant-render-results.json'))):[];
 for(const item of JSON.parse(fs.readFileSync(path.join(root,'variants-summary.json'))).results){
  if(results.some(r=>r.slug===item.slug&&r.format===item.format))continue;
  const page=await browser.newPage({viewport:{width:1200,height:800},deviceScaleFactor:1});
  const errors=[]; const blocked=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>{const url=new URL(route.request().url());if(url.hostname==='127.0.0.1'&&url.port==='8769')return route.continue();blocked.push(url.origin);return route.abort();});
  const start=Date.now();let ready=false;let renderError=null;
  try{
   await page.goto('http://127.0.0.1:8769/'+item.file,{waitUntil:'load',timeout:30000});
   if(item.format==='canvas'){await page.waitForFunction(()=>window.sceneReady===true,null,{timeout:5000});ready=true;}
   else ready=await page.locator('svg').count()>0;
   await page.screenshot({path:path.join(root,item.slug+'-'+item.format+'-'+(item.variant==='expanded-cap'?'expanded':item.variant)+'.png')});
   await page.setViewportSize({width:900,height:600});await page.waitForTimeout(100);
  }catch(e){renderError=e.message;await page.screenshot({path:path.join(root,item.slug+'-'+item.format+'-'+(item.variant==='expanded-cap'?'expanded':item.variant)+'.png')}).catch(()=>{});}
  results.push({slug:item.slug,format:item.format,ready,errors,blocked,render_error:renderError,render_ms:Date.now()-start});
  fs.writeFileSync(path.join(root,'variant-render-results.json'),JSON.stringify(results,null,2));
  console.log(JSON.stringify(results.at(-1)));await Promise.race([page.close(),new Promise(r=>setTimeout(r,2000))]);
 }
 fs.writeFileSync(path.join(root,'variant-render-results.json'),JSON.stringify(results,null,2));await browser.close();
})();
