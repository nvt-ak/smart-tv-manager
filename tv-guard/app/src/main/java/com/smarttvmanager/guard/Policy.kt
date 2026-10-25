package com.smarttvmanager.guard

import org.json.JSONArray
import org.json.JSONObject

enum class LockMode {
    /** Cover the whole TV during a lock window. */
    ALL,

    /** Cover only the apps listed in [Policy.apps] during a lock window. */
    APPS,
}

/**
 * One recurring lock window.
 *
 * [days] uses ISO numbering (1 = Monday ... 7 = Sunday). A window whose end is earlier than its
 * start crosses midnight and belongs to the day it starts on.
 */
data class Schedule(val days: Set<Int>, val startMin: Int, val endMin: Int)

data class Policy(
    val mode: LockMode = LockMode.ALL,
    val apps: Set<String> = emptySet(),
    val schedules: List<Schedule> = emptyList(),
    /** Upper bound for a manual lock, so a forgotten lock always expires. */
    val failsafeHours: Int = 12,
    /** How long a correct PIN keeps the TV unlocked. */
    val unlockMinutes: Int = 30,
    /** IANA zone the schedule is evaluated in (the TV's own zone, not the controlling PC's). */
    val zoneId: String = "UTC",
) {
    fun toJson(): String {
        val o = JSONObject()
        o.put("version", 1)
        o.put("mode", mode.name.lowercase())
        o.put("apps", JSONArray(apps.sorted()))
        o.put("failsafe_hours", failsafeHours)
        o.put("unlock_minutes", unlockMinutes)
        o.put("tz", zoneId)
        val arr = JSONArray()
        for (s in schedules) {
            val so = JSONObject()
            so.put("days", JSONArray(s.days.sorted()))
            so.put("start", formatHm(s.startMin))
            so.put("end", formatHm(s.endMin))
            arr.put(so)
        }
        o.put("schedules", arr)
        return o.toString()
    }

    companion object {
        fun fromJson(raw: String): Policy {
            val o = JSONObject(raw)
            require(o.optInt("version", 1) == 1) { "unsupported policy version" }
            val mode = when (o.optString("mode", "all").lowercase()) {
                "all" -> LockMode.ALL
                "apps" -> LockMode.APPS
                else -> throw IllegalArgumentException("unknown mode")
            }
            val apps = HashSet<String>()
            val appsArr = o.optJSONArray("apps") ?: JSONArray()
            for (i in 0 until appsArr.length()) apps.add(appsArr.getString(i))

            val schedules = ArrayList<Schedule>()
            val arr = o.optJSONArray("schedules") ?: JSONArray()
            for (i in 0 until arr.length()) {
                val so = arr.getJSONObject(i)
                val days = HashSet<Int>()
                val da = so.getJSONArray("days")
                for (j in 0 until da.length()) {
                    val d = da.getInt(j)
                    require(d in 1..7) { "day out of range: $d" }
                    days.add(d)
                }
                val start = parseHm(so.getString("start"))
                val end = parseHm(so.getString("end"))
                require(start != end) { "empty schedule window" }
                schedules.add(Schedule(days, start, end))
            }
            val failsafe = o.optInt("failsafe_hours", 12)
            val unlock = o.optInt("unlock_minutes", 30)
            require(failsafe in 1..72) { "failsafe_hours out of range" }
            require(unlock in 1..720) { "unlock_minutes out of range" }
            return Policy(
                mode = mode,
                apps = apps,
                schedules = schedules,
                failsafeHours = failsafe,
                unlockMinutes = unlock,
                zoneId = o.optString("tz", "UTC"),
            )
        }

        /** "HH:mm" to minutes since midnight. */
        fun parseHm(s: String): Int {
            val parts = s.split(":")
            require(parts.size == 2) { "bad time: $s" }
            val h = parts[0].toInt()
            val m = parts[1].toInt()
            require(h in 0..23 && m in 0..59) { "bad time: $s" }
            return h * 60 + m
        }

        fun formatHm(min: Int): String = "%02d:%02d".format(min / 60, min % 60)
    }
}
