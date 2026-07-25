package com.example.apphear.ui.profile

import android.os.Bundle
import android.view.View
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import com.example.apphear.R
import com.example.apphear.databinding.FragmentProfileBinding

class ProfileFragment : Fragment(R.layout.fragment_profile) {
    private var binding: FragmentProfileBinding? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val fragmentBinding = FragmentProfileBinding.bind(view)
        binding = fragmentBinding

        fragmentBinding.profileOpenSettingsButton.setOnClickListener {
            findNavController().navigate(R.id.settingsFragment)
        }
    }

    override fun onDestroyView() {
        binding = null
        super.onDestroyView()
    }
}