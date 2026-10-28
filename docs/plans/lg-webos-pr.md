# feat: add LG webOS control and SmartTV Home theme support

Base: master. Head: feat/lg-webos-support.

LG TVs can now be added alongside Android TVs in SmartTV Manager. The Manager pairs
through LG's second-screen protocol for remote/text, app launching and HDMI input
selection, while Android-only tools are gated in both the UI and backend.

The new webOS Home app uses the existing SmartTV Manager catalog, four dashboard
profiles, wallpapers, shared widget sources and per-theme widget switches. Apply
builds a data snapshot, verifies the configured webOS CLI profile targets the
selected TV, then packages, installs and launches Home. Failed deployment never
updates the recorded theme. LG-specific app mapping does not relabel SmartTube as
YouTube; missing icons retain launchable fallback tiles.

Implementation follows the use-case/task plan committed before product changes,
with RED→GREEN tests, independent QA and subsequent integration fixes. See
`docs/plans/lg-webos.md`, `docs/plans/lg-webos-qa.md` and `docs/lg-webos.md`.

Validation: 147 Python regression tests, 5 Guard CLI tests, 21 JavaScript behavior
tests, LG Manager DOM smoke and 44 Android Guard DOM assertions passed. Chromium
checks passed for all four profiles with empty and populated QA snapshots. The
real official webOS CLI 3.2.6 successfully packaged the Home app as `.ipk`.

Limitations: no real LG TV installation/firmware validation, no target-OS installer
builds yet. Home data is an explicit snapshot refreshed by Apply; Developer Mode
must be configured and maintained. This does not replace system Home, provide an
always-on watcher, or implement Android APK/debloat/Guard behavior on LG. App icons
currently use text fallback tiles. Review hardware acceptance before release.
