package com.smarttvmanager.guard

import android.app.Activity
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Base64

/**
 * Control channel, used as:
 *
 *   adb shell am broadcast -n com.smarttvmanager.guard/.CommandReceiver \
 *       -a com.smarttvmanager.guard.CMD --es cmd <name> --es seq <epoch ms> \
 *       --es payload <urlsafe base64> --es sig <hex hmac>
 *
 * Commands: provision, ping, status, set_policy, set_pin, lock_now, unlock_now, clear_policy.
 * Payloads are URL-safe base64 so they need no shell quoting.
 */
class CommandReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val store = PolicyStore(context)
        val cmd = intent.getStringExtra("cmd").orEmpty()
        val result = try {
            handle(context, store, intent, cmd)
        } catch (e: Exception) {
            "error:${e.message}"
        }
        store.lastCommand = "$cmd -> $result @ ${System.currentTimeMillis()}"
        // Only visible to `am broadcast` when the broadcast is ordered, which is its default.
        setResult(Activity.RESULT_OK, result, null)
        GuardService.instance?.evaluate()
    }

    private fun handle(context: Context, store: PolicyStore, intent: Intent, cmd: String): String {
        if (cmd.isEmpty()) return "error:no_cmd"
        val payload = intent.getStringExtra("payload").orEmpty()
        val now = System.currentTimeMillis()

        if (cmd == "provision") return provision(context, store, payload, now)

        val secret = store.secret ?: return "error:not_provisioned"
        val seq = intent.getStringExtra("seq")?.toLongOrNull() ?: return "error:bad_seq"
        val sig = intent.getStringExtra("sig").orEmpty()
        if (!CommandAuth.verify(secret, cmd, seq, payload, sig, store.lastSeq, now)) {
            return "error:auth"
        }
        store.lastSeq = seq

        val text = if (payload.isEmpty()) "" else decode(payload)
        return when (cmd) {
            "ping" -> "ok:pong"
            "status" -> {
                // One line of compact JSON: `am broadcast` prints it as data="ok:{...}".
                val snap = GuardService.instance?.currentSnapshot() ?: StatusWriter.offlineSnapshot(store)
                "ok:" + StatusWriter.toJson(snap).toString()
            }
            "set_policy" -> {
                val policy = Policy.fromJson(text) // validates before anything is stored
                store.policyJson = policy.toJson()
                "ok"
            }
            "set_pin" -> {
                if (!PinHasher.isWellFormed(text)) return "error:bad_pin_hash"
                store.pinHash = text
                store.failedAttempts = 0
                store.lockoutUntilMs = 0L
                "ok"
            }
            "lock_now" -> {
                val policy = store.loadPolicy() ?: return "error:no_policy"
                val cap = policy.failsafeHours * 60L
                val minutes = (text.trim().toLongOrNull() ?: return "error:bad_minutes").coerceIn(1L, cap)
                store.manualLockUntilMs = now + minutes * 60_000L
                store.unlockedUntilMs = 0L
                "ok:until=${store.manualLockUntilMs}"
            }
            "unlock_now" -> {
                val minutes = text.trim().toLongOrNull() ?: 0L
                store.manualLockUntilMs = 0L
                store.unlockedUntilMs = if (minutes > 0) now + minutes.coerceAtMost(720L) * 60_000L else 0L
                "ok"
            }
            "clear_policy" -> {
                store.policyJson = null
                store.manualLockUntilMs = 0L
                store.unlockedUntilMs = 0L
                "ok"
            }
            else -> "error:unknown_cmd"
        }
    }

    /**
     * First-time key exchange. The secret can only be set once, and only shortly after install,
     * so another app cannot claim the channel later. Trust-on-first-use is a known limitation of
     * this spike; the README lists it.
     */
    private fun provision(context: Context, store: PolicyStore, payload: String, now: Long): String {
        if (store.secret != null) return "error:already_provisioned"
        val installedAt = context.packageManager.getPackageInfo(context.packageName, 0).firstInstallTime
        if (now - installedAt > PROVISION_WINDOW_MS) return "error:provision_window_closed"
        val secret = Base64.decode(payload, Base64.URL_SAFE)
        if (secret.size < 16) return "error:secret_too_short"
        store.secret = secret
        return "ok"
    }

    private fun decode(payload: String): String =
        String(Base64.decode(payload, Base64.URL_SAFE), Charsets.UTF_8)

    companion object {
        private const val PROVISION_WINDOW_MS = 15 * 60 * 1000L
    }
}
