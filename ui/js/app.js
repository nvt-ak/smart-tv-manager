/** pywebview bridge — use window.pywebview; bare `pywebview` may be undefined at parse time. */
function hasPywebviewApi() {
  return !!(window.pywebview && window.pywebview.api);
}

function getApi() {
  if (!hasPywebviewApi()) {
    throw new Error('Chạy SmartTV Manager bằng `python main.py` — không mở file HTML trực tiếp trong trình duyệt.');
  }
  return window.pywebview.api;
}

function hideAppBoot() {
  const el = document.getElementById('appBoot');
  if (!el) return;
  el.classList.add('app-boot--out');
  window.setTimeout(() => el.remove(), 220);
}

function bootApp() {
  initDevGuide();
  refreshList('cache')
    .catch((err) => {
      setStatus(String(err.message || err));
    })
    .finally(() => {
      requestAnimationFrame(() => hideAppBoot());
    });
  window.setTimeout(() => {
    refreshList('port').catch(() => {});
  }, 350);
}

function waitForPywebviewAndBoot() {
  if (hasPywebviewApi()) {
    bootApp();
    return;
  }
  window.addEventListener('pywebviewready', bootApp, { once: true });
  let attempts = 0;
  const poll = setInterval(() => {
    if (hasPywebviewApi()) {
      clearInterval(poll);
      bootApp();
      return;
    }
    attempts += 1;
    if (attempts >= 120) {
      clearInterval(poll);
      setStatus('Không tìm thấy pywebview. Chạy: python main.py');
      if (terminalBodyEl) appendTerminal('init', 'pywebview API chưa sẵn sàng', 'log-err');
    }
  }, 50);
}

const statusEl = document.getElementById('status');
const listEl = document.getElementById('deviceList');
const scanResultsEl = document.getElementById('scanResults');
const scanBtn = document.getElementById('scanBtn');
const addBtn = document.getElementById('addBtn');
const refreshBtn = document.getElementById('refreshBtn');
const scanQuickBtn = document.getElementById('scanQuickBtn');
const deviceSavedCountEl = document.getElementById('deviceSavedCount');
const footerActiveDeviceEl = document.getElementById('footerActiveDevice');
const quickRemoteTargetEl = document.getElementById('quickRemoteTarget');
const terminalBodyEl = document.getElementById('terminal-body');
const clearLogsBtn = document.getElementById('clearLogsBtn');

const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');
const tabRemoteBtn = document.getElementById('tabRemoteBtn');
const tabAppsBtn = document.getElementById('tabAppsBtn');
const tabApkBtn = document.getElementById('tabApkBtn');
const tabHomeBtn = document.getElementById('tabHomeBtn');
const backToDevices = document.getElementById('backToDevices');
const remoteTarget = document.getElementById('remoteTarget');
const remoteTargetMeta = document.getElementById('remoteTargetMeta');
const remoteStatus = document.getElementById('remoteStatus');

const appsTarget = document.getElementById('appsTarget');
const appsTargetMeta = document.getElementById('appsTargetMeta');
const refreshAppsBtn = document.getElementById('refreshAppsBtn');
const backToDevicesFromApps = document.getElementById('backToDevicesFromApps');
const appSearch = document.getElementById('appSearch');
const appsStatus = document.getElementById('appsStatus');
const appsHomeInfo = document.getElementById('appsHomeInfo');
const appsList = document.getElementById('appsList');
const appsFilterTabs = document.getElementById('appsFilterTabs');
const appsMasterCheckbox = document.getElementById('appsMasterCheckbox');
const appsBatchBar = document.getElementById('appsBatchBar');
const appsSelectedCountEl = document.getElementById('appsSelectedCount');
const appsNoResults = document.getElementById('appsNoResults');
const appsVisibleCountEl = document.getElementById('appsVisibleCount');
const appsFooterTotalEl = document.getElementById('appsFooterTotal');
const appsTerminalOutput = document.getElementById('appsTerminalOutput');
const appsToast = document.getElementById('appsToast');
const appsToastMsg = document.getElementById('appsToastMsg');
const appsToastIcon = document.getElementById('appsToastIcon');

const apkTarget = document.getElementById('apkTarget');
const apkTargetMeta = document.getElementById('apkTargetMeta');
const backToDevicesFromApk = document.getElementById('backToDevicesFromApk');
const apkDropzone = document.getElementById('apkDropzone');
const apkSelectBtn = document.getElementById('apkSelectBtn');
const apkFileInput = document.getElementById('apkFileInput');
const apkStatus = document.getElementById('apkStatus');
const apkInfo = document.getElementById('apkInfo');
const apkInstallBtn = document.getElementById('apkInstallBtn');
const apkClearBtn = document.getElementById('apkClearBtn');

const homeTarget = document.getElementById('homeTarget');
const homeTargetMeta = document.getElementById('homeTargetMeta');
const backToDevicesFromHome = document.getElementById('backToDevicesFromHome');
const homeStatus = document.getElementById('homeStatus');
const homeDetectBtn = document.getElementById('homeDetectBtn');
const homeDetectInfo = document.getElementById('homeDetectInfo');
const homeReloadBtn = document.getElementById('homeReloadBtn');
const homeBackupBtn = document.getElementById('homeBackupBtn');
const homeCurrentInfo = document.getElementById('homeCurrentInfo');
const homeResetThemeBtn = document.getElementById('homeResetThemeBtn');
const homeRestartBtn = document.getElementById('homeRestartBtn');
const homeDiscoverBtn = document.getElementById('homeDiscoverBtn');
const homeDiscoverOut = document.getElementById('homeDiscoverOut');
const homeLoadThemesBtn = document.getElementById('homeLoadThemesBtn');
const homeThemesGrid = document.getElementById('homeThemesGrid');
const homeLoadBackupsBtn = document.getElementById('homeLoadBackupsBtn');
const homeBackupsList = document.getElementById('homeBackupsList');

const themeModal = document.getElementById('themeModal');
const themeModalTitle = document.getElementById('themeModalTitle');
const themeModalImg = document.getElementById('themeModalImg');
const themeModalMeta = document.getElementById('themeModalMeta');
const themeModalConfig = document.getElementById('themeModalConfig');
const themeModalApply = document.getElementById('themeModalApply');
const themeModalClose = document.getElementById('themeModalClose');
const themeModalCancel = document.getElementById('themeModalCancel');
const themeModalDesc = document.getElementById('themeModalDesc');
const homeSearchInput = document.getElementById('homeSearchInput');
const homeSetDefaultBtn = document.getElementById('homeSetDefaultBtn');
const homeImportBtn = document.getElementById('homeImportBtn');
const homeToast = document.getElementById('homeToast');
const homeToastMsg = document.getElementById('homeToastMsg');
const homeApplyLogWrap = document.getElementById('homeApplyLogWrap');
const homeApplyLog = document.getElementById('homeApplyLog');
const homeApplyLogHint = document.getElementById('homeApplyLogHint');

let activeDevice = null;
let keyThrottle = new Map();
let appsCache = [];
let appsHome = null;
let appsActiveFilter = 'all';
let appsToastTimer = null;
let currentApk = null;
let savedDeviceCount = 0;

function appendTerminal(cmd, message, tone = 'log-info') {
  if (!terminalBodyEl || !message) return;
  const time = new Date().toTimeString().split(' ')[0];
  const line1 = document.createElement('div');
  line1.innerHTML = `<span class="log-time">${time}</span> <span class="log-cmd">$ ${escapeHtml(cmd)}</span>`;
  const line2 = document.createElement('div');
  line2.className = tone;
  line2.textContent = message;
  terminalBodyEl.appendChild(line1);
  terminalBodyEl.appendChild(line2);
  terminalBodyEl.scrollTop = terminalBodyEl.scrollHeight;
}

function updateAppChrome(deviceCount) {
  if (typeof deviceCount === 'number' && !Number.isNaN(deviceCount)) {
    savedDeviceCount = deviceCount;
  }
  if (deviceSavedCountEl) {
    deviceSavedCountEl.textContent = `${savedDeviceCount} Đã lưu`;
  }
  if (footerActiveDeviceEl) {
    if (activeDevice) {
      footerActiveDeviceEl.textContent = `${activeDevice.name} (${activeDevice.host}:${activeDevice.port})`;
    } else {
      footerActiveDeviceEl.textContent = 'Chưa chọn thiết bị';
    }
  }
  if (quickRemoteTargetEl) {
    quickRemoteTargetEl.textContent = activeDevice ? activeDevice.name : '—';
  }
}

async function updateRemoteDeviceHeader() {
  if (!activeDevice) return;
  if (remoteTarget) remoteTarget.textContent = activeDevice.name;
  if (remoteTargetMeta) {
    remoteTargetMeta.textContent = `${activeDevice.host}:${activeDevice.port}`;
  }
  const badge = document.getElementById('remoteOnlineBadge');
  try {
    const devices = await getApi().list_devices('port');
    const row = devices.find((d) => d.host === activeDevice.host);
    if (row) activeDevice.online = row.online;
  } catch {
    /* ignore */
  }
  if (badge) {
    badge.className = activeDevice.online ? 'badge badge--online' : 'badge badge--offline';
    badge.textContent = activeDevice.online ? 'ONLINE' : 'Offline';
  }
  const dot = document.getElementById('remoteLiveDot');
  if (dot) dot.style.opacity = activeDevice.online ? '1' : '0.35';
}

function setActiveDevice(dev) {
  activeDevice = dev;
  if (remoteTarget) remoteTarget.textContent = dev.name;
  if (remoteTargetMeta) remoteTargetMeta.textContent = `${dev.host}:${dev.port}`;
  updateRemoteDeviceHeader();
  tabRemoteBtn.disabled = false;
  if (tabAppsBtn) tabAppsBtn.disabled = false;
  if (tabApkBtn) tabApkBtn.disabled = false;
  if (tabHomeBtn) tabHomeBtn.disabled = false;
  updateAppChrome();
  updateHomeChrome();
  updateApkChrome();
  updateDeviceCardHighlights();
  const homePane = document.getElementById('tab-home');
  if (homePane?.classList.contains('active')) activateHomeTab();
}

function updateDeviceCardHighlights() {
  if (!listEl) return;
  listEl.querySelectorAll('.device-item[data-host]').forEach((li) => {
    const isActive = activeDevice && li.dataset.host === activeDevice.host;
    li.classList.toggle('device-card--active', !!isActive);
    li.classList.toggle('device-card--featured', !!isActive);
    li.classList.toggle('device-card--dim', !isActive);
  });
}

function setStatus(msg) {
  if (statusEl) statusEl.textContent = msg || '';
}

function setRemoteStatus(msg) {
  if (remoteStatus) remoteStatus.textContent = msg || '';
}

function formatTime(iso) {
  if (!iso) return 'Chưa có';
  try {
    const d = new Date(iso);
    return d.toLocaleString('vi-VN');
  } catch {
    return iso;
  }
}

function switchTab(tab) {
  tabBtns.forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.tab === tab);
  });
  tabPanes.forEach((pane) => {
    pane.classList.toggle('active', pane.id === `tab-${tab}`);
  });
  if (tab === 'remote' && activeDevice) updateRemoteDeviceHeader();
  if (tab === 'home') activateHomeTab();
  if (tab === 'apk' && activeDevice) {
    updateApkChrome();
    refreshApkStorage();
  }
}

tabBtns.forEach((btn) => {
  btn.addEventListener('click', () => {
    if (btn.disabled) return;
    switchTab(btn.dataset.tab);
  });
});

backToDevices.addEventListener('click', () => {
  switchTab('devices');
});

if (backToDevicesFromApps) {
  backToDevicesFromApps.addEventListener('click', () => {
    switchTab('devices');
  });
}

if (backToDevicesFromApk) {
  backToDevicesFromApk.addEventListener('click', () => {
    switchTab('devices');
  });
}

if (backToDevicesFromHome) {
  backToDevicesFromHome.addEventListener('click', () => {
    switchTab('devices');
  });
}

function setAppsStatus(msg) {
  if (appsStatus) appsStatus.textContent = msg || '';
}

function friendlyPkgName(pkg) {
  const leaf = (pkg.split('.').pop() || pkg).replace(/[_-]/g, ' ');
  return leaf.charAt(0).toUpperCase() + leaf.slice(1);
}

function appMaterialIcon(pkg) {
  const icons = ['android', 'live_tv', 'movie', 'cast', 'home', 'settings', 'extension', 'smart_display'];
  let h = 0;
  for (let i = 0; i < pkg.length; i += 1) h = (h + pkg.charCodeAt(i)) % icons.length;
  return icons[h];
}

function logAppsConsole(cmd, detail, tone = '') {
  if (!appsTerminalOutput) return;
  const time = new Date().toTimeString().split(' ')[0];
  const line1 = document.createElement('div');
  line1.className = tone || 'log-cmd';
  line1.textContent = `[${time}] $ ${cmd}`;
  appsTerminalOutput.appendChild(line1);
  if (detail) {
    const line2 = document.createElement('div');
    line2.textContent = detail;
    appsTerminalOutput.appendChild(line2);
  }
  appsTerminalOutput.scrollTop = appsTerminalOutput.scrollHeight;
}

function showAppsToast(message, icon = 'check_circle') {
  if (!appsToast || !appsToastMsg) return;
  if (appsToastIcon) appsToastIcon.textContent = icon;
  appsToastMsg.textContent = message;
  appsToast.classList.add('visible');
  if (appsToastTimer) clearTimeout(appsToastTimer);
  appsToastTimer = setTimeout(() => appsToast.classList.remove('visible'), 2800);
}

function updateAppsFilterLabels() {
  if (!appsFilterTabs) return;
  const total = appsCache.length;
  const user = appsCache.filter((a) => a.type === 'user').length;
  const system = appsCache.filter((a) => a.type === 'system').length;
  const disabled = appsCache.filter((a) => a.type === 'disabled' || !a.enabled).length;
  const labels = {
    all: `Tất cả (${total})`,
    user: `Người dùng (${user})`,
    disabled: `Đã vô hiệu hóa (${disabled})`,
    system: `Hệ thống (${system})`,
  };
  appsFilterTabs.querySelectorAll('.filter-tab').forEach((btn) => {
    const key = btn.dataset.filter;
    if (labels[key]) btn.textContent = labels[key];
  });
  const totalEl = document.getElementById('appsTotalStat');
  const breakdownEl = document.getElementById('appsTypeBreakdown');
  const disabledEl = document.getElementById('appsDisabledStat');
  if (totalEl) totalEl.textContent = String(total);
  if (breakdownEl) breakdownEl.textContent = `(${user} user / ${system} sys)`;
  if (disabledEl) disabledEl.textContent = String(disabled);
  if (appsFooterTotalEl) appsFooterTotalEl.textContent = String(total);
}

async function updateAppsDeviceHeader() {
  if (!activeDevice) return;
  if (appsTarget) appsTarget.textContent = activeDevice.name;
  if (appsTargetMeta) appsTargetMeta.textContent = `${activeDevice.host}:${activeDevice.port}`;
  const badge = document.getElementById('appsOnlineBadge');
  try {
    const devices = await getApi().list_devices('port');
    const row = devices.find((d) => d.host === activeDevice.host);
    if (row) activeDevice.online = row.online;
  } catch {
    /* ignore */
  }
  if (badge) {
    badge.className = activeDevice.online ? 'badge badge--online' : 'badge badge--offline';
    badge.textContent = activeDevice.online ? 'ONLINE' : 'Offline';
  }
  const sub = document.getElementById('appsDeviceSub');
  if (sub) {
    sub.textContent = activeDevice.online
      ? 'Điều khiển package qua ADB shell'
      : 'Thiết bị offline — một số thao tác có thể thất bại';
  }
}

function updateAppsLauncherBanner() {
  const nameEl = document.getElementById('appsLauncherName');
  const verEl = document.getElementById('appsLauncherVer');
  if (!appsHome) {
    if (nameEl) nameEl.textContent = '—';
    if (verEl) verEl.textContent = '';
    if (appsHomeInfo) appsHomeInfo.textContent = 'Chưa xác định launcher mặc định';
    return;
  }
  const homeApp = appsCache.find((a) => a.package === appsHome);
  if (nameEl) nameEl.textContent = friendlyPkgName(appsHome);
  if (verEl && homeApp?.version) {
    verEl.textContent = `v${homeApp.version}${homeApp.version_code ? ` (${homeApp.version_code})` : ''}`;
  } else if (verEl) verEl.textContent = '';
  if (appsHomeInfo) {
    appsHomeInfo.textContent = `${appsHome} — launcher mặc định trên TV`;
  }
}

function getFilteredApps() {
  const search = (appSearch?.value || '').toLowerCase().trim();
  let list = appsCache.slice();
  if (appsActiveFilter === 'user') list = list.filter((a) => a.type === 'user');
  else if (appsActiveFilter === 'system') list = list.filter((a) => a.type === 'system');
  else if (appsActiveFilter === 'disabled') {
    list = list.filter((a) => a.type === 'disabled' || !a.enabled);
  }
  if (search) {
    list = list.filter((a) => {
      const pkg = a.package.toLowerCase();
      const label = friendlyPkgName(a.package).toLowerCase();
      return pkg.includes(search) || label.includes(search);
    });
  }
  return list;
}

function updateAppsSelectionUi() {
  if (!appsList) return;
  const checked = appsList.querySelectorAll('.app-row-checkbox:checked').length;
  if (appsSelectedCountEl) appsSelectedCountEl.textContent = String(checked);
  if (appsBatchBar) appsBatchBar.classList.toggle('visible', checked > 0);
}

function renderApps() {
  if (!appsList) return;
  const list = getFilteredApps();
  appsList.innerHTML = '';
  if (appsVisibleCountEl) appsVisibleCountEl.textContent = String(list.length);
  if (appsNoResults) appsNoResults.classList.toggle('visible', list.length === 0);
  if (!list.length) {
    updateAppsSelectionUi();
    return;
  }
  list.forEach((app, idx) => {
    const row = document.createElement('div');
    row.className = 'app-row';
    row.dataset.package = app.package;
    if (app.is_home) row.classList.add('is-home');
    if (!app.enabled || app.type === 'disabled') row.classList.add('is-disabled');

    const typePill =
      app.type === 'user'
        ? '<span class="badge pill-type-user">Người dùng</span>'
        : app.type === 'disabled' || !app.enabled
          ? '<span class="badge pill-type-disabled">Đã vô hiệu hóa</span>'
          : '<span class="badge pill-type-system">Hệ thống</span>';
    const homePill = app.is_home ? '<span class="badge pill-home">Default Launcher</span>' : '';
    const protectedPill = app.protected ? '<span class="badge pill-type-system">Bảo vệ</span>' : '';

    const ver =
      app.version != null
        ? `v${escapeHtml(app.version)}${app.version_code ? ` (${escapeHtml(app.version_code)})` : ''}`
        : '—';

    const pkgAttr = escapeAttr(app.package);
    const canOpen = app.enabled && app.type !== 'disabled';
    const toggleBtn = app.enabled
      ? app.can_disable
        ? `<button type="button" class="app-act app-act--danger" data-act="disable" data-pkg="${pkgAttr}">Vô hiệu hóa</button>`
        : `<button type="button" class="app-act" disabled title="${escapeAttr(app.disable_reason || 'Không được phép')}">Khóa</button>`
      : `<button type="button" class="app-act app-act--primary" data-act="enable" data-pkg="${pkgAttr}">Bật lại</button>`;

    row.innerHTML = `
      <div class="app-row-index">
        <input type="checkbox" class="app-row-checkbox" data-pkg="${pkgAttr}">
        <span>${String(idx + 1).padStart(2, '0')}</span>
      </div>
      <div class="app-row-main">
        <div class="app-row-icon"><span class="material-symbols-outlined">${appMaterialIcon(app.package)}</span></div>
        <div style="min-width:0;">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
            <span class="app-row-title">${escapeHtml(friendlyPkgName(app.package))}</span>
            ${homePill}
          </div>
          <div class="app-row-pkg">${escapeHtml(app.package)}</div>
        </div>
      </div>
      <div class="app-row-meta">${typePill}${protectedPill}</div>
      <div class="app-row-size">
        <span class="app-row-pkg" style="color:var(--color-on-surface);">${ver}</span>
      </div>
      <div class="app-row-actions">
        <button type="button" class="app-act app-act--open" data-act="open" data-pkg="${pkgAttr}" ${canOpen ? '' : 'disabled'}>
          <span class="material-symbols-outlined" style="font-size:16px;">play_arrow</span>Mở
        </button>
        <button type="button" class="app-act" data-act="stop" data-pkg="${pkgAttr}">Force stop</button>
        <button type="button" class="app-act" data-act="info" data-pkg="${pkgAttr}">App info</button>
        ${toggleBtn}
      </div>`;
    appsList.appendChild(row);
  });
  if (appsMasterCheckbox) appsMasterCheckbox.checked = false;
  updateAppsSelectionUi();
}

let appsVersionSyncTimer = null;

function scheduleAppsVersionSync() {
  if (appsVersionSyncTimer) clearTimeout(appsVersionSyncTimer);
  appsVersionSyncTimer = setTimeout(() => {
    appsVersionSyncTimer = null;
    syncAppsVersions().catch(() => {});
  }, 2000);
}

const APPS_VERSION_SYNC_MAX = 100;
const APPS_VERSION_BATCH = 40;

function applyAppsInfoMap(info) {
  for (const [pkg, data] of Object.entries(info || {})) {
    const i = appsCache.findIndex((a) => a.package === pkg);
    if (i >= 0) {
      if (data.version) appsCache[i].version = data.version;
      if (data.version_code) appsCache[i].version_code = data.version_code;
    }
  }
}

async function syncAppsVersions(maxTotal = APPS_VERSION_SYNC_MAX) {
  if (!activeDevice || !appsCache.length || !window.pywebview?.api?.get_apps_info) return;
  const missing = appsCache
    .filter((a) => !a.version && !a.version_code)
    .map((a) => a.package)
    .slice(0, maxTotal);
  if (!missing.length) return;

  let done = 0;
  for (let i = 0; i < missing.length; i += APPS_VERSION_BATCH) {
    const batch = missing.slice(i, i + APPS_VERSION_BATCH);
    setAppsStatus(
      `Đang lấy phiên bản… ${done}/${missing.length} (Wi‑Fi ADB có thể chậm)`,
    );
    const info = await getApi().get_apps_info(
      activeDevice.host,
      activeDevice.port,
      batch,
      APPS_VERSION_BATCH,
    );
    applyAppsInfoMap(info);
    done += batch.length;
    updateAppsLauncherBanner();
    renderApps();
  }
  setAppsStatus(`Đã đồng bộ phiên bản cho ${done}/${missing.length} gói (tối đa ${maxTotal})`);
  setTimeout(() => setAppsStatus(''), 2000);
}

async function loadApps() {
  if (!activeDevice) return;
  await updateAppsDeviceHeader();
  setAppsStatus('Đang tải danh sách ứng dụng...');
  logAppsConsole(
    `adb -s ${activeDevice.host}:${activeDevice.port} shell pm list packages`,
    'Đang đồng bộ...'
  );
  if (appsList) appsList.innerHTML = '';
  try {
    const res = await getApi().list_apps(activeDevice.host, activeDevice.port);
    appsCache = res.apps || [];
    appsHome = res.current_home || null;
    updateAppsFilterLabels();
    updateAppsLauncherBanner();
    renderApps();
    logAppsConsole('pm list packages', `Đồng bộ ${appsCache.length} gói`, 'log-ok');
    setAppsStatus(`Đã tải ${appsCache.length} package`);
    scheduleAppsVersionSync();
    setTimeout(() => setAppsStatus(''), 1500);
  } catch (err) {
    setAppsStatus(`Lỗi tải danh sách: ${err}`);
    logAppsConsole('pm list packages', String(err), 'log-err');
  }
}

if (appSearch) appSearch.addEventListener('input', renderApps);

if (appsFilterTabs) {
  appsFilterTabs.addEventListener('click', (e) => {
    const btn = e.target.closest('.filter-tab');
    if (!btn) return;
    appsActiveFilter = btn.dataset.filter || 'all';
    appsFilterTabs.querySelectorAll('.filter-tab').forEach((b) => b.classList.toggle('active', b === btn));
    renderApps();
  });
}

const appsSearchClear = document.getElementById('appsSearchClear');
if (appsSearchClear && appSearch) {
  appsSearchClear.addEventListener('click', () => {
    appSearch.value = '';
    renderApps();
  });
}

const appsEmptyClear = document.getElementById('appsEmptyClear');
if (appsEmptyClear) {
  appsEmptyClear.addEventListener('click', () => {
    appsActiveFilter = 'all';
    if (appSearch) appSearch.value = '';
    appsFilterTabs?.querySelectorAll('.filter-tab').forEach((b) => {
      b.classList.toggle('active', b.dataset.filter === 'all');
    });
    renderApps();
  });
}

if (appsMasterCheckbox && appsList) {
  appsMasterCheckbox.addEventListener('change', () => {
    const on = appsMasterCheckbox.checked;
    appsList.querySelectorAll('.app-row-checkbox').forEach((cb) => {
      cb.checked = on;
    });
    updateAppsSelectionUi();
  });
}

if (appsList) {
  appsList.addEventListener('change', (e) => {
    if (e.target.classList.contains('app-row-checkbox')) updateAppsSelectionUi();
  });
}

const appsClearSelection = document.getElementById('appsClearSelection');
if (appsClearSelection) {
  appsClearSelection.addEventListener('click', () => {
    appsList?.querySelectorAll('.app-row-checkbox').forEach((cb) => {
      cb.checked = false;
    });
    if (appsMasterCheckbox) appsMasterCheckbox.checked = false;
    updateAppsSelectionUi();
  });
}

if (appsBatchBar) {
  appsBatchBar.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-batch]');
    if (!btn || !activeDevice) return;
    const action = btn.dataset.batch;
    const pkgs = [...appsList.querySelectorAll('.app-row-checkbox:checked')].map((cb) => cb.dataset.pkg);
    if (!pkgs.length) return;
    setButtonLoading(btn, true);
    for (const pkg of pkgs) {
      try {
        if (action === 'force_stop') {
          await getApi().app_action(activeDevice.host, activeDevice.port, 'force_stop', pkg);
          logAppsConsole(`am force-stop ${pkg}`, 'ok');
        } else if (action === 'disable') {
          await getApi().app_action(activeDevice.host, activeDevice.port, 'disable', pkg);
          logAppsConsole(`pm disable-user ${pkg}`, 'ok');
        }
      } catch (err) {
        logAppsConsole(action, `${pkg}: ${err}`, 'log-err');
      }
    }
    setButtonLoading(btn, false);
    showAppsToast(`Đã xử lý ${pkgs.length} gói (${action})`, 'checklist');
    await loadApps();
  });
}

const appsClearConsole = document.getElementById('appsClearConsole');
if (appsClearConsole && appsTerminalOutput) {
  appsClearConsole.addEventListener('click', () => {
    appsTerminalOutput.innerHTML = '';
  });
}

const appsLogcatBtn = document.getElementById('appsLogcatBtn');
if (appsLogcatBtn) {
  appsLogcatBtn.addEventListener('click', () => {
    showAppsToast('Logcat trực tiếp sẽ có ở bản sau', 'terminal');
  });
}

const appsLauncherPickBtn = document.getElementById('appsLauncherPickBtn');
if (appsLauncherPickBtn) {
  appsLauncherPickBtn.addEventListener('click', () => {
    showAppsToast('Mở Cài đặt → Apps → Default launcher trên TV', 'swap_horiz');
  });
}

const appsHomeThemeBtn = document.getElementById('appsHomeThemeBtn');
if (appsHomeThemeBtn) {
  appsHomeThemeBtn.addEventListener('click', () => {
    if (tabHomeBtn && !tabHomeBtn.disabled) switchTab('home');
    else showAppsToast('Chọn thiết bị trước', 'info');
  });
}

const SMART_CLEAN_TIER_LABEL = {
  recommend: 'Nên tắt',
  review: 'Cân nhắc',
  skip: 'Giữ',
  blocked: 'Khóa',
};

const SMART_CLEAN_APP_KIND = {
  user: 'User app',
  system: 'System app',
  disabled: 'Đã vô hiệu hóa',
};

function smartCleanPkgBadge(s) {
  const tier = s.tier || 'skip';
  if (tier === 'recommend') {
    const pkg = (s.package || '').toLowerCase();
    if (/partner|ads|customizer|promo|bloat/.test(pkg)) return 'NÊN TẮT (BLOATWARE)';
    return 'NÊN TẮT (RECOMMENDED)';
  }
  if (tier === 'review') return 'CÂN NHẮC (WARNING)';
  return '';
}

function smartCleanPkgKind(s) {
  const pkg = (s.package || '').toLowerCase();
  if (/partner|ads|customizer|promo/.test(pkg)) return 'OEM Quảng cáo';
  if (s.type === 'system') return 'System / Daemon';
  if (s.type === 'user') return 'User App';
  return SMART_CLEAN_APP_KIND[s.type] || s.type || 'Package';
}

let smartCleanSuggestions = [];
let smartCleanTierFilter = 'all';
let smartCleanSearchQuery = '';
let smartCleanScanMode = 'offline';
let smartCleanDismissed = new Set();
let smartCleanModelsCache = [];
let smartCleanModelsFetchGen = 0;

const smartCleanModal = document.getElementById('smartCleanModal');
const smartCleanList = document.getElementById('smartCleanList');
const smartCleanStatus = document.getElementById('smartCleanStatus');
const smartCleanSummary = document.getElementById('smartCleanSummary');
const smartCleanApplyBtn = document.getElementById('smartCleanApply');
const smartCleanAiWarn = document.getElementById('smartCleanAiWarn');
const smartCleanOnlyActionable = document.getElementById('smartCleanOnlyActionable');
const smartCleanKeyHint = document.getElementById('smartCleanKeyHint');
const smartCleanSelectedCount = document.getElementById('smartCleanSelectedCount');
const smartCleanSearch = document.getElementById('smartCleanSearch');

function setSmartCleanStatus(msg) {
  if (smartCleanStatus) smartCleanStatus.textContent = msg || '';
}

function syncSmartCleanDeviceBadge() {
  const nameEl = document.getElementById('smartCleanDeviceName');
  const hostEl = document.getElementById('smartCleanDeviceHost');
  if (nameEl) nameEl.textContent = activeDevice?.name || 'Chưa chọn TV';
  if (hostEl) {
    hostEl.textContent = activeDevice
      ? `${activeDevice.host}:${activeDevice.port || 5555}`
      : '—';
  }
}

function setSmartCleanScanMode(mode) {
  smartCleanScanMode = mode === 'ai' ? 'ai' : 'offline';
  document.getElementById('smartCleanModeOffline')?.classList.toggle('is-active', smartCleanScanMode === 'offline');
  document.getElementById('smartCleanModeAi')?.classList.toggle('is-active', smartCleanScanMode === 'ai');
}

function getSmartCleanFilteredRows() {
  let rows = smartCleanSuggestions.slice();
  if (smartCleanOnlyActionable?.checked) {
    rows = rows.filter((s) => s.tier === 'recommend' || s.tier === 'review');
  }
  if (smartCleanTierFilter !== 'all') {
    rows = rows.filter((s) => s.tier === smartCleanTierFilter);
  }
  const q = (smartCleanSearchQuery || '').trim().toLowerCase();
  if (q) rows = rows.filter((s) => (s.package || '').toLowerCase().includes(q));
  if (smartCleanDismissed.size) {
    rows = rows.filter((s) => !smartCleanDismissed.has(s.package));
  }
  return rows;
}

function updateSmartCleanApplyBtn() {
  if (!smartCleanApplyBtn || !smartCleanList) return;
  const n = smartCleanList.querySelectorAll('.smart-clean-check:checked').length;
  smartCleanApplyBtn.disabled = n === 0;
  if (smartCleanSelectedCount) smartCleanSelectedCount.textContent = String(n);
}

function renderSmartCleanList() {
  if (!smartCleanList) return;
  const rows = getSmartCleanFilteredRows();
  if (!rows.length) {
    smartCleanList.innerHTML =
      '<p class="smart-clean-empty">Chưa có gói phù hợp — chọn chế độ quét hoặc nới bộ lọc.</p>';
    updateSmartCleanApplyBtn();
    return;
  }
  smartCleanList.innerHTML = rows
    .map((s) => {
      const tier = s.tier || 'skip';
      const canCheck = s.can_disable && s.enabled && tier !== 'blocked' && tier !== 'skip';
      const checked = canCheck && s.selected ? 'checked' : '';
      const disabled = canCheck ? '' : 'disabled';
      const iconTier = tier === 'recommend' ? 'danger' : tier === 'review' ? 'warn' : 'warn';
      const icon =
        tier === 'recommend'
          ? 'delete'
          : tier === 'review'
            ? 'warning'
            : 'apps';
      const badgeText = smartCleanPkgBadge(s);
      const badge = badgeText
        ? `<span class="smart-clean-pkg-badge smart-clean-pkg-badge--${tier}">${escapeHtml(badgeText)}</span>`
        : '';
      const kind = smartCleanPkgKind(s);
      const reason = `${s.reason || ''}${s.source === 'ai' ? ' · AI' : ''}`;
      let secondaryBtn = '';
      if (tier === 'recommend' && canCheck) {
        secondaryBtn = `<button type="button" class="smart-clean-pkg-btn smart-clean-pkg-btn--danger" data-act="disable-one" data-pkg="${escapeAttr(s.package)}">Vô hiệu ngay</button>`;
      } else if (tier === 'review') {
        secondaryBtn = `<button type="button" class="smart-clean-pkg-btn smart-clean-pkg-btn--skip" data-act="skip" data-pkg="${escapeAttr(s.package)}">Bỏ qua</button>`;
      }
      return `<article class="smart-clean-pkg-card" data-tier="${tier}" data-pkg="${escapeAttr(s.package)}">
        <div class="smart-clean-pkg-main">
          <input type="checkbox" class="smart-clean-check" data-pkg="${escapeAttr(s.package)}" ${checked} ${disabled} aria-label="Chọn ${escapeAttr(s.package)}">
          <div class="smart-clean-pkg-icon smart-clean-pkg-icon--${iconTier}">
            <span class="material-symbols-outlined">${icon}</span>
          </div>
          <div class="smart-clean-pkg-body">
            <div class="smart-clean-pkg-head">
              <span class="smart-clean-pkg-name">${escapeHtml(s.package)}</span>
              ${badge}
              <span class="smart-clean-pkg-kind">${escapeHtml(kind)}</span>
            </div>
            <p class="smart-clean-pkg-reason">${escapeHtml(reason)}</p>
          </div>
        </div>
        <div class="smart-clean-pkg-actions">
          <button type="button" class="smart-clean-pkg-btn smart-clean-pkg-btn--ghost" data-act="detail" data-pkg="${escapeAttr(s.package)}">Chi tiết</button>
          ${secondaryBtn}
        </div>
      </article>`;
    })
    .join('');
  updateSmartCleanApplyBtn();
}

function computeSmartCleanCounts() {
  const c = { recommend: 0, review: 0, skip: 0, blocked: 0 };
  smartCleanSuggestions.forEach((s) => {
    const t = s.tier || 'skip';
    if (Object.prototype.hasOwnProperty.call(c, t)) c[t] += 1;
    else c.skip += 1;
  });
  return c;
}

function renderSmartCleanSummary(counts) {
  if (!smartCleanSummary) return;
  const total = smartCleanSuggestions.length;
  const c = counts || computeSmartCleanCounts();
  const pills = [
    ['all', 'Tất cả', total, 'metric--all', null, false],
    ['recommend', 'Nên tắt', c.recommend ?? 0, 'metric--danger', '#f43f5e', true],
    ['review', 'Cân nhắc', c.review ?? 0, 'metric--warn', '#fbbf24', true],
    ['skip', 'Giữ', c.skip ?? 0, 'metric--ok', '#34d399', true],
    ['blocked', 'Khóa', c.blocked ?? 0, 'metric--muted', '#64748b', false],
  ];
  smartCleanSummary.innerHTML = pills
    .map(([key, label, n, cls, dotColor, withPkg]) => {
      const active = smartCleanTierFilter === key ? ' is-active' : '';
      const dot = dotColor
        ? `<span class="smart-clean-metric-dot" style="background:${dotColor}"></span>`
        : '';
      const countHtml = withPkg
        ? `<strong>${n}</strong> gói`
        : `<strong>${n}</strong>`;
      return `<button type="button" class="smart-clean-metric ${cls}${active}" data-tier-filter="${key}">${dot}${escapeHtml(label)}: ${countHtml}</button>`;
    })
    .join('');
}

function readSmartCleanAiForm() {
  return {
    key: document.getElementById('smartCleanApiKey')?.value?.trim() || '',
    base: document.getElementById('smartCleanApiBase')?.value?.trim() || '',
    model: getSmartCleanModelValue(),
  };
}

function getSmartCleanModelValue() {
  return document.getElementById('smartCleanModel')?.value?.trim() || '';
}

function isSmartCleanModelCommitted(modelId) {
  const id = (modelId || '').trim();
  return Boolean(id && smartCleanModelsCache.includes(id));
}

function syncSmartCleanModelSearchToSelection() {
  const search = document.getElementById('smartCleanModelSearch');
  const selected = getSmartCleanModelValue();
  if (!search) return;
  if (selected && isSmartCleanModelCommitted(selected)) {
    search.value = selected;
    return;
  }
  const q = search.value.trim();
  if (q && smartCleanModelsCache.includes(q)) {
    setSmartCleanModelValue(q, { syncSearch: true });
  } else if (selected) {
    search.value = selected;
  }
}

function updateSmartCleanModelChrome() {
  const model = getSmartCleanModelValue();
  const committed = isSmartCleanModelCommitted(model);
  const badge = document.getElementById('smartCleanModelBadge');
  const modeTag = document.getElementById('smartCleanAiModeTag');
  const meta = document.getElementById('smartCleanModelMeta');
  const pickerField = document.querySelector('.smart-clean-model-picker-field');
  const total = smartCleanModelsCache.length;
  pickerField?.classList.toggle('is-selected', committed);
  if (badge) {
    badge.classList.toggle('is-selected', committed);
    if (committed) {
      const short = model.length > 28 ? `${model.slice(0, 26)}…` : model;
      badge.textContent = short;
      badge.title = model;
    } else if (model && total) {
      badge.textContent = 'Model không hợp lệ';
      badge.title = model;
    } else {
      badge.textContent = total ? 'Chưa chọn' : 'Chưa tải model';
      badge.title = '';
    }
  }
  if (modeTag) {
    modeTag.textContent = committed ? model : total ? 'Chưa chọn' : 'Ping';
    modeTag.title = committed ? model : '';
    modeTag.classList.toggle('is-selected', committed);
  }
  if (meta) {
    if (total) {
      meta.hidden = false;
      if (committed) {
        meta.textContent = `✓ Đã chọn · ${total} model · gõ lọc danh sách`;
      } else {
        meta.textContent = `${total} model · chọn dòng hoặc Enter khi khớp 1 kết quả`;
      }
    } else {
      meta.hidden = true;
      meta.textContent = '';
    }
  }
}

function setSmartCleanModelValue(modelId, { syncSearch = true } = {}) {
  const hidden = document.getElementById('smartCleanModel');
  const search = document.getElementById('smartCleanModelSearch');
  const id = (modelId || '').trim();
  if (hidden) hidden.value = id;
  if (syncSearch && search) search.value = id;
  updateSmartCleanModelChrome();
}

function filterSmartCleanModels(query) {
  const q = (query || '').trim().toLowerCase();
  let list = smartCleanModelsCache;
  if (q) list = list.filter((id) => id.toLowerCase().includes(q));
  return list.slice(0, 120);
}

function renderSmartCleanModelDropdown(items) {
  const box = document.getElementById('smartCleanModelDropdown');
  const search = document.getElementById('smartCleanModelSearch');
  if (!box) return;
  if (!items.length) {
    box.innerHTML = '<p class="smart-clean-model-dropdown-empty">Không khớp model nào</p>';
    box.hidden = false;
    if (search) search.setAttribute('aria-expanded', 'true');
    return;
  }
  const current = getSmartCleanModelValue();
  box.innerHTML = items
    .map((id) => {
      const active = id === current ? ' is-active' : '';
      return `<button type="button" class="smart-clean-model-option${active}" role="option" aria-selected="${id === current}" data-model="${escapeAttr(id)}">${escapeHtml(id)}</button>`;
    })
    .join('');
  box.hidden = false;
  if (search) search.setAttribute('aria-expanded', 'true');
}

function closeSmartCleanModelDropdown() {
  const box = document.getElementById('smartCleanModelDropdown');
  const search = document.getElementById('smartCleanModelSearch');
  if (box) box.hidden = true;
  if (search) search.setAttribute('aria-expanded', 'false');
}

function openSmartCleanModelDropdown() {
  if (!smartCleanModelsCache.length) return;
  const search = document.getElementById('smartCleanModelSearch');
  renderSmartCleanModelDropdown(filterSmartCleanModels(search?.value));
}

function pickSmartCleanModelId(list, preferredId) {
  if (preferredId && list.includes(preferredId)) return preferredId;
  const autoBest = list.find((id) => id === 'auto/best-chat' || String(id).startsWith('auto/'));
  if (autoBest) return autoBest;
  const notDefaultOpenAi = list.find((id) => id !== 'gpt-4o-mini');
  return notDefaultOpenAi || list[0];
}

function populateSmartCleanModelPicker(
  models,
  preferredId,
  { autoPick = true, respectCurrent = true } = {},
) {
  const search = document.getElementById('smartCleanModelSearch');
  const list = Array.isArray(models) ? models.filter(Boolean) : [];
  smartCleanModelsCache = list.slice();
  if (!list.length) {
    setSmartCleanModelValue('', { syncSearch: true });
    if (search) {
      search.disabled = true;
      search.placeholder = 'Test Ping để tải danh sách model…';
    }
    closeSmartCleanModelDropdown();
    updateSmartCleanModelChrome();
    return;
  }
  if (search) {
    search.disabled = false;
    search.placeholder = 'Gõ để tìm model (vd. auto/, gpt-)…';
  }
  const pref = (preferredId || '').trim();
  const current = getSmartCleanModelValue();
  let pick = '';
  // Luôn giữ model user vừa chọn trên form — không ghi đè bằng default/settings.
  if (respectCurrent && current && list.includes(current)) {
    pick = current;
  } else if (pref && list.includes(pref)) {
    pick = pref;
  } else if (autoPick) {
    pick = pickSmartCleanModelId(list, pref);
  } else if (pref) {
    pick = pref;
  }
  if (pick !== current) {
    setSmartCleanModelValue(pick, { syncSearch: true });
  } else {
    updateSmartCleanModelChrome();
  }
}

async function refreshSmartCleanModels({
  key = '',
  base = '',
  preferred = '',
  autoPick = false,
  toastOnError = false,
} = {}) {
  const gen = ++smartCleanModelsFetchGen;
  const settings = await getApi().get_app_settings();
  if (!settings.openai_configured && !key) return { ok: false, skipped: true };
  const res = await getApi().test_openai_connection(key || null, base || null);
  if (gen !== smartCleanModelsFetchGen) {
    return { ok: false, stale: true };
  }
  if (!res?.ok) {
    if (toastOnError) showAppsToast(res?.error || 'Không tải được model', 'error');
    return res;
  }
  const baseEl = document.getElementById('smartCleanApiBase');
  if (baseEl && res.base_url) baseEl.value = res.base_url;
  const current = getSmartCleanModelValue();
  const want =
    (current && (res.models || []).includes(current) ? current : '') ||
    preferred ||
    settings.openai_model ||
    '';
  populateSmartCleanModelPicker(res.models || [], want, {
    autoPick,
    respectCurrent: true,
  });
  updateSmartCleanModelChrome();
  return res;
}

async function syncSmartCleanAiFormFromSettings() {
  try {
    const s = await getApi().get_app_settings();
    const baseEl = document.getElementById('smartCleanApiBase');
    const base = s.openai_base_url || 'https://api.openai.com/v1';
    if (baseEl) baseEl.value = base;
    if (smartCleanKeyHint) {
      if (s.openai_configured) {
        smartCleanKeyHint.hidden = false;
        smartCleanKeyHint.textContent = 'Đã lưu';
      } else {
        smartCleanKeyHint.hidden = true;
        smartCleanKeyHint.textContent = '';
      }
    }
    if (smartCleanModelsCache.length) {
      populateSmartCleanModelPicker(smartCleanModelsCache, s.openai_model, {
        autoPick: false,
        respectCurrent: true,
      });
    } else if (s.openai_configured) {
      const search = document.getElementById('smartCleanModelSearch');
      if (search) {
        search.disabled = true;
        search.placeholder = 'Đang tải danh sách model…';
      }
      await refreshSmartCleanModels({
        base,
        preferred: s.openai_model || '',
        autoPick: false,
      });
    } else if (s.openai_model) {
      populateSmartCleanModelPicker([s.openai_model], s.openai_model, { autoPick: false });
    } else {
      updateSmartCleanModelChrome();
    }
  } catch {
    if (smartCleanKeyHint) smartCleanKeyHint.hidden = true;
  }
}

function setSmartCleanListLoading(loading, message) {
  if (!smartCleanList) return;
  if (loading) {
    smartCleanList.classList.add('is-loading');
    smartCleanList.innerHTML = `<div class="smart-clean-list-loading" role="status" aria-live="polite">
      <span class="material-symbols-outlined smart-clean-list-loading-icon">progress_activity</span>
      <p class="smart-clean-list-loading-title">${escapeHtml(message || 'Đang phân tích…')}</p>
      <p class="smart-clean-list-loading-hint">Quét ADB + phân loại package, có thể mất vài phút trên Wi‑Fi.</p>
    </div>`;
  } else {
    smartCleanList.classList.remove('is-loading');
  }
}

async function runSmartCleanAnalyze(useAi) {
  if (!activeDevice) {
    showAppsToast('Chọn thiết bị trước', 'info');
    return;
  }
  if (!appsCache.length) {
    setAppsStatus('Đang tải danh sách app...');
    await loadApps();
  }
  const { base, model } = readSmartCleanAiForm();
  if (useAi) {
    const panel = document.getElementById('smartCleanAiPanel');
    if (panel && !panel.open) panel.open = true;
    if (!isSmartCleanModelCommitted(model)) {
      showAppsToast('Chọn model hợp lệ từ danh sách (click hoặc Enter)', 'info');
      setSmartCleanStatus('Cần chọn model trong ô Model trước khi quét AI.');
      syncSmartCleanModelSearchToSelection();
      updateSmartCleanModelChrome();
      return;
    }
    if (model || base) {
      try {
        await getApi().save_app_settings(null, model || null, base || null);
      } catch {
        /* vẫn truyền override xuống smart_clean_suggest */
      }
    }
  }
  setSmartCleanScanMode(useAi ? 'ai' : 'offline');
  const loadMsg = useAi
    ? 'Đang quét Offline DB + gọi AI (OpenAI-compatible)…'
    : 'Đang quét Offline DB (heuristic)…';
  setSmartCleanStatus(loadMsg);
  setSmartCleanListLoading(true, loadMsg);
  if (smartCleanAiWarn) {
    smartCleanAiWarn.hidden = true;
    smartCleanAiWarn.textContent = '';
  }
  const modeOffline = document.getElementById('smartCleanModeOffline');
  const modeAi = document.getElementById('smartCleanModeAi');
  modeOffline?.classList.toggle('is-busy', !useAi);
  modeAi?.classList.toggle('is-busy', useAi);
  try {
    const res = await getApi().smart_clean_suggest(
      activeDevice.host,
      activeDevice.port,
      useAi,
      model || null,
      base || null,
    );
    smartCleanSuggestions = res.suggestions || [];
    smartCleanDismissed = new Set();
    renderSmartCleanSummary(res.counts);
    renderSmartCleanList();
    const rec = res.counts?.recommend ?? 0;
    setSmartCleanStatus(`Hoàn tất — ${rec} gói «Nên tắt».`);
    if (res.ai_error && smartCleanAiWarn) {
      smartCleanAiWarn.hidden = false;
      smartCleanAiWarn.textContent = res.ai_error;
    }
  } catch (err) {
    setSmartCleanStatus(`Lỗi: ${err}`);
    if (smartCleanList) {
      smartCleanList.innerHTML =
        '<p class="smart-clean-empty">Không phân tích được — thử Làm mới app hoặc kết nối lại TV.</p>';
    }
  } finally {
    modeOffline?.classList.remove('is-busy');
    modeAi?.classList.remove('is-busy');
    smartCleanList?.classList.remove('is-loading');
  }
}

async function openSmartCleanModal() {
  if (!activeDevice) {
    showAppsToast('Chọn thiết bị và tải app trước', 'info');
    return;
  }
  syncSmartCleanDeviceBadge();
  if (smartCleanModal) smartCleanModal.hidden = false;
  document.body.classList.add('smart-clean-modal-open');
  const aiPanel = document.getElementById('smartCleanAiPanel');
  if (aiPanel) aiPanel.removeAttribute('open');
  await syncSmartCleanAiFormFromSettings();
  requestAnimationFrame(() => {
    smartCleanList?.scrollTo(0, 0);
  });
  if (!smartCleanSuggestions.length) {
    runSmartCleanAnalyze(smartCleanScanMode === 'ai');
  } else {
    renderSmartCleanSummary(computeSmartCleanCounts());
    renderSmartCleanList();
  }
}

function closeSmartCleanModal() {
  if (smartCleanModal) smartCleanModal.hidden = true;
  document.body.classList.remove('smart-clean-modal-open');
}

async function smartCleanDisablePackages(pkgs, { closeOnSuccess = false } = {}) {
  if (!activeDevice || !pkgs.length) return;
  setButtonLoading(smartCleanApplyBtn, true);
  setSmartCleanStatus('Đang vô hiệu hóa qua ADB...');
  try {
    const res = await getApi().smart_clean_apply(activeDevice.host, activeDevice.port, pkgs);
    logAppsConsole('smart_clean_apply', `${res.ok_count}/${pkgs.length} ok`, res.fail_count ? 'log-err' : 'log-ok');
    (res.results || []).forEach((r) => {
      if (!r.ok) logAppsConsole(`pm disable-user ${r.package}`, r.error || 'fail', 'log-err');
    });
    showAppsToast(`Đã tắt ${res.ok_count}/${pkgs.length} app`, res.fail_count ? 'warning' : 'check_circle');
    smartCleanSuggestions = [];
    await loadApps();
    if (closeOnSuccess) closeSmartCleanModal();
    else runSmartCleanAnalyze(smartCleanScanMode === 'ai');
  } catch (err) {
    setSmartCleanStatus(`Lỗi: ${err}`);
  } finally {
    setButtonLoading(smartCleanApplyBtn, false);
  }
}

const smartCleanBtn = document.getElementById('smartCleanBtn');
smartCleanBtn?.addEventListener('click', () => openSmartCleanModal());

document.getElementById('smartCleanClose')?.addEventListener('click', () => closeSmartCleanModal());

smartCleanModal?.addEventListener('click', (e) => {
  if (e.target === smartCleanModal) closeSmartCleanModal();
});

document.getElementById('smartCleanModeOffline')?.addEventListener('click', () => runSmartCleanAnalyze(false));
document.getElementById('smartCleanModeAi')?.addEventListener('click', () => runSmartCleanAnalyze(true));

async function persistSmartCleanModelChoice({ quiet = false } = {}) {
  const { model, base } = readSmartCleanAiForm();
  if (!isSmartCleanModelCommitted(model)) return;
  try {
    await getApi().save_app_settings(null, model, base || null);
    updateSmartCleanModelChrome();
    if (!quiet) showAppsToast(`Đã chọn: ${model}`, 'check_circle');
  } catch (err) {
    showAppsToast(String(err), 'error');
  }
}

function applySmartCleanModelChoice(modelId) {
  const id = (modelId || '').trim();
  if (!id || !smartCleanModelsCache.includes(id)) return false;
  setSmartCleanModelValue(id, { syncSearch: true });
  return true;
}

const smartCleanModelSearchEl = document.getElementById('smartCleanModelSearch');
smartCleanModelSearchEl?.addEventListener('focus', () => openSmartCleanModelDropdown());
smartCleanModelSearchEl?.addEventListener('input', () => openSmartCleanModelDropdown());
smartCleanModelSearchEl?.addEventListener('keydown', async (e) => {
  if (e.key === 'Escape') {
    closeSmartCleanModelDropdown();
    return;
  }
  if (e.key === 'Enter') {
    e.preventDefault();
    const q = smartCleanModelSearchEl.value.trim();
    const matches = filterSmartCleanModels(q);
    if (matches.length === 1 && applySmartCleanModelChoice(matches[0])) {
      closeSmartCleanModelDropdown();
      await persistSmartCleanModelChoice();
    } else if (matches.length > 1 && applySmartCleanModelChoice(q)) {
      closeSmartCleanModelDropdown();
      await persistSmartCleanModelChoice();
    }
  }
});

document.getElementById('smartCleanModelDropdown')?.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-model]');
  if (!btn) return;
  if (!applySmartCleanModelChoice(btn.dataset.model)) return;
  closeSmartCleanModelDropdown();
  await persistSmartCleanModelChoice();
});

document.getElementById('smartCleanModelPicker')?.addEventListener('focusout', (e) => {
  const picker = document.getElementById('smartCleanModelPicker');
  if (picker && !picker.contains(e.relatedTarget)) {
    closeSmartCleanModelDropdown();
    window.setTimeout(() => {
      syncSmartCleanModelSearchToSelection();
      updateSmartCleanModelChrome();
    }, 120);
  }
});

smartCleanOnlyActionable?.addEventListener('change', () => renderSmartCleanList());

smartCleanSearch?.addEventListener('input', () => {
  smartCleanSearchQuery = smartCleanSearch.value;
  renderSmartCleanList();
});

smartCleanSummary?.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-tier-filter]');
  if (!btn) return;
  smartCleanTierFilter = btn.dataset.tierFilter || 'all';
  renderSmartCleanSummary();
  renderSmartCleanList();
});

smartCleanList?.addEventListener('change', (e) => {
  if (e.target.classList.contains('smart-clean-check')) updateSmartCleanApplyBtn();
});

smartCleanList?.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-act]');
  if (!btn || !activeDevice) return;
  const pkg = btn.dataset.pkg;
  const act = btn.dataset.act;
  if (act === 'detail') {
    const row = smartCleanSuggestions.find((s) => s.package === pkg);
    alert(`${pkg}\n\n${row?.reason || 'Không có mô tả thêm.'}`);
    return;
  }
  if (act === 'disable-one') {
    if (!confirm(`Vô hiệu hóa ${pkg}?`)) return;
    await smartCleanDisablePackages([pkg]);
    return;
  }
  if (act === 'skip' && pkg) {
    smartCleanDismissed.add(pkg);
    renderSmartCleanList();
  }
});

document.getElementById('smartCleanSelectRecommend')?.addEventListener('click', () => {
  smartCleanList?.querySelectorAll('.smart-clean-pkg-card[data-tier="recommend"]').forEach((card) => {
    const cb = card.querySelector('.smart-clean-check');
    if (cb && !cb.disabled) cb.checked = true;
  });
  updateSmartCleanApplyBtn();
});

document.getElementById('smartCleanSaveKey')?.addEventListener('click', async () => {
  const input = document.getElementById('smartCleanApiKey');
  let { key, base, model } = readSmartCleanAiForm();
  const btn = document.getElementById('smartCleanSaveKey');
  setButtonLoading(btn, true, 'Đang lưu…');
  try {
    if (!model) {
      const cur = await getApi().get_app_settings();
      model = cur.openai_model || '';
    }
    await getApi().save_app_settings(
      key || null,
      model || null,
      base || null,
    );
    if (input) input.value = '';
    const s = await getApi().get_app_settings();
    if (smartCleanKeyHint && s.openai_configured) {
      smartCleanKeyHint.hidden = false;
      smartCleanKeyHint.textContent = 'Đã lưu';
    }
    updateSmartCleanModelChrome();
    showAppsToast('Đã lưu cấu hình AI (key, URL, model)', 'key');
  } catch (err) {
    showAppsToast(String(err), 'error');
  } finally {
    setButtonLoading(btn, false);
  }
});

document.getElementById('smartCleanTestPing')?.addEventListener('click', async () => {
  const input = document.getElementById('smartCleanApiKey');
  const btn = document.getElementById('smartCleanTestPing');
  const { key, base } = readSmartCleanAiForm();
  setButtonLoading(btn, true, 'Đang ping…');
  try {
    if (key) {
      await getApi().save_app_settings(key, null, base || null);
    }
    const settings = await getApi().get_app_settings();
    const preferred = getSmartCleanModelValue() || settings.openai_model || '';
    const res = await refreshSmartCleanModels({
      key,
      base,
      preferred,
      autoPick: !preferred,
      toastOnError: true,
    });
    if (!res?.ok) return;
    const pickedModel = getSmartCleanModelValue();
    const pickedBase = readSmartCleanAiForm().base || null;
    if (isSmartCleanModelCommitted(pickedModel)) {
      await getApi().save_app_settings(null, pickedModel, pickedBase);
    }
    const n = res.models_total ?? (res.models || []).length;
    showAppsToast(
      n ? `Kết nối OK — ${n} model (gõ để tìm)` : 'Kết nối OK (không có model trong response)',
      'cloud_done',
    );
    if (input && key) input.value = '';
    if (smartCleanKeyHint && (key || settings.openai_configured)) {
      smartCleanKeyHint.hidden = false;
      smartCleanKeyHint.textContent = 'Đã lưu';
    }
  } catch (err) {
    showAppsToast(String(err), 'error');
  } finally {
    setButtonLoading(btn, false);
  }
});

document.getElementById('smartCleanToggleKey')?.addEventListener('click', () => {
  const input = document.getElementById('smartCleanApiKey');
  if (!input) return;
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
});

document.getElementById('smartCleanBackupBtn')?.addEventListener('click', () => {
  showAppsToast('Sao lưu profile debloat — sắp có (UC-05)', 'save');
});

smartCleanApplyBtn?.addEventListener('click', async () => {
  if (!activeDevice || !smartCleanList) return;
  const pkgs = [...smartCleanList.querySelectorAll('.smart-clean-check:checked')].map((cb) => cb.dataset.pkg);
  if (!pkgs.length) return;
  if (
    !confirm(
      `Vô hiệu hóa ${pkgs.length} app đã chọn?\n\nBạn có thể bật lại từng app trong tab Quản lý ứng dụng.`,
    )
  ) {
    return;
  }
  await smartCleanDisablePackages(pkgs, { closeOnSuccess: true });
});

if (appsList) {
  appsList.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn || !activeDevice) return;
    const pkg = btn.dataset.pkg;
    const act = btn.dataset.act;
    const loadingLabels = {
      open: 'Đang mở...',
      stop: 'Đang dừng...',
      info: 'Đang mở...',
      enable: 'Đang bật...',
      disable: 'Đang tắt...',
    };
    if (act === 'disable' && !confirm(`Vô hiệu hóa ${pkg}?\n\nHãy chắc chắn bạn hiểu tác động. Một số app hệ thống có thể ảnh hưởng chức năng TV.`)) {
      return;
    }
    setButtonLoading(btn, true, loadingLabels[act] || 'Đang xử lý...');
    try {
      if (act === 'open') {
        setAppsStatus(`Đang mở ${pkg}...`);
        logAppsConsole(`monkey -p ${pkg} 1`, '');
        await getApi().app_action(activeDevice.host, activeDevice.port, 'open', pkg);
        setAppsStatus('Đã gửi yêu cầu mở app');
        showAppsToast(`Đã mở ${pkg}`, 'play_arrow');
      } else if (act === 'stop') {
        setAppsStatus(`Đang force stop ${pkg}...`);
        logAppsConsole(`am force-stop ${pkg}`, '');
        await getApi().app_action(activeDevice.host, activeDevice.port, 'force_stop', pkg);
        setAppsStatus('Đã force stop');
        showAppsToast(`Force stop ${pkg}`, 'stop_circle');
      } else if (act === 'info') {
        setAppsStatus('Đang mở App info...');
        logAppsConsole(`am start ... APPLICATION_DETAILS_SETTINGS ${pkg}`, '');
        await getApi().app_action(activeDevice.host, activeDevice.port, 'app_info', pkg);
        setAppsStatus('Đã mở màn hình App info');
      } else if (act === 'enable') {
        setAppsStatus(`Đang kích hoạt ${pkg}...`);
        await getApi().app_action(activeDevice.host, activeDevice.port, 'enable', pkg);
        setAppsStatus('Đã kích hoạt, đang tải lại...');
        await loadApps();
        return;
      } else if (act === 'disable') {
        setAppsStatus(`Đang vô hiệu hóa ${pkg}...`);
        await getApi().app_action(activeDevice.host, activeDevice.port, 'disable', pkg);
        setAppsStatus('Đã vô hiệu hóa, đang tải lại...');
        await loadApps();
        return;
      }
      setTimeout(() => setAppsStatus(''), 1200);
    } catch (err) {
      setAppsStatus(`Lỗi: ${err}`);
    }
    setButtonLoading(btn, false);
  });
}

if (refreshAppsBtn) {
  refreshAppsBtn.addEventListener('click', async () => {
    setButtonLoading(refreshAppsBtn, true, 'Đang tải...');
    await loadApps();
    setButtonLoading(refreshAppsBtn, false);
  });
}

function deviceCardActions(d, featured) {
  const online = d.online;
  const name = escapeAttr(d.name);
  if (featured && online) {
    return `
      <button type="button" class="btn btn--accent" data-act="control" data-host="${d.host}" data-port="${d.port}" data-name="${name}">
        <span class="material-symbols-outlined">settings_remote</span>Mở Remote ảo
      </button>
      <button type="button" class="btn btn--surface" data-act="apps" data-host="${d.host}" data-port="${d.port}" data-name="${name}">Ứng dụng</button>
      <button type="button" class="btn btn--icon" data-act="rename" data-host="${d.host}" title="Đổi tên">
        <span class="material-symbols-outlined">edit</span>
      </button>
      <button type="button" class="btn btn--icon btn--danger-icon" data-act="remove" data-host="${d.host}" title="Xóa">
        <span class="material-symbols-outlined">delete</span>
      </button>`;
  }
  const primaryAct = online ? 'control' : 'reconnect';
  const primaryLabel = online ? 'Mở Remote' : 'Kết nối lại';
  return `
    <button type="button" class="btn btn--surface" data-act="${primaryAct}" data-host="${d.host}" data-port="${d.port}" data-name="${name}">${primaryLabel}</button>
    <button type="button" class="btn btn--ghost" data-act="apps" data-host="${d.host}" data-port="${d.port}" data-name="${name}" ${online ? '' : 'disabled'}>Ứng dụng</button>
    <button type="button" class="btn btn--icon" data-act="rename" data-host="${d.host}" title="Đổi tên">
      <span class="material-symbols-outlined">edit</span>
    </button>
    <button type="button" class="btn btn--icon btn--danger-icon" data-act="remove" data-host="${d.host}" title="Xóa">
      <span class="material-symbols-outlined">delete</span>
    </button>`;
}

async function refreshList(check = 'adb') {
  try {
    const devices = await getApi().list_devices(check);
    listEl.innerHTML = '';
    updateAppChrome(devices.length);
    if (!devices.length) {
      const empty = document.createElement('li');
      empty.className = 'device-card device-item';
      empty.innerHTML =
        '<div class="device-identity"><div class="device-avatar"><span class="material-symbols-outlined">devices</span></div>' +
        '<div><div class="device-name">Chưa có thiết bị</div><div class="device-meta">Thêm thủ công hoặc quét mạng để bắt đầu</div></div></div>';
      listEl.appendChild(empty);
      return;
    }
    for (const d of devices) {
      const li = document.createElement('li');
      const online = d.online;
      const isActive = activeDevice?.host === d.host;
      li.dataset.host = d.host;
      li.className = `device-card device-item${isActive ? ' device-card--active device-card--featured' : ' device-card--dim'}`;
      const badge = online
        ? '<span class="badge badge--online"><span style="width:6px;height:6px;border-radius:999px;background:var(--color-tertiary-container);"></span>Online</span>'
        : '<span class="badge badge--offline">Offline</span>';
      const icon = online ? 'tv' : 'cast';
      let telemetry = '';
      if (isActive) {
        telemetry = `
          <div class="telemetry-grid">
            <div class="telemetry-tile"><span class="telemetry-tile-label">Trạng thái</span><span class="telemetry-tile-value">${online ? 'Đang kết nối' : 'Offline'}</span></div>
            <div class="telemetry-tile"><span class="telemetry-tile-label">ADB</span><span class="telemetry-tile-value">${online ? 'Authorized' : '—'}</span></div>
            <div class="telemetry-tile"><span class="telemetry-tile-label">Host</span><span class="telemetry-tile-value">${escapeHtml(d.host)}</span></div>
            <div class="telemetry-tile"><span class="telemetry-tile-label">Port</span><span class="telemetry-tile-value">${d.port}</span></div>
            <div class="telemetry-tile"><span class="telemetry-tile-label">Lần cuối</span><span class="telemetry-tile-value">${formatTime(d.last_seen)}</span></div>
          </div>`;
      }
      li.innerHTML = `
        <div class="device-card-top">
          <div class="device-identity">
            <div class="device-avatar"><span class="material-symbols-outlined">${icon}</span></div>
            <div>
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                <span class="device-name">${escapeHtml(d.name)}</span>${badge}
              </div>
              <div class="device-meta">${d.host}:${d.port} • Lần cuối: ${formatTime(d.last_seen)}</div>
            </div>
          </div>
          <div class="device-actions">${deviceCardActions(d, isActive)}</div>
        </div>${telemetry}`;
      listEl.appendChild(li);
    }
    updateAppChrome(devices.length);
  } catch (err) {
    setStatus(`Lỗi làm mới: ${err}`);
    appendTerminal('list_devices', String(err), 'log-ok');
  }
}

function escapeHtml(s = '') {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function escapeAttr(s = '') {
  return escapeHtml(s).replace(/"/g, '&quot;');
}

function setButtonLoading(btn, loading, text) {
  if (!btn) return;
  if (loading) {
    if (text) {
      btn.dataset.originalText = btn.dataset.originalText || btn.innerHTML;
      btn.innerHTML = text;
    }
    btn.classList.add('loading');
    btn.disabled = true;
  } else {
    btn.classList.remove('loading');
    btn.disabled = false;
    if (btn.dataset.originalText !== undefined) {
      btn.innerHTML = btn.dataset.originalText;
      delete btn.dataset.originalText;
    }
  }
}

/** Add a spinner without replacing the button label (good for icon buttons). */
function setButtonBusy(btn, busy) {
  if (!btn) return;
  btn.classList.toggle('loading', busy);
  if (busy) btn.disabled = true;
  else btn.disabled = false;
}

listEl.addEventListener('click', async (e) => {
  const btn = e.target.closest('button');
  if (!btn) return;
  const host = btn.dataset.host;
  const port = btn.dataset.port || 5555;

  if (btn.dataset.act === 'control') {
    setActiveDevice({ host, port, name: btn.dataset.name || host });
    setRemoteStatus('');
    appendTerminal(`focus ${host}:${port}`, 'Thiết bị điều khiển đã chọn', 'log-ok');
    switchTab('remote');
    return;
  }

  if (btn.dataset.act === 'reconnect') {
    setButtonLoading(btn, true, 'Đang kết nối...');
    setStatus(`Đang kết nối ${host}...`);
    appendTerminal(`connect ${host}:${port}`, 'Đang bắt tay ADB...', 'log-info');
    try {
      const info = await getApi().connect(host, port);
      appendTerminal(`connect ${host}`, `${info.model || host} · Android ${info.android || '?'}`, 'log-ok');
      setStatus(`${host}: ${info.model} · Android ${info.android}`);
      await refreshList();
    } catch (err) {
      setStatus(`Lỗi kết nối ${host}: ${err}`);
      appendTerminal(`connect ${host}`, String(err), 'log-err');
      setButtonLoading(btn, false);
    }
    return;
  }

  if (btn.dataset.act === 'apps') {
    setActiveDevice({ host, port, name: btn.dataset.name || host });
    switchTab('apps');
    loadApps();
    return;
  }

  if (btn.dataset.act === 'rename') {
    const current = btn.closest('.device-item')?.querySelector('.device-name')?.textContent;
    if (!current) return;
    const name = prompt('Đổi tên thiết bị', current);
    if (name === null) return;
    setButtonLoading(btn, true, 'Đang lưu...');
    try {
      await getApi().rename(host, name);
      setStatus('Đã đổi tên thiết bị');
      await refreshList();
    } catch (err) {
      setStatus(`Lỗi đổi tên: ${err}`);
      setButtonLoading(btn, false);
    }
    return;
  }

  if (btn.dataset.act === 'remove') {
    if (!confirm('Xóa thiết bị này khỏi danh sách?')) return;
    setButtonLoading(btn, true, 'Đang xóa...');
    try {
      await getApi().remove(host);
      setStatus('Đã xóa thiết bị');
      if (activeDevice && activeDevice.host === host) {
        activeDevice = null;
        tabRemoteBtn.disabled = true;
        if (tabAppsBtn) tabAppsBtn.disabled = true;
        if (tabApkBtn) tabApkBtn.disabled = true;
        if (tabHomeBtn) tabHomeBtn.disabled = true;
        updateAppChrome();
        switchTab('devices');
      }
      await refreshList();
    } catch (err) {
      setStatus(`Lỗi xóa: ${err}`);
      setButtonLoading(btn, false);
    }
  }
});

addBtn.addEventListener('click', async () => {
  const host = document.getElementById('manualHost').value.trim();
  if (!host) return;
  setButtonLoading(addBtn, true, 'Đang kết nối...');
  setStatus(`Đang kết nối ${host}... (nếu lần đầu, chấp nhận "Allow USB debugging?" trên TV)`);
  try {
    const info = await getApi().connect(host);
    setStatus(`${host}: ${info.model} · Android ${info.android}`);
    appendTerminal(`connect ${host}`, `${info.model} · Android ${info.android}`, 'log-ok');
    document.getElementById('manualHost').value = '';
    await refreshList();
  } catch (err) {
    setStatus(`Lỗi kết nối ${host}: ${err}`);
  }
  setButtonLoading(addBtn, false);
});

if (scanQuickBtn && scanBtn) {
  scanQuickBtn.addEventListener('click', () => scanBtn.click());
}

scanBtn.addEventListener('click', async () => {
  scanResultsEl.innerHTML = '';
  setStatus('Đang quét mạng, có thể mất 10-30 giây tùy mạng...');
  appendTerminal('scan_subnet', 'Quét cổng 5555 trên các mạng local...', 'log-info');
  setButtonLoading(scanBtn, true, 'Đang quét...');
  try {
    const ips = await getApi().scan();
    if (!ips.length) {
      setStatus('Không tìm thấy thiết bị mở cổng 5555 trên các mạng local.');
    } else {
      setStatus(`Tìm thấy ${ips.length} thiết bị mở cổng 5555`);
      for (const ip of ips) {
        const div = document.createElement('div');
        div.className = 'scan-item';
        div.innerHTML = `<span>${ip}</span><button data-host="${ip}">Kết nối</button>`;
        div.querySelector('button').addEventListener('click', async (e) => {
          const btn = e.target;
          setButtonLoading(btn, true, 'Đang kết nối...');
          setStatus(`Đang kết nối ${ip}...`);
          try {
            const info = await getApi().connect(ip);
            setStatus(`${ip}: ${info.model} · Android ${info.android}`);
            div.remove();
            await refreshList();
          } catch (err) {
            setStatus(`Lỗi kết nối ${ip}: ${err}`);
            setButtonLoading(btn, false);
          }
        });
        scanResultsEl.appendChild(div);
      }
    }
  } catch (err) {
    setStatus(`Lỗi quét mạng: ${err}`);
  }
  setButtonLoading(scanBtn, false);
});

if (tabAppsBtn) {
  tabAppsBtn.addEventListener('click', () => {
    if (tabAppsBtn.disabled) return;
    switchTab('apps');
    if (activeDevice) loadApps();
  });
}

if (tabApkBtn) {
  tabApkBtn.addEventListener('click', () => {
    if (tabApkBtn.disabled) return;
    updateApkChrome();
    switchTab('apk');
  });
}

const backToAppsFromApk = document.getElementById('backToAppsFromApk');
if (backToAppsFromApk) {
  backToAppsFromApk.addEventListener('click', () => {
    if (tabAppsBtn && !tabAppsBtn.disabled) switchTab('apps');
    else switchTab('devices');
  });
}

refreshBtn.addEventListener('click', async () => {
  setButtonLoading(refreshBtn, true, 'Đang làm mới...');
  setStatus('Đang cập nhật trạng thái thiết bị (ADB)...');
  await refreshList('adb');
  setStatus('Đã cập nhật trạng thái');
  setTimeout(() => setStatus(''), 1500);
  setButtonLoading(refreshBtn, false);
});

const remoteAdbLog = document.getElementById('remoteAdbLog');
const remoteToast = document.getElementById('remoteToast');
const remoteToastMsg = document.getElementById('remoteToastMsg');
let remoteToastTimer = null;

function logRemoteAdb(cmd, detail, tone) {
  if (!remoteAdbLog) return;
  const time = new Date().toTimeString().split(' ')[0];
  const line = document.createElement('div');
  if (tone === 'ok') line.className = 'log-ok';
  if (tone === 'err') line.className = 'log-err';
  line.textContent = detail ? `[${time}] $ ${cmd} → ${detail}` : `[${time}] $ ${cmd}`;
  remoteAdbLog.appendChild(line);
  remoteAdbLog.scrollTop = remoteAdbLog.scrollHeight;
}

function showRemoteToast(message, icon = 'check_circle') {
  if (!remoteToast || !remoteToastMsg) return;
  const iconEl = document.getElementById('remoteToastIcon');
  if (iconEl) iconEl.textContent = icon;
  remoteToastMsg.textContent = message;
  remoteToast.classList.add('visible');
  if (remoteToastTimer) clearTimeout(remoteToastTimer);
  remoteToastTimer = setTimeout(() => remoteToast.classList.remove('visible'), 2200);
}

async function sendRemoteKey(btn, keycode) {
  if (!activeDevice) {
    setRemoteStatus('Chưa chọn thiết bị — quay lại tab Thiết bị');
    switchTab('devices');
    return;
  }
  const now = Date.now();
  const last = keyThrottle.get(keycode) || 0;
  if (now - last < 150) return;
  keyThrottle.set(keycode, now);
  const label = btn?.title || btn?.dataset?.name || keycode;
  setButtonBusy(btn, true);
  setRemoteStatus(`Đang gửi ${label}...`);
  logRemoteAdb(`input keyevent ${keycode}`, '...');
  try {
    await getApi().remote_key(activeDevice.host, activeDevice.port, keycode);
    logRemoteAdb(`input keyevent ${keycode}`, 'OK', 'ok');
    setRemoteStatus(`Đã gửi: ${label}`);
    setTimeout(() => setRemoteStatus(''), 800);
  } catch (err) {
    logRemoteAdb(`input keyevent ${keycode}`, String(err), 'err');
    setRemoteStatus(`Lỗi: ${err}`);
  }
  setButtonBusy(btn, false);
}

document.addEventListener('click', async (e) => {
  const quickBtn = e.target.closest('.quick-remote-pad .dpad, .quick-remote-keys .rbtn');
  const remoteBtn = e.target.closest('#tab-remote [data-key]');
  const btn = quickBtn || remoteBtn;
  if (!btn || !btn.dataset.key) return;
  if (remoteBtn && e.target.closest('form')) return;
  await sendRemoteKey(btn, parseInt(btn.dataset.key, 10));
});

document.getElementById('tab-remote')?.addEventListener('click', async (e) => {
  const appBtn = e.target.closest('[data-pkg]');
  if (!appBtn || !activeDevice) return;
  const pkg = appBtn.dataset.pkg;
  setRemoteStatus(`Đang mở ${pkg}...`);
  logRemoteAdb(`monkey -p ${pkg}`, '...');
  try {
    await getApi().app_action(activeDevice.host, activeDevice.port, 'open', pkg);
    logRemoteAdb(`monkey -p ${pkg}`, 'OK', 'ok');
    showRemoteToast(`Đã mở ${pkg}`, 'play_arrow');
  } catch (err) {
    logRemoteAdb(`monkey -p ${pkg}`, String(err), 'err');
    setRemoteStatus(`Lỗi: ${err}`);
  }
});

const remoteTextForm = document.getElementById('remoteTextForm');
const remoteTextInput = document.getElementById('remoteTextInput');
if (remoteTextForm) {
  remoteTextForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!activeDevice || !remoteTextInput) return;
    const text = remoteTextInput.value.trim();
    if (!text) return;
    setRemoteStatus('Đang gửi văn bản...');
    logRemoteAdb(`input text "${text}"`, '...');
    try {
      await getApi().send_input_text(activeDevice.host, activeDevice.port, text);
      logRemoteAdb('input text', 'OK', 'ok');
      remoteTextInput.value = '';
      showRemoteToast('Đã gửi văn bản lên TV', 'send');
      setRemoteStatus('');
    } catch (err) {
      logRemoteAdb('input text', String(err), 'err');
      setRemoteStatus(`Lỗi: ${err}`);
    }
  });
}

document.getElementById('remoteTextClear')?.addEventListener('click', () => {
  if (remoteTextInput) remoteTextInput.value = '';
});

document.querySelectorAll('.remote-preset-tag[data-preset]').forEach((tag) => {
  tag.addEventListener('click', () => {
    if (remoteTextInput) remoteTextInput.value = tag.dataset.preset || tag.textContent;
  });
});

document.getElementById('remotePasteBtn')?.addEventListener('click', async () => {
  try {
    const t = await navigator.clipboard.readText();
    if (remoteTextInput && t) remoteTextInput.value = t;
  } catch {
    showRemoteToast('Không đọc được clipboard', 'error');
  }
});

document.getElementById('remoteWakeBtn')?.addEventListener('click', (e) => {
  sendRemoteKey(e.currentTarget, 224);
});

document.getElementById('remoteMouseLeft')?.addEventListener('click', (e) => {
  sendRemoteKey(e.currentTarget, 23);
});
document.getElementById('remoteMouseBack')?.addEventListener('click', (e) => {
  sendRemoteKey(e.currentTarget, 4);
});
document.getElementById('remoteMouseScroll')?.addEventListener('click', async () => {
  if (!activeDevice) return;
  const cmd = 'input swipe 960 1400 960 600 300';
  logRemoteAdb(cmd, '...');
  try {
    await getApi().device_shell(activeDevice.host, activeDevice.port, cmd);
    logRemoteAdb(cmd, 'OK', 'ok');
    showRemoteToast('Cuộn xuống', 'swap_vert');
  } catch (err) {
    logRemoteAdb(cmd, String(err), 'err');
  }
});

document.getElementById('remoteSendKeycodeBtn')?.addEventListener('click', async (e) => {
  const input = document.getElementById('remoteCustomKeycode');
  const val = parseInt(input?.value, 10);
  if (!val) return;
  await sendRemoteKey(e.currentTarget, val);
  if (input) input.value = '';
});

document.getElementById('remoteScreencapBtn')?.addEventListener('click', async () => {
  if (!activeDevice) return;
  const fn = `smarttvmanager_${Date.now()}.png`;
  const cmd = `screencap -p /sdcard/${fn}`;
  logRemoteAdb(cmd, '...');
  try {
    await getApi().device_shell(activeDevice.host, activeDevice.port, cmd);
    logRemoteAdb(cmd, `/sdcard/${fn}`, 'ok');
    showRemoteToast(`Đã chụp /sdcard/${fn}`, 'photo_camera');
  } catch (err) {
    logRemoteAdb(cmd, String(err), 'err');
  }
});

document.getElementById('remoteDevBtn')?.addEventListener('click', async () => {
  if (!activeDevice) return;
  const cmd =
    'am start -a android.settings.APPLICATION_DEVELOPMENT_SETTINGS';
  logRemoteAdb(cmd, '...');
  try {
    await getApi().device_shell(activeDevice.host, activeDevice.port, cmd);
    logRemoteAdb(cmd, 'OK', 'ok');
  } catch (err) {
    logRemoteAdb(cmd, String(err), 'err');
  }
});

document.getElementById('remoteRebootBtn')?.addEventListener('click', async () => {
  if (!activeDevice) return;
  if (!confirm('Khởi động lại TV qua ADB?')) return;
  logRemoteAdb('reboot', '...');
  try {
    await getApi().device_shell(activeDevice.host, activeDevice.port, 'reboot');
    logRemoteAdb('reboot', 'sent', 'ok');
    showRemoteToast('Đã gửi reboot', 'restart_alt');
  } catch (err) {
    logRemoteAdb('reboot', String(err), 'err');
  }
});

document.getElementById('remoteClearLog')?.addEventListener('click', () => {
  if (remoteAdbLog) remoteAdbLog.innerHTML = '';
});

const remoteTrackpad = document.getElementById('remoteTrackpad');
const remoteTrackpadDot = document.getElementById('remoteTrackpadDot');
if (remoteTrackpad && remoteTrackpadDot) {
  let trackpadDragging = false;
  let lastSwipeAt = 0;
  remoteTrackpad.addEventListener('mousemove', (ev) => {
    const rect = remoteTrackpad.getBoundingClientRect();
    const x = ev.clientX - rect.left;
    const y = ev.clientY - rect.top;
    remoteTrackpadDot.classList.add('visible');
    remoteTrackpadDot.style.left = `${x}px`;
    remoteTrackpadDot.style.top = `${y}px`;
    if (!trackpadDragging || !activeDevice) return;
    const now = Date.now();
    if (now - lastSwipeAt < 120) return;
    lastSwipeAt = now;
    const tvX = Math.round((x / rect.width) * 1920);
    const tvY = Math.round((y / rect.height) * 1080);
    const cmd = `input swipe ${tvX} ${tvY} ${tvX} ${tvY} 40`;
    getApi().device_shell(activeDevice.host, activeDevice.port, cmd).catch(() => {});
  });
  remoteTrackpad.addEventListener('mousedown', () => {
    trackpadDragging = true;
  });
  remoteTrackpad.addEventListener('mouseup', () => {
    trackpadDragging = false;
  });
  remoteTrackpad.addEventListener('mouseleave', () => {
    remoteTrackpadDot.classList.remove('visible');
    trackpadDragging = false;
  });
  remoteTrackpad.addEventListener('dblclick', () => sendRemoteKey(null, 23));
}

if (remoteAdbLog) {
  logRemoteAdb('remote', 'Sẵn sàng — chọn thiết bị và gửi keyevent', 'ok');
}

const APK_HISTORY_KEY = 'smarttvmanager_apk_history_v1';
const APK_HISTORY_KEY_LEGACY = 'tvremotehub_apk_history_v1';

function setApkStatus(msg) {
  if (apkStatus) apkStatus.textContent = msg || '';
}

function formatApkBytes(n) {
  const b = Number(n) || 0;
  if (b >= 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)} MB`;
  if (b >= 1024) return `${Math.round(b / 1024)} KB`;
  return `${b} B`;
}

function updateApkChrome() {
  if (!activeDevice) return;
  if (apkTarget) apkTarget.textContent = activeDevice.name;
  if (apkTargetMeta) apkTargetMeta.textContent = `(${activeDevice.host}:${activeDevice.port})`;
}

async function refreshApkStorage() {
  const chip = document.getElementById('apkStorageChip');
  const text = document.getElementById('apkStorageText');
  if (!activeDevice || !text) return;
  try {
    const res = await getApi().device_shell(activeDevice.host, activeDevice.port, 'df -h /sdcard 2>/dev/null | tail -1');
    const line = (res.output || '').trim();
    const parts = line.split(/\s+/);
    if (parts.length >= 4) {
      text.textContent = `${parts[3]} trống / ${parts[1]}`;
      if (chip) chip.classList.add('visible');
    }
  } catch {
    /* ignore */
  }
}

function loadApkHistory() {
  try {
    return JSON.parse(
      localStorage.getItem(APK_HISTORY_KEY) || localStorage.getItem(APK_HISTORY_KEY_LEGACY) || '[]',
    );
  } catch {
    return [];
  }
}

function saveApkHistory(items) {
  localStorage.setItem(APK_HISTORY_KEY, JSON.stringify(items.slice(0, 12)));
}

function pushApkHistory(entry) {
  const items = loadApkHistory().filter((x) => x.package !== entry.package || x.filename !== entry.filename);
  items.unshift(entry);
  saveApkHistory(items);
  renderApkHistory();
}

function renderApkHistory() {
  const list = document.getElementById('apkHistoryList');
  if (!list) return;
  const items = loadApkHistory();
  if (!items.length) {
    list.innerHTML = '<p class="apk-history-meta">Chưa có lịch sử cài trên máy này.</p>';
    return;
  }
  list.innerHTML = '';
  for (const it of items) {
    const row = document.createElement('div');
    row.className = 'apk-history-item';
    row.innerHTML = `
      <div class="apk-history-main">
        <div class="apk-history-icon"><span class="material-symbols-outlined">android</span></div>
        <div class="min-w-0">
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="apk-history-name">${escapeHtml(it.label || it.filename)}</span>
            <span class="apk-history-exit">${it.ok ? 'OK' : 'Fail'}</span>
          </div>
          <div class="apk-history-meta">${escapeHtml(it.version || '—')} · ${escapeHtml(it.time || '')}</div>
        </div>
      </div>
      <div class="apk-history-actions">
        <button type="button" class="apk-icon-btn" data-act="open-pkg" data-pkg="${escapeAttr(it.package || '')}" title="Mở trên TV"><span class="material-symbols-outlined" style="font-size:16px;">open_in_new</span></button>
      </div>`;
    list.appendChild(row);
  }
}

function permShortName(p) {
  const s = (p || '').replace('android.permission.', '');
  return s.length > 28 ? s.slice(0, 26) + '…' : s;
}

function renderApkCompat(info) {
  const perms = info.permissions || [];
  const target = parseInt(info.target_sdk, 10) || 0;
  const lean = perms.some((p) => /LEANBACK|leanback/i.test(p));
  const tvScore = (target >= 26 ? 40 : target >= 21 ? 25 : 10) + (lean ? 30 : 10) + (info.certs_count ? 20 : 5) + (perms.length ? 10 : 0);
  const scoreEl = document.getElementById('apkCompatScore');
  if (scoreEl) scoreEl.textContent = `${Math.min(100, tvScore)}%`;
  const setCompat = (id, html) => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = html;
  };
  setCompat(
    'apkCompatLeanback',
    lean
      ? '<span class="material-symbols-outlined" style="font-size:14px;color:var(--color-tertiary-fixed);">check_circle</span> Có leanback'
      : '<span class="material-symbols-outlined" style="font-size:14px;">help</span> Chưa rõ'
  );
  setCompat(
    'apkCompatDpad',
    target >= 21
      ? '<span class="material-symbols-outlined" style="font-size:14px;color:var(--color-tertiary-fixed);">check_circle</span> TV SDK OK'
      : 'SDK thấp'
  );
  setCompat(
    'apkCompatProtect',
    '<span class="material-symbols-outlined" style="font-size:14px;color:var(--color-tertiary-fixed);">verified_user</span> ADB sideload'
  );
  setCompat(
    'apkCompatSdk',
    `<span class="material-symbols-outlined" style="font-size:14px;color:var(--color-tertiary-fixed);">check_circle</span> ${escapeHtml(String(info.target_sdk || '—'))}`
  );
}

function setApkProgress(show, pct, label, cmd) {
  const block = document.getElementById('apkProgressBlock');
  const fill = document.getElementById('apkProgressFill');
  const pctEl = document.getElementById('apkProgressPct');
  const labelEl = document.getElementById('apkProgressLabel');
  const cmdEl = document.getElementById('apkProgressCmd');
  if (block) block.hidden = !show;
  if (fill) fill.style.width = `${Math.max(0, Math.min(100, pct))}%`;
  if (pctEl) pctEl.textContent = `${Math.round(pct)}%`;
  if (labelEl && label) labelEl.textContent = label;
  if (cmdEl && cmd) cmdEl.textContent = cmd;
}

/** Progress bar while install_apk runs (push + pm install can take many minutes on Wi‑Fi). */
function startApkInstallProgressTimer(flags) {
  const started = Date.now();
  let pct = 3;
  return setInterval(() => {
    const elapsed = Date.now() - started;
    let label;
    if (elapsed < 45000) {
      label = 'Đang đẩy APK lên TV qua Wi‑Fi…';
    } else if (elapsed < 120000) {
      label = 'Đang chạy pm install trên TV…';
    } else {
      label = 'TV vẫn đang xử lý — APK lớn có thể mất 5–10 phút';
    }
    if (elapsed > 45000 && pct < 52) pct = 52;
    else if (elapsed > 120000 && pct < 75) pct = 75;
    else if (pct < 97) {
      const step = pct < 45 ? 2.2 : pct < 80 ? 0.9 : 0.35;
      pct = Math.min(97, pct + step);
    }
    setApkProgress(true, pct, label, `pm install ${flags} …`);
  }, 1000);
}

function showApkInspector(show) {
  const insp = document.getElementById('apkInspector');
  const sideEmpty = document.getElementById('apkSideEmpty');
  const sidePanel = document.getElementById('apkSidePanel');
  if (insp) insp.hidden = !show;
  if (sideEmpty) sideEmpty.hidden = show;
  if (sidePanel) sidePanel.hidden = !show;
  if (show) renderApkHistory();
}

function renderApkInfo(info) {
  showApkInspector(true);
  setApkProgress(false, 0);
  const fn = document.getElementById('apkFileName');
  const fs = document.getElementById('apkFileSize');
  const pkg = document.getElementById('apkPackageName');
  const meta = document.getElementById('apkMetaLine');
  const tags = document.getElementById('apkPermTags');
  const warns = document.getElementById('apkWarnList');
  if (fn) {
    fn.textContent = info.filename || '—';
    fn.title = info.filename || '';
  }
  if (fs) fs.textContent = formatApkBytes(info.size);
  if (pkg) pkg.textContent = info.package || '—';
  if (meta) {
    const ver = `v${info.version_name || '?'} (${info.version_code || '?'})`;
    const sdk = `Target SDK ${info.target_sdk || '—'}`;
    const sig = info.certs_count ? `${info.certs_count} chữ ký` : 'Chữ ký: —';
    const inst = info.installed
      ? `Đã cài: ${info.installed.version_name || '?'}`
      : 'Chưa cài trên TV';
    meta.innerHTML = `<span>${escapeHtml(ver)}</span><span>${escapeHtml(sdk)}</span><span>${escapeHtml(sig)}</span><span>${escapeHtml(inst)}</span>`;
  }
  if (tags) {
    const perms = (info.permissions || []).slice(0, 8);
    tags.innerHTML = perms.length
      ? perms.map((p) => `<span class="apk-perm-tag">${escapeHtml(permShortName(p))}</span>`).join('')
      : '<span class="apk-perm-tag">Không đọc được quyền</span>';
  }
  if (warns) {
    const w = [];
    if (info.warning_downgrade) w.push('<div class="apk-warn apk-warn--downgrade">APK cũ hơn bản trên TV — cần «Hạ cấp (-d)» hoặc sẽ lỗi.</div>');
    else if (info.warning_same) w.push('<div class="apk-warn apk-warn--downgrade">Cùng version — dùng «Cài đè (-r)».</div>');
    else if (info.warning_upgrade) w.push('<div class="apk-warn apk-warn--ok">Nâng cấp từ bản đang cài.</div>');
    if (info.dangerous_count) w.push('<div class="apk-warn apk-warn--danger">APK có quyền nhạy cảm — chỉ cài nguồn tin cậy.</div>');
    warns.innerHTML = w.join('');
  }
  renderApkCompat(info);
  suggestApkInstallPreset(info);
  updateApkInstallCmdPreview();
  if (apkInfo) apkInfo.textContent = JSON.stringify(info, null, 2);
}

function getApkInstallOptions() {
  const preset = document.getElementById('apkInstallPreset')?.value || 'replace';
  const post = document.getElementById('apkPostInstall')?.value || 'none';
  let reinstall = true;
  let allowDowngrade = false;
  if (preset === 'replace_downgrade') {
    reinstall = true;
    allowDowngrade = true;
  } else if (preset === 'fresh') {
    reinstall = false;
    allowDowngrade = false;
  } else if (preset === 'downgrade') {
    reinstall = false;
    allowDowngrade = true;
  }
  const grant = post === 'grant' || post === 'grant_open';
  const openAfter = post === 'open' || post === 'grant_open';
  return { reinstall, allowDowngrade, grant, openAfter };
}

function buildApkInstallFlagStr(opts) {
  const flags = ['-t'];
  if (opts.reinstall) flags.push('-r');
  if (opts.allowDowngrade) flags.push('-d');
  if (opts.grant) flags.push('-g');
  return flags.join(' ');
}

function updateApkInstallCmdPreview() {
  const el = document.getElementById('apkInstallCmdPreview');
  if (!el) return;
  const flags = buildApkInstallFlagStr(getApkInstallOptions());
  el.textContent = `pm install ${flags} /sdcard/Download/…apk`;
}

function suggestApkInstallPreset(info) {
  const sel = document.getElementById('apkInstallPreset');
  if (!sel || !info) return;
  if (info.warning_downgrade) sel.value = 'replace_downgrade';
  else if (info.warning_same) sel.value = 'replace';
}

function clearApk() {
  currentApk = null;
  if (apkFileInput) apkFileInput.value = '';
  if (apkInfo) apkInfo.textContent = '';
  if (apkInstallBtn) apkInstallBtn.disabled = true;
  if (apkClearBtn) apkClearBtn.disabled = true;
  showApkInspector(false);
  setApkProgress(false, 0);
  setApkStatus('');
}

if (apkSelectBtn && apkFileInput) {
  apkSelectBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    apkFileInput.click();
  });
}

if (apkDropzone && apkFileInput) {
  apkDropzone.addEventListener('click', (e) => {
    if (e.target.closest('button')) return;
    apkFileInput.click();
  });
}

if (apkFileInput) {
  apkFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (lower.endsWith('.xapk') || lower.endsWith('.apks')) {
      setApkStatus('XAPK/APKS chưa hỗ trợ — giải nén base.apk trước.');
      return;
    }
    if (!lower.endsWith('.apk')) {
      setApkStatus('Chỉ chấp nhận file .apk');
      return;
    }
    setApkStatus(`Đang đọc manifest ${file.name}…`);
    setButtonLoading(apkSelectBtn, true, 'Đang đọc...');
    try {
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const base64 = reader.result.split(',')[1];
          const info = await getApi().analyze_apk(file.name, base64, activeDevice ? activeDevice.host : null, activeDevice ? activeDevice.port : 5555);
          currentApk = info;
          renderApkInfo(info);
          if (apkInstallBtn) apkInstallBtn.disabled = !activeDevice;
          if (apkClearBtn) apkClearBtn.disabled = false;
          setApkStatus('Đã phân tích APK. Kiểm tra thông tin trước khi cài đặt.');
        } catch (err) {
          setApkStatus(`Lỗi phân tích: ${err}`);
          clearApk();
        }
        setButtonLoading(apkSelectBtn, false);
      };
      reader.readAsDataURL(file);
    } catch (err) {
      setApkStatus(`Lỗi đọc file: ${err}`);
      setButtonLoading(apkSelectBtn, false);
    }
  });
}

if (apkDropzone) {
  apkDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    apkDropzone.classList.add('dragover');
  });
  apkDropzone.addEventListener('dragleave', () => apkDropzone.classList.remove('dragover'));
  apkDropzone.addEventListener('drop', async (e) => {
    e.preventDefault();
    apkDropzone.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const dt = new DataTransfer();
    dt.items.add(file);
    apkFileInput.files = dt.files;
    apkFileInput.dispatchEvent(new Event('change'));
  });
}

if (apkClearBtn) {
  apkClearBtn.addEventListener('click', clearApk);
}

document.getElementById('apkInstallPreset')?.addEventListener('change', updateApkInstallCmdPreview);
document.getElementById('apkPostInstall')?.addEventListener('change', updateApkInstallCmdPreview);
updateApkInstallCmdPreview();

if (apkInstallBtn) {
  apkInstallBtn.addEventListener('click', async () => {
    if (!activeDevice || !currentApk) return;
    if (!confirm(`Cài đặt ${currentApk.filename} lên ${activeDevice.name}?\n\nHãy đảm bảo APK đến từ nguồn đáng tin cậy.`)) return;
    const { reinstall, allowDowngrade, grant, openAfter } = getApkInstallOptions();
    const flags = buildApkInstallFlagStr({ reinstall, allowDowngrade, grant, openAfter: false });
    setButtonLoading(apkInstallBtn, true, 'Đang cài đặt...');
    setApkStatus('Đang đẩy APK và cài đặt...');
    setApkProgress(true, 3, 'Bắt đầu đẩy APK lên TV…', `pm install ${flags} …`);
    const timer = startApkInstallProgressTimer(flags);
    try {
      const res = await getApi().install_apk(
        activeDevice.host,
        activeDevice.port,
        currentApk._tmp_path,
        currentApk.filename,
        reinstall,
        allowDowngrade,
        grant
      );
      clearInterval(timer);
      setApkProgress(true, 100, 'Hoàn tất', res.output || 'Success');
      setApkStatus(res.ok ? 'Cài đặt thành công!' : 'Cài đặt hoàn tất');
      pushApkHistory({
        filename: currentApk.filename,
        package: currentApk.package,
        label: currentApk.package || currentApk.filename,
        version: currentApk.version_name,
        time: new Date().toLocaleString('vi-VN'),
        ok: !!res.ok,
      });
      if (openAfter && currentApk.package) {
        try {
          await getApi().app_action(activeDevice.host, activeDevice.port, 'open', currentApk.package);
        } catch {
          /* ignore */
        }
      }
      setTimeout(() => clearApk(), 800);
    } catch (err) {
      clearInterval(timer);
      setApkProgress(false, 0);
      setApkStatus(`Lỗi cài đặt: ${err}`);
    }
    setButtonLoading(apkInstallBtn, false);
  });
}

document.getElementById('apkHistoryList')?.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-act="open-pkg"]');
  if (!btn || !activeDevice) return;
  const pkg = btn.dataset.pkg;
  if (!pkg) return;
  try {
    await getApi().app_action(activeDevice.host, activeDevice.port, 'open', pkg);
    setApkStatus(`Đã mở ${pkg}`);
  } catch (err) {
    setApkStatus(`Lỗi mở app: ${err}`);
  }
});

document.getElementById('apkClearHistoryBtn')?.addEventListener('click', () => {
  saveApkHistory([]);
  renderApkHistory();
});

function setHomeStatus(msg) {
  if (homeStatus) homeStatus.textContent = msg || '';
}

function formatApplyStepLine(step) {
  const t = step.t
    ? new Date(step.t * 1000).toLocaleTimeString('vi-VN', { hour12: false })
    : '--:--:--';
  const detail = step.detail ? ` — ${step.detail}` : '';
  return `[${t}] ${step.msg}${detail}`;
}

function renderHomeApplyLog(steps, opts = {}) {
  const { error = null, logPath = null, open = true } = opts;
  if (!homeApplyLogWrap || !homeApplyLog) return;
  const lines = (steps || []).map(formatApplyStepLine);
  if (error) lines.push(`[LỖI] ${error}`);
  homeApplyLog.textContent = lines.length ? lines.join('\n') : '';
  if (homeApplyLogHint) {
    homeApplyLogHint.textContent = logPath
      ? `File log: ${logPath} (append mỗi lần áp dụng)`
      : '';
  }
  homeApplyLogWrap.hidden = !lines.length;
  if (open && lines.length) homeApplyLogWrap.open = true;
  if (homeApplyLog) {
    homeApplyLog.scrollTop = homeApplyLog.scrollHeight;
  }
  const last = steps && steps.length ? steps[steps.length - 1] : null;
  if (last && !error) {
    setHomeStatus(`${last.msg}${last.detail ? `: ${last.detail}` : ''}`);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollApplyThemeJob(jobId, btn) {
  const logPathHint = null;
  for (let i = 0; i < 600; i += 1) {
    const st = await getApi().apply_gathin_theme_job(jobId);
    renderHomeApplyLog(st.steps, {
      error: st.status === 'failed' ? st.error : null,
      logPath: st.log_path || logPathHint,
    });
    if (st.status === 'done') {
      return st.result;
    }
    if (st.status === 'failed') {
      throw new Error(st.error || 'Áp dụng theme thất bại');
    }
    if (st.status === 'unknown') {
      throw new Error('Job áp dụng theme không còn tồn tại');
    }
    await sleep(400);
  }
  throw new Error('Hết thời gian chờ (quá 4 phút). Xem nhật ký bên dưới hoặc file log.');
}

let homeThemes = [];
let homeThemesLoading = null;
let previewThemeId = null;
let homeActiveThemeId = null;
let homeToastTimer = null;

function showHomeToast(message, icon = 'check_circle') {
  if (!homeToast || !homeToastMsg) return;
  const iconEl = document.getElementById('homeToastIcon');
  if (iconEl) iconEl.textContent = icon;
  homeToastMsg.textContent = message;
  homeToast.classList.add('visible');
  if (homeToastTimer) clearTimeout(homeToastTimer);
  homeToastTimer = setTimeout(() => homeToast.classList.remove('visible'), 2600);
}

function updateHomeChrome() {
  if (!activeDevice) return;
  if (homeTarget) homeTarget.textContent = activeDevice.name;
  if (homeTargetMeta) homeTargetMeta.textContent = `(${activeDevice.host}:${activeDevice.port})`;
  updateHomeThemeCount();
}

async function activateHomeTab() {
  if (!activeDevice) {
    if (homeTarget) homeTarget.textContent = '—';
    if (homeTargetMeta) homeTargetMeta.textContent = '—';
    setHomeStatus('Chọn thiết bị để quản lý theme.');
    return;
  }
  updateHomeChrome();
  await loadHomeThemes();
  await loadCurrentTheme();
}

async function loadHomeThemes(opts = {}) {
  const force = !!opts.force;
  const btn = opts.btn || null;
  if (!force && homeThemes.length) {
    renderHomeThemeGrid();
    return;
  }
  if (homeThemesLoading && !force) {
    return homeThemesLoading;
  }

  const run = async () => {
    if (btn) setButtonLoading(btn, true, force ? 'Đang tải lại...' : 'Đang tải...');
    setHomeStatus(
      force ? 'Đang tải lại danh sách theme...' : 'Đang tải danh sách theme từ cleanyourtv...'
    );
    if (force && homeThemesGrid) homeThemesGrid.innerHTML = '';
    try {
      const themes = await getApi().list_gathin_themes();
      homeThemes = themes || [];
      if (!homeThemes.length) {
        setHomeStatus('Không tìm thấy theme trong data/cleanyourtv/themes');
        return;
      }
      updateHomeThemeCount();
      renderHomeThemeGrid();
      const invalid = homeThemes.filter((t) => (t.errors || []).length).length;
      setHomeStatus(
        force
          ? `Đã tải lại ${homeThemes.length} theme${invalid ? ` (${invalid} không hợp lệ)` : ''}`
          : `Đã tải ${homeThemes.length} theme${invalid ? ` (${invalid} không hợp lệ)` : ''}`
      );
      if (force) showHomeToast(`Đã tải lại ${homeThemes.length} theme`, 'refresh');
    } catch (err) {
      setHomeStatus(`Lỗi: ${err}`);
    } finally {
      if (btn) setButtonLoading(btn, false);
    }
  };

  homeThemesLoading = run().finally(() => {
    homeThemesLoading = null;
  });
  return homeThemesLoading;
}

function updateHomeThemeCount() {
  const el = document.getElementById('homeThemeCount');
  if (el) el.textContent = `${homeThemes.length} theme`;
}

function stableThemeJson(obj) {
  if (!obj || typeof obj !== 'object') return '{}';
  const sorted = {};
  Object.keys(obj)
    .sort()
    .forEach((k) => {
      sorted[k] = obj[k];
    });
  return JSON.stringify(sorted);
}

function guessActiveThemeId(config) {
  const cur = stableThemeJson(config || {});
  if (cur === '{}') return null;
  for (const t of homeThemes) {
    if (stableThemeJson(t.config || {}) === cur) return t.id;
  }
  return null;
}

function renderHomeDetect(info) {
  const badge = document.getElementById('homeDetectBadge');
  const pkgEl = document.getElementById('homeKpiPackage');
  const instEl = document.getElementById('homeKpiInstalled');
  const defEl = document.getElementById('homeKpiDefault');
  const compatEl = document.getElementById('homeKpiCompat');
  if (!info) return;
  if (pkgEl) pkgEl.textContent = info.pkg || '—';
  if (instEl) {
    instEl.textContent = info.installed ? 'Đã cài' : 'Chưa cài';
    instEl.className = `home-kpi-value ${info.installed ? 'ok' : 'err'}`;
  }
  if (defEl) {
    if (info.is_default_home) {
      defEl.textContent = 'Gathin (mặc định)';
      defEl.className = 'home-kpi-value ok';
    } else {
      defEl.textContent = info.current_home ? `Khác: ${info.current_home}` : 'Chưa thiết lập';
      defEl.className = `home-kpi-value ${info.current_home ? '' : 'err'}`;
    }
  }
  if (compatEl) {
    compatEl.textContent = info.compatible ? '100% — sẵn sàng' : 'Không tương thích';
    compatEl.className = `home-kpi-value ${info.compatible ? 'ok' : 'err'}`;
  }
  if (badge) {
    if (info.installed && info.compatible) {
      badge.textContent = 'Sẵn sàng ADB';
      badge.className = 'home-adb-badge';
    } else {
      badge.textContent = 'Cần cài launcher';
      badge.className = 'home-adb-badge home-adb-badge--warn';
    }
  }
}

function renderActiveThemePanel(cur, matchedTheme) {
  const titleEl = document.getElementById('homeActiveTitle');
  const descEl = document.getElementById('homeActiveDesc');
  const wallEl = document.getElementById('homeActiveWall');
  const revEl = document.getElementById('homeActiveRevision');
  const provEl = document.getElementById('homeActiveProvider');
  const updatedEl = document.getElementById('homeActiveUpdated');
  const thumb = document.getElementById('homeActiveThumb');
  const placeholder = document.getElementById('homeActiveThumbPlaceholder');
  const keys = Object.keys(cur.config || {});
  const walls = cur.wallpapers || [];
  homeActiveThemeId = matchedTheme ? matchedTheme.id : guessActiveThemeId(cur.config);

  const displayName = matchedTheme
    ? matchedTheme.name
    : keys.length
      ? 'Theme tùy chỉnh trên TV'
      : 'Mặc định (chưa overlay)';

  if (titleEl) titleEl.textContent = displayName;
  if (descEl) {
    descEl.textContent = matchedTheme
      ? `Khớp thư viện cleanyourtv · ${keys.length} khoá config`
      : keys.length
        ? `${keys.length} khoá config trên TV — chưa khớp theme local`
        : 'Launcher chưa có config.json overlay.';
  }
  if (wallEl) {
    wallEl.textContent = walls.length
      ? `${walls.length} file (${walls.slice(0, 2).join(', ')}${walls.length > 2 ? '…' : ''})`
      : 'Không';
  }
  if (revEl) revEl.textContent = cur.revision ? cur.revision.slice(0, 12) + '…' : '—';
  if (provEl) {
    provEl.textContent = cur.provider ? 'ThemeProvider' : 'cp fallback';
  }
  if (updatedEl) updatedEl.textContent = `Đồng bộ ${new Date().toLocaleTimeString('vi-VN')}`;

  const resBadge = document.getElementById('homeActiveRes');
  if (thumb && placeholder) {
    const tvWall = cur.wallpaper_b64;
    const localShot = matchedTheme && matchedTheme.screenshot;
    const previewB64 = tvWall || localShot;
    if (previewB64) {
      thumb.src = `data:image/jpeg;base64,${previewB64}`;
      thumb.hidden = false;
      placeholder.hidden = true;
      if (resBadge) {
        resBadge.textContent = tvWall ? 'Wallpaper trên TV' : 'Preview thư viện';
        resBadge.classList.add('has-preview');
      }
    } else {
      thumb.removeAttribute('src');
      thumb.hidden = true;
      placeholder.hidden = false;
      const hint = placeholder.querySelector('.home-active-empty-hint');
      if (hint) {
        hint.textContent =
          keys.length || cur.has_overlay
            ? 'Không lấy được ảnh từ TV — vẫn có config'
            : 'Đồng bộ từ TV để xem preview';
      }
      if (resBadge) {
        resBadge.textContent = keys.length ? 'Config trên TV' : 'Chưa có overlay';
        resBadge.classList.remove('has-preview');
      }
    }
  }

  if (homeCurrentInfo) {
    homeCurrentInfo.textContent = keys.length ? JSON.stringify(cur.config, null, 2) : '';
  }
}

function renderHomeThemeGrid() {
  if (!homeThemesGrid) return;
  const q = (homeSearchInput?.value || '').trim().toLowerCase();
  homeThemesGrid.innerHTML = '';
  const list = homeThemes.filter((t) => {
    if (!q) return true;
    return (t.name || '').toLowerCase().includes(q) || (t.id || '').toLowerCase().includes(q);
  });
  if (!list.length) {
    homeThemesGrid.innerHTML =
      '<p class="home-gallery-desc">Chưa có theme — đang tải hoặc thư mục data/cleanyourtv/themes trống.</p>';
    return;
  }
  for (const t of list) {
    const errs = t.errors || [];
    const warns = t.warnings || [];
    const isActive = homeActiveThemeId === t.id;
    const card = document.createElement('article');
    card.className =
      'home-theme-card' + (errs.length ? ' invalid' : '') + (isActive ? ' is-active' : '');
    card.dataset.search = (t.name || t.id || '').toLowerCase();
    const thumb = t.screenshot
      ? `<img src="data:image/jpeg;base64,${t.screenshot}" alt="${escapeAttr(t.name)}">`
      : '';
    const activeBadge = isActive
      ? `<span class="home-theme-badge"><span class="home-theme-badge-dot"></span>ĐANG DÙNG</span>`
      : '';
    const applyBtn = isActive
      ? `<button type="button" class="btn btn--surface" disabled><span class="material-symbols-outlined">check</span>Đang áp dụng</button>`
      : `<button type="button" class="btn btn--primary" data-act="apply-theme" data-id="${escapeAttr(t.id)}" ${errs.length ? 'disabled' : ''}><span class="material-symbols-outlined">play_arrow</span>Áp dụng</button>`;
    card.innerHTML = `
      <div>
        <div class="home-theme-preview">${activeBadge}${thumb}<span class="home-theme-tag">${t.wallpapers_count} apps</span></div>
        <div class="home-theme-head">
          <h3 class="home-theme-name">${escapeHtml(t.name)}</h3>
          <span class="home-theme-version">${t.has_config ? 'config' : 'wall only'}</span>
        </div>
        <div class="home-theme-meta">config: ${t.has_config ? 'có' : 'không'} • wallpaper: ${t.has_wallpaper ? 'có' : 'không'} • bộ sưu tập: ${t.wallpapers_count}</div>
        ${errs.length ? `<div class="theme-badge error">Không hợp lệ</div>` : ''}
        ${!errs.length && warns.length ? `<div class="theme-badge warn">Cảnh báo</div>` : ''}
      </div>
      <div class="home-theme-actions">
        ${applyBtn}
        <button type="button" class="btn btn--surface btn--preview" data-act="preview-theme" data-id="${escapeAttr(t.id)}"><span class="material-symbols-outlined">visibility</span>Xem</button>
      </div>`;
    homeThemesGrid.appendChild(card);
  }
}

async function runHomeDetect(btn) {
  if (!activeDevice) {
    setHomeStatus('Vui lòng chọn thiết bị trước');
    return;
  }
  if (btn) setButtonLoading(btn, true, 'Đang kiểm tra...');
  setHomeStatus('Đang phát hiện launcher...');
  try {
    const res = await getApi().detect_launcher(activeDevice.host, activeDevice.port);
    renderHomeDetect(res.info || {});
    setHomeStatus(res.info?.compatible ? 'Phát hiện com.gathin.tvhome.' : 'Chưa sẵn sàng gathin.tvhome.');
  } catch (err) {
    setHomeStatus(`Lỗi: ${err}`);
  }
  if (btn) setButtonLoading(btn, false);
}

async function syncFromTv(btn) {
  if (!activeDevice) {
    setHomeStatus('Vui lòng chọn thiết bị trước');
    return;
  }
  if (btn) setButtonLoading(btn, true, 'Đang đồng bộ...');
  if (!homeThemes.length) await loadHomeThemes();
  await runHomeDetect(null);
  await loadCurrentTheme();
  await loadHomeBackups();
  if (btn) setButtonLoading(btn, false);
  showHomeToast('Đã đồng bộ trạng thái từ TV', 'sync');
}

async function loadCurrentTheme(btn) {
  if (!activeDevice) {
    setHomeStatus('Vui lòng chọn thiết bị trước');
    return;
  }
  if (btn) setButtonLoading(btn, true, 'Đang tải...');
  setHomeStatus('Đang đọc theme và wallpaper từ TV...');
  try {
    const cur = await getApi().current_launcher_theme(activeDevice.host, activeDevice.port);
    const matched =
      homeThemes.find(
        (t) => stableThemeJson(t.config || {}) === stableThemeJson(cur.config || {})
      ) || null;
    renderActiveThemePanel(cur, matched);
    if (homeThemes.length) renderHomeThemeGrid();
    const keyCount = Object.keys(cur.config || {}).length;
    if (keyCount || cur.wallpaper_b64) {
      setHomeStatus(
        `Đã đồng bộ: ${keyCount} khoá config${cur.wallpaper_b64 ? ', có preview wallpaper' : ''}.`
      );
    } else if (cur.has_overlay) {
      setHomeStatus('TV có overlay nhưng chưa đọc được config — thử bật ThemeProvider / đồng bộ lại.');
    } else {
      setHomeStatus('Chưa có theme overlay trên TV (launcher mặc định).');
    }
  } catch (err) {
    setHomeStatus(`Lỗi đọc theme: ${err}`);
  }
  if (btn) setButtonLoading(btn, false);
}

async function loadHomeBackups(btn) {
  if (!activeDevice) {
    setHomeStatus('Vui lòng chọn thiết bị trước');
    return;
  }
  if (btn) setButtonLoading(btn, true, 'Đang tải...');
  if (homeBackupsList) homeBackupsList.innerHTML = '';
  try {
    const items = await getApi().list_launcher_backups(activeDevice.host, activeDevice.port);
    if (!homeBackupsList) return;
    if (!items.length) {
      homeBackupsList.innerHTML = '<li class="backup-empty">Chưa có bản sao lưu nào cho thiết bị này.</li>';
      return;
    }
    for (const b of items) {
      const li = document.createElement('li');
      li.className = 'backup-item';
      li.innerHTML = `
        <div class="backup-info">
          <div class="backup-time">${escapeHtml(b.time)}</div>
          <div class="theme-meta">config: ${b.had_config ? 'có' : 'không'} • wallpapers: ${b.wallpapers}</div>
        </div>
        <button type="button" class="btn btn--surface" data-act="restore-backup" data-id="${escapeAttr(b.id)}">Khôi phục</button>`;
      homeBackupsList.appendChild(li);
    }
  } catch (err) {
    setHomeStatus(`Lỗi tải backup: ${err}`);
  }
  if (btn) setButtonLoading(btn, false);
}

function closeThemeModal() {
  if (themeModal) themeModal.hidden = true;
  previewThemeId = null;
}

function openThemeModal(id) {
  const t = homeThemes.find((x) => x.id === id);
  if (!t || !themeModal) return;
  previewThemeId = id;
  if (themeModalTitle) themeModalTitle.textContent = t.name;
  if (themeModalDesc) {
    themeModalDesc.textContent = `config: ${t.has_config ? 'có' : 'không'} · wallpaper: ${t.has_wallpaper ? 'có' : 'không'}`;
  }
  if (themeModalImg) {
    if (t.screenshot) {
      themeModalImg.src = `data:image/jpeg;base64,${t.screenshot}`;
      themeModalImg.style.display = '';
    } else {
      themeModalImg.removeAttribute('src');
      themeModalImg.style.display = 'none';
    }
  }
  const errs = t.errors || [];
  const warns = t.warnings || [];
  if (themeModalMeta) {
    themeModalMeta.innerHTML = `
      <div>config: <strong>${t.has_config ? 'có' : 'không'}</strong> • wallpaper: <strong>${t.has_wallpaper ? 'có' : 'không'}</strong> • bộ sưu tập: <strong>${t.wallpapers_count}</strong></div>
      ${errs.length ? `<div class="theme-error">Lỗi: ${escapeHtml(errs.join('; '))}</div>` : ''}
      ${warns.length ? `<div class="theme-warn">Cảnh báo: ${escapeHtml(warns.join('; '))}</div>` : ''}
    `;
  }
  if (themeModalConfig) {
    themeModalConfig.textContent = t.has_config
      ? JSON.stringify(t.config || {}, null, 2)
      : 'Theme không có config.json (chỉ đổi wallpaper).';
  }
  if (themeModalApply) {
    themeModalApply.disabled = errs.length > 0;
    themeModalApply.innerHTML = errs.length
      ? 'Theme không hợp lệ'
      : '<span class="material-symbols-outlined">check_circle</span> Áp dụng theme này';
  }
  themeModal.hidden = false;
}

async function applyTheme(id, btn) {
  if (!activeDevice) {
    setHomeStatus('Vui lòng chọn thiết bị trước');
    return;
  }
  const theme = homeThemes.find((t) => t.id === id);
  if (!theme) return;
  if ((theme.errors || []).length) {
    setHomeStatus(`Theme không hợp lệ: ${theme.errors.join('; ')}`);
    return;
  }
  if (!confirm(`Áp dụng theme "${theme.name}" lên ${activeDevice.name}?\n\nApp sẽ tự động sao lưu cấu hình hiện tại trước khi ghi.`)) return;

  if (btn) setButtonLoading(btn, true, 'Đang áp dụng...');
  renderHomeApplyLog([], { open: true });
  setHomeStatus('Đang sao lưu và áp dụng theme...');
  try {
    const started = await getApi().apply_gathin_theme_async(
      activeDevice.host,
      activeDevice.port,
      id
    );
    const res = await pollApplyThemeJob(started.job_id, btn);
    const backupTime = res.backup && res.backup.time ? res.backup.time : '-';
    const warns = (res.warnings || []).length ? ` (${res.warnings.join('; ')})` : '';
    renderHomeApplyLog(res.steps || [], { logPath: res.log_path || started.log_path });
    if (btn) setButtonLoading(btn, false);
    closeThemeModal();
    setHomeStatus(`Đã áp dụng "${theme.name}". Backup: ${backupTime}${warns}`);
    homeActiveThemeId = id;
    showHomeToast(`Đã áp dụng theme "${theme.name}"`, 'palette');
    await loadCurrentTheme();
    await loadHomeBackups();
    renderHomeThemeGrid();
  } catch (err) {
    if (btn) setButtonLoading(btn, false);
    const msg = String(err);
    setHomeStatus(`Lỗi áp dụng: ${msg}`);
    alert(`Áp dụng thất bại: ${msg}\n\nXem «Nhật ký áp dụng theme» hoặc ~/.smarttv-manager/theme-apply.log`);
  }
}

if (homeDetectBtn) {
  homeDetectBtn.addEventListener('click', () => runHomeDetect(homeDetectBtn));
}

if (homeSetDefaultBtn) {
  homeSetDefaultBtn.addEventListener('click', async () => {
    if (!activeDevice) return;
    if (!confirm('Đặt com.gathin.tvhome làm launcher mặc định?')) return;
    setButtonLoading(homeSetDefaultBtn, true, 'Đang gửi...');
    const cmd = 'cmd package set-home-activity com.gathin.tvhome/com.gathin.tvhome.MainActivity';
    try {
      await getApi().device_shell(activeDevice.host, activeDevice.port, cmd);
      showHomeToast('Đã gửi lệnh đặt Home mặc định', 'home');
      await runHomeDetect(null);
    } catch (err) {
      setHomeStatus(`Lỗi: ${err}`);
    }
    setButtonLoading(homeSetDefaultBtn, false);
  });
}

if (homeBackupBtn) {
  homeBackupBtn.addEventListener('click', async () => {
    if (!activeDevice) return;
    if (!confirm('Tạo backup cấu hình gathin.tvhome? Khuyến nghị làm trước mọi thay đổi.')) return;
    setButtonLoading(homeBackupBtn, true, 'Đang sao lưu...');
    setHomeStatus('Đang sao lưu cấu hình...');
    try {
      const res = await getApi().backup_launcher(activeDevice.host, activeDevice.port);
      setHomeStatus(`Đã tạo backup lúc ${res.time}.`);
      await loadHomeBackups();
    } catch (err) {
      setHomeStatus(`Lỗi backup: ${err}`);
    }
    setButtonLoading(homeBackupBtn, false);
  });
}

if (homeResetThemeBtn) {
  homeResetThemeBtn.addEventListener('click', async () => {
    if (!activeDevice) return;
    if (!confirm('Xoá config/wallpaper đã áp dụng và quay về cấu hình mặc định của launcher?\n\nMột bản sao lưu sẽ được tạo trước khi xoá.')) return;
    setButtonLoading(homeResetThemeBtn, true, 'Đang xử lý...');
    setHomeStatus('Đang sao lưu và đưa launcher về mặc định...');
    try {
      const res = await getApi().reset_launcher(activeDevice.host, activeDevice.port);
      const backupTime = res.backup && res.backup.time ? res.backup.time : '-';
      setHomeStatus(`Đã đưa về mặc định. Backup trước khi reset: ${backupTime}`);
      await loadCurrentTheme();
      await loadHomeBackups();
    } catch (err) {
      setHomeStatus(`Lỗi reset: ${err}`);
    }
    setButtonLoading(homeResetThemeBtn, false);
  });
}

if (homeRestartBtn) {
  homeRestartBtn.addEventListener('click', async () => {
    if (!activeDevice) return;
    setButtonLoading(homeRestartBtn, true, 'Đang khởi động lại...');
    setHomeStatus('Đang khởi động lại Home...');
    try {
      const res = await getApi().restart_launcher(activeDevice.host, activeDevice.port);
      setHomeStatus(res.ok ? 'Đã khởi động lại Home.' : 'Đã gửi lệnh nhưng không xác nhận được kết quả.');
    } catch (err) {
      setHomeStatus(`Lỗi khởi động lại: ${err}`);
    }
    setButtonLoading(homeRestartBtn, false);
  });
}

if (homeReloadBtn) {
  homeReloadBtn.addEventListener('click', () => syncFromTv(homeReloadBtn));
}

if (homeImportBtn) {
  homeImportBtn.addEventListener('click', () => {
    showHomeToast('Nhập ZIP/JSON — đặt file vào data/cleanyourtv/themes', 'file_upload');
  });
}

if (homeSearchInput) {
  homeSearchInput.addEventListener('input', () => renderHomeThemeGrid());
}

if (homeLoadBackupsBtn) {
  homeLoadBackupsBtn.addEventListener('click', async () => {
    await loadHomeBackups(homeLoadBackupsBtn);
  });
}

if (homeBackupsList) {
  homeBackupsList.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.act !== 'restore-backup') return;
    const id = btn.dataset.id;
    if (!activeDevice) return;
    if (!confirm(`Khôi phục bản sao lưu ${id}?\n\nCấu hình và wallpaper hiện tại sẽ bị thay thế.`)) return;
    setButtonLoading(btn, true, 'Đang khôi phục...');
    setHomeStatus(`Đang khôi phục bản sao lưu ${id}...`);
    try {
      await getApi().restore_launcher_backup(activeDevice.host, activeDevice.port, id);
      setHomeStatus('Đã khôi phục bản sao lưu.');
      await loadCurrentTheme();
    } catch (err) {
      setHomeStatus(`Lỗi khôi phục: ${err}`);
    }
    setButtonLoading(btn, false);
  });
}

if (homeDiscoverBtn) {
  homeDiscoverBtn.addEventListener('click', async () => {
    if (!activeDevice) return;
    setButtonLoading(homeDiscoverBtn, true, 'Đang tìm...');
    setHomeStatus('Đang khám phá vị trí config...');
    if (homeDiscoverOut) homeDiscoverOut.textContent = '';
    try {
      const res = await getApi().detect_launcher(activeDevice.host, activeDevice.port);
      if (homeDiscoverOut) {
        homeDiscoverOut.textContent = JSON.stringify(res.discovery, null, 2);
      }
      setHomeStatus('Đã khám phá. Xem kết quả bên dưới.');
    } catch (err) {
      setHomeStatus(`Lỗi: ${err}`);
    }
    setButtonLoading(homeDiscoverBtn, false);
  });
}

if (homeLoadThemesBtn) {
  homeLoadThemesBtn.addEventListener('click', () => {
    loadHomeThemes({ force: true, btn: homeLoadThemesBtn });
  });
}

if (homeThemesGrid) {
  homeThemesGrid.addEventListener('click', async (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const act = btn.dataset.act;
    const id = btn.dataset.id;
    if (act === 'preview-theme') {
      openThemeModal(id);
      return;
    }
    if (act === 'apply-theme') {
      await applyTheme(id, btn);
    }
  });
}

if (themeModalClose) {
  themeModalClose.addEventListener('click', closeThemeModal);
}

if (themeModalCancel) {
  themeModalCancel.addEventListener('click', closeThemeModal);
}

if (themeModal) {
  themeModal.addEventListener('click', (e) => {
    if (e.target === themeModal) closeThemeModal();
  });
}

if (themeModalApply) {
  themeModalApply.addEventListener('click', async () => {
    if (!previewThemeId) return;
    await applyTheme(previewThemeId, themeModalApply);
  });
}

document.addEventListener('keydown', (e) => {
  if (devGuideModal && !devGuideModal.hidden) {
    if (e.key === 'Escape') {
      closeDevGuide();
      return;
    }
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      devGuideTourStep(-1);
      return;
    }
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      devGuideTourStep(1);
      return;
    }
  }
  if (e.key !== 'Escape') return;
  if (themeModal && !themeModal.hidden) closeThemeModal();
});

const DEV_GUIDE_STORAGE = 'smarttvmanager.devGuideBanner.v1';
const DEV_GUIDE_STORAGE_LEGACY = 'tvremotehub.devGuideBanner.v1';

const DEV_GUIDE_BRAND_HINTS = {
  tcl: 'TCL / Google TV: Cài đặt → Hệ thống → Giới thiệu → Bản dựng hệ điều hành Android TV.',
  sony: 'Sony Bravia: Cài đặt → Device Preferences → About → Build.',
  xiaomi: 'Xiaomi: có thể cần bấm «Số phiên bản (Build)» thay vì dòng Android TV OS Build.',
  casper: 'Casper Google TV: tương tự TCL — mục Build trong Giới thiệu.',
  other: 'Android Box / AOSP: tìm About → Build number, bấm OK 7 lần.',
};

const DEV_GUIDE_TOUR_IMAGES = [
  'assets/guide/dev-options-system.png',
  'assets/guide/about-build.png',
  'assets/guide/usb-debugging.png',
];

const DEV_GUIDE_TOUR_SHORT = [
  'Cài đặt → Giới thiệu',
  'Nhấn 7 lần vào Bản dựng HĐH',
  'Bật Gỡ lỗi qua USB',
];

let devGuideTourIndex = 0;
let devGuideClicksLeft = 7;
const devGuideModal = document.getElementById('devGuideModal');
const devGuideBanner = document.getElementById('devGuideBanner');

function devGuideBannerHidden() {
  try {
    return (
      localStorage.getItem(DEV_GUIDE_STORAGE) === '1'
      || localStorage.getItem(DEV_GUIDE_STORAGE_LEGACY) === '1'
    );
  } catch {
    return false;
  }
}

function setDevGuideBannerHidden(hidden) {
  try {
    if (hidden) localStorage.setItem(DEV_GUIDE_STORAGE, '1');
    else localStorage.removeItem(DEV_GUIDE_STORAGE);
  } catch {
    /* ignore */
  }
}

function resetDevGuideSimulator() {
  devGuideClicksLeft = 7;
  const tag = document.getElementById('devGuideClickTag');
  const bar = document.getElementById('devGuideClickBar');
  const toast = document.getElementById('devGuideClickToast');
  const btn = document.getElementById('devGuideSimOk');
  if (tag) {
    tag.textContent = 'Còn 7 lần';
    tag.classList.remove('is-done');
  }
  if (bar) bar.style.width = '0%';
  if (toast) {
    toast.textContent = 'Chạm nút để xem hiệu ứng Toast trên TV…';
    toast.className = 'dev-guide-click-toast';
  }
  if (btn) {
    btn.disabled = false;
    btn.innerHTML =
      '<span class="material-symbols-outlined">radio_button_checked</span> Bấm phím OK thử';
  }
}

function updateDevGuideBrandHint(brand) {
  const el = document.getElementById('devGuideBrandHint');
  if (el) el.textContent = DEV_GUIDE_BRAND_HINTS[brand] || '';
}

function renderDevGuideTour() {
  const idx = devGuideTourIndex;
  const stepNum = document.getElementById('devGuideTourStepNum');
  const stepShort = document.getElementById('devGuideTourStepShort');
  const img = document.getElementById('devGuideTourImg');
  const hotspot = document.getElementById('devGuideTourHotspot');
  const prevBtn = document.getElementById('devGuideTourPrev');
  const nextBtn = document.getElementById('devGuideTourNext');
  const doneBtn = document.getElementById('devGuideDoneClose');

  if (stepNum) stepNum.textContent = String(idx + 1);
  if (stepShort) stepShort.textContent = DEV_GUIDE_TOUR_SHORT[idx] || '';
  if (img) {
    img.src = DEV_GUIDE_TOUR_IMAGES[idx] || DEV_GUIDE_TOUR_IMAGES[0];
    img.alt = DEV_GUIDE_TOUR_SHORT[idx] || 'Ảnh hướng dẫn TV';
  }
  if (hotspot) hotspot.hidden = idx !== 1;

  document.querySelectorAll('.dev-guide-tour-rail-item').forEach((el) => {
    const step = Number(el.dataset.tourStep);
    el.classList.toggle('is-active', step === idx);
    el.classList.toggle('is-done', step < idx);
  });

  document.querySelectorAll('.dev-guide-tour-img-tab').forEach((tab) => {
    tab.classList.toggle('is-active', Number(tab.dataset.tourImg) === idx);
  });

  for (let i = 0; i < 3; i += 1) {
    const panel = document.getElementById(`devGuideTourPanel${i}`);
    if (panel) panel.hidden = i !== idx;
  }

  if (prevBtn) prevBtn.disabled = idx <= 0;
  if (nextBtn) {
    nextBtn.hidden = idx >= 2;
    const nextLabels = [
      'Tiếp tục: Bước 2',
      'Tiếp tục: Bước 3 (USB debugging)',
    ];
    const label = nextLabels[idx] || 'Tiếp tục';
    nextBtn.innerHTML = `${label} <span class="material-symbols-outlined">arrow_forward</span>`;
  }
  if (doneBtn) doneBtn.hidden = idx < 2;

  const dpadHint = document.querySelector('.dev-guide-tour-dpad-hint');
  if (dpadHint) dpadHint.hidden = idx !== 1;

  if (idx === 1) resetDevGuideSimulator();
}

function setDevGuideTourIndex(nextIndex) {
  devGuideTourIndex = Math.max(0, Math.min(2, nextIndex));
  renderDevGuideTour();
}

function devGuideTourStep(delta) {
  if (delta > 0 && devGuideTourIndex >= 2) {
    closeDevGuide();
    setStatus('Đã hoàn tất tour — nhập IP TV và bấm Thêm & Kết nối.');
    document.getElementById('manualHost')?.focus();
    return;
  }
  setDevGuideTourIndex(devGuideTourIndex + delta);
}

function openDevGuide() {
  if (!devGuideModal) return;
  devGuideTourIndex = 0;
  renderDevGuideTour();
  devGuideModal.hidden = false;
}

function closeDevGuide() {
  if (!devGuideModal) return;
  const dontShow = document.getElementById('devGuideDontShow');
  if (dontShow && dontShow.checked) setDevGuideBannerHidden(true);
  devGuideModal.hidden = true;
  if (devGuideBanner) devGuideBanner.hidden = devGuideBannerHidden();
}

function initDevGuide() {
  if (devGuideBanner) {
    devGuideBanner.hidden = devGuideBannerHidden();
  }
  document.getElementById('devGuideOpenBtn')?.addEventListener('click', () => openDevGuide());
  document.getElementById('devGuideBannerStart')?.addEventListener('click', () => openDevGuide());
  document.getElementById('devGuideBannerDismiss')?.addEventListener('click', () => {
    setDevGuideBannerHidden(true);
    if (devGuideBanner) devGuideBanner.hidden = true;
  });
  document.getElementById('devGuideClose')?.addEventListener('click', closeDevGuide);
  document.getElementById('devGuideCloseCompact')?.addEventListener('click', closeDevGuide);
  document.getElementById('devGuideTourSkip')?.addEventListener('click', closeDevGuide);
  document.getElementById('devGuideTourPrev')?.addEventListener('click', () => devGuideTourStep(-1));
  document.getElementById('devGuideTourNext')?.addEventListener('click', () => devGuideTourStep(1));
  document.getElementById('devGuideDoneClose')?.addEventListener('click', () => {
    closeDevGuide();
    setStatus('Đã xem hướng dẫn — nhập IP TV và bấm Thêm & Kết nối.');
    document.getElementById('manualHost')?.focus();
  });
  document.getElementById('devGuideMarkDone')?.addEventListener('click', () => {
    setDevGuideBannerHidden(true);
    if (devGuideBanner) devGuideBanner.hidden = true;
    closeDevGuide();
    setStatus('Đã đánh dấu hoàn thành hướng dẫn Developer Mode.');
  });
  devGuideModal?.addEventListener('click', (e) => {
    if (e.target === devGuideModal) closeDevGuide();
  });

  document.querySelectorAll('.dev-guide-brand').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.dev-guide-brand').forEach((b) => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      updateDevGuideBrandHint(btn.dataset.brand || 'tcl');
    });
  });
  updateDevGuideBrandHint('tcl');

  document.querySelectorAll('.dev-guide-tour-rail-item').forEach((el) => {
    el.addEventListener('click', () => {
      const step = Number(el.dataset.tourStep);
      if (!Number.isNaN(step)) setDevGuideTourIndex(step);
    });
  });

  document.querySelectorAll('.dev-guide-tour-img-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      const step = Number(tab.dataset.tourImg);
      if (!Number.isNaN(step)) setDevGuideTourIndex(step);
    });
  });

  document.getElementById('devGuideSimOk')?.addEventListener('click', () => {
    if (devGuideClicksLeft <= 0) return;
    devGuideClicksLeft -= 1;
    const tag = document.getElementById('devGuideClickTag');
    const bar = document.getElementById('devGuideClickBar');
    const toast = document.getElementById('devGuideClickToast');
    const btn = document.getElementById('devGuideSimOk');
    const pct = ((7 - devGuideClicksLeft) / 7) * 100;
    if (bar) bar.style.width = `${pct}%`;
    if (devGuideClicksLeft > 0) {
      if (tag) tag.textContent = `Còn ${devGuideClicksLeft} lần`;
      if (toast) {
        toast.textContent = `TV Toast: "Bạn còn ${devGuideClicksLeft} bước nữa để trở thành nhà phát triển."`;
        toast.className = 'dev-guide-click-toast is-warn';
      }
    } else {
      if (tag) {
        tag.textContent = 'ĐÃ MỞ KHÓA!';
        tag.classList.add('is-done');
      }
      if (toast) {
        toast.textContent = 'TV Toast: "Bạn hiện đã là nhà phát triển!"';
        toast.className = 'dev-guide-click-toast is-success';
      }
      if (btn) {
        btn.disabled = true;
        btn.innerHTML =
          '<span class="material-symbols-outlined">check_circle</span> Đã hoàn thành!';
      }
    }
  });
}

if (clearLogsBtn && terminalBodyEl) {
  clearLogsBtn.addEventListener('click', () => {
    terminalBodyEl.innerHTML = '';
  });
}

if (terminalBodyEl) {
  appendTerminal('smarttv-manager', 'ADB console sẵn sàng', 'log-ok');
}

waitForPywebviewAndBoot();
