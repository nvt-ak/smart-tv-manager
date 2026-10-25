package com.smarttvmanager.guard

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SecurityTest {
    private val secret = ByteArray(32) { it.toByte() }

    @Test
    fun pinVerifiesOnlyWithTheRightPin() {
        val stored = PinHasher.hash("1234", ByteArray(16) { 7 }, 10_000)
        assertTrue(PinHasher.verify(stored, "1234"))
        assertFalse(PinHasher.verify(stored, "1235"))
        assertFalse(PinHasher.verify(stored, ""))
    }

    @Test
    fun malformedPinHashNeverVerifies() {
        assertFalse(PinHasher.verify(null, "1234"))
        assertFalse(PinHasher.verify("", "1234"))
        assertFalse(PinHasher.verify("plain1234", "1234"))
        assertFalse(PinHasher.isWellFormed("pbkdf2\$1\$AA\$BB"))
    }

    @Test
    fun validSignatureIsAccepted() {
        val sig = CommandAuth.sign(secret, "lock_now", 1_000L, "NjA=")
        assertTrue(CommandAuth.verify(secret, "lock_now", 1_000L, "NjA=", sig, 999L, 1_000L))
    }

    @Test
    fun tamperedFieldsAreRejected() {
        val sig = CommandAuth.sign(secret, "lock_now", 1_000L, "NjA=")
        assertFalse(CommandAuth.verify(secret, "unlock_now", 1_000L, "NjA=", sig, 999L, 1_000L))
        assertFalse(CommandAuth.verify(secret, "lock_now", 1_000L, "MzA=", sig, 999L, 1_000L))
        assertFalse(CommandAuth.verify(secret, "lock_now", 1_001L, "NjA=", sig, 999L, 1_001L))
    }

    @Test
    fun wrongSecretIsRejected() {
        val sig = CommandAuth.sign(ByteArray(32) { 9 }, "ping", 1_000L, "cA==")
        assertFalse(CommandAuth.verify(secret, "ping", 1_000L, "cA==", sig, 0L, 1_000L))
    }

    @Test
    fun replayedAndFutureSequencesAreRejected() {
        val sig = CommandAuth.sign(secret, "ping", 1_000L, "cA==")
        // Replay: sequence not greater than the last accepted one.
        assertFalse(CommandAuth.verify(secret, "ping", 1_000L, "cA==", sig, 1_000L, 2_000L))
        // Far-future sequence would freeze the channel for everyone else.
        val future = 10_000_000L
        val sigF = CommandAuth.sign(secret, "ping", future, "cA==")
        assertFalse(CommandAuth.verify(secret, "ping", future, "cA==", sigF, 0L, 1_000L))
    }
}
