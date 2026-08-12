package com.example.apphear.ui.texttoasl

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.webkit.WebViewAssetLoader
import com.example.apphear.domain.texttoasl.AslAnimationAsset

class TextToAslPlaybackController(
    context: Context,
    private val webView: WebView,
) {
    interface ReadyCallback {
        fun onReady()
    }

    interface PlaybackCallback {
        fun onFinished(asset: AslAnimationAsset)
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
    var isReady: Boolean = false
        private set

    init {
        configureWebView()
    }

    fun setReadyCallback(callback: ReadyCallback?) {
        readyCallback = callback
        if (isReady && callback != null) {
            mainHandler.post { callback.onReady() }
        }
    }

    fun setPlaybackCallback(callback: PlaybackCallback?) {
        playbackCallback = callback
    }

    fun play(asset: AslAnimationAsset?) {
        if (asset == null) return
        playingAsset = asset
        if (!isReady) {
            pendingAsset = asset
            return
        }
        val url = (BASE_URL + asset.assetPath).replace("'", "\\'")
        webView.evaluateJavascript("playSign('$url')", null)
    }

    fun preload(asset: AslAnimationAsset?) {
        if (asset == null || !isReady) return
        val url = (BASE_URL + asset.assetPath).replace("'", "\\'")
        webView.evaluateJavascript("preloadSign('$url')", null)
    }

    fun destroy() {
        readyCallback = null
        playbackCallback = null
        pendingAsset = null
        playingAsset = null
        isReady = false
        webView.removeJavascriptInterface(JS_BRIDGE_NAME)
        webView.stopLoading()
        webView.loadUrl("about:blank")
        webView.clearHistory()
        webView.destroy()
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
        webView.loadUrl(BASE_URL + "model_viewer.html")
    }


    private fun isAppDebuggable(): Boolean {
        return (appContext.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0
    }
    private inner class JsBridge {
        @JavascriptInterface
        fun onViewerReady() {
            Log.d(TAG, "model-viewer ready")
            isReady = true
            mainHandler.post {
                readyCallback?.onReady()
                pendingAsset?.let { asset ->
                    pendingAsset = null
                    play(asset)
                }
            }
        }

        @JavascriptInterface
        fun onModelLoaded(src: String, animationsJson: String) {
            Log.d(TAG, "GLB loaded: $src animations=$animationsJson")
        }

        @JavascriptInterface
        fun onAnimationFinished(src: String) {
            mainHandler.post {
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