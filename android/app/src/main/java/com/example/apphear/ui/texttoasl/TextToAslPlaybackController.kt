package com.example.apphear.ui.texttoasl

import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.ApplicationInfo
import android.os.Handler
import android.os.Looper
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
import org.json.JSONObject

class TextToAslPlaybackController(context: Context, private val webView: WebView) {
    interface ReadyCallback { fun onReady() }
    interface PlaybackCallback {
        fun onFinished(asset: AslAnimationAsset)
        fun onStarted(asset: AslAnimationAsset) {}
        fun onError(message: String) {}
    }

    private val appContext = context.applicationContext
    private val handler = Handler(Looper.getMainLooper())
    private val loader = WebViewAssetLoader.Builder()
        .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(appContext)).build()
    private var readyCallback: ReadyCallback? = null
    private var playbackCallback: PlaybackCallback? = null
    private var playing: AslAnimationAsset? = null
    private var pending: AslAnimationAsset? = null
    private var generation = 0L
    private var destroyed = false
    private var speed = 1.0
    var isReady = false
        private set

    init { configureWebView() }

    fun setReadyCallback(callback: ReadyCallback?) {
        readyCallback = callback
        if (isReady) handler.post { if (!destroyed) callback?.onReady() }
    }
    fun setPlaybackCallback(callback: PlaybackCallback?) { playbackCallback = callback }

    fun play(asset: AslAnimationAsset?) {
        if (asset == null || destroyed) return
        if (!isReady) { pending = asset; return }
        generation++
        playing = asset
        val url = JSONObject.quote(BASE_URL + asset.assetPath)
        if (BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED) {
            val clipName = JSONObject.quote(asset.animationName)
            val loop = asset.type == AslAnimationAsset.Type.POSE
            webView.evaluateJavascript("playSign($url, $generation, $clipName, $loop)", null)
            setSpeed(speed)
        } else {
            webView.evaluateJavascript("playSign($url)", null)
        }
    }

    fun preload(asset: AslAnimationAsset?) {
        // A single viewer keeps mobile memory bounded and avoids autoplaying preloads.
        if (!BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED && asset != null && isReady) {
            webView.evaluateJavascript("preloadSign(" + JSONObject.quote(BASE_URL + asset.assetPath) + ")", null)
        }
    }

    fun stop() {
        generation++
        pending = null
        playing = null
        if (isReady && !destroyed && BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED) {
            webView.evaluateJavascript("stopSign($generation)", null)
        }
    }
    fun setPaused(paused: Boolean) {
        if (isReady && !destroyed && BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED) {
            webView.evaluateJavascript("pauseSign($paused)", null)
        }
    }
    fun setSpeed(value: Double) {
        speed = value.coerceIn(0.5, 1.5)
        if (isReady && !destroyed && BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED) {
            webView.evaluateJavascript("setSignSpeed($speed)", null)
        }
    }
    fun destroy() {
        stop()
        destroyed = true
        isReady = false
        readyCallback = null
        playbackCallback = null
        handler.removeCallbacksAndMessages(null)
        webView.removeJavascriptInterface("Android")
        webView.stopLoading()
        webView.loadUrl("about:blank")
        webView.destroy()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            allowFileAccess = false
            allowContentAccess = false
            setSupportMultipleWindows(false)
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            blockNetworkLoads = true
        }
        webView.setBackgroundColor(0xFF0D2020.toInt())
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? =
                loader.shouldInterceptRequest(request.url)
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                request.url.scheme != "https" || request.url.host != "appassets.androidplatform.net"
        }
        webView.addJavascriptInterface(JsBridge(), "Android")
        WebView.setWebContentsDebuggingEnabled(
            appContext.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE != 0)
        val page = if (BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED) "model_viewer.html" else "model_viewer_legacy.html"
        webView.loadUrl(BASE_URL + page)
    }

    private inner class JsBridge {
        @JavascriptInterface fun onViewerReady() {
            handler.post {
                if (destroyed) return@post
                isReady = true
                readyCallback?.onReady()
                pending?.let { pending = null; play(it) }
            }
        }
        @JavascriptInterface fun onPlaybackStarted(token: Long) {
            handler.post {
                if (!destroyed && token == generation) playing?.let { playbackCallback?.onStarted(it) }
            }
        }
        @JavascriptInterface fun onPlaybackFinished(token: Long) {
            handler.post {
                if (!destroyed && token == generation) {
                    val asset = playing ?: return@post
                    playing = null
                    playbackCallback?.onFinished(asset)
                }
            }
        }
        @JavascriptInterface fun onPlaybackError(token: Long, message: String) {
            handler.post {
                if (!destroyed && (token == generation || token == -1L)) {
                    playing = null
                    pending = null
                    if (token == -1L) isReady = false
                    playbackCallback?.onError(message)
                }
            }
        }
        // Original viewer protocol is retained solely for the rollback flag.
        @JavascriptInterface fun onModelLoaded(src: String, animationsJson: String) {}
        @JavascriptInterface fun onAnimationFinished(src: String) {
            handler.post {
                if (!BuildConfig.TEXT_TO_ASL_REDESIGN_ENABLED && !destroyed) {
                    playing?.takeIf { BASE_URL + it.assetPath == src }?.let {
                        playing = null
                        playbackCallback?.onFinished(it)
                    }
                }
            }
        }
    }

    private companion object { const val BASE_URL = "https://appassets.androidplatform.net/assets/" }
}

