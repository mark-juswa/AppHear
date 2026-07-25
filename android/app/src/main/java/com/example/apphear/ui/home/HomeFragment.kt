package com.example.apphear.ui.home

import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.view.View
import android.view.ViewGroup
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.content.res.ResourcesCompat
import androidx.fragment.app.Fragment
import androidx.navigation.fragment.findNavController
import androidx.viewpager2.widget.ViewPager2
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.databinding.FragmentHomeBinding

class HomeFragment : Fragment(R.layout.fragment_home) {
    private var binding: FragmentHomeBinding? = null

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val fragmentBinding = FragmentHomeBinding.bind(view)
        binding = fragmentBinding

        fragmentBinding.avatarView.setOnClickListener {
            findNavController().navigate(R.id.profileFragment)
        }

        renderRecentSigns(fragmentBinding)
        setupFeatureCards(fragmentBinding)
    }

    private fun setupFeatureCards(fragmentBinding: FragmentHomeBinding) {
        fragmentBinding.featureViewPager.adapter = FeatureCardAdapter(
            object : FeatureCardAdapter.Listener {
                override fun onDetectClicked() {
                    startActivity(Intent(requireContext(), RecognitionActivity::class.java))
                }

                override fun onProjectClicked() {
                    findNavController().navigate(R.id.textToAslFragment)
                }
            },
        )
        fragmentBinding.featureViewPager.offscreenPageLimit = 1
        fragmentBinding.featureViewPager.setPageTransformer { page, position ->
            page.scaleY = 1f - kotlin.math.abs(position) * 0.05f
        }
        fragmentBinding.featureViewPager.registerOnPageChangeCallback(
            object : ViewPager2.OnPageChangeCallback() {
                override fun onPageSelected(position: Int) {
                    updateDots(fragmentBinding, position)
                }
            },
        )
    }

    private fun renderRecentSigns(fragmentBinding: FragmentHomeBinding) {
        val container = fragmentBinding.recentSignsContainer
        container.removeAllViews()
        addRecentChip(container, "No recent signs", active = true)
    }

    private fun addRecentChip(container: LinearLayout, text: String, active: Boolean) {
        val chip = TextView(requireContext())
        val params = LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            dpToPx(36),
        )
        params.marginEnd = dpToPx(8)
        chip.layoutParams = params
        chip.setBackgroundResource(if (active) R.drawable.bg_chip_active else R.drawable.bg_chip_inactive)
        chip.gravity = android.view.Gravity.CENTER
        chip.setPadding(dpToPx(18), 0, dpToPx(18), 0)
        chip.text = text
        chip.setTextColor(if (active) 0xFFFFFFFF.toInt() else 0xFF3A3A3A.toInt())
        chip.textSize = 13f
        chip.isSingleLine = true
        chip.typeface = ResourcesCompat.getFont(
            requireContext(),
            if (active) R.font.inter_semibold else R.font.inter_regular,
        ) ?: Typeface.DEFAULT
        container.addView(chip)
    }

    private fun updateDots(fragmentBinding: FragmentHomeBinding, activePage: Int) {
        setDotActive(fragmentBinding.dot0, activePage == 0)
        setDotActive(fragmentBinding.dot1, activePage == 1)
    }

    private fun setDotActive(dot: View, active: Boolean) {
        val params = dot.layoutParams
        params.width = dpToPx(if (active) 24 else 8)
        params.height = dpToPx(8)
        dot.layoutParams = params
        dot.setBackgroundResource(if (active) R.drawable.dot_active_pill else R.drawable.dot_inactive_circle)
    }

    private fun dpToPx(dp: Int): Int = (dp * resources.displayMetrics.density).toInt()

    override fun onDestroyView() {
        binding?.featureViewPager?.adapter = null
        binding = null
        super.onDestroyView()
    }
}