import WaveSurfer from './vendor/wavesurfer.esm.js';
import TimelinePlugin from './vendor/wavesurfer-timeline.esm.js';

let wavesurfer = null;
let lastInitSignature = null;
let pxPerSec = 100;
let duration = 0;
let currentCaptions = []; // [{id, text, start, end}]
let timelineInitialized = false;
let nextCaptionId = 1;

const REGION_COLORS = [
  'rgba(91, 141, 239, 0.55)',
  'rgba(233, 121, 178, 0.55)',
  'rgba(96, 201, 165, 0.55)',
  'rgba(240, 173, 78, 0.55)',
];

const POSITION_BOTTOM = { top: 'auto', bottom: '8%' };
const POSITION_TOP = { top: '10%', bottom: 'auto' };
const POSITION_CENTER = { top: '50%', bottom: 'auto', transform: 'translateY(-50%)' };

let currentCaptionStyle = {
  fontFamily: 'Montserrat',
  fontSize: 76,
  textColor: '#ffffff',
  strokeColor: '#000000',
  strokeEnabled: true,
  background: 'none',
  position: 'bottom',
  frameWidth: 1920,
  animation: 'pop',
  popIntensity: 65,
};

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function colorForId(id) {
  return REGION_COLORS[id % REGION_COLORS.length];
}

// ---- Live style overlay on the preview video (unchanged contract from before) ----

function applyOverlayVisualStyle(overlay, videoEl) {
  const s = currentCaptionStyle;
  const displayWidth = (videoEl && videoEl.clientWidth) || s.frameWidth;
  const scaledFontSize = Math.max(10, Math.round(s.fontSize * (displayWidth / s.frameWidth)));

  overlay.style.fontFamily = `'${s.fontFamily}', sans-serif`;
  overlay.style.fontSize = scaledFontSize + 'px';
  overlay.style.fontWeight = '900';
  overlay.style.color = s.textColor;
  overlay.style.textShadow = s.strokeEnabled
    ? `-2px -2px 0 ${s.strokeColor}, 2px -2px 0 ${s.strokeColor}, -2px 2px 0 ${s.strokeColor}, 2px 2px 0 ${s.strokeColor}, 0 4px 10px rgba(0,0,0,0.6)`
    : '0 4px 10px rgba(0,0,0,0.6)';

  if (s.background === 'box') {
    overlay.style.background = 'rgba(0,0,0,0.65)';
    overlay.style.borderRadius = '8px';
    overlay.style.padding = '4px 14px';
    overlay.style.display = 'inline-block';
    overlay.style.left = '50%';
    overlay.style.right = 'auto';
    overlay.style.transform = 'translateX(-50%)';
    overlay.style.maxWidth = '85%';
  } else {
    overlay.style.background = 'transparent';
    overlay.style.padding = '0 6%';
    overlay.style.display = 'block';
    overlay.style.left = '0';
    overlay.style.right = '0';
    overlay.style.transform = '';
    overlay.style.maxWidth = 'none';
  }

  const pos = s.position === 'top' ? POSITION_TOP : s.position === 'center' ? POSITION_CENTER : POSITION_BOTTOM;
  overlay.style.top = pos.top;
  overlay.style.bottom = pos.bottom;
  if (s.background !== 'box') {
    overlay.style.transform = pos.transform || '';
  }
}

function applyVideoAspectRatio() {
  const wrap = document.querySelector('.timeline-video-wrap');
  if (!wrap) return;
  const frameWidth = currentCaptionStyle.frameWidth;
  const frameHeight = frameWidth === 1080 ? 1920 : 1080;

  // Computed explicitly in JS rather than via CSS aspect-ratio: aspect-ratio combined
  // with a definite width and a max-height that ends up binding doesn't reliably
  // shrink both dimensions together across browsers — it can produce a square instead
  // of the intended ratio. Explicit pixel math sidesteps that entirely.
  const maxBox = 480;
  const availableWidth = Math.min(maxBox, (wrap.parentElement && wrap.parentElement.clientWidth) || maxBox);
  const scale = Math.min(availableWidth / frameWidth, maxBox / frameHeight);

  wrap.style.width = Math.round(frameWidth * scale) + 'px';
  wrap.style.height = Math.round(frameHeight * scale) + 'px';
}

function updateCaptionOverlayNow() {
  applyVideoAspectRatio();
  const videoEl = document.getElementById('timeline-video');
  if (videoEl) updateCaptionOverlay(videoEl);
}

function ensureOverlayTextSpan(overlay) {
  let span = overlay.querySelector('.timeline-caption-overlay-text');
  if (!span) {
    overlay.innerHTML = '';
    span = document.createElement('span');
    span.className = 'timeline-caption-overlay-text';
    span.style.display = 'inline-block';
    overlay.appendChild(span);
  }
  return span;
}

// Mirrors the entrance animations Caption.tsx applies in the real render, so the
// live preview isn't just a static style swatch — it actually shows how the pop/
// fade/slide will look, including the same pop-intensity-controlled scale range.
function playEntranceAnimation(span) {
  if (span.getAnimations) {
    span.getAnimations().forEach((a) => a.cancel());
  }
  const s = currentCaptionStyle;
  const anim = s.animation || 'pop';

  if (anim === 'fade') {
    span.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: 'ease-out', fill: 'backwards' });
  } else if (anim === 'slide') {
    span.animate(
      [
        { opacity: 0, transform: 'translateY(30px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ],
      { duration: 260, easing: 'ease-out', fill: 'backwards' }
    );
  } else {
    // Same formula as Caption.tsx's pop animation, so popIntensity looks identical
    // in the live preview and the final render.
    const intensity = s.popIntensity ?? 65;
    const startScale = 1 - (intensity / 100) * 0.9;
    const overshoot = startScale + 1.155 * (1 - startScale);
    const dip = startScale + 0.97 * (1 - startScale);
    span.animate(
      [
        { opacity: 0, transform: `scale(${startScale})` },
        { opacity: 1, transform: `scale(${overshoot})`, offset: 0.4 },
        { opacity: 1, transform: `scale(${dip})`, offset: 0.7 },
        { opacity: 1, transform: 'scale(1)' },
      ],
      { duration: 420, easing: 'ease-out', fill: 'backwards' }
    );
  }
}

let lastOverlayCaptionId = null;

function updateCaptionOverlay(videoEl) {
  const overlay = document.getElementById('timeline-caption-overlay');
  if (!overlay) return;
  applyOverlayVisualStyle(overlay, videoEl);
  const span = ensureOverlayTextSpan(overlay);

  const t = videoEl.currentTime;
  const active = currentCaptions.find((c) => t >= c.start && t <= c.end);
  // While the playhead isn't over any caption (e.g. still paused at 0:00 right after
  // transcribing), fall back to showing the first caption statically instead of
  // nothing at all — otherwise a style tweak like text color looks like it did
  // nothing just because there happened to be no caption under the playhead.
  const displayCaption = active || (videoEl.paused ? currentCaptions[0] : null);
  const activeId = displayCaption ? displayCaption.id : null;

  if (activeId !== lastOverlayCaptionId) {
    lastOverlayCaptionId = activeId;
    span.textContent = displayCaption ? displayCaption.text : '';
    if (active) playEntranceAnimation(span);
  } else if (displayCaption) {
    // Same caption still showing (e.g. its text was just edited) — update without
    // replaying the entrance animation.
    span.textContent = displayCaption.text;
  }
}

window.__updateCaptionStyle = function (style) {
  currentCaptionStyle = Object.assign({}, currentCaptionStyle, style);
  updateCaptionOverlayNow();
};

// ---- Track 1: video thumbnail filmstrip ----

function renderFilmstrip(videoEl, container, dur, px) {
  container.innerHTML = '';
  const totalWidth = Math.max(dur * px, 1);
  container.style.width = totalWidth + 'px';

  const thumbWidth = 80;
  const thumbHeight = 45;
  const count = Math.max(1, Math.round(totalWidth / thumbWidth));
  const interval = dur / count;

  const hiddenVideo = document.createElement('video');
  hiddenVideo.src = videoEl.currentSrc || videoEl.src;
  hiddenVideo.muted = true;
  hiddenVideo.preload = 'auto';
  hiddenVideo.style.cssText = 'position:absolute;width:1px;height:1px;opacity:0;pointer-events:none;';
  document.body.appendChild(hiddenVideo);

  const canvas = document.createElement('canvas');
  canvas.width = thumbWidth;
  canvas.height = thumbHeight;
  const ctx = canvas.getContext('2d');

  let i = 0;
  function captureNext() {
    if (i >= count) {
      hiddenVideo.remove();
      return;
    }
    const t = Math.min(i * interval, Math.max(dur - 0.05, 0));
    i++;
    hiddenVideo.currentTime = t;
  }

  hiddenVideo.addEventListener('loadedmetadata', captureNext);
  hiddenVideo.addEventListener('seeked', () => {
    try {
      ctx.drawImage(hiddenVideo, 0, 0, thumbWidth, thumbHeight);
      const img = document.createElement('img');
      img.className = 'timeline-thumb';
      img.style.width = thumbWidth + 'px';
      img.style.height = thumbHeight + 'px';
      img.src = canvas.toDataURL('image/jpeg', 0.6);
      container.appendChild(img);
    } catch (e) {
      console.error('[timeline] thumbnail capture failed', e);
    }
    captureNext();
  });
}

// ---- Track 2: audio waveform ----

function renderWaveform(videoEl, container, px) {
  if (wavesurfer) {
    wavesurfer.destroy();
    wavesurfer = null;
  }
  wavesurfer = WaveSurfer.create({
    container,
    media: videoEl,
    url: videoEl.currentSrc || videoEl.src,
    waveColor: '#5b8def',
    progressColor: '#2f5fb3',
    cursorColor: '#ffffff',
    cursorWidth: 2,
    height: 56,
    normalize: true,
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    fillParent: false,
    minPxPerSec: px,
    hideScrollbar: true,
    autoScroll: false,
    plugins: [
      TimelinePlugin.create({
        height: 20,
        style: { color: '#9fb4d8', fontSize: '10px' },
      }),
    ],
  });
  wavesurfer.on('error', (err) => console.error('[timeline] wavesurfer error', err));
}

// ---- Track 3: captions (custom-built, not the Regions plugin) ----

function positionBlock(block, cap, px) {
  block.style.left = cap.start * px + 'px';
  block.style.width = Math.max((cap.end - cap.start) * px, 6) + 'px';
}

// Real mice/trackpads have enough hand-tremor during a "simple click" that a tight
// threshold here misclassifies clicks as micro-drags, silently preventing text edit
// mode from ever engaging. 10px is a much more forgiving, commonly-used threshold.
const CLICK_THRESHOLD_PX = 10;

function wireDrag(block, cap, leftHandle, rightHandle, textEl, getPx, getDur) {
  let mode = null;
  let startClientX = 0;
  let startCap = null;
  let moved = false;
  let downTarget = null;

  function onDown(e, m) {
    mode = m;
    startClientX = e.clientX;
    startCap = { start: cap.start, end: cap.end };
    moved = false;
    downTarget = e.target;
    block.setPointerCapture(e.pointerId);
    e.stopPropagation();
  }

  block.addEventListener('pointerdown', (e) => onDown(e, 'move'));
  leftHandle.addEventListener('pointerdown', (e) => onDown(e, 'resize-left'));
  rightHandle.addEventListener('pointerdown', (e) => onDown(e, 'resize-right'));

  block.addEventListener('pointermove', (e) => {
    if (!mode) return;
    const dx = e.clientX - startClientX;
    if (!moved && Math.abs(dx) < CLICK_THRESHOLD_PX) return;
    moved = true;

    const px = getPx();
    const dur = getDur();
    const dt = dx / px;
    if (mode === 'move') {
      const length = startCap.end - startCap.start;
      const newStart = clamp(startCap.start + dt, 0, Math.max(dur - length, 0));
      cap.start = newStart;
      cap.end = newStart + length;
    } else if (mode === 'resize-left') {
      cap.start = clamp(Math.min(startCap.start + dt, cap.end - 0.05), 0, dur);
    } else if (mode === 'resize-right') {
      cap.end = clamp(Math.max(startCap.end + dt, cap.start + 0.05), 0, dur);
    }
    positionBlock(block, cap, px);
  });

  function onUp() {
    if (!mode) return;
    const wasClick = !moved;
    const clickedText = downTarget === textEl || textEl.contains(downTarget);
    mode = null;
    if (wasClick && clickedText) {
      openEditPopup(block, cap, textEl);
    }
    updateCaptionOverlayNow();
  }
  block.addEventListener('pointerup', onUp);
  block.addEventListener('pointercancel', onUp);
}

// A floating popup for editing caption text, instead of expanding the text in place —
// the caption block is deliberately small/clipped (overflow: hidden) so blocks don't
// visually collide, which means in-place expansion just gets clipped right back off.
// A popup that lives outside that clipped hierarchy is the only way to reliably show
// (and edit) the full text regardless of how narrow the block is.
let activeEditPopup = null;

function closeEditPopup() {
  if (activeEditPopup) {
    activeEditPopup.remove();
    activeEditPopup = null;
  }
}

function openEditPopup(block, cap, textEl) {
  closeEditPopup();

  const rect = block.getBoundingClientRect();
  const popup = document.createElement('div');
  popup.className = 'timeline-caption-edit-popup';
  popup.style.left = Math.max(8, rect.left) + 'px';
  popup.style.top = Math.max(8, rect.top) + 'px';

  const editArea = document.createElement('div');
  editArea.className = 'timeline-caption-edit-popup-text';
  editArea.contentEditable = 'true';
  editArea.spellcheck = false;
  editArea.textContent = cap.text;

  function commit() {
    cap.text = editArea.textContent;
    textEl.textContent = cap.text;
    textEl.title = cap.text;
    updateCaptionOverlayNow();
  }

  editArea.addEventListener('input', commit);
  editArea.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' || (e.key === 'Enter' && !e.shiftKey)) {
      e.preventDefault();
      commit();
      closeEditPopup();
    }
  });

  popup.appendChild(editArea);
  document.body.appendChild(popup);
  activeEditPopup = popup;

  // Keep the popup on-screen if the block is near the right/bottom edge.
  const popupRect = popup.getBoundingClientRect();
  if (popupRect.right > window.innerWidth - 8) {
    popup.style.left = Math.max(8, window.innerWidth - popupRect.width - 8) + 'px';
  }
  if (popupRect.bottom > window.innerHeight - 8) {
    popup.style.top = Math.max(8, rect.top - popupRect.height - 8) + 'px';
  }

  requestAnimationFrame(() => {
    editArea.focus();
    document.execCommand && document.execCommand('selectAll', false, null);
  });

  setTimeout(() => {
    document.addEventListener('pointerdown', function onOutside(e) {
      if (popup.contains(e.target)) return;
      document.removeEventListener('pointerdown', onOutside);
      commit();
      closeEditPopup();
    });
  }, 0);
}

function buildCaptionBlock(cap, getPx, getDur) {
  const block = document.createElement('div');
  block.className = 'timeline-caption-block';
  block.style.background = colorForId(cap.id);
  positionBlock(block, cap, getPx());

  const leftHandle = document.createElement('div');
  leftHandle.className = 'timeline-caption-handle timeline-caption-handle-left';

  const textEl = document.createElement('div');
  textEl.className = 'timeline-caption-text';
  textEl.spellcheck = false;
  textEl.textContent = cap.text;
  textEl.title = cap.text; // hover to see the full text; click opens the full editor popup
  // Deliberately does NOT stop propagation here — pointer events need to bubble up to
  // the block's own handler so both "click to edit" and "click-and-drag to move" work
  // when the pointer happens to come down on the text specifically.

  const deleteBtn = document.createElement('button');
  deleteBtn.type = 'button';
  deleteBtn.className = 'timeline-caption-delete';
  deleteBtn.textContent = '×';
  deleteBtn.title = 'Delete caption';
  deleteBtn.addEventListener('pointerdown', (e) => e.stopPropagation());
  deleteBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    currentCaptions = currentCaptions.filter((c) => c.id !== cap.id);
    block.remove();
    updateCaptionOverlayNow();
  });

  const rightHandle = document.createElement('div');
  rightHandle.className = 'timeline-caption-handle timeline-caption-handle-right';

  block.appendChild(leftHandle);
  block.appendChild(textEl);
  block.appendChild(deleteBtn);
  block.appendChild(rightHandle);

  wireDrag(block, cap, leftHandle, rightHandle, textEl, getPx, getDur);
  return block;
}

function renderCaptionsTrack(container, dur, px) {
  container.innerHTML = '';
  container.style.width = Math.max(dur * px, 1) + 'px';

  const getPx = () => pxPerSec;
  const getDur = () => duration;

  currentCaptions.forEach((cap) => container.appendChild(buildCaptionBlock(cap, getPx, getDur)));

  let creating = null;
  container.addEventListener('pointerdown', (e) => {
    if (e.target !== container) return;
    const rect = container.getBoundingClientRect();
    const startTime = clamp((e.clientX - rect.left) / getPx(), 0, getDur());
    const cap = { id: nextCaptionId++, text: '', start: startTime, end: startTime };
    currentCaptions.push(cap);
    const block = buildCaptionBlock(cap, getPx, getDur);
    container.appendChild(block);
    creating = { cap, block, startTime };
  });
  container.addEventListener('pointermove', (e) => {
    if (!creating) return;
    const rect = container.getBoundingClientRect();
    const t = clamp((e.clientX - rect.left) / getPx(), 0, getDur());
    creating.cap.start = Math.min(creating.startTime, t);
    creating.cap.end = Math.max(creating.startTime, t);
    positionBlock(creating.block, creating.cap, getPx());
  });
  window.addEventListener('pointerup', () => {
    if (!creating) return;
    if (creating.cap.end - creating.cap.start < 0.05) {
      currentCaptions = currentCaptions.filter((c) => c.id !== creating.cap.id);
      creating.block.remove();
    } else {
      updateCaptionOverlayNow();
    }
    creating = null;
  });
}

// ---- Zoom (shared pixels-per-second across all three tracks) ----

function reRenderTracks(videoEl) {
  const filmstripEl = document.getElementById('filmstrip-track');
  const waveformEl = document.getElementById('waveform-track');
  const captionsEl = document.getElementById('captions-track');
  if (!filmstripEl || !waveformEl || !captionsEl) return;
  renderFilmstrip(videoEl, filmstripEl, duration, pxPerSec);
  renderWaveform(videoEl, waveformEl, pxPerSec);
  renderCaptionsTrack(captionsEl, duration, pxPerSec);
}

function setZoom(videoEl, newPx) {
  pxPerSec = clamp(newPx, 20, 400);
  reRenderTracks(videoEl);
}

function wireZoomButtons(videoEl) {
  const zoomIn = document.getElementById('timeline-zoom-in');
  const zoomOut = document.getElementById('timeline-zoom-out');
  if (zoomIn && !zoomIn.dataset.wired) {
    zoomIn.dataset.wired = '1';
    zoomIn.addEventListener('click', () => setZoom(videoEl, pxPerSec * 1.4));
  }
  if (zoomOut && !zoomOut.dataset.wired) {
    zoomOut.dataset.wired = '1';
    zoomOut.addEventListener('click', () => setZoom(videoEl, pxPerSec / 1.4));
  }
}

// ---- Entry points called from app.py ----

function waitForVideoReady(maxAttempts, callback) {
  const videoEl = document.getElementById('timeline-video');
  const tracksReady = document.getElementById('filmstrip-track') && document.getElementById('waveform-track') && document.getElementById('captions-track');
  if (videoEl && tracksReady && isFinite(videoEl.duration) && videoEl.duration > 0) {
    callback(videoEl);
    return;
  }
  if (maxAttempts <= 0) {
    console.error('[timeline] timeline-video/tracks not ready after waiting');
    return;
  }
  setTimeout(() => waitForVideoReady(maxAttempts - 1, callback), 150);
}

window.__initCaptionTimeline = function (captions) {
  waitForVideoReady(60, (videoEl) => {
    const signature = JSON.stringify({ src: videoEl.currentSrc || videoEl.src, captions });
    if (wavesurfer && signature === lastInitSignature) {
      timelineInitialized = true;
      return;
    }
    lastInitSignature = signature;

    duration = videoEl.duration;
    currentCaptions = (captions || []).map((c) => ({
      id: nextCaptionId++,
      text: c.text || '',
      start: c.start,
      end: c.end,
    }));

    reRenderTracks(videoEl);
    wireZoomButtons(videoEl);

    videoEl.addEventListener('timeupdate', () => updateCaptionOverlay(videoEl));
    updateCaptionOverlayNow();
    timelineInitialized = true;
  });
};

// Returns null (instead of an empty array) while the timeline hasn't finished
// initializing yet, so callers can tell "not ready" apart from "genuinely no
// captions" and fall back to the server-side caption data instead.
window.__collectCaptionTimeline = function () {
  if (!timelineInitialized) {
    return null;
  }
  return currentCaptions
    .map((c) => ({ text: (c.text || '').trim(), start: c.start, end: c.end }))
    .sort((a, b) => a.start - b.start);
};

let resizeDebounce = null;
window.addEventListener('resize', () => {
  clearTimeout(resizeDebounce);
  resizeDebounce = setTimeout(updateCaptionOverlayNow, 150);
});

console.log('[timeline] timeline.js module loaded');
