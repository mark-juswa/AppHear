package com.example.apphear.fingerspelling

import android.content.Context
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import com.example.apphear.R

/**
 * FINGERSPELL practical v1 (debug flag): DELETE LAST LETTER in the pull-up panel above CLEAR.
 * The RECOGNIZED card has no extra controls; the existing Hear button owns spelling review.
 * Delete is GONE unless FINGERSPELL owns the frames and disabled during review.
 */
internal class FingerspellPracticalControls(
    context: Context,
    panelParent: LinearLayout,
    panelAnchor: View,
    private val onDelete: () -> Unit,
) {
    private val density = context.resources.displayMetrics.density
    private fun dp(n: Int) = (n * density).toInt()

    /** Same look as the existing CLEAR button (bg_chip_inactive, 56 dp, Inter semibold 13 sp bold, #8C775B). */
    private val delete = FrameLayout(context).apply {
        id = R.id.fingerspellDelete
        setBackgroundResource(R.drawable.bg_chip_inactive)
        isClickable = true; isFocusable = true; visibility = View.GONE
        contentDescription = "Delete last letter"
        setOnClickListener { onDelete() }
        addView(TextView(context).apply {
            text = "DELETE LAST LETTER"; letterSpacing = 0.1f; textSize = 13f
            setTextColor(0xFF8C775B.toInt())
            typeface = android.graphics.Typeface.create(context.resources.getFont(R.font.inter_semibold),
                android.graphics.Typeface.BOLD)
        }, FrameLayout.LayoutParams(FrameLayout.LayoutParams.WRAP_CONTENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.CENTER))
    }

    init {
        panelParent.addView(delete, panelParent.indexOfChild(panelAnchor), LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(56)).apply { bottomMargin = dp(12) })
    }

    private fun enable(view: View, enabled: Boolean) { view.isEnabled = enabled; view.alpha = if (enabled) 1f else 0.4f }

    /** Pure presentation of the snapshot. Hidden for WORD and for non-practical snapshots. */
    fun render(s: FingerspellSnapshot) {
        val active = s.practical && s.mode == RecognitionMode.FINGERSPELL
        delete.visibility = if (active) View.VISIBLE else View.GONE
        if (!active) return
        enable(delete, s.preview.isNotEmpty() && !s.reviewing)
    }
}
