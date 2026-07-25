package com.example.apphear

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.example.apphear.databinding.ActivitySplashBinding

class SplashActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySplashBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

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
