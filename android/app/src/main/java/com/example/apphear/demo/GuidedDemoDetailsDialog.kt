package com.example.apphear.demo

import android.content.Context
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import com.example.apphear.R

/** The guided demo's options window (opened from Settings): whether only the presenter paces the demo. */
object GuidedDemoDetailsDialog {
    fun show(context: Context): AlertDialog {
        val settings = GuidedDemoSettings(context)
        val pad = (20 * context.resources.displayMetrics.density).toInt()
        val presenter = CheckBox(context).apply {
            setText(R.string.guided_demo_presenter_title)
            isChecked = settings.presenterOnly
        }
        val form = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad / 2, pad, 0)
            addView(presenter)
            addView(TextView(context).apply {
                setText(R.string.guided_demo_presenter_body)
                setTextColor(context.getColor(R.color.color_text_secondary))
                textSize = 12f
            })
        }
        return AlertDialog.Builder(context).setTitle(R.string.guided_demo_details_title)
            .setView(form)
            .setPositiveButton(R.string.guided_demo_save) { _, _ -> settings.presenterOnly = presenter.isChecked }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }
}
