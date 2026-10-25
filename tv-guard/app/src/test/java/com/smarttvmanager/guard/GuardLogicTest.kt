package com.smarttvmanager.guard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

class GuardLogicTest {
    private val zone = ZoneId.of("Asia/Ho_Chi_Minh")

    // day is the ISO weekday (1 = Monday); 2026-10-26 is a Monday.
    private fun at(day: Int, hour: Int, minute: Int): ZonedDateTime =
        ZonedDateTime.of(LocalDate.of(2026, 10, 26).plusDays(day - 1L), LocalTime.of(hour, minute), zone)

    private val night = Schedule(setOf(1, 2, 3, 4, 5, 6, 7), Policy.parseHm("21:00"), Policy.parseHm("06:30"))
    private val afternoon = Schedule(setOf(1), Policy.parseHm("14:00"), Policy.parseHm("16:00"))

    @Test
    fun sameDayWindowIsHalfOpen() {
        val p = Policy(schedules = listOf(afternoon))
        assertFalse(GuardLogic.inLockWindow(p, at(1, 13, 59)))
        assertTrue(GuardLogic.inLockWindow(p, at(1, 14, 0)))
        assertTrue(GuardLogic.inLockWindow(p, at(1, 15, 59)))
        assertFalse(GuardLogic.inLockWindow(p, at(1, 16, 0)))
    }

    @Test
    fun windowOnlyAppliesOnListedDays() {
        val p = Policy(schedules = listOf(afternoon))
        assertFalse(GuardLogic.inLockWindow(p, at(2, 15, 0))) // Tuesday
    }

    @Test
    fun overnightWindowCoversBothSidesOfMidnight() {
        val p = Policy(schedules = listOf(night))
        assertTrue(GuardLogic.inLockWindow(p, at(1, 21, 0)))
        assertTrue(GuardLogic.inLockWindow(p, at(2, 0, 30)))
        assertTrue(GuardLogic.inLockWindow(p, at(2, 6, 29)))
        assertFalse(GuardLogic.inLockWindow(p, at(2, 6, 30)))
        assertFalse(GuardLogic.inLockWindow(p, at(2, 12, 0)))
    }

    @Test
    fun overnightWindowBelongsToTheStartDay() {
        // Friday night only: Saturday 01:00 is locked, Friday 01:00 (from Thursday) is not.
        val fridayNight = Schedule(setOf(5), Policy.parseHm("22:00"), Policy.parseHm("06:00"))
        val p = Policy(schedules = listOf(fridayNight))
        assertTrue(GuardLogic.inLockWindow(p, at(6, 1, 0))) // Saturday
        assertFalse(GuardLogic.inLockWindow(p, at(5, 1, 0))) // Friday morning
    }

    @Test
    fun sundayToMondayWrapsTheWeek() {
        val sundayNight = Schedule(setOf(7), Policy.parseHm("22:00"), Policy.parseHm("06:00"))
        val p = Policy(schedules = listOf(sundayNight))
        assertTrue(GuardLogic.inLockWindow(p, at(1, 1, 0))) // Monday 01:00
    }

    private val state = RuntimeState(pinSet = true)

    @Test
    fun failsOpenWithoutPolicyOrPin() {
        val now = at(1, 22, 0)
        val ms = now.toInstant().toEpochMilli()
        val p = Policy(schedules = listOf(night))
        assertEquals(Decision.ALLOW, GuardLogic.decide(null, state, "com.x", now, ms))
        assertEquals(
            Decision.ALLOW,
            GuardLogic.decide(p, RuntimeState(pinSet = false), "com.x", now, ms),
        )
    }

    @Test
    fun allModeLocksEverythingInWindow() {
        val now = at(1, 22, 0)
        val ms = now.toInstant().toEpochMilli()
        val p = Policy(mode = LockMode.ALL, schedules = listOf(night))
        assertEquals(Decision.LOCK, GuardLogic.decide(p, state, "com.google.android.youtube.tv", now, ms))
        assertEquals(Decision.LOCK, GuardLogic.decide(p, state, null, now, ms))
    }

    @Test
    fun appsModeLocksOnlyListedPackages() {
        val now = at(1, 22, 0)
        val ms = now.toInstant().toEpochMilli()
        val p = Policy(
            mode = LockMode.APPS,
            apps = setOf("com.google.android.youtube.tv"),
            schedules = listOf(night),
        )
        assertEquals(Decision.LOCK, GuardLogic.decide(p, state, "com.google.android.youtube.tv", now, ms))
        assertEquals(Decision.ALLOW, GuardLogic.decide(p, state, "com.example.learning", now, ms))
        assertEquals(Decision.ALLOW, GuardLogic.decide(p, state, null, now, ms))
    }

    @Test
    fun outsideWindowAllowsEverythingExceptGuardedPackages() {
        val now = at(1, 12, 0)
        val ms = now.toInstant().toEpochMilli()
        val p = Policy(mode = LockMode.ALL, schedules = listOf(night))
        assertEquals(Decision.ALLOW, GuardLogic.decide(p, state, "com.google.android.youtube.tv", now, ms))
        assertEquals(Decision.LOCK, GuardLogic.decide(p, state, "com.android.tv.settings", now, ms))
    }

    @Test
    fun correctPinUnlocksUntilExpiry() {
        val now = at(1, 22, 0)
        val ms = now.toInstant().toEpochMilli()
        val p = Policy(mode = LockMode.ALL, schedules = listOf(night))
        val unlocked = RuntimeState(unlockedUntilMs = ms + 60_000, pinSet = true)
        assertEquals(Decision.ALLOW, GuardLogic.decide(p, unlocked, "com.x", now, ms))
        assertEquals(Decision.ALLOW, GuardLogic.decide(p, unlocked, "com.android.tv.settings", now, ms))
        assertEquals(Decision.LOCK, GuardLogic.decide(p, unlocked, "com.x", now, ms + 61_000))
    }

    @Test
    fun manualLockExpiresOnItsOwn() {
        val now = at(1, 12, 0)
        val ms = now.toInstant().toEpochMilli()
        val p = Policy(mode = LockMode.ALL)
        val s = RuntimeState(manualLockUntilMs = ms + 10 * 60_000, pinSet = true)
        assertEquals(Decision.LOCK, GuardLogic.decide(p, s, "com.x", now, ms))
        assertEquals(Decision.ALLOW, GuardLogic.decide(p, s, "com.x", now, ms + 11 * 60_000))
    }

    @Test
    fun policyJsonRoundTrips() {
        val p = Policy(
            mode = LockMode.APPS,
            apps = setOf("b.app", "a.app"),
            schedules = listOf(night, afternoon),
            failsafeHours = 6,
            unlockMinutes = 15,
            zoneId = "Asia/Ho_Chi_Minh",
        )
        assertEquals(p, Policy.fromJson(p.toJson()))
    }

    @Test(expected = IllegalArgumentException::class)
    fun policyRejectsEmptyWindow() {
        Policy.fromJson(
            """{"mode":"all","schedules":[{"days":[1],"start":"10:00","end":"10:00"}]}""",
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun policyRejectsBadDay() {
        Policy.fromJson(
            """{"mode":"all","schedules":[{"days":[8],"start":"10:00","end":"11:00"}]}""",
        )
    }

    @Test
    fun explainNamesTheDecidingRule() {
        val p = Policy(mode = LockMode.ALL, schedules = listOf(afternoon)) // Monday 14:00-16:00
        fun reason(day: Int, h: Int, m: Int, st: RuntimeState = state, fg: String? = "com.x", pol: Policy? = p): Reason {
            val z = at(day, h, m)
            return GuardLogic.explain(pol, st, fg, z, z.toInstant().toEpochMilli())
        }
        assertEquals(Reason.NO_POLICY, reason(1, 15, 0, pol = null))
        assertEquals(Reason.NO_PIN, reason(1, 15, 0, st = RuntimeState(pinSet = false)))
        assertEquals(Reason.LOCKED_WINDOW, reason(1, 15, 0))
        assertEquals(Reason.OUTSIDE_WINDOW, reason(1, 17, 0))
        assertEquals(Reason.WRONG_DAY, reason(2, 15, 0)) // right time, but Tuesday is not selected
        assertEquals(Reason.GUARDED_APP, reason(1, 17, 0, fg = "com.android.tv.settings"))
        val z = at(1, 15, 0)
        val ms = z.toInstant().toEpochMilli()
        assertEquals(
            Reason.UNLOCKED_BY_PIN,
            GuardLogic.explain(p, RuntimeState(unlockedUntilMs = ms + 1000, pinSet = true), "com.x", z, ms),
        )
        val evening = at(1, 17, 0) // outside the window, so only the manual lock can explain a lock
        val eveningMs = evening.toInstant().toEpochMilli()
        assertEquals(
            Reason.LOCKED_MANUAL,
            GuardLogic.explain(p, RuntimeState(manualLockUntilMs = eveningMs + 1000, pinSet = true), "com.x", evening, eveningMs),
        )
    }

    @Test
    fun explainAgreesWithDecide() {
        val policies = listOf(
            Policy(mode = LockMode.ALL, schedules = listOf(night)),
            Policy(mode = LockMode.APPS, apps = setOf("com.yt"), schedules = listOf(afternoon, night)),
        )
        val locking = setOf(Reason.GUARDED_APP, Reason.LOCKED_MANUAL, Reason.LOCKED_WINDOW)
        for (p in policies) for (day in 1..7) for (h in listOf(0, 7, 12, 15, 21, 23)) {
            for (fg in listOf(null, "com.yt", "com.other", "com.android.settings")) {
                for (st in listOf(state, RuntimeState(pinSet = true, unlockedUntilMs = Long.MAX_VALUE),
                    RuntimeState(pinSet = true, manualLockUntilMs = Long.MAX_VALUE))) {
                    val z = at(day, h, 30)
                    val ms = z.toInstant().toEpochMilli()
                    val d = GuardLogic.decide(p, st, fg, z, ms)
                    val r = GuardLogic.explain(p, st, fg, z, ms)
                    assertEquals("$day $h $fg $st", d == Decision.LOCK, r in locking)
                }
            }
        }
    }
}
