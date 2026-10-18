// Pilot-only playback. Original player remains the flag-off path.
const viewers = [document.getElementById('viewerA'), document.getElementById('viewerB')];
let activeIndex = 0;
let pendingRequest = null;
let queuedPreload = null;
let lastRequest = 0;
let releaseTimer = null;
let completionFrame = null;
let pinnedSource = null;
const LOAD_TIMEOUT_MS = 20_000;
const FADE_MS = 0;

function finishSign(viewer) {
  if (viewer.playLoop || viewer !== viewers[activeIndex] || viewer.playRequest == null ||
      viewer.playRequest !== lastRequest) return;
  // Late/early mixer events cannot finish the current named clip.
  if (!(viewer.duration > 0) || viewer.currentTime + 0.001 < viewer.duration) return;
  const token = viewer.playRequest;
  viewer.pause();
  viewer.playRequest = null;
  cancelAnimationFrame(completionFrame);
  completionFrame = null;
  if (window.Android) Android.onPilotFinished(viewer.src, token);
}

function watchCompletion(viewer, options) {
  if (options.loop || options.neutralFrame != null) return;
  // Model-viewer 4.3.1 subscribes to mixers before they exist. Use its public
  // animation timeline, not elapsed wall time, when its finished event is absent.
  const check = () => {
    if (viewer.playRequest !== lastRequest || lastRequest !== options.requestId) return;
    if (viewer.duration > 0 && viewer.currentTime >= viewer.duration) {
      finishSign(viewer);
      return;
    }
    completionFrame = requestAnimationFrame(check);
  };
  completionFrame = requestAnimationFrame(check);
}

customElements.whenDefined('model-viewer').then(() => {
  customElements.get('model-viewer').modelCacheSize = 0;
  viewers.forEach(v => v.classList.add('defined'));
  if (window.Android) Android.onViewerReady();
});

viewers.forEach(viewer => {
  viewer.addEventListener('load', () => {
    viewer.pause();
    // A cancelled cold model switch can dispatch load before its animations exist.
    // Treat that as incomplete so the next real load, rather than an empty clip list,
    // settles the waiting request.
    viewer.loadedSource = viewer.loaded && (viewer.availableAnimations || []).length > 0 ? viewer.src : null;
    viewer.failedUrl = null;
    if (viewer.loadedSource && window.Android) {
      Android.onModelLoaded(viewer.src, JSON.stringify(viewer.availableAnimations));
    }
  });
  viewer.addEventListener('error', () => {viewer.failedUrl = viewer.src;});
  viewer.addEventListener('finished', () => {
    finishSign(viewer);
  });
});

function waitForModel(viewer, url) {
  if (viewer.src === url && viewer.loaded && viewer.loadedSource === url) return Promise.resolve();
  // An explicit Repeat may retry a failed load; keep the visible character intact.
  if (viewer.src === url && viewer.failedUrl === url) {
    viewer.removeAttribute('src'); viewer.failedUrl = null; viewer.loadedSource = null;
  }
  return new Promise((resolve, reject) => {
    const clean = () => {
      clearTimeout(timer);
      viewer.removeEventListener('load', onLoad);
      viewer.removeEventListener('error', onError);
      viewer.cancelWait = null;
    };
    const onLoad = () => {if (viewer.src === url && viewer.loaded && viewer.loadedSource === url) {clean(); resolve();}};
    const onError = () => {clean(); reject(new Error('Model load failed'));};
    const timer = setTimeout(() => {clean(); reject(new Error('Model load timed out'));}, LOAD_TIMEOUT_MS);
    viewer.cancelWait = () => {clean(); reject(new Error('Playback cancelled'));};
    viewer.addEventListener('load', onLoad);
    viewer.addEventListener('error', onError);
    if (viewer.src !== url) {viewer.loadedSource = null; viewer.failedUrl = null; viewer.src = url;}
  });
}

async function replay(viewer, options) {
  const animations = viewer.availableAnimations || [];
  // Shared bundles supply a name; unnamed legacy files must have one action.
  const neutral = options.neutralFrame != null;
  const relaxed = neutral && animations.includes('SIGN_RELAXED_NEUTRAL');
  const name = relaxed ? 'SIGN_RELAXED_NEUTRAL' : options.animationName || (animations.length === 1 ? animations[0] : null);
  if (!name || !animations.includes(name)) throw new Error('Expected animation missing');
  const previous = viewer.animationName;
  const held = viewer.currentTime;
  const previousDuration = viewer.duration;
  const transition = options.fingerspelling ? 0.12 : relaxed && viewer.lastSigningLetter ? 0.22 : 0;
  // In bundled model-viewer 4.3.1, currentTime resets the entire mixer clock.
  // Scheduling a crossfade BEFORE that seek leaves the new letter at weight 0
  // and old idle/letters at weight 1. Clear cached actions while paused, seek,
  // then schedule a bounded outgoing-pose fade using the public append API.
  viewer.pause();
  viewer.animationCrossfadeDuration = 0;
  if (viewer.animationName === name) {
    // A repeated letter must reset cached actions too; Lit skips equal names.
    viewer.animationName = undefined;
    await viewer.updateComplete;
  }
  viewer.animationName = name;
  // Lit's animationName update otherwise replaces explicit loop settings with Infinity.
  await viewer.updateComplete;
  if (lastRequest !== options.requestId) return false;
  viewer.currentTime = neutral ? options.neutralFrame : 0;
  viewer.playLoop = Boolean(options.loop) || neutral;
  viewer.playRequest = neutral ? null : options.requestId;
  if (!neutral || relaxed) {
    viewer.play({repetitions: options.loop || relaxed ? Infinity : 1});
    if (transition && previous && previous !== name && animations.includes(previous)) {
      // Clamp the outgoing clip at its own endpoint. Do not freeze its cached
      // timeScale: that would prevent that letter moving on a later request.
      viewer.appendAnimation(previous, {time: Math.min(held, previousDuration - 0.0001),
        timeScale: 1, repetitions: 1, weight: 1, fade: false});
      viewer.detachAnimation(previous, {fade: transition});
    }
  }
  viewer.lastSigningLetter = Boolean(options.fingerspelling);
  if (options.pinSource) pinnedSource = viewer.src;
  if (window.Android) Android.onPlaybackStarted(viewer.src, options.requestId);
  return true;
}

window.playSign = async function(url, options) {
  cancelAnimationFrame(completionFrame);
  completionFrame = null;
  lastRequest = options.requestId;
  clearTimeout(releaseTimer);
  releaseTimer = null;
  viewers.forEach(v => {v.cancelWait?.(); v.pause();});
  pendingRequest = options.requestId;
  // A newly submitted phrase must not inherit the old phrase's next-sign preload.
  queuedPreload = null;
  const old = viewers[activeIndex];
  const inactive = viewers[1 - activeIndex];
  // Keep the large New-character bundle resident while playing original-only
  // signs. Reloading it after every mixed phrase can time out on phones.
  const keepPinnedInactive = pinnedSource && inactive.src === pinnedSource &&
    inactive.loaded && inactive.loadedSource === pinnedSource && url !== pinnedSource;
  const index = old.src === url && old.loaded && old.loadedSource === url || keepPinnedInactive
    ? activeIndex : 1 - activeIndex;
  const next = viewers[index];
  try {
    await waitForModel(next, url);
    if (lastRequest !== options.requestId) return;
    if (!await replay(next, options)) return;
    next.classList.add('active');
    if (next !== old) old.classList.remove('active');
    activeIndex = index;
    watchCompletion(next, options);
    pendingRequest = null;
    releaseTimer = setTimeout(() => {
      if (lastRequest !== options.requestId) return;
      releaseTimer = null;
      const inactive = viewers[1 - activeIndex];
      // Retain the most recently used original alongside the shared New model.
      // Re-adding a released URL timed out on the target WebView during Replay.
      // There are only two viewers, so residency remains bounded.
      if (!pinnedSource) {
        inactive.pause();
        inactive.loadedSource = null;
        inactive.removeAttribute('src');
      }
      const preload = queuedPreload;
      queuedPreload = null;
      if (preload) window.preloadSign(preload);
    }, FADE_MS);
  } catch (error) {
    if (lastRequest !== options.requestId) return;
    if (pinnedSource === url) pinnedSource = null;
    pendingRequest = null;
    queuedPreload = null;
    console.warn('Pilot load/play failed', url, error.message);
    if (window.Android) Android.onModelFailed(url, options.requestId);
  }
};

window.preloadSign = function(url) {
  if (viewers[activeIndex].src === url) return;
  if (pendingRequest !== null || releaseTimer !== null) {queuedPreload = url; return;}
  const next = viewers[1 - activeIndex];
  // A cold viewer's src is null like an unset pin; only a real pin blocks the preload.
  if (pinnedSource && next.src === pinnedSource && url !== pinnedSource) return;
  next.pause();
  if (next.src !== url) {next.loadedSource = null; next.failedUrl = null; next.src = url;}
};

window.pausePlayback = function() {
  cancelAnimationFrame(completionFrame);
  completionFrame = null;
  lastRequest = -1;
  pendingRequest = null;
  queuedPreload = null;
  clearTimeout(releaseTimer);
  releaseTimer = null;
  // Pause invalidates callbacks, but retains the two bounded resident models.
  // Only WebView destruction releases them; unsupported input cannot change character.
  viewers.forEach(v => {v.cancelWait?.(); v.pause(); v.playRequest = null;});
};
