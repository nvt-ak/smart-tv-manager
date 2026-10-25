package com.smarttvmanager.guard

import android.accessibilityservice.AccessibilityService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.util.concurrent.Executors

/**
 * Enforcement service. It never reads screen content (canRetrieveWindowContent = false); it
 * only learns which package owns the foreground window.
 *
 * G0 limits: re-evaluation is driven by window events plus a coarse timer. G1 should add
 * AlarmManager so a window start fires exactly on time even if the handler is throttled.
 */
class GuardService : AccessibilityService() {

    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private lateinit var store: PolicyStore
    private var overlay: OverlayController? = null

    private var foreground: String? = null
    private var lastDecision = Decision.ALLOW

    /** Last failure while drawing/removing the overlay; surfaced in status so it is never silent. */
    private var overlayError: String? = null

    private val tick = object : Runnable {
        override fun run() {
            evaluateNow()
            main.postDelayed(this, TICK_MS)
        }
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        store = PolicyStore(this)
        overlay = OverlayController(this, ::onPinSubmitted)
        main.post(tick)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        if (event == null || event.eventType != AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED) return
        val pkg = event.packageName?.toString() ?: return
        // Our own overlay also produces window events; counting them would hide the overlay.
        if (pkg == packageName || pkg in GuardLogic.IGNORED) return
        foreground = pkg
        evaluateNow()
    }

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null)
        overlay?.hide()
        worker.shutdown()
        instance = null
        StatusWriter.write(
            this,
            mapOf("running" to false, "now_ms" to System.currentTimeMillis()),
        )
        super.onDestroy()
    }

    /** Safe to call from any thread. */
    fun evaluate() {
        main.post { evaluateNow() }
    }

    private fun evaluateNow() {
        val nowMs = System.currentTimeMillis()
        val policy = store.loadPolicy()
        val zone = try {
            ZoneId.of(policy?.zoneId ?: "UTC")
        } catch (e: Exception) {
            ZoneId.systemDefault()
        }
        val now = ZonedDateTime.ofInstant(Instant.ofEpochMilli(nowMs), zone)
        val decision = GuardLogic.decide(policy, store.runtimeState(), foreground, now, nowMs)
        lastDecision = decision

        val ov = overlay
        if (ov != null) {
            try {
                if (decision == Decision.LOCK) {
                    val guardedOnly = foreground != null && foreground in GuardLogic.ALWAYS_PIN &&
                        policy != null && !isLockedByPolicy(policy, now, nowMs)
                    ov.show(if (guardedOnly) "Parent PIN required" else "Screen time is over")
                } else {
                    ov.hide()
                }
                overlayError = null
            } catch (e: Exception) {
                // An uncaught exception here would kill the service, so record it instead.
                overlayError = "${e.javaClass.simpleName}: ${e.message}"
            }
        }
        writeStatus(policy, nowMs, zone)
    }

    private fun isLockedByPolicy(policy: Policy, now: ZonedDateTime, nowMs: Long): Boolean =
        nowMs < store.manualLockUntilMs || GuardLogic.inLockWindow(policy, now)

    private fun onPinSubmitted(pin: String) {
        val nowMs = System.currentTimeMillis()
        if (nowMs < store.lockoutUntilMs) {
            val secs = (store.lockoutUntilMs - nowMs) / 1000 + 1
            overlay?.setMessage("Too many attempts. Try again in ${secs}s")
            return
        }
        val hash = store.pinHash
        // PBKDF2 is deliberately slow; keep it off the main thread.
        worker.execute {
            val ok = PinHasher.verify(hash, pin)
            main.post {
                if (ok) {
                    val minutes = (store.loadPolicy()?.unlockMinutes ?: 30).toLong()
                    store.unlockedUntilMs = System.currentTimeMillis() + minutes * 60_000L
                    store.failedAttempts = 0
                    store.lockoutUntilMs = 0L
                    overlay?.setMessage("")
                    evaluateNow()
                } else {
                    val fails = store.failedAttempts + 1
                    store.failedAttempts = fails
                    if (fails >= FREE_ATTEMPTS) {
                        // 30s, 60s, 120s ... capped at 15 minutes.
                        val shift = (fails - FREE_ATTEMPTS).coerceAtMost(5)
                        val lockSecs = (30L shl shift).coerceAtMost(900L)
                        store.lockoutUntilMs = System.currentTimeMillis() + lockSecs * 1000L
                        overlay?.setMessage("Wrong PIN. Locked for ${lockSecs}s")
                    } else {
                        overlay?.setMessage("Wrong PIN")
                    }
                }
            }
        }
    }

    private fun snapshot(policy: Policy?, nowMs: Long, zone: ZoneId): Map<String, Any?> {
        val now = ZonedDateTime.ofInstant(Instant.ofEpochMilli(nowMs), zone)
        return mapOf(
        "running" to true,
        "version" to BuildConfigLike.VERSION,
        "sdk" to Build.VERSION.SDK_INT,
        "device" to Build.MODEL,
        "now_ms" to nowMs,
        "zone" to zone.id,
        "local_time" to now.toLocalDateTime().toString(),
        "local_day" to now.dayOfWeek.value,
        "reason" to GuardLogic.explain(policy, store.runtimeState(), foreground, now, nowMs).name,
        "overlay_error" to overlayError,
        "foreground" to foreground,
        "decision" to lastDecision.name,
        "overlay_showing" to (overlay?.isShowing == true),
        "policy_loaded" to (policy != null),
        "policy" to store.policyJson?.let { runCatching { JSONObject(it) }.getOrNull() },
        "pin_set" to store.hasPin,
        "provisioned" to (store.secret != null),
        "manual_lock_until_ms" to store.manualLockUntilMs,
        "unlocked_until_ms" to store.unlockedUntilMs,
        "failed_attempts" to store.failedAttempts,
        "boot_count" to store.bootCount,
        "last_command" to store.lastCommand,
        )
    }

    private fun writeStatus(policy: Policy?, nowMs: Long, zone: ZoneId) {
        StatusWriter.write(this, snapshot(policy, nowMs, zone))
    }

    /** Used by the `status` command; safe to call from the receiver thread (reads only). */
    fun currentSnapshot(): Map<String, Any?> {
        val nowMs = System.currentTimeMillis()
        val policy = store.loadPolicy()
        val zone = try {
            ZoneId.of(policy?.zoneId ?: "UTC")
        } catch (e: Exception) {
            ZoneId.systemDefault()
        }
        return snapshot(policy, nowMs, zone)
    }

    companion object {
        @Volatile
        var instance: GuardService? = null
            private set

        private const val TICK_MS = 15_000L
        private const val FREE_ATTEMPTS = 5
    }
}
