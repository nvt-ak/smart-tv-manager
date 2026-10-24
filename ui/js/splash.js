(function splashBoot() {
  const STATUSES = [
    { pct: 12, msg: 'Khởi động ADB server socket nội bộ...' },
    { pct: 28, msg: 'Tự động quét mạng LAN tìm thiết bị TV (cổng 5555)...' },
    { pct: 48, msg: 'Nạp giao diện TV Remote Hub...' },
    { pct: 68, msg: 'Đồng bộ module Home & Theme...' },
    { pct: 88, msg: 'Chuẩn bị bàn điều khiển thiết bị...' },
    { pct: 100, msg: 'Khởi tạo thành công! Đang vào màn hình chính...' },
  ];

  const MIN_SPLASH_MS = 2400;
  const STEP_MS = 520;

  const bar = document.getElementById('splashProgressBar');
  const percentEl = document.getElementById('splashPercent');
  const statusEl = document.getElementById('splashStatusText');
  const logActiveEl = document.getElementById('splashLogActive');
  const skipBtn = document.getElementById('splashSkip');

  let stepIndex = 0;
  let pywebviewReady = false;
  let minTimeDone = false;
  let finished = false;

  function applyStep(i) {
    const step = STATUSES[Math.min(i, STATUSES.length - 1)];
    if (bar) bar.style.width = `${step.pct}%`;
    if (percentEl) percentEl.textContent = `${step.pct}%`;
    if (statusEl) statusEl.textContent = step.msg;
    if (logActiveEl) logActiveEl.textContent = step.msg;
  }

  function enterMain() {
    if (finished) return;
    finished = true;
    window.location.replace('index.html');
  }

  function tryEnterMain() {
    if (finished) return;
    const atEnd = stepIndex >= STATUSES.length - 1;
    if (atEnd && minTimeDone && pywebviewReady) {
      window.setTimeout(enterMain, 280);
    }
  }

  function onPywebviewReady() {
    pywebviewReady = true;
    tryEnterMain();
  }

  if (window.pywebview && window.pywebview.api) {
    onPywebviewReady();
  } else {
    window.addEventListener('pywebviewready', onPywebviewReady, { once: true });
    window.setTimeout(() => {
      if (!pywebviewReady) onPywebviewReady();
    }, 4000);
  }

  window.setTimeout(() => {
    minTimeDone = true;
    tryEnterMain();
  }, MIN_SPLASH_MS);

  applyStep(0);
  const tick = window.setInterval(() => {
    if (finished) {
      window.clearInterval(tick);
      return;
    }
    if (stepIndex < STATUSES.length - 1) {
      stepIndex += 1;
      applyStep(stepIndex);
      tryEnterMain();
    } else {
      window.clearInterval(tick);
      tryEnterMain();
    }
  }, STEP_MS);

  skipBtn?.addEventListener('click', (e) => {
    e.preventDefault();
    enterMain();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      enterMain();
    }
  });
})();
