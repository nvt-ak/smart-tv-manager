# TV Guard

On-TV companion app for SmartTV Manager. It enforces a screen-time schedule **on the TV itself**,
so the lock still works when the desktop app is closed or the PC is off.

Status: **G0 spike**. The goal of this version is to answer the open questions below on real
hardware (TCL Google TV and Chromecast with Google TV) before the real feature is built.

## How it works

- An **accessibility service** (`GuardService`) learns which package owns the foreground window
  (window events only; `canRetrieveWindowContent` is false, no screen content is read).
- Inside a lock window it draws a full-screen **overlay** with a D-pad PIN entry
  (`OverlayController`), pauses media and mutes the music stream.
- `com.android.settings`, the Play Store and the package installers always need the PIN, even
  outside lock windows. Otherwise a child could switch the service off in Settings.
- The schedule, the PIN hash and the state live in the app (`PolicyStore`), so nothing depends on
  adb or the desktop app after setup.
- The desktop app sends commands with `adb shell am broadcast` (`CommandReceiver`). Every command
  except `provision` carries an HMAC signature and a strictly increasing sequence number
  (`CommandAuth`). Status comes back through `status.json` (`adb pull`); no network port is opened.
- Decision logic (`GuardLogic`) is pure Kotlin and unit tested. It **fails open**: no policy or no
  PIN means no lock, so a misconfiguration can never trap the family behind an overlay.

## Layout

```
tv-guard/
  app/src/main/java/com/smarttvmanager/guard/
    Policy.kt             policy model + JSON (de)serialisation + validation
    GuardLogic.kt         schedule windows and the lock decision (pure)
    PinHasher.kt          PBKDF2 verify (hash is computed on the desktop)
    CommandAuth.kt        HMAC check for control-channel commands (pure)
    CommandReceiver.kt    adb control channel
    GuardService.kt       accessibility service, evaluation loop, PIN attempts/lockout
    OverlayController.kt  overlay + D-pad PIN entry + pause/mute
    PolicyStore.kt        persistent state
    StatusWriter.kt       status.json for the desktop app
    BootReceiver.kt       records boots
  app/src/test/...        JVM unit tests (schedule, decisions, PIN, signatures)
  tools/guard_cli.py      desktop helper: prints signed adb commands (no TV access)
  tools/policy.example.json
```

## Build

CI builds it (`.github/workflows/build-guard.yml`) and publishes `TvGuard.apk` to the rolling
release `tv-guard`. Locally you need JDK 17, the Android SDK and Gradle 8.7:

```
cd tv-guard
gradle testDebugUnitTest assembleDebug
```

Desktop helper tests: `python -m unittest discover -s tv-guard/tools`.

## Using it from SmartTV Manager

The desktop app has a **Khoá trẻ em** tab (select a TV first). One button installs TV Guard, turns on
the accessibility service, pairs, sets the PIN and the schedule, and shows each step. Afterwards the
tab shows the live state read from the TV (protected / locked / service off), lets you edit the
schedule, lock or unlock for a while, and uninstall. The code lives in `core/tv_guard.py`,
`Api.guard_*` in `main.py` and `ui/js/app.js` (section "Khoá trẻ em").

The APK is taken from `tv-guard/dist/TvGuard-debug.apk` when it exists (developer checkout), or
`SMARTTV_GUARD_APK`, otherwise downloaded from the `tv-guard` release (SHA-256 checked). The control
key for each TV is kept in `~/.smarttv-manager/guard/`. The manual steps below remain for debugging.

## Setting up a TV (manual, for debugging)

Replace `<serial>` with `192.168.x.x:5555`. Commands use only double quotes so they work in cmd,
PowerShell and bash.

```
adb connect <serial>
adb -s <serial> install -r TvGuard.apk

:: Enable the accessibility service without touching the TV UI.
adb -s <serial> shell settings put secure enabled_accessibility_services com.smarttvmanager.guard/com.smarttvmanager.guard.GuardService
adb -s <serial> shell settings put secure accessibility_enabled 1
```

Then, from `tv-guard/tools`, within 15 minutes of installing (see Known limitations). `--run`
executes adb for you without a shell, so `$` and `=` in values are never mangled (this matters in
PowerShell). Without `--run` the helper only prints the command.

```
python guard_cli.py gen-secret > guard.secret
python guard_cli.py cmd provision  --secret-file guard.secret --run --serial <serial>
python guard_cli.py cmd set_pin    --secret-file guard.secret --run --serial <serial> --pin 1234
python guard_cli.py cmd set_policy --secret-file guard.secret --run --serial <serial> --policy-file policy.example.json
python guard_cli.py cmd lock_now   --secret-file guard.secret --run --serial <serial> --text 5
```

The broadcast result shows `data="ok"` or `data="error:..."`; the helper exits non-zero on error.
Read the state with:

```
adb -s <serial> pull /sdcard/Android/data/com.smarttvmanager.guard/files/status.json
```

Emergency exits: `cmd unlock_now --text 60` (needs the secret), or
`adb -s <serial> uninstall com.smarttvmanager.guard` (always works; the adb key is already trusted).

Keep `guard.secret` private; it is the control credential.

## G0 checklist (run on every target TV)

Record pass/fail and notes for each; the answers decide what G1 looks like.

| # | Question | If it fails |
|---|----------|-------------|
| 1 | Does `pm install` + `settings put secure enabled_accessibility_services` really enable the service (check status.json `running`)? | Need a manual enable step or another mechanism |
| 2 | On Android 13+, is the service blocked by "restricted settings" when installed by adb? | Document a one-time manual allow |
| 3 | Does the overlay appear when a lock starts, over YouTube, Netflix, the launcher and Live TV? | Overlay type or flags need changing |
| 4 | **Does the overlay receive D-pad and OK key events** (PIN entry works)? | Fall back to a full-screen Activity of the app for PIN entry |
| 5 | Is the Home button handled (overlay stays on top after Home)? | Same as above |
| 6 | Does media pause and the picture/sound stay covered while locked? Is volume restored on unlock? | Handle apps that ignore media keys |
| 7 | Does an HDMI input switch produce a window event (can it be covered)? What package name? | Document that HDMI is out of scope |
| 8 | Does opening Settings trigger the PIN overlay outside lock windows? Which package names does this TV's Settings use? | Extend `GuardLogic.ALWAYS_PIN` |
| 9 | Does the service survive standby, a reboot and a power cut (status.json `boot_count`, `running`)? | Need a watchdog or battery-optimisation exemption |
| 10 | After a reboot, is adb on port 5555 still reachable? (matters for remote management) | Companion app must re-enable it, or document the limit |
| 11 | Does a lock window starting while the TV is idle fire on time (15 s timer)? | Add AlarmManager in G1 |
| 12 | Wrong PIN x5 triggers lockout; correct PIN unlocks for `unlock_minutes` | Fix `GuardService` |
| 13 | Does `set_policy` with an invalid payload leave the old policy untouched? | Fix `CommandReceiver` |

## Known limitations (G0)

- **Trust on first use.** `provision` is unsigned. It is accepted only once, and only within 15
  minutes of installation, so another app can claim the channel only inside that window. G1 should
  bind provisioning to something only the desktop can do (for example a one-time code shown on the
  TV overlay).
- The coarse 15 s timer can be late; G1 adds exact alarms.
- Only digits can be entered as PIN (4-8), because the remote is the only input.
- Not covered by design: factory reset, HDMI/console input, casting, a child who can reach adb.
- Debug-signed. Updates over adb need the same signing key, so release builds need a keystore.
- Times are evaluated in the zone stored in the policy (`tz`), not in the PC's zone.
