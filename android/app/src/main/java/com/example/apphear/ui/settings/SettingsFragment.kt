package com.example.apphear.ui.settings

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import com.example.apphear.R

class SettingsFragment : Fragment(R.layout.fragment_settings) {
    private var content: SettingsContent? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        content = SettingsContent(requireContext(), view).also { it.render() }
    }

    override fun onResume() {
        super.onResume()
        content?.render()
    }

    override fun onDestroyView() {
        content?.close()
        content = null
        super.onDestroyView()
    }
}
