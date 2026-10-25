package com.smarttvmanager.guard

import android.content.Context
import android.util.Base64

/** Everything the guard must remember across reboots, kept in app-private SharedPreferences. */
class PolicyStore(context: Context) {
    private val prefs = context.applicationContext
        .getSharedPreferences("guard", Context.MODE_PRIVATE)

    var policyJson: String?
        get() = prefs.getString("policy", null)
        set(v) = prefs.edit().putString("policy", v).apply()

    var pinHash: String?
        get() = prefs.getString("pin_hash", null)
        set(v) = prefs.edit().putString("pin_hash", v).apply()

    /** HMAC secret shared with the desktop app, URL-safe base64. */
    var secret: ByteArray?
        get() = prefs.getString("secret", null)?.let { Base64.decode(it, Base64.URL_SAFE) }
        set(v) = prefs.edit().putString(
            "secret",
            v?.let { Base64.encodeToString(it, Base64.URL_SAFE or Base64.NO_WRAP) },
        ).apply()

    var lastSeq: Long
        get() = prefs.getLong("last_seq", 0L)
        set(v) = prefs.edit().putLong("last_seq", v).apply()

    var manualLockUntilMs: Long
        get() = prefs.getLong("manual_lock_until", 0L)
        set(v) = prefs.edit().putLong("manual_lock_until", v).apply()

    var unlockedUntilMs: Long
        get() = prefs.getLong("unlocked_until", 0L)
        set(v) = prefs.edit().putLong("unlocked_until", v).apply()

    var failedAttempts: Int
        get() = prefs.getInt("failed_attempts", 0)
        set(v) = prefs.edit().putInt("failed_attempts", v).apply()

    var lockoutUntilMs: Long
        get() = prefs.getLong("lockout_until", 0L)
        set(v) = prefs.edit().putLong("lockout_until", v).apply()

    var bootCount: Int
        get() = prefs.getInt("boot_count", 0)
        set(v) = prefs.edit().putInt("boot_count", v).apply()

    var lastCommand: String?
        get() = prefs.getString("last_command", null)
        set(v) = prefs.edit().putString("last_command", v).apply()

    val hasPin: Boolean get() = !pinHash.isNullOrEmpty()

    fun loadPolicy(): Policy? = try {
        policyJson?.let { Policy.fromJson(it) }
    } catch (e: Exception) {
        null
    }

    fun runtimeState() = RuntimeState(
        manualLockUntilMs = manualLockUntilMs,
        unlockedUntilMs = unlockedUntilMs,
        pinSet = hasPin,
    )
}
