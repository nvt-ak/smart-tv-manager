# LG webOS QA report

Date: 2026-10-28. Scope and acceptance criteria: [implementation plan](lg-webos.md).
QA reviewed desktop integration independently of the client, Home and UI owners.
All automated protocol/CLI tests use controlled fakes; they do not establish real-TV
compatibility or successful installation on a particular firmware.

## Test-first evidence

The PM approved and committed the use-case/task breakdown (`d406bf5`) before product
implementation. Each owner ran missing-behavior tests before implementing its module.

| Area | Observed RED | GREEN evidence |
| --- | --- | --- |
| API/storage | 10 tests failed with 5 failures and 6 errors; legacy platform missing, new connect/input endpoints absent and LG attempted ADB. RED committed `d349ff5`; fixtures aligned to agreed client names in `52d4a8c`. | 15 API/storage/job tests passed independently. |
| Theme apply jobs | Missing `webos_apply_theme_async` caused 2 errors. RED committed `92ee303`. | Failed deploy never saves last theme; success records host/port only after deploy; Android/unknown theme rejected; selected host passed to CLI verification. |
| Actual remote buttons | Reading `ui/index.html` exposed missing Input/channel mappings and Settings mapped to Input. RED committed `62b9e30`. | Actual numeric keycodes now reach supported semantic LG commands. |
| Client | Senior owner recorded missing-module RED, followed by malformed frame/certificate/optional-info/pointer behavior RED cases. | QA independently ran 25 protocol tests successfully. |
| Home bundle/model | Home owner recorded missing-module RED before implementation, then target-device and schema regression cases. | QA independently ran 8 bundle/deploy tests and 6 Node model tests successfully. |
| Manager UI | UI owner recorded missing platform-helper RED; current-theme load failure regression reproduced rejected promise before correction. | QA independently ran 4 platform-helper tests and actual Manager DOM smoke successfully. |

The initial unmodified Python run discovered 56 tests with 6 import errors caused
by missing `adb_shell`; the remaining tests passed. Dependencies were installed
before subsequent verification. The original Node suite passed 10/10 at baseline.

## Independent review findings addressed

- LG operations are dispatched by saved platform; port numbers do not identify OS.
- Unsupported package mutations, shell, screenshot, default-Home operations and
  Guard fail before obtaining an Android connection. UI hides unsupported controls.
- Client registration persists credentials only after a valid `registered` response;
  certificates are pinned on first approved pairing. Changed certificates fail before
  sending the stored client key; malformed responses and timeouts are typed errors.
- Optional metadata denial on newer firmware does not undo successful pairing.
- Pointer sockets must remain on the same TV host with approved local service ports;
  malformed port or external-host redirects are rejected.
- Missing app icons do not remove launchable apps. SmartTube is not relabeled YouTube.
- Theme bundles use the project's four catalog profiles and canonical widget switches,
  reject assets outside the selected theme, and do not modify the source catalog.
- Deployment verifies the configured CLI target matches the selected TV before install;
  CLI failures/timeouts never produce a successful apply or overwrite saved theme state.
- Manager shows LG TCP reachability as an open port rather than falsely claiming
  authorization, and labels local theme records as unverified on the TV.
- Read failures in the LG current-theme panel show an error rather than an unhandled
  promise rejection. Returning from LG to Android restores normal Android controls.

## Reproducible automated checks

```bash
python -m unittest discover -s tests -v
python -m unittest discover -s tv-guard/tools -p 'test_*.py' -v
node --test tests/*.test.mjs
NODE_PATH=/path/to/jsdom/node_modules node tests/lg_webos_ui_smoke.js
```

The Manager smoke uses jsdom 24 and a controlled pywebview API. It verifies saved LG
selection, UI gates, launch-only app rows, canonical-catalog apply and failure polling,
HDMI selection, current-state read errors and return to Android. It is a DOM behavior
test, not a rendered image comparison.

Final full-suite counts and visual evidence will be recorded below after integration.

## Hardware and release acceptance still required

- First pairing/rejection/key reuse on actual target LG firmware; certificate changes
  after firmware update and explicit WS port 3000 on older TVs.
- Native remote/Magic Remote behavior, text input in target apps, app launching and
  HDMI switching; sleep/reconnect and power-off response behavior.
- Developer Mode account/key setup, real `ares` packaging/install/launch, target-host
  verification, session expiry and recovery. Windows/macOS distribution builds and
  npm CLI shim behavior must be exercised on their target OS.
- Real-TV rendering of all four themes and every widget toggle, including font metrics,
  clipping/overscan, snapshot data freshness and low-memory performance.

Home deployment is an explicit snapshot/reinstall workflow. Automatic data refresh,
system-default Home replacement and an always-on external Home watcher are not
delivered. Root access, Android APK/debloat/Guard support on LG and universal firmware
compatibility are not claimed.

## Final integration results (PM verification)

- Python discovery: **147 passed**, 49.844 seconds; includes 16 API/storage/job,
  25 client and 10 Home bundle/deployment tests.
- TV Guard CLI Python regression: **5 passed**.
- Repository JavaScript runner: **21 passed** (existing 10 + platform 4 + Home 7).
- Actual Manager DOM: LG smoke passed; Android Guard smoke **44 assertions passed**.
  The Guard harness now supplies jsdom's missing scrollIntoView method explicitly.
- Chromium 153 rendered all four profiles with empty snapshots and populated QA
  fixtures. Browser checks cover date/quote/lunar-header collisions, card bounds,
  card-content clipping, keyboard input, and browser exceptions. All passed after
  fixing Aurora date/quote overlap and compact weather/calendar card overflow.
- Real official `@webos-tools/cli` **3.2.6** successfully produced
  `com.smtvmanager.home_1.0.0_all.ipk` from the generated Home bundle. No TV install
  was performed. Install/launch behavior was tested with controlled CLI fakes.
- Windows npm `.cmd` shims resolve to the official CLI JavaScript entrypoint and
  run through Node with argv; no batch-shell interpolation of device names/paths.
  Both missing-tool and metacharacter/space argument tests passed. Real Windows
  and macOS installers still require target-OS build verification.
- New shared display-name regression was observed RED (missing greeting_name),
  then fixed by applying the shared launcher config patch to a deep copy of the
  catalog theme. Source theme immutability is asserted.
- `compileall`, JavaScript syntax checks and `git diff --check` passed.

### Reproduce browser QA

Install development dependencies `playwright` and an appropriate Chromium build,
then build separate empty and populated fixture bundles (fresh destinations):

```bash
python scripts/build_webos_qa_bundles.py /tmp/lg-empty
python scripts/build_webos_qa_bundles.py /tmp/lg-fixtures --fixtures
HOME_BUNDLE_ROOT=/tmp/lg-empty node tests/webos_home_render_smoke.js
HOME_BUNDLE_ROOT=/tmp/lg-fixtures node tests/webos_home_render_smoke.js
```

Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` if using a system/local browser and
`HOME_SCREENSHOT_ROOT` to an existing output directory for screenshots.
Synthetic weather/price values exist only in the QA builder, never the production
Home bundle builder or the theme catalog. Browser checks are not real-TV QA.


## Publication

Repository write access was initially rejected with HTTP403. After authorization
was updated, the branch and PR were published via the GitHub API. The large QA
image montage is retained in the local Git bundle and omitted from this PR.
No real-TV, target-OS installation or merge/release is claimed.
