package com.example.apphear.fingerspelling

import android.content.Context
import android.view.Gravity
import android.view.View
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import com.example.apphear.R

/**
 * FINGERSPELL practical v1 (debug flag): Repeat / Done inside the RECOGNIZED card, and DELETE LAST LETTER in the
 * pull-up panel above CLEAR (user request: correction lives with CLEAR, not in the card). No hint text or counter.
 * Every view is GONE unless FINGERSPELL owns the frames, so the WORD card and panel are unchanged.
 * Done opens the existing spelling review (same commit path as Hear); nothing here commits by itself.
 */
internal class FingerspellPracticalControls(
    context: Context,
    parent: LinearLayout,
    anchor: View,
    panelParent: LinearLayout,
    panelAnchor: View,
    private val onDelete: () -> Unit,
    private val onRepeat: () -> Unit,
    private val onDone: () -> Unit,
) {
    private val density = context.resources.displayMetrics.density
    private fun dp(n: Int) = (n * density).toInt()

    val repeat = chip(context, R.id.fingerspellRepeat, "Repeat", "Add the last letter again")
        .apply { setOnClickListener { onRepeat() } }
    val done = chip(context, R.id.fingerspellDone, "Done ✓", "Review and use this spelling")
        .apply { setOnClickListener { onDone() } }
    val container = LinearLayout(context).apply {
        id = R.id.fingerspellPracticalPanel
        orientation = LinearLayout.HORIZONTAL; gravity = Gravity.CENTER
        visibility = View.GONE
        setPadding(0, dp(8), 0, 0)
        for (button in listOf(repeat, done)) addView(button, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, dp(44)).apply { marginStart = dp(4); marginEnd = dp(4) })
    }

    /** Same look as the existing CLEAR button (bg_chip_inactive, 56 dp, Inter semibold 13 sp bold, #8C775B). */
    val delete = FrameLayout(context).apply {
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

    // Own WRAP_CONTENT width: a default MATCH_PARENT child would take the card's (draft-text) width and clip buttons.
    init {
        parent.addView(container, parent.indexOfChild(anchor) + 1, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT))
        panelParent.addView(delete, panelParent.indexOfChild(panelAnchor), LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(56)).apply { bottomMargin = dp(12) })
    }

    private fun chip(context: Context, viewId: Int, label: String, description: String) = TextView(context).apply {
        id = viewId; text = label; contentDescription = description
        textSize = 13f; setTextColor(0xFFFFFFFF.toInt()); gravity = Gravity.CENTER
        typeface = context.resources.getFont(R.font.inter_semibold)
        minWidth = dp(72); setPadding(dp(14), 0, dp(14), 0)
        setBackgroundResource(R.drawable.bg_glass_pill)
        isClickable = true; isFocusable = true
    }

    private fun enable(view: View, enabled: Boolean) { view.isEnabled = enabled; view.alpha = if (enabled) 1f else 0.4f }

    /** Pure presentation of the snapshot. Hidden for WORD and for non-practical snapshots. */
    fun render(s: FingerspellSnapshot) {
        val active = s.practical && s.mode == RecognitionMode.FINGERSPELL
        container.visibility = if (active) View.VISIBLE else View.GONE
        delete.visibility = container.visibility
        if (!active) return
        enable(delete, s.preview.isNotEmpty() && !s.reviewing)
        enable(repeat, s.preview.isNotEmpty() && !s.reviewing)
        repeat.text = if (s.preview.isNotEmpty()) "Repeat ${s.preview.last()}" else "Repeat"
        enable(done, (s.preview.isNotEmpty() || s.confirmed.isNotEmpty()) && !s.reviewing)
    }
}
