/**
 * UI smoke test for the "Khoá trẻ em" tab. Loads the real index.html and app.js in jsdom with a
 * fake pywebview API and drives the setup, lock/unlock and error flows.
 * Run: npm install --no-save jsdom@24 && node tests/guard_ui_smoke.js
 */
const { JSDOM, ResourceLoader } = require('jsdom');
const path = require('path');
const UI = path.resolve(__dirname, '..', 'ui', 'index.html');

class LocalOnly extends ResourceLoader {
  fetch(url, options) {
    return url.startsWith('file:') ? super.fetch(url, options) : Promise.resolve(Buffer.from(''));
  }
}

const calls = [];
let statusInfo = { installed: false, enabled: false, paired: false, state: 'not_installed', status: null };
let jobTick = 0;
const protectedInfo = {
  installed: true, enabled: true, paired: true, state: 'protected',
  status: { running: true, pin_set: true, policy_loaded: true, now_ms: Date.now(), manual_lock_until_ms: 0,
    policy: { schedules: [{ days: [1, 2, 3, 4, 5], start: '22:00', end: '06:00' }], unlock_minutes: 60 } },
};
const STEPS = ['apk', 'install', 'enable', 'pair', 'pin', 'policy', 'verify', 'done'];

const handlers = {
  app_version: async () => '1.7.0',
  list_devices: async () => [],
  guard_status: async () => statusInfo,
  guard_setup_async: async (...a) => { calls.push(['setup', ...a]); jobTick = 0; return { job_id: 'j1' }; },
  guard_job: async () => {
    jobTick += 1;
    const n = Math.min(jobTick * 2, STEPS.length);
    const steps = STEPS.slice(0, n).map((m) => ({ msg: m, detail: `detail ${m}` }));
    if (n >= STEPS.length) return { status: 'done', steps, result: protectedInfo };
    return { status: 'running', steps };
  },
  guard_save_policy: async (...a) => { calls.push(['save', ...a]); return protectedInfo; },
  guard_lock_now: async (...a) => { calls.push(['lock', ...a]); return { ...protectedInfo, state: 'locked_manual',
    status: { ...protectedInfo.status, manual_lock_until_ms: Date.now() + 1800000 } }; },
  guard_unlock_now: async (...a) => { calls.push(['unlock', ...a]); return protectedInfo; },
  guard_diagnose: async () => ({ text: '== settings ==\nfake' }),
  guard_uninstall: async (...a) => { calls.push(['uninstall', ...a]); return { installed: false, state: 'not_installed', status: null }; },
};

const fail = [];
function check(cond, msg) { if (!cond) fail.push(msg); console.log(`${cond ? 'PASS' : 'FAIL'}  ${msg}`); }
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const dom = await JSDOM.fromFile(UI, {
    runScripts: 'dangerously', resources: new LocalOnly(), pretendToBeVisual: true,
    beforeParse(win) {
      win.HTMLElement.prototype.scrollIntoView = function () {};
      win.pywebview = { api: new Proxy({}, { get: (_, k) => handlers[k] || (async () => null) }) };
      win.confirm = () => true;
      win.alert = () => {};
      win.matchMedia = win.matchMedia || (() => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {} }));
    },
  });
  const { window } = dom;
  const errors = [];
  window.addEventListener('error', (e) => errors.push(e.message));
  await wait(1500);
  const $ = (id) => window.document.getElementById(id);

  window.eval("setActiveDevice({name:'TCL TV',host:'192.168.1.50',port:5555,online:true})");
  check(!$('tabGuardBtn').disabled, 'tab "Khoá trẻ em" is enabled once a TV is selected');

  $('tabGuardBtn').click();
  await wait(200);
  check($('tab-guard').classList.contains('active'), 'guard pane becomes active');
  check($('guardTarget').textContent === 'TCL TV', 'header shows the selected TV');
  check($('guardBannerTitle').textContent.includes('Chưa cài'), 'not installed banner');
  check($('guardSaveLabel').textContent.includes('Cài đặt'), 'primary button says install when not installed');
  check($('guardQuick').hidden === true, 'action row hidden while TV Guard is not installed');
  check(window.document.querySelectorAll('.guard-window').length === 1, 'default schedule window rendered');

  // validation: no PIN -> no call
  $('guardSaveBtn').click();
  await wait(100);
  check(calls.length === 0, 'empty PIN blocks setup');
  $('guardPin').value = '12';
  $('guardSaveBtn').click();
  await wait(100);
  check(calls.length === 0, 'short PIN blocks setup');

  // toggle a day and edit time, then run setup
  window.document.querySelector('.guard-day[data-day="7"]').click();
  const start = window.document.querySelector('.guard-time[data-act="start"]');
  start.value = '20:30';
  start.dispatchEvent(new window.Event('change', { bubbles: true }));
  const day7 = window.document.querySelector('.guard-day[data-day="7"]');
  const day1 = window.document.querySelector('.guard-day[data-day="1"]');
  check(day7.getAttribute('aria-pressed') === 'false', 'deselected day reports aria-pressed=false');
  check(day1.getAttribute('aria-pressed') === 'true', 'selected day reports aria-pressed=true');
  day7.click();
  check(day7.getAttribute('aria-pressed') === 'true', 'clicking a day selects it again');
  day7.click();
  check($('guardDirtyHint').hidden === false, 'unsaved-changes hint is shown after editing');

  // A status refresh must not wipe unsaved edits.
  const prevStatus = statusInfo;
  statusInfo = protectedInfo;
  $('guardRefreshBtn').click();
  await wait(200);
  check(window.document.querySelector('.guard-day[data-day="7"]').getAttribute('aria-pressed') === 'false'
    && window.document.querySelector('.guard-time[data-act="start"]').value === '20:30',
  'refresh keeps unsaved schedule edits');
  statusInfo = prevStatus;
  $('guardRefreshBtn').click();
  await wait(200);

  $('guardPin').value = '2468';
  $('guardSaveBtn').click();
  await wait(300);
  check($('guardProgressCard').hidden === false, 'progress card appears');
  check(window.document.querySelectorAll('.guard-stage').length === 7, 'seven progress stages');
  await wait(2500);
  const setupCall = calls.find((c) => c[0] === 'setup');
  check(!!setupCall, 'guard_setup_async was called');
  check(setupCall && setupCall[3] === '2468', 'PIN passed to backend');
  const sched = setupCall && setupCall[4].schedules[0];
  check(sched && sched.start === '20:30' && sched.days.length === 6 && !sched.days.includes(7), 'edited schedule passed to backend');
  check(window.document.querySelectorAll('.guard-stage.done').length === 7, 'all stages marked done');
  check($('guardBannerTitle').textContent === 'Đang bảo vệ', 'banner shows protected after setup');
  check($('guardPin').value === '', 'PIN field is cleared after setup');
  check($('guardDirtyHint').hidden === true, 'unsaved-changes hint clears after a successful setup');
  check($('guardSaveLabel').textContent === 'Lưu thay đổi', 'primary button becomes "save" after setup');
  check($('guardLockNowBtn').hidden === false, 'lock/unlock visible once protected');
  check(window.document.querySelector('.guard-time[data-act="start"]').value === '22:00', 'schedule loaded back from TV status');

  // The banner explains why the TV is not locked, using the TV's own clock and zone.
  handlers.guard_status = async () => ({ ...protectedInfo, update_available: false,
    status: { ...protectedInfo.status, reason: 'WRONG_DAY', zone: 'Asia/Ho_Chi_Minh', local_time: '2026-10-25T16:30:12.5', local_day: 7 } });
  $('guardRefreshBtn').click();
  await wait(200);
  const sub = $('guardBannerSub').textContent;
  check(sub.includes('Giờ trên TV: CN 16:30 (Asia/Ho_Chi_Minh)'), 'banner shows the TV clock, weekday and zone');
  check(sub.includes('không thuộc các ngày đã chọn'), 'banner explains the wrong-day reason');

  handlers.guard_status = async () => ({ ...protectedInfo, state: 'lock_failed',
    status: { ...protectedInfo.status, overlay_error: 'BadTokenException: x' } });
  $('guardRefreshBtn').click();
  await wait(200);
  check($('guardBannerTitle').textContent.includes('chưa bị che') && $('guardBannerSub').textContent.includes('BadTokenException'), 'lock_failed banner names the overlay error');

  handlers.guard_status = async () => ({ ...protectedInfo, update_available: true, version: '0.1.0-spike' });
  $('guardRefreshBtn').click();
  await wait(200);
  check($('guardSaveLabel').textContent === 'Cập nhật & lưu', 'outdated TV Guard offers "Cập nhật & lưu"');
  check($('guardBannerSub').textContent.includes('bản TV Guard mới hơn'), 'outdated TV Guard is announced');
  handlers.guard_status = async () => statusInfo;
  $('guardRefreshBtn').click();
  await wait(100);

  // quick actions
  $('guardTempMin').value = '60';
  $('guardLockNowBtn').click();
  await wait(200);
  check(calls.some((c) => c[0] === 'lock' && c[3] === 60), 'lock now sends 60 minutes');
  check($('guardBannerTitle').textContent.startsWith('TV đang khoá đến'), 'banner shows manual lock');
  $('guardUnlockNowBtn').click();
  await wait(200);
  check(calls.some((c) => c[0] === 'unlock' && c[3] === 60), 'unlock sends 60 minutes');

  // save without PIN keeps the existing one
  $('guardSaveBtn').click();
  await wait(200);
  const save = calls.find((c) => c[0] === 'save');
  check(!!save && save[4] === '', 'save with empty PIN passes empty PIN (keeps current)');

  // remove window, then validation
  window.document.querySelector('[data-act="remove"]').click();
  $('guardSaveBtn').click();
  await wait(100);
  check(calls.filter((c) => c[0] === 'save').length === 1, 'no windows blocks save');

  // uninstall
  $('guardUninstallBtn').click();
  await wait(200);
  check(calls.some((c) => c[0] === 'uninstall'), 'uninstall called');
  check($('guardBannerTitle').textContent.includes('Chưa cài'), 'back to not installed');

  // error path
  handlers.guard_setup_async = async () => ({ job_id: 'j2' });
  handlers.guard_job = async () => ({ status: 'failed', steps: [{ msg: 'install', detail: 'x' }, { msg: 'diag', detail: '== accessibility ==\nCrashed services: GuardService' }], error: 'Không tải được TV Guard' });
  statusInfo = { installed: false, enabled: false, paired: false, state: 'not_installed', status: null };
  $('guardPin').value = '1357';
  if (!window.document.querySelectorAll('.guard-window').length) $('guardAddWindowBtn').click();
  $('guardSaveBtn').click();
  await wait(900);
  check(!$('guardError').hidden && $('guardError').textContent.includes('Không tải được'), 'failed setup shows the error');
  check(window.document.querySelector('.guard-stage.failed') !== null, 'failing stage is highlighted');
  check($('guardSaveBtn').disabled === false, 'button re-enabled after failure');
  check($('guardTechBox').open && $('guardTech').textContent.includes('Crashed services'), 'diagnostics are shown automatically on failure');
  $('guardTechBox').open = false;
  $('guardDiagBtn').click();
  await wait(200);
  check($('guardTechBox').open && $('guardTech').textContent.includes('== settings =='), 'diagnose button fills the technical panel');

  check(errors.length === 0, `no uncaught page errors ${errors.join(' | ')}`);
  console.log(fail.length ? `\n${fail.length} FAILED` : '\nALL PASSED');
  process.exit(fail.length ? 1 : 0);
})();
