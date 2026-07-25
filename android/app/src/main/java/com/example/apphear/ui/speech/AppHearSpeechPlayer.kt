package com.example.apphear.ui.speech

import android.content.Context
import android.media.MediaPlayer
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.util.Log
import com.example.apphear.BuildConfig
import org.json.JSONObject
import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

class AppHearSpeechPlayer(context: Context) : Closeable {
    private val appContext = context.applicationContext
    private val executor: ExecutorService = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    private var mediaPlayer: MediaPlayer? = null
    private var fallbackTts: TextToSpeech? = null
    private var ttsReady = false

    init {
        fallbackTts = TextToSpeech(appContext) { status ->
            val tts = fallbackTts
            if (status == TextToSpeech.SUCCESS && tts != null) {
                TtsVoiceHelper.applyNaturalEnglishVoice(tts)
                ttsReady = true
            } else {
                Log.w(TAG, "Android TextToSpeech initialization failed: $status")
            }
        }
    }

    fun speak(text: String) {
        val cleanText = text.trim()
        if (cleanText.isEmpty()) return

        if (!elevenLabsConfigured()) {
            speakWithFallback(cleanText)
            return
        }

        executor.execute {
            try {
                val audioFile = requestElevenLabsSpeech(cleanText)
                mainHandler.post { playAudio(audioFile, cleanText) }
            } catch (exception: Exception) {
                Log.w(TAG, "ElevenLabs speech failed; falling back to Android TTS.", exception)
                mainHandler.post { speakWithFallback(cleanText) }
            }
        }
    }

    fun stop() {
        stopMediaPlayer()
        fallbackTts?.stop()
    }

    private fun elevenLabsConfigured(): Boolean {
        return BuildConfig.ELEVENLABS_API_KEY.isNotBlank() &&
            BuildConfig.ELEVENLABS_VOICE_ID.isNotBlank()
    }

    private fun requestElevenLabsSpeech(text: String): File {
        val voiceId = BuildConfig.ELEVENLABS_VOICE_ID.trim()
        val url = URL("https://api.elevenlabs.io/v1/text-to-speech/$voiceId?output_format=mp3_44100_128")
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            doOutput = true
            setRequestProperty("xi-api-key", BuildConfig.ELEVENLABS_API_KEY.trim())
            setRequestProperty("Accept", "audio/mpeg")
            setRequestProperty("Content-Type", "application/json")
        }

        try {
            val body = JSONObject()
                .put("text", text)
                .put("model_id", BuildConfig.ELEVENLABS_MODEL_ID.ifBlank { DEFAULT_MODEL_ID })
                .put(
                    "voice_settings",
                    JSONObject()
                        .put("stability", 0.45)
                        .put("similarity_boost", 0.80)
                        .put("style", 0.20)
                        .put("use_speaker_boost", true),
                )

            connection.outputStream.use { outputStream ->
                outputStream.write(body.toString().toByteArray(StandardCharsets.UTF_8))
            }

            val responseCode = connection.responseCode
            if (responseCode !in 200..299) {
                throw IllegalStateException("ElevenLabs returned HTTP $responseCode")
            }

            val outputFile = File.createTempFile("apphear_elevenlabs_tts_", ".mp3", appContext.cacheDir)
            connection.inputStream.use { inputStream ->
                FileOutputStream(outputFile).use { outputStream ->
                    inputStream.copyTo(outputStream)
                }
            }
            return outputFile
        } finally {
            connection.disconnect()
        }
    }

    private fun playAudio(audioFile: File, fallbackText: String) {
        stopMediaPlayer()
        val player = MediaPlayer()
        mediaPlayer = player
        try {
            player.setDataSource(audioFile.absolutePath)
            player.setOnCompletionListener {
                stopMediaPlayer()
                deleteQuietly(audioFile)
            }
            player.setOnErrorListener { _, _, _ ->
                stopMediaPlayer()
                speakWithFallback(fallbackText)
                deleteQuietly(audioFile)
                true
            }
            player.setOnPreparedListener { preparedPlayer -> preparedPlayer.start() }
            player.prepareAsync()
        } catch (exception: Exception) {
            Log.w(TAG, "Could not play ElevenLabs audio; falling back to Android TTS.", exception)
            stopMediaPlayer()
            speakWithFallback(fallbackText)
            deleteQuietly(audioFile)
        }
    }
    private fun deleteQuietly(file: File) {
        runCatching { file.delete() }
    }

    private fun speakWithFallback(text: String) {
        mainHandler.post {
            if (ttsReady) {
                fallbackTts?.speak(text, TextToSpeech.QUEUE_FLUSH, null, FALLBACK_UTTERANCE_ID)
            } else {
                Log.w(TAG, "Android TTS fallback requested before initialization completed.")
            }
        }
    }

    private fun stopMediaPlayer() {
        val player = mediaPlayer ?: return
        try {
            if (player.isPlaying) player.stop()
        } catch (_: IllegalStateException) {
            // MediaPlayer can already be released after async preparation or playback errors.
        }
        player.release()
        mediaPlayer = null
    }

    override fun close() {
        stop()
        fallbackTts?.shutdown()
        fallbackTts = null
        executor.shutdownNow()
    }

    private companion object {
        const val TAG = "AppHearSpeechPlayer"
        const val DEFAULT_MODEL_ID = "eleven_multilingual_v2"
        const val FALLBACK_UTTERANCE_ID = "apphear_tts_fallback"
        const val CONNECT_TIMEOUT_MS = 20_000
        const val READ_TIMEOUT_MS = 45_000
    }
}
