package com.smarttvmanager.guard

import java.time.ZonedDateTime

enum class Decision { ALLOW, LOCK }

/** Why [GuardLogic.decide] answered the way it did. Shown to the parent in the desktop app. */
enum class Reason {
    NO_POLICY, NO_PIN, UNLOCKED_BY_PIN, GUARDED_APP, LOCKED_MANUAL, LOCKED_WINDOW,
    APP_NOT_LISTED, WRONG_DAY, OUTSIDE_WINDOW,
}

/** Mutable runtime state that is not part of the policy itself. */
data class RuntimeState(
    val manualLockUntilMs: Long = 0L,
    val unlockedUntilMs: Long = 0L,
    val pinSet: Boolean = false,
)

/**
 * Pure decision logic: no Android classes, so it can be unit tested on the JVM.
 */
object GuardLogic {

    /**
     * Packages that always need the parent PIN, even outside lock windows. Without this a child
     * could open Settings, switch the accessibility service off and bypass everything.
     */
    val ALWAYS_PIN: Set<String> = setOf(
        "com.android.settings",
        "com.android.tv.settings",
        "com.android.vending",
        "com.google.android.packageinstaller",
        "com.android.packageinstaller",
    )

    /** System surfaces that must never change the "current foreground app". */
    val IGNORED: Set<String> = setOf(
        "android",
        "com.android.systemui",
    )

    fun inLockWindow(policy: Policy, now: ZonedDateTime): Boolean {
        val minute = now.hour * 60 + now.minute
        val today = now.dayOfWeek.value
        val yesterday = if (today == 1) 7 else today - 1
        for (s in policy.schedules) {
            if (s.startMin < s.endMin) {
                if (today in s.days && minute >= s.startMin && minute < s.endMin) return true
            } else {
                // Crosses midnight: the evening part belongs to the start day, the morning part
                // to the day after it.
                if (today in s.days && minute >= s.startMin) return true
                if (yesterday in s.days && minute < s.endMin) return true
            }
        }
        return false
    }

    /**
     * Decide whether the overlay must be shown.
     *
     * Fail-open on purpose: with no policy or no PIN the guard never locks, because a lock that
     * cannot be dismissed would leave the family stuck until the failsafe expires.
     */
    fun decide(
        policy: Policy?,
        state: RuntimeState,
        foreground: String?,
        now: ZonedDateTime,
        nowMs: Long,
    ): Decision {
        if (policy == null || !state.pinSet) return Decision.ALLOW
        if (nowMs < state.unlockedUntilMs) return Decision.ALLOW

        if (foreground != null && foreground in ALWAYS_PIN) return Decision.LOCK

        val locked = nowMs < state.manualLockUntilMs || inLockWindow(policy, now)
        if (!locked) return Decision.ALLOW

        return when (policy.mode) {
            LockMode.ALL -> Decision.LOCK
            LockMode.APPS ->
                if (foreground != null && foreground in policy.apps) Decision.LOCK else Decision.ALLOW
        }
    }

    /** True when [minute] lies inside the time range of any window, ignoring which days it applies to. */
    private fun inTimeRangeOfAnyDay(policy: Policy, minute: Int): Boolean = policy.schedules.any {
        if (it.startMin < it.endMin) minute >= it.startMin && minute < it.endMin
        else minute >= it.startMin || minute < it.endMin
    }

    /** Mirrors [decide] step by step and names the deciding rule. Keep both in sync (see tests). */
    fun explain(
        policy: Policy?,
        state: RuntimeState,
        foreground: String?,
        now: ZonedDateTime,
        nowMs: Long,
    ): Reason {
        if (policy == null) return Reason.NO_POLICY
        if (!state.pinSet) return Reason.NO_PIN
        if (nowMs < state.unlockedUntilMs) return Reason.UNLOCKED_BY_PIN
        if (foreground != null && foreground in ALWAYS_PIN) return Reason.GUARDED_APP

        val manual = nowMs < state.manualLockUntilMs
        val inWindow = inLockWindow(policy, now)
        if (!manual && !inWindow) {
            return if (inTimeRangeOfAnyDay(policy, now.hour * 60 + now.minute)) {
                Reason.WRONG_DAY
            } else {
                Reason.OUTSIDE_WINDOW
            }
        }
        if (policy.mode == LockMode.APPS && (foreground == null || foreground !in policy.apps)) {
            return Reason.APP_NOT_LISTED
        }
        return if (manual) Reason.LOCKED_MANUAL else Reason.LOCKED_WINDOW
    }
}
