package com.example.apphear

import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.res.ResourcesCompat
import com.example.apphear.databinding.ActivityLoadingBinding

class LoadingActivity : AppCompatActivity() {
    private lateinit var binding: ActivityLoadingBinding
    private val handler = Handler(Looper.getMainLooper())
    private var navigateRunnable: Runnable? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityLoadingBinding.inflate(layoutInflater)
        setContentView(binding.root)

        animateLogo()
        buildAndAnimateSlogan()
        animateIcons()
        scheduleNavigation()
    }

    private fun animateLogo() {
        binding.logoGroup.alpha = 0f
        binding.logoGroup.translationY = 14f
        binding.logoGroup.scaleX = 0.96f
        binding.logoGroup.scaleY = 0.96f
        handler.postDelayed({
            binding.logoGroup.animate()
                .alpha(1f)
                .translationY(0f)
                .scaleX(1f)
                .scaleY(1f)
                .setDuration(LOGO_DURATION)
                .setInterpolator(DecelerateInterpolator())
                .start()
        }, LOGO_DELAY)
    }

    private fun buildAndAnimateSlogan() {
        val typeface = ResourcesCompat.getFont(this, R.font.inter_semibold)
        LOADING_SLOGAN.forEachIndexed { index, char ->
            val letterView = TextView(this).apply {
                text = char.toString()
                setTextColor(0xFF403E3A.toInt())
                textSize = 15f
                includeFontPadding = false
                if (typeface != null) setTypeface(typeface, Typeface.NORMAL)
                alpha = 0f
                translationX = 24f
            }
            binding.sloganContainer.addView(letterView)
            handler.postDelayed({
                letterView.animate()
                    .alpha(1f)
                    .translationX(0f)
                    .setDuration(LETTER_DURATION)
                    .setInterpolator(DecelerateInterpolator())
                    .start()
            }, SLOGAN_DELAY + index * LETTER_STAGGER)
        }
    }

    private fun animateIcons() {
        animateIcon(binding.iconDetect, ICON_START_DELAY)
        animateIcon(binding.iconAsl, ICON_START_DELAY + ICON_STAGGER)
        animateIcon(binding.iconSpeech, ICON_START_DELAY + ICON_STAGGER * 2)
    }

    private fun animateIcon(icon: View, delay: Long) {
        icon.alpha = 0f
        icon.scaleX = 0.55f
        icon.scaleY = 0.55f
        icon.translationY = 10f
        handler.postDelayed({
            icon.animate()
                .alpha(1f)
                .translationY(0f)
                .scaleX(1f)
                .scaleY(1f)
                .setDuration(ICON_DURATION)
                .setInterpolator(OvershootInterpolator(1.05f))
                .start()
        }, delay)
    }

    private fun scheduleNavigation() {
        navigateRunnable = Runnable {
            startActivity(Intent(this, MainActivity::class.java))
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out)
            finish()
        }.also { handler.postDelayed(it, NAVIGATE_DELAY) }
    }

    override fun onDestroy() {
        navigateRunnable?.let(handler::removeCallbacks)
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    private companion object {
        const val LOADING_SLOGAN = "Where Signs Find a Voice"
        const val LOGO_DELAY = 180L
        const val LOGO_DURATION = 650L
        const val SLOGAN_DELAY = 930L
        const val LETTER_DURATION = 190L
        const val LETTER_STAGGER = 32L
        const val ICON_START_DELAY = 1850L
        const val ICON_STAGGER = 190L
        const val ICON_DURATION = 360L
        const val NAVIGATE_DELAY = 2200L
    }
}
