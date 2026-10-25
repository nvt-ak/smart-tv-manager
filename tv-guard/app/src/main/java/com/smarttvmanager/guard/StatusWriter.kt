package com.smarttvmanager.guard

import android.content.Context
import org.json.JSONObject
import java.io.File

/**
 * Writes status.json to the app's external files dir so the desktop app can read it with
 * `adb pull` (no network port is opened). Path on the TV:
 * /sdcard/Android/data/com.smarttvmanager.guard/files/status.json
 */
object StatusWriter {
    fun toJson(fields: Map<String, Any?>): JSONObject {
        val o = JSONObject()
        for ((k, v) in fields) o.put(k, v ?: JSONObject.NULL)
        return o
    }

    /** What the receiver can report when the accessibility service is not running. */
    fun offlineSnapshot(store: PolicyStore): Map<String, Any?> = mapOf(
        "running" to false,
        "version" to BuildConfigLike.VERSION,
        "now_ms" to System.currentTimeMillis(),
        "policy_loaded" to (store.loadPolicy() != null),
        "policy" to store.policyJson?.let { runCatching { JSONObject(it) }.getOrNull() },
        "pin_set" to store.hasPin,
        "provisioned" to (store.secret != null),
        "manual_lock_until_ms" to store.manualLockUntilMs,
        "unlocked_until_ms" to store.unlockedUntilMs,
        "failed_attempts" to store.failedAttempts,
        "boot_count" to store.bootCount,
        "last_command" to store.lastCommand,
    )

    fun write(context: Context, fields: Map<String, Any?>) {
        try {
            val dir = context.getExternalFilesDir(null) ?: return
            val o = toJson(fields)
            val tmp = File(dir, "status.json.tmp")
            tmp.writeText(o.toString(2))
            tmp.renameTo(File(dir, "status.json"))
        } catch (e: Exception) {
            // Status is best-effort and must never break enforcement.
        }
    }
}
