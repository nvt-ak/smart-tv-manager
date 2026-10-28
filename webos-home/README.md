# SmartTV Home for LG webOS

This is SmartTV Manager's webOS renderer, not a copy of webos-vibehack's UI.
`core/webos_home.py` builds a snapshot from the existing catalog and its widget
switches. It copies the selected wallpaper collection, app fonts and brand icon.

## Runtime and platform contracts

`runtime.js` and `runtime.json` are generated, not committed credentials. Schema 1:
`theme_id`, `config`, `widgets`, `apps`, `inputs`, `wallpapers`, `data_updated_at`.
The widget snapshot is the unmodified `core.home_widgets.widgets_data()` format.
Missing values show an unavailable message; network/API failures never invent data.
The clock updates locally; prices/weather/lunar data refresh only when redeployed.

Dashboard geometry uses the project's own `nvt-ak/smtv-home` DesignFrame.java
(2000 × 1125 frame): Aurora bottom dock and three cards; Hanoi left sidebar and
three cards; Hanoi2 left sidebar and right stacked cards; Hanoi3 right sidebar and
left weather/market/calendar cards. HTML/CSS is a native webOS port and still needs
real-TV visual comparison before claiming exact parity with the Android renderer.
All canonical `theme_widgets.py` show_* controls are applied to the snapshot.
App IDs are mapped only when the semantic LG equivalent is installed. SmartTube is
not silently replaced by YouTube. Apps without icons remain usable with initials.

D-pad/OK and Magic Remote click select applications. Back closes the app/input
library. App launch uses PalmServiceBridge. The app does not replace system Home,
change TV system settings, execute arbitrary commands or install Android apps.

## Install and update

Install current `@webos-tools/cli`, enable Developer Mode on the TV, configure its
SSH device profile and key. Manager checks `ares-setup-device --listfull` against
the selected TV host before applying. Profile names must identify the intended TV.
The native ares-package/install/launch executables must be on PATH.
Developer Mode session expiry remains the TV owner's responsibility.

Every Apply builds a fresh directory and executes ares-package, ares-install and
then ares-launch with argv arrays and bounded timeouts. No success is returned
when any command fails. The bundled runtime includes a snapshot update notice.
No background daemon or external Home redirect is included in this implementation.

## Validation

Python: `python -m unittest discover -s tests -p test_webos_home.py`.
JavaScript: `node --test tests/webos_home_model.test.mjs`.
Manual TV checks: all four profiles, each widget toggle, app/input launch, pointer,
D-pad, Back, install/reinstall, Developer Mode expiry and missing network data.
