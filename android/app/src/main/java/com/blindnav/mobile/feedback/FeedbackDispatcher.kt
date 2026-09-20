package com.blindnav.mobile.feedback

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.VibrationEffect
import android.os.Vibrator
import android.speech.tts.TextToSpeech
import java.util.Locale

/**
 * Executes the platform-neutral feedback contract on an Android phone.
 *
 * The dispatcher deliberately does not infer risk or distance. It only executes
 * already validated actions and applies a small safety policy: duplicate speech
 * for one track is suppressed for one second and urgent feedback cancels
 * pending lower-priority speech.
 */
class FeedbackDispatcher(
    context: Context,
    private val nowMs: () -> Long = { System.currentTimeMillis() },
) : TextToSpeech.OnInitListener, AutoCloseable {
    private val appContext = context.applicationContext
    private val vibrator = appContext.getSystemService(Vibrator::class.java)
    private val toneGenerator = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
    private val handler = Handler(Looper.getMainLooper())
    private var textToSpeech: TextToSpeech? = TextToSpeech(appContext, this)
    private var speechReady = false
    private var pendingSpeech: Runnable? = null
    private var pendingPriority: FeedbackPriority? = null
    private val lastSpeechByTrack = mutableMapOf<String, Long>()

    override fun onInit(status: Int) {
        speechReady = status == TextToSpeech.SUCCESS
        if (speechReady) textToSpeech?.language = Locale.SIMPLIFIED_CHINESE
    }

    fun dispatch(trackId: String, action: FeedbackAction) {
        playVibration(action.vibrationMs)
        playTone(action.tone)

        val speech = action.speech ?: return
        val last = lastSpeechByTrack[trackId]
        if (last != null && nowMs() - last < SPEECH_DEDUPE_WINDOW_MS) return
        if (action.priority == FeedbackPriority.URGENT) cancelPendingSpeech()
        lastSpeechByTrack[trackId] = nowMs()

        lateinit var runnable: Runnable
        runnable = Runnable {
            if (action.priority != FeedbackPriority.URGENT && pendingPriority == FeedbackPriority.URGENT) return@Runnable
            if (speechReady) {
                textToSpeech?.speak(speech, TextToSpeech.QUEUE_FLUSH, null, "blindnav-$trackId")
            }
            if (pendingSpeech === runnable) {
                pendingSpeech = null
                pendingPriority = null
            }
        }
        pendingSpeech = runnable
        pendingPriority = action.priority
        handler.postDelayed(runnable, action.speechDelayMs ?: 0L)
    }

    private fun playVibration(patternMs: List<Long>) {
        val target = vibrator ?: return
        if (!target.hasVibrator()) return
        val waveform = LongArray(patternMs.size + 1)
        patternMs.forEachIndexed { index, duration -> waveform[index + 1] = duration }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            target.vibrate(VibrationEffect.createWaveform(waveform, -1))
        } else {
            @Suppress("DEPRECATION")
            target.vibrate(waveform, -1)
        }
    }

    private fun playTone(tone: String?) {
        when (tone) {
            "warning" -> toneGenerator.startTone(ToneGenerator.TONE_PROP_BEEP2, 160)
            "danger" -> toneGenerator.startTone(ToneGenerator.TONE_PROP_NACK, 220)
        }
    }

    private fun cancelPendingSpeech() {
        pendingSpeech?.let(handler::removeCallbacks)
        pendingSpeech = null
        pendingPriority = null
        textToSpeech?.stop()
    }

    override fun close() {
        cancelPendingSpeech()
        vibrator?.cancel()
        toneGenerator.release()
        textToSpeech?.stop()
        textToSpeech?.shutdown()
        textToSpeech = null
        lastSpeechByTrack.clear()
    }

    private companion object {
        const val SPEECH_DEDUPE_WINDOW_MS = 1_000L
    }
}
