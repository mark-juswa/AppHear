package com.example.apphear.ui.profile

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import com.example.apphear.R
import com.example.apphear.databinding.FragmentProfileBinding
import com.example.apphear.data.settings.AslCharacterSettings
import com.example.apphear.ui.settings.SettingsContent
import com.example.apphear.data.profile.AccountServices

class ProfileFragment : Fragment(R.layout.fragment_profile) {
    private var binding: FragmentProfileBinding? = null
    private var settingsContent: SettingsContent? = null
    private val accounts = ProfileAccountContent(this)

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val fragmentBinding = FragmentProfileBinding.bind(view)
        binding = fragmentBinding

        if (AslCharacterSettings(requireContext()).selectionAvailable || AccountServices.enabled) {
            settingsContent = SettingsContent(requireContext(), view).also { it.render() }
        }

        if (AccountServices.enabled) {
            accounts.attach(fragmentBinding, savedInstanceState) { settingsContent?.render() }
        } else {
            fragmentBinding.profileEditButton.visibility = View.GONE
            fragmentBinding.profileLogoutButton.visibility = View.GONE
            fragmentBinding.avatarPicker.isEnabled = false
            fragmentBinding.tvProfileStatus.setText(R.string.profile_account_disabled_body)
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        if (AccountServices.enabled) accounts.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onResume() {
        super.onResume()
        settingsContent?.render()
    }

    override fun onDestroyView() {
        accounts.close()
        settingsContent?.close()
        settingsContent = null
        binding = null
        super.onDestroyView()
    }
}
