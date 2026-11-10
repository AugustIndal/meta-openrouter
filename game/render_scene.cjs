/** Render an untrusted scene on its own credential-free loopback origin. */
const fs = require('fs');
const http = require('http');
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); }
catch { ({ chromium } = require('/tmp/openrouter-draw-preview/node_modules/playwright')); }

(async () => {
  const [source, output, modules] = process.argv.slice(2);
  if (!source || !output || !modules) throw new Error('Expected source, PNG output and module directory.');
  const content = fs.readFileSync(source);
  const allowed = new Map([
    ['/scene.html', { body: content, type: 'text/html' }],
    ['/three.module.js', { body: fs.readFileSync(path.join(modules, 'three.module.js')), type: 'text/javascript' }],
    ['/three.core.js', { body: fs.readFileSync(path.join(modules, 'three.core.js')), type: 'text/javascript' }],
  ]);
  const csp = "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src data: 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'; frame-src 'none'; worker-src 'none'";
  const server = http.createServer((req, res) => {
    const item = allowed.get(req.url);
    if (!item || req.method !== 'GET') { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': item.type, 'Content-Security-Policy': csp });
    res.end(item.body);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = await chromium.launch({ headless: true,
      executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      args: ['--enable-unsafe-swiftshader', '--disable-dev-shm-usage'] });
    const context = await browser.newContext({ viewport: { width: 1200, height: 800 }, deviceScaleFactor: 1,
      serviceWorkers: 'block', acceptDownloads: false });
    const blocked = [];
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.origin === origin && allowed.has(url.pathname) && !url.search && route.request().method() === 'GET') route.continue();
      else { blocked.push(url.origin); route.abort(); }
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message.slice(0, 200)));
    page.on('dialog', dialog => dialog.dismiss());
    await page.goto(origin + '/scene.html', { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForFunction(() => window.sceneReady === true, null, { timeout: 25000 });
    await page.waitForTimeout(200);
    if (errors.length) throw new Error('Generated scene runtime error: ' + errors[0]);
    if (blocked.length) throw new Error('Generated scene attempted a blocked network request.');
    const valid = await page.locator('canvas').evaluateAll(nodes => nodes.some(n => n.width >= 200 && n.height >= 200));
    if (!valid) throw new Error('Generated scene has no usable canvas.');
    await page.screenshot({ path: output, type: 'png' });
    process.stdout.write(JSON.stringify({ width: 1200, height: 800, errors, blockedRequests: blocked.length }));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { process.stderr.write(String(error.message).slice(0, 400)); process.exitCode = 1; });
