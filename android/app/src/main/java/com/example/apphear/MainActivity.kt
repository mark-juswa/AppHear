package com.example.apphear

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.constraintlayout.widget.ConstraintLayout
import androidx.core.os.bundleOf
import androidx.core.view.isVisible
import androidx.navigation.NavOptions
import androidx.navigation.fragment.NavHostFragment
import com.example.apphear.conversation.ConversationTimeline
import com.example.apphear.databinding.ActivityAppShellBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityAppShellBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ConversationTimeline.screenCreated("main")
        binding = ActivityAppShellBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val navHost = supportFragmentManager
            .findFragmentById(R.id.app_shell_nav_host) as NavHostFragment
        val navController = navHost.navController

        navController.addOnDestinationChangedListener { _, destination, _ ->
            setBottomNavigationVisible(destination.id != R.id.textToAslFragment)
        }

        fun navigateShell(destinationId: Int) {
            if (navController.currentDestination?.id == destinationId) return
            val options = NavOptions.Builder()
                .setLaunchSingleTop(true)
                .setPopUpTo(R.id.homeFragment, false)
                .build()
            navController.navigate(destinationId, null, options)
        }

        binding.appShellBottomNav.navHomeContainer.setOnClickListener {
            navigateShell(R.id.homeFragment)
        }
        binding.appShellBottomNav.navDetect.setOnClickListener {
            ConversationTimeline.tap("main", "nav_detect")
            startActivity(Intent(this, RecognitionActivity::class.java))
        }
        binding.appShellBottomNav.navAsl.setOnClickListener {
            ConversationTimeline.tap("main", "nav_text_to_asl")
            navigateShell(R.id.textToAslFragment)
        }
        binding.appShellBottomNav.navProfile.setOnClickListener {
            navigateShell(R.id.profileFragment)
        }

        handleTextToAslIntent(intent)
    }

    override fun onDestroy() {
        ConversationTimeline.screenDestroyed("main")
        super.onDestroy()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        ConversationTimeline.mark("main_new_intent")
        setIntent(intent)
        handleTextToAslIntent(intent)
    }

    private fun handleTextToAslIntent(intent: Intent?) {
        val transcript = intent
            ?.takeIf { it.getBooleanExtra(EXTRA_OPEN_TEXT_TO_ASL, false) }
            ?.getStringExtra(EXTRA_TEXT_TO_ASL_INPUT)
            ?.trim()
            .orEmpty()
        if (transcript.isBlank()) return

        val navHost = supportFragmentManager
            .findFragmentById(R.id.app_shell_nav_host) as NavHostFragment
        val navController = navHost.navController
        ConversationTimeline.mark("transcript_routed", "chars" to transcript.length,
            "already_on_text_to_asl" to (navController.currentDestination?.id == R.id.textToAslFragment))
        val options = NavOptions.Builder()
            .setLaunchSingleTop(true)
            .setPopUpTo(R.id.homeFragment, false)
            .build()
        navController.navigate(
            R.id.textToAslFragment,
            Bundle().apply { putString(TextToAslArgument.INCOMING_TEXT, transcript) },
            options,
        )
        intent?.removeExtra(EXTRA_OPEN_TEXT_TO_ASL)
        intent?.removeExtra(EXTRA_TEXT_TO_ASL_INPUT)
    }

    private fun setBottomNavigationVisible(visible: Boolean) {
        binding.appShellBottomNav.root.isVisible = visible
        val params = binding.appShellNavHost.layoutParams as ConstraintLayout.LayoutParams
        if (visible) {
            params.bottomToBottom = ConstraintLayout.LayoutParams.UNSET
            params.bottomToTop = R.id.app_shell_bottom_nav
        } else {
            params.bottomToTop = ConstraintLayout.LayoutParams.UNSET
            params.bottomToBottom = ConstraintLayout.LayoutParams.PARENT_ID
        }
        binding.appShellNavHost.layoutParams = params
    }

    companion object {
        const val EXTRA_OPEN_TEXT_TO_ASL = "com.example.apphear.extra.OPEN_TEXT_TO_ASL"
        const val EXTRA_TEXT_TO_ASL_INPUT = "com.example.apphear.extra.TEXT_TO_ASL_INPUT"
    }
}

object TextToAslArgument {
    const val INCOMING_TEXT = "incoming_text"
}