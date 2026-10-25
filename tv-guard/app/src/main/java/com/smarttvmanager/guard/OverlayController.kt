package com.smarttvmanager.guard

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.media.AudioManager
import android.view.Gravity
import android.view.KeyEvent
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView

/**
 * Full-screen cover with a D-pad PIN entry, drawn as an accessibility overlay.
 *
 * Remote controls: Up/Down change the current digit, Right adds a digit, Left removes the last
 * one, OK submits. Back is swallowed. Home cannot be intercepted, which is fine: the overlay is
 * a window and stays on top of whatever Home shows.
 *
 * G0 question: does an accessibility overlay receive D-pad key events on the target TVs?
 */
class OverlayController(
    private val service: AccessibilityService,
    private val onSubmit: (String) -> Unit,
) {
    private val wm = service.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private val audio = service.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    private var root: FrameLayout? = null
    private var title: TextView? = null
    private var message: TextView? = null
    private var pinView: TextView? = null
    private var mutedByUs = false
    private val digits = mutableListOf(0)

    val isShowing: Boolean get() = root != null

    fun show(titleText: String) {
        if (root == null) {
            build()
            pauseAndMute()
        }
        title?.text = titleText
    }

    fun hide() {
        val r = root ?: return
        try {
            wm.removeView(r)
        } catch (e: Exception) {
            // The window may already be gone if the service is being torn down.
        }
        root = null
        unmute()
        digits.clear()
        digits.add(0)
    }

    fun setMessage(text: String) {
        message?.text = text
    }

    private fun build() {
        val ctx = service
        val frame = FrameLayout(ctx)
        frame.setBackgroundColor(Color.parseColor("#F2000000"))
        frame.isFocusable = true
        frame.isFocusableInTouchMode = true

        val column = LinearLayout(ctx)
        column.orientation = LinearLayout.VERTICAL
        column.gravity = Gravity.CENTER

        val t = TextView(ctx)
        t.setTextColor(Color.WHITE)
        t.textSize = 36f
        t.typeface = Typeface.DEFAULT_BOLD
        t.gravity = Gravity.CENTER

        val pin = TextView(ctx)
        pin.setTextColor(Color.WHITE)
        pin.textSize = 56f
        pin.typeface = Typeface.MONOSPACE
        pin.gravity = Gravity.CENTER
        pin.setPadding(0, 48, 0, 24)

        val msg = TextView(ctx)
        msg.setTextColor(Color.parseColor("#FFB4AB"))
        msg.textSize = 22f
        msg.gravity = Gravity.CENTER

        val hint = TextView(ctx)
        hint.setTextColor(Color.parseColor("#B0B0B0"))
        hint.textSize = 18f
        hint.gravity = Gravity.CENTER
        hint.setPadding(0, 32, 0, 0)
        hint.text = "Up/Down: change digit    Right: add digit    Left: delete    OK: confirm"

        column.addView(t)
        column.addView(pin)
        column.addView(msg)
        column.addView(hint)
        frame.addView(
            column,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER,
            ),
        )

        frame.setOnKeyListener { _, keyCode, event -> onKey(keyCode, event) }

        // No FLAG_NOT_FOCUSABLE: the overlay has to take key focus to receive remote input.
        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.MATCH_PARENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON,
            PixelFormat.TRANSLUCENT,
        )
        wm.addView(frame, params)
        frame.requestFocus()

        root = frame
        title = t
        message = msg
        pinView = pin
        render()
    }

    private fun onKey(keyCode: Int, event: KeyEvent): Boolean {
        val handled = when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP, KeyEvent.KEYCODE_DPAD_DOWN,
            KeyEvent.KEYCODE_DPAD_LEFT, KeyEvent.KEYCODE_DPAD_RIGHT,
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_NUMPAD_ENTER, KeyEvent.KEYCODE_BACK -> true
            else -> false
        }
        if (!handled || event.action != KeyEvent.ACTION_DOWN) return handled

        val last = digits.size - 1
        when (keyCode) {
            KeyEvent.KEYCODE_DPAD_UP -> digits[last] = (digits[last] + 1) % 10
            KeyEvent.KEYCODE_DPAD_DOWN -> digits[last] = (digits[last] + 9) % 10
            KeyEvent.KEYCODE_DPAD_RIGHT -> if (digits.size < MAX_DIGITS) digits.add(0)
            KeyEvent.KEYCODE_DPAD_LEFT ->
                if (digits.size > 1) digits.removeAt(last) else digits[0] = 0
            KeyEvent.KEYCODE_DPAD_CENTER, KeyEvent.KEYCODE_ENTER,
            KeyEvent.KEYCODE_NUMPAD_ENTER -> {
                val pin = digits.joinToString("")
                digits.clear()
                digits.add(0)
                onSubmit(pin)
            }
        }
        render()
        return true
    }

    private fun render() {
        val last = digits.size - 1
        val sb = StringBuilder()
        for ((i, d) in digits.withIndex()) {
            // Earlier digits are masked; the digit being edited stays visible.
            sb.append(if (i == last) d.toString() else "•").append(' ')
        }
        pinView?.text = sb.toString().trim()
    }

    private fun pauseAndMute() {
        try {
            audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PAUSE))
            audio.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_PAUSE))
            if (!audio.isStreamMute(AudioManager.STREAM_MUSIC)) {
                audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_MUTE, 0)
                mutedByUs = true
            }
        } catch (e: Exception) {
            // Some TVs use fixed volume or restrict this; the overlay still covers the picture.
        }
    }

    private fun unmute() {
        if (!mutedByUs) return
        try {
            audio.adjustStreamVolume(AudioManager.STREAM_MUSIC, AudioManager.ADJUST_UNMUTE, 0)
        } catch (e: Exception) {
            // See pauseAndMute.
        }
        mutedByUs = false
    }

    companion object {
        private const val MAX_DIGITS = 8
    }
}
