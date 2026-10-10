package com.example.apphear.ui.texttoasl

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import com.example.apphear.BuildConfig
import com.example.apphear.domain.texttoasl.AslAnimationAsset
import com.example.apphear.domain.texttoasl.AslAvatarCatalogPolicy
import com.example.apphear.domain.texttoasl.AslSingleAvatarPolicy
import com.example.apphear.domain.texttoasl.SignDictionaryMetadata
import org.json.JSONObject

class TextToAslPlaybackController(
    context: Context,
    private val webView: WebView,
    avatarProfile: SignDictionaryMetadata.AvatarProfile? = null,
) {
    interface ReadyCallback {
        fun onReady()
    }

    interface PlaybackCallback {
        fun onFinished(asset: AslAnimationAsset)
        fun onStarted(asset: AslAnimationAsset) {}
        fun onFailed(asset: AslAnimationAsset) {}
    }

    private val appContext = context.applicationContext
    private val mainHandler = Handler(Looper.getMainLooper())
    private val assetLoader = WebViewAssetLoader.Builder()
        .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(appContext))
        .build()

    private var pendingAsset: AslAnimationAsset? = null
    private var playingAsset: AslAnimationAsset? = null
    private var readyCallback: ReadyCallback? = null
    private var playbackCallback: PlaybackCallback? = null
    private var requestId = 0L
    private var requestedAtMs = 0L
    private var lockedAvatarProfile = avatarProfile ?: AslSingleAvatarPolicy.profile
    private var destroyed = false
    var isReady: Boolean = false
        private set

    init {
        configureWebView()
    }

    fun setReadyCallback(callback: ReadyCallback?) {
        readyCallback = callback
        if (isReady && callback != null) {
            mainHandler.post { if (!destroyed) callback.onReady() }
        }
    }

    fun setPlaybackCallback(callback: PlaybackCallback?) {
        playbackCallback = callback
    }

    fun play(asset: AslAnimationAsset?) {
        if (asset == null || destroyed) return
        if (!AslSingleAvatarPolicy.permits(asset) || !AslAvatarCatalogPolicy.permits(asset, lockedAvatarProfile)) {
            playbackCallback?.onFailed(asset)
            return
        }
        playingAsset = asset
        if (!isReady) {
            pendingAsset = asset
            return
        }
        val url = (BASE_URL + asset.assetPath).replace("'", "\\'")
        if (BuildConfig.ASL_ASSET_PILOT_ENABLED) {
            requestId++
            requestedAtMs = SystemClock.elapsedRealtime()
            val options = JSONObject().apply {
                put("requestId", requestId)
                put("animationName", asset.replacement?.animationName ?: JSONObject.NULL)
                put("loop", asset.type == AslAnimationAsset.Type.POSE && asset.neutralFrameSeconds == null)
                put("neutralFrame", asset.neutralFrameSeconds ?: JSONObject.NULL)
                put("pinSource", asset.type == AslAnimationAsset.Type.POSE)
                // Alphabet clips hold a raised signing posture; the WebView
                // blends only these transitions, never full lexical actions.
                put("fingerspelling", asset.type == AslAnimationAsset.Type.LETTER)
            }
            webView.evaluateJavascript("playSign(${JSONObject.quote(BASE_URL + asset.assetPath)}, $options)", null)
        } else {
            webView.evaluateJavascript("playSign('$url')", null)
        }
    }

    fun preload(asset: AslAnimationAsset?) {
        if (asset == null || !isReady || destroyed) return
        if (!AslSingleAvatarPolicy.permits(asset) || !AslAvatarCatalogPolicy.permits(asset, lockedAvatarProfile)) return
        webView.evaluateJavascript("preloadSign(${JSONObject.quote(BASE_URL + asset.assetPath)})", null)
    }

    fun pause() {
        if (!BuildConfig.ASL_ASSET_PILOT_ENABLED || destroyed) return
        requestId++
        pendingAsset = null
        playingAsset = null
        webView.evaluateJavascript("pausePlayback()", null)
    }

    fun destroy(releaseWebView: Boolean = true) {
        destroyed = true
        requestId++
        mainHandler.removeCallbacksAndMessages(null)
        readyCallback = null
        playbackCallback = null
        pendingAsset = null
        playingAsset = null
        isReady = false
        webView.removeJavascriptInterface(JS_BRIDGE_NAME)
        webView.stopLoading()
        webView.loadUrl("about:blank")
        webView.clearHistory()
        if (releaseWebView) webView.destroy()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.mediaPlaybackRequiresUserGesture = false
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.setSupportMultipleWindows(false)
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.blockNetworkLoads = true

        webView.setBackgroundColor(0xFF0D2020.toInt())
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest,
            ): WebResourceResponse? {
                return assetLoader.shouldInterceptRequest(request.url)
            }
        }
        webView.addJavascriptInterface(JsBridge(), JS_BRIDGE_NAME)
        WebView.setWebContentsDebuggingEnabled(isAppDebuggable())
        val page = if (BuildConfig.ASL_ASSET_PILOT_ENABLED) "model_viewer_pilot.html" else "model_viewer.html"
        webView.loadUrl(BASE_URL + page)
    }


    private fun isAppDebuggable(): Boolean {
        return (appContext.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
    }
    private inner class JsBridge {
        @JavascriptInterface
        fun onViewerReady() {
            Log.d(TAG, "model-viewer ready")
            mainHandler.post {
                if (destroyed) return@post
                if (isReady) return@post
                isReady = true
                readyCallback?.onReady()
                pendingAsset?.let { asset ->
                    pendingAsset = null
                    play(asset)
                }
            }
        }

        @JavascriptInterface
        fun onPlaybackStarted(src: String, token: Long) {
            mainHandler.post {
                if (destroyed) return@post
                val asset = playingAsset ?: return@post
                if (token != requestId || src != BASE_URL + asset.assetPath) return@post
                Log.d(TAG, "Pilot started id=${asset.id} request=$token loadMs=${SystemClock.elapsedRealtime() - requestedAtMs}")
                playbackCallback?.onStarted(asset)
            }
        }

        @JavascriptInterface
        fun onPilotFinished(src: String, token: Long) {
            mainHandler.post {
                if (destroyed) return@post
                val asset = playingAsset ?: return@post
                if (token == requestId && src == BASE_URL + asset.assetPath) {
                    playingAsset = null
                    Log.d(TAG, "Pilot finished id=${asset.id} request=$token")
                    playbackCallback?.onFinished(asset)
                }
            }
        }

        @JavascriptInterface
        fun onModelFailed(src: String, token: Long) {
            mainHandler.post {
                if (destroyed) return@post
                val asset = playingAsset ?: return@post
                if (token != requestId || src != BASE_URL + asset.assetPath) return@post
                playingAsset = null
                Log.w(TAG, "${asset.id} failed; retain selected character and report failure")
                playbackCallback?.onFailed(asset)
            }
        }

        @JavascriptInterface
        fun onModelLoaded(src: String, animationsJson: String) {
            Log.d(TAG, "GLB loaded: $src animations=$animationsJson")
        }

        @JavascriptInterface
        fun onAnimationFinished(src: String) {
            mainHandler.post {
                if (destroyed) return@post
                if (BuildConfig.ASL_ASSET_PILOT_ENABLED) return@post
                val asset = playingAsset ?: return@post
                val expectedUrl = BASE_URL + asset.assetPath
                if (src == expectedUrl) {
                    playbackCallback?.onFinished(asset)
                }
            }
        }
    }

    private companion object {
        const val TAG = "TextToAslPlayback"
        const val JS_BRIDGE_NAME = "Android"
        const val BASE_URL = "https://appassets.androidplatform.net/assets/"
    }
}
