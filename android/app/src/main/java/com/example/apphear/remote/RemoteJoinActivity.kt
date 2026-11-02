package com.example.apphear.remote

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import com.example.apphear.MainActivity

/**
 * Opened by an invite link (`apphear://join?...`, e.g. from the phone's camera scanning a QR). Keeps the
 * invite for the Text-to-ASL screen, which asks before joining, and opens the app. No UI of its own.
 * Disabled in the manifest unless the remoteConversation flag is on.
 */
class RemoteJoinActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val link = intent?.dataString?.let { RemoteInvite.parse(it) }
        if (RemoteSession.enabled && link != null) {
            RemoteConversations.pendingLink = link
            startActivity(Intent(this, MainActivity::class.java)
                .putExtra(MainActivity.EXTRA_OPEN_REMOTE_INVITE, true)
                .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP))
        }
        finish()
    }
}
