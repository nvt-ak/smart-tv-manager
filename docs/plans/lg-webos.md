# LG webOS implementation plan

Status: PM approved for implementation after team research, 2026-10-28.
Base: fec103a; branch: feat/lg-webos-support. PM owns integration, senior webOS owns
protocol, Home engineer owns renderer/deployment, UI engineer owns Manager UX, QA owns
independent acceptance/regression review. User reviews the final PR; no merge/release.

## Scope and constraints

Support LG consumer webOS from the existing desktop Manager: explicit IP pairing,
remote/text, installed-app launching, HDMI selection, and installation of our branded
Home web app using the existing smart-tv-manager theme catalog and widget settings.
webos-vibehack is platform research only: no replacement catalog or borrowed UI.
No APK, debloat, Android shell, Android screenshot or TV Guard support on LG.
No claim that a web app becomes the system default launcher. Developer Mode setup and
session renewal remain explicit. Theme/widget apply initially packages a snapshot and
redeploys; this is not background/live widget refresh. Hardware checks remain required.

## Use cases, acceptance criteria and task ownership

| ID | Use case / acceptance | Tasks / owner | Validation |
| --- | --- | --- | --- |
| LG01 | Existing devices remain Android with port 5555; new LG has platform lg_webos and port 3001 | Normalize/store platform, preserve metadata and per-TV state; PM | Migration and multi-TV tests |
| LG02 | Pair by IP with TV approval, persist key only after registration; actionable failure | Minimal unsigned manifest, bounded WSS requests, keyed credentials, atomic save, reconnect; senior | Fake transport registration/rejection/timeout/correlation/error tests |
| LG03 | Remote, text, app launch and HDMI use LG protocol, never ADB | Semantic commands and compatibility mapping; app/input adapters; PM + senior | Dispatch tests with ADB mocked to fail |
| LG04 | LG exposes only supported controls in UI and backend | Platform selector, identity, tabs/action capability gating; PM + UI | Capability tests and UI smoke |
| LG05 | Home uses the existing theme catalog and show_* switches | Bundle config/assets/widget snapshot and app mappings; Home engineer | All four bundled profiles, flags, path safety, missing icons tests |
| LG06 | Home renders dashboard profiles and remote/pointer focus | Implement aurora/hanoi/hanoi2/hanoi3 from smtv-home design, native cards and settings; Home engineer | JS behavior tests and rendered screenshots |
| LG07 | Apply packages/installs/launches Home via configured webOS CLI device | Safe argv, timeouts, CLI error handling, cleanup; success state after completion; Home + PM + UI | Fake CLI failures and apply integration tests |
| LG08 | Home redirect is optional and depends on an awake external host | Document quick-access alternative and optional watcher contract; senior | If delivered: subscribe/escape/reconnect tests; otherwise explicitly deferred |
| LG09 | Android operation remains unchanged | Run existing Python/JS suites, check packaging resources/dependencies; QA + PM | Baseline comparison, regression and build-input inspection |
| LG10 | Reviewable delivery | Vietnamese changelog, setup guide, task evidence, branch commits and PR; PM | QA report, git diff check, remote PR |

## Contracts

- Existing API signatures stay backward compatible. connect adds optional platform;
  stored device platform controls dispatch, rather than assuming a port identifies OS.
- core.webos_client.WebOsClient: connect, close, info, list_apps, list_inputs,
  launch_app, switch_input, remote_key, send_text; typed errors; dependency injection.
- core.webos_home.build_bundle(theme, destination, apps, inputs, widget_data,
  widget_switches): runtime schema version 1, no secrets in bundle.
- Runtime SMARTTV_HOME: schema_version, theme_id, config, widgets, apps, inputs,
  wallpapers, data_updated_at. Existing theme config is authoritative.
- core.webos_home.deploy(bundle_path, device_name): bounded CLI argv; explicit snapshot.
- Unsupported platform operations fail before acquiring an Android connection.

## TDD sequence and review gates

1. Research + this complete use-case/task breakdown precede production changes.
2. Each owner writes behavior tests first, runs and records RED (missing module/behavior).
3. Implement the smallest working behavior; run GREEN and refactor without changing contracts.
4. QA independently checks failure paths, platform isolation, theme fidelity and regression.
5. Integrate and fix findings; record commands/results and unverified hardware cases.
6. Push branch and open PR for the user; never merge automatically.

## Hardware acceptance (cannot be replaced by mocks)

- First pairing, rejected pairing and reuse after app/TV restart on target firmware.
- Native remote + Magic Remote, text fields, app launch and HDMI switching.
- Developer Mode key setup, package install and session expiry/recovery.
- Compare every theme and widget toggle on a real screen; verify no overlapping cards.
- Standby/reconnect and external-host sleep behavior; no universal compatibility claim.

## Implementation status

- LG01–LG07: implemented and covered by automated tests. See [QA evidence](lg-webos-qa.md).
- LG08: external Home watcher deferred; Quick Access and system-Home limitations documented.
- LG09: automated Android regression passed; hardware and target-OS builds remain open.
- LG10: local branch/commits, documentation and PR body prepared; remote branch/PR
  blocked by GitHub integration HTTP 403 (write permission unavailable).
- Release gate: real LG TV and macOS/Windows acceptance remain mandatory before a
  compatibility/release claim. No automatic merge or publication.
