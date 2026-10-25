package com.smarttvmanager.guard

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

/**
 * The accessibility service restarts itself after a reboot as long as it stays enabled in
 * secure settings. This receiver only records the boot so the desktop app can see it.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return
        val store = PolicyStore(context)
        store.bootCount = store.bootCount + 1
        StatusWriter.write(
            context,
            mapOf(
                "event" to "boot_completed",
                "boot_count" to store.bootCount,
                "now_ms" to System.currentTimeMillis(),
                "device" to Build.MODEL,
            ),
        )
    }
}
