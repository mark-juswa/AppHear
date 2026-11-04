package com.example.apphear.demo

import android.content.Context
import android.text.InputFilter
import android.text.InputType
import android.widget.CheckBox
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import com.example.apphear.R

/**
 * The script details window: the values the scenarios fill in (name, age, city, ...) and whether only
 * the presenter paces the demo. Opened from Settings and from the Recognition screen's scenario card.
 */
object GuidedDemoDetailsDialog {
    private val labels = mapOf(
        "name" to R.string.guided_demo_field_name, "age" to R.string.guided_demo_field_age,
        "city" to R.string.guided_demo_field_city, "province" to R.string.guided_demo_field_province,
        "school" to R.string.guided_demo_field_school, "school_short" to R.string.guided_demo_field_school_short,
        "course" to R.string.guided_demo_field_course, "year_level" to R.string.guided_demo_field_year_level,
        "occupation" to R.string.guided_demo_field_occupation, "destination" to R.string.guided_demo_field_destination,
        "favorite_subject" to R.string.guided_demo_field_favorite_subject, "adviser" to R.string.guided_demo_field_adviser,
        "hearing_name" to R.string.guided_demo_field_hearing_name,
    )

    fun show(context: Context, onSaved: () -> Unit = {}): AlertDialog {
        val settings = GuidedDemoSettings(context)
        val current = settings.values
        val density = context.resources.displayMetrics.density
        val pad = (20 * density).toInt()
        val form = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(pad, pad / 2, pad, 0)
        }
        form.addView(TextView(context).apply {
            setText(R.string.guided_demo_details_hint)
            setTextColor(context.getColor(R.color.color_text_secondary))
            textSize = 13f
        })
        val inputs = DemoValues.keys.map { key ->
            form.addView(TextView(context).apply {
                labels[key]?.let(::setText)
                setTextColor(context.getColor(R.color.color_text_secondary))
                textSize = 12f
                setPadding(0, (10 * density).toInt(), 0, 0)
            })
            key to EditText(context).apply {
                setText(current[key].orEmpty())
                setSingleLine()
                filters = arrayOf(InputFilter.LengthFilter(DemoValues.MAX_VALUE))
                inputType = if (key == "age") InputType.TYPE_CLASS_NUMBER
                    else InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_WORDS
                form.addView(this)
            }
        }
        val presenter = CheckBox(context).apply {
            setText(R.string.guided_demo_presenter_title)
            isChecked = settings.presenterOnly
            setPadding(0, (8 * density).toInt(), 0, 0)
        }
        form.addView(presenter)
        form.addView(TextView(context).apply {
            setText(R.string.guided_demo_presenter_body)
            setTextColor(context.getColor(R.color.color_text_secondary))
            textSize = 12f
        })
        return AlertDialog.Builder(context).setTitle(R.string.guided_demo_details_title)
            .setView(ScrollView(context).apply { addView(form) })
            .setPositiveButton(R.string.guided_demo_save) { _, _ ->
                settings.values = inputs.associate { (key, input) -> key to input.text.toString() }
                settings.presenterOnly = presenter.isChecked
                onSaved()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }
}
