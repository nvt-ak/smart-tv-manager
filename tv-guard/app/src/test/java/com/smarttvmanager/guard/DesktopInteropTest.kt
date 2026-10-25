package com.smarttvmanager.guard

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Fixtures produced by tools/guard_cli.py. If either side changes the message format or the hash
 * format, these fail, which is the point: the desktop and the TV must agree byte for byte.
 *
 * Regenerate the values with guard_cli.sign() and guard_cli.hash_pin() (same arguments as below).
 */
class DesktopInteropTest {
    private val secret = ByteArray(32) { it.toByte() }

    @Test
    fun signatureFromPythonVerifies() {
        val sig = "764e1fe274957e67d168d970734876fdb8e30eefcc1eaa2edb822ae365baabaa"
        assertEquals(sig, CommandAuth.sign(secret, "set_policy", 1761370000000L, "eyJtb2RlIjoiYWxsIn0="))
        assertTrue(
            CommandAuth.verify(
                secret, "set_policy", 1761370000000L, "eyJtb2RlIjoiYWxsIn0=", sig,
                lastSeq = 0L, nowMs = 1761370000000L,
            ),
        )
    }

    @Test
    fun pinHashFromPythonVerifies() {
        val stored = "pbkdf2\$20000\$AwMDAwMDAwMDAwMDAwMDAw\$MHVDWZ27xS2bdIuVTSux98T2ddHjD7bjI1dzbj-y3ik"
        assertTrue(PinHasher.isWellFormed(stored))
        assertTrue(PinHasher.verify(stored, "2468"))
        assertFalse(PinHasher.verify(stored, "2469"))
    }
}
