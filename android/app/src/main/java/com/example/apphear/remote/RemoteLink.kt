package com.example.apphear.remote

import kotlinx.coroutines.flow.StateFlow

/**
 * One phone's side of a remote conversation, whatever carries it: the AppHear server
 * ([RemoteSession]) or a direct phone-to-phone link with no internet ([NearbySession]).
 * Main-thread API.
 */
interface RemoteLink {
    val state: StateFlow<RemoteState>

    /** Viewer: the newest message already signed on this phone (survives screens being recreated). */
    var playedSeq: Long

    /** A screen showing this conversation became visible / hidden (counted; screens can overlap). */
    fun attach()
    fun detach()

    /** Host: sends typed or spoken text to the viewer. Ignored unless connected. */
    fun send(text: String)
    /** Viewer: everything up to [seq] has been shown. */
    fun markSeen(seq: Long)
    /** Host: replaces an expired invite. */
    fun renewInvite()
    /** Ends the conversation on both phones. */
    fun end()
    /** Releases everything; the link is not used afterwards. */
    fun close()
}
