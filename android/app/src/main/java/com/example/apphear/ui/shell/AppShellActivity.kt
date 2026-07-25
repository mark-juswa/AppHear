package com.example.apphear.ui.shell

import android.content.Intent
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import androidx.navigation.fragment.NavHostFragment
import com.example.apphear.R
import com.example.apphear.RecognitionActivity
import com.example.apphear.databinding.ActivityAppShellBinding

class AppShellActivity : AppCompatActivity() {
    private lateinit var binding: ActivityAppShellBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAppShellBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val navHost = supportFragmentManager
            .findFragmentById(R.id.app_shell_nav_host) as NavHostFragment
        val navController = navHost.navController

        binding.appShellBottomNav.navHomeContainer.setOnClickListener {
            navController.navigate(R.id.homeFragment)
        }
        binding.appShellBottomNav.navDetect.setOnClickListener {
            startActivity(Intent(this, RecognitionActivity::class.java))
        }
        binding.appShellBottomNav.navAsl.setOnClickListener {
            navController.navigate(R.id.textToAslFragment)
        }
        binding.appShellBottomNav.navProfile.setOnClickListener {
            navController.navigate(R.id.profileFragment)
        }
    }
}