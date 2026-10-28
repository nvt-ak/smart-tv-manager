/** Optional Chromium check against bundles built by core.webos_home.build_bundle.
 * HOME_BUNDLE_ROOT contains aurora/, hanoi/, hanoi2/, hanoi3/.
 * PLAYWRIGHT_CHROMIUM_EXECUTABLE selects an installed local Chromium binary.
 * Browser dependencies are development-only and are not shipped with Manager.
 */
const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require('playwright');
(async () => {
  assert(process.env.HOME_BUNDLE_ROOT, 'Set HOME_BUNDLE_ROOT to generated QA bundles');
  const browser = await chromium.launch({
    executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
    headless:true, args:['--no-sandbox','--disable-dev-shm-usage','--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
  });
  try {
    const page = await browser.newPage({viewport:{width:1920,height:1080}});
    const errors=[];
    page.on('pageerror', error => errors.push(String(error)));
    for (const profile of ['aurora','hanoi','hanoi2','hanoi3']) {
      await page.goto(pathToFileURL(path.join(process.env.HOME_BUNDLE_ROOT,profile,'index.html')).href);
      await page.evaluate(() => document.fonts.ready);
      const defects = await page.evaluate(() => {
        const failures=[];
        const date=document.getElementById('date').getBoundingClientRect();
        const quote=document.getElementById('quote').getBoundingClientRect();
        const lunarElement=document.getElementById('lunar-header');
        const lunar=lunarElement.getBoundingClientRect();
        if(lunarElement.textContent && lunar.x<quote.right && lunar.right>quote.x && lunar.y<quote.bottom && lunar.bottom>quote.y) failures.push('lunar header overlaps quote');
        if (date.x<quote.right && date.right>quote.x && date.y<quote.bottom && date.bottom>quote.y) failures.push('date overlaps quote');
        document.querySelectorAll('.card').forEach(card => {
          const box=card.getBoundingClientRect();
          if(lunarElement.textContent && lunar.x<box.right && lunar.right>box.x && lunar.y<box.bottom && lunar.bottom>box.y) failures.push('lunar header overlaps card');
          if (box.bottom>innerHeight || box.right>innerWidth) failures.push('card outside screen');
          card.querySelectorAll('p,.forecast,.month').forEach(child=>{
            if(child.getBoundingClientRect().bottom>box.bottom-8) failures.push('card content clipped: '+card.className);
          });
        });
        return failures;
      });
      assert.deepEqual(defects,[],profile);
      assert(await page.locator('.app').count()>0,profile+' app controls');
      await page.keyboard.press('ArrowDown');
      if(process.env.HOME_SCREENSHOT_ROOT) await page.screenshot({path:path.join(process.env.HOME_SCREENSHOT_ROOT,profile+'.png')});
      console.log('PASS rendered Home',profile);
    }
    assert.deepEqual(errors,[],'no browser exceptions');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
