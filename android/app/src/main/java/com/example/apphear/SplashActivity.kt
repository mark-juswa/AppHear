package com.example.apphear

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.example.apphear.databinding.ActivitySplashBinding

class SplashActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySplashBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (BuildConfig.RU_D1_ENABLED && intent.hasExtra(RecognitionActivity.EXTRA_RU_D1_GLOSS)) {
            startActivity(
                Intent(this, RecognitionActivity::class.java).apply {
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_GLOSS,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_GLOSS),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_EXPECTED_HANDS,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_EXPECTED_HANDS),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_SIGNER_ID,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_SIGNER_ID),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_VARIANT,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_VARIANT),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_SESSION_ID,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_SESSION_ID),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_REPETITION_ID,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_REPETITION_ID),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_CAPTURE_ORDER,
                        intent.getIntExtra(RecognitionActivity.EXTRA_RU_D1_CAPTURE_ORDER, 0),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_TOTAL_ATTEMPTS,
                        intent.getIntExtra(RecognitionActivity.EXTRA_RU_D1_TOTAL_ATTEMPTS, 0),
                    )
                    putExtra(
                        RecognitionActivity.EXTRA_RU_D1_INSTRUCTION_B64,
                        intent.getStringExtra(RecognitionActivity.EXTRA_RU_D1_INSTRUCTION_B64),
                    )
                },
            )
            finish()
            return
        }

        if (hasSeenSplash()) {
            openLoading()
            return
        }

        binding = ActivitySplashBinding.inflate(layoutInflater)
        setContentView(binding.root)
        binding.btnGetStarted.setOnClickListener {
            getSharedPreferences(PREFS, MODE_PRIVATE)
                .edit()
                .putBoolean(KEY_HAS_SEEN_SPLASH, true)
                .apply()
            openLoading()
        }
    }

    private fun hasSeenSplash(): Boolean =
        getSharedPreferences(PREFS, MODE_PRIVATE).getBoolean(KEY_HAS_SEEN_SPLASH, false)

    private fun openLoading() {
        startActivity(Intent(this, LoadingActivity::class.java))
        finish()
    }

    private companion object {
        const val PREFS = "apphear_onboarding"
        const val KEY_HAS_SEEN_SPLASH = "has_seen_splash"
    }
}
