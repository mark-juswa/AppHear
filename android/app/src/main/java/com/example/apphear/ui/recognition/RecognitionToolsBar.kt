package com.example.apphear.ui.recognition

import android.content.Context
import android.view.View
import android.view.ViewTreeObserver
import androidx.core.view.isVisible
import com.example.apphear.BuildConfig
import com.example.apphear.R
import com.example.apphear.databinding.ActivityRecognitionBinding

/**
 * The Recognition screen's right-side tool tray. The camera switch and speaker stay visible; the
 * less-used buttons (WORD/FINGERSPELL, conversation demo, connect a device, positioning guide) sit in
 * a tray that the chevron opens and closes. Each button keeps its own feature rule for showing; the
 * chevron appears only when the tray has something in it. Open/closed and guide hidden are remembered.
 */
class RecognitionToolsBar(context: Context, private val binding: ActivityRecognitionBinding) {
    private val preferences = context.applicationContext.getSharedPreferences("apphear_recognition_tools", Context.MODE_PRIVATE)
    private var expanded = preferences.getBoolean(KEY_EXPANDED, false)
    private var guideHidden = preferences.getBoolean(KEY_GUIDE_HIDDEN, false)
    private val trayButtons = listOf(binding.modeToolsToggle, binding.btnGuidedDemo, binding.btnRemoteConnect,
        binding.btnPlacementToggle)

    init {
        binding.btnPlacementToggle.isVisible = BuildConfig.PLACEMENT_GUIDE_ENABLED
        binding.btnToolsExpand.setOnClickListener {
            expanded = !expanded
            preferences.edit().putBoolean(KEY_EXPANDED, expanded).apply()
            render()
        }
        binding.btnPlacementToggle.setOnClickListener {
            guideHidden = !guideHidden
            preferences.edit().putBoolean(KEY_GUIDE_HIDDEN, guideHidden).apply()
            render()
        }
        // Other screens' code decides when each tray button shows; follow along after every layout pass.
        binding.root.viewTreeObserver.addOnGlobalLayoutListener(object : ViewTreeObserver.OnGlobalLayoutListener {
            override fun onGlobalLayout() = updateChevron()
        })
        render()
    }

    private fun render() {
        binding.placementGuide.userHidden = guideHidden
        binding.btnPlacementToggle.alpha = if (guideHidden) 0.45f else 1f
        binding.btnPlacementToggle.contentDescription = binding.root.context.getString(
            if (guideHidden) R.string.tools_guide_show else R.string.tools_guide_hide)
        binding.btnToolsExpand.rotation = if (expanded) 180f else 0f
        binding.btnToolsExpand.contentDescription = binding.root.context.getString(
            if (expanded) R.string.tools_more_hide else R.string.tools_more_show)
        updateChevron()
    }

    private fun updateChevron() {
        val anything = trayButtons.any { it.visibility == View.VISIBLE }
        if (binding.btnToolsExpand.isVisible != anything) binding.btnToolsExpand.isVisible = anything
        val showTray = anything && expanded
        if (binding.recognitionToolsMore.isVisible != showTray) binding.recognitionToolsMore.isVisible = showTray
    }

    private companion object {
        const val KEY_EXPANDED = "expanded"
        const val KEY_GUIDE_HIDDEN = "guide_hidden"
    }
}
