package com.smarttvmanager.guard

import java.security.MessageDigest
import java.util.Base64
import javax.crypto.SecretKeyFactory
import javax.crypto.spec.PBEKeySpec

/**
 * PIN hashes are computed on the desktop and stored as
 * `pbkdf2$<iterations>$<salt>$<hash>` (URL-safe base64, no padding).
 * The PIN itself never leaves the desktop app.
 */
object PinHasher {
    private val enc = Base64.getUrlEncoder().withoutPadding()
    private val dec = Base64.getUrlDecoder()

    fun hash(pin: String, salt: ByteArray, iterations: Int): String {
        val dk = derive(pin, salt, iterations, 32)
        return listOf("pbkdf2", iterations.toString(), enc.encodeToString(salt), enc.encodeToString(dk))
            .joinToString("\$")
    }

    fun isWellFormed(stored: String): Boolean = try {
        parse(stored)
        true
    } catch (e: Exception) {
        false
    }

    fun verify(stored: String?, pin: String): Boolean {
        if (stored.isNullOrEmpty()) return false
        return try {
            val (iters, salt, expected) = parse(stored)
            val actual = derive(pin, salt, iters, expected.size)
            MessageDigest.isEqual(expected, actual)
        } catch (e: Exception) {
            false
        }
    }

    private data class Parsed(val iters: Int, val salt: ByteArray, val hash: ByteArray)

    private fun parse(stored: String): Parsed {
        val p = stored.split("$")
        require(p.size == 4 && p[0] == "pbkdf2") { "bad hash format" }
        val iters = p[1].toInt()
        require(iters in 10_000..1_000_000) { "iterations out of range" }
        val salt = dec.decode(p[2])
        val hash = dec.decode(p[3])
        require(salt.size >= 8 && hash.size >= 16) { "salt or hash too short" }
        return Parsed(iters, salt, hash)
    }

    private fun derive(pin: String, salt: ByteArray, iters: Int, bytes: Int): ByteArray {
        val spec = PBEKeySpec(pin.toCharArray(), salt, iters, bytes * 8)
        return SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256").generateSecret(spec).encoded
    }
}
