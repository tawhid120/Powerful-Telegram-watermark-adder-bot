/**
 * Renders a live, client-side approximation of the watermark placement
 * inside a preview frame div. This mirrors (but does not replace) the
 * server-side Pillow/ffmpeg engine — it's for instant visual feedback only.
 */
const Preview = (() => {

  function clear(frameEl) {
    frameEl.querySelectorAll('.wm-layer, .base-media').forEach(el => el.remove());
    let empty = frameEl.querySelector('.preview-empty');
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'preview-empty';
      frameEl.appendChild(empty);
    }
    empty.style.display = 'flex';
  }

  function setBaseMedia(frameEl, fileOrUrl, isVideo = false) {
    const empty = frameEl.querySelector('.preview-empty');
    if (empty) empty.style.display = 'none';
    frameEl.querySelectorAll('.base-media').forEach(el => el.remove());

    const el = document.createElement(isVideo ? 'video' : 'img');
    el.className = 'base-media';
    if (isVideo) { el.muted = true; el.loop = true; el.autoplay = true; el.playsInline = true; }
    el.src = typeof fileOrUrl === 'string' ? fileOrUrl : URL.createObjectURL(fileOrUrl);
    frameEl.insertBefore(el, frameEl.firstChild);
  }

  function positionStyle(config) {
    const { position, offset_x_pct, offset_y_pct } = config;
    const ox = offset_x_pct + '%';
    const oy = offset_y_pct + '%';
    const map = {
      'top-left':      { top: oy, left: ox },
      'top-center':    { top: oy, left: '50%', transform: 'translateX(-50%)' },
      'top-right':     { top: oy, right: ox },
      'middle-left':   { top: '50%', left: ox, transform: 'translateY(-50%)' },
      'center':        { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' },
      'middle-right':  { top: '50%', right: ox, transform: 'translateY(-50%)' },
      'bottom-left':   { bottom: oy, left: ox },
      'bottom-center': { bottom: oy, left: '50%', transform: 'translateX(-50%)' },
      'bottom-right':  { bottom: oy, right: ox },
      'random':        { top: '40%', left: '40%' },
      'fill':          { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' },
    };
    return map[position] || map['bottom-right'];
  }

  function render(frameEl, config) {
    frameEl.querySelectorAll('.wm-layer').forEach(el => el.remove());

    const layer = document.createElement('div');
    layer.className = 'wm-layer';
    layer.style.width = config.width_pct + '%';
    layer.style.opacity = config.opacity_pct / 100;
    layer.style.transform = (layer.style.transform || '') + ` rotate(${config.rotation_deg || 0}deg)`;

    Object.assign(layer.style, positionStyle(config));
    // re-apply rotation after positionStyle may have set a transform (translate)
    const posStyle = positionStyle(config);
    let transformStr = posStyle.transform || '';
    transformStr += ` rotate(${config.rotation_deg || 0}deg)`;
    layer.style.transform = transformStr;

    if (config.kind === 'photo' && config.previewImageUrl) {
      const img = document.createElement('img');
      img.src = config.previewImageUrl;
      layer.appendChild(img);
    } else {
      layer.textContent = config.text_content || 'Sample watermark';
      layer.style.color = config.font_color || '#ffffff';
      layer.style.fontSize = Math.max(10, (config.font_size || 32) * 0.35) + 'px';
      layer.style.width = 'auto';
      layer.style.maxWidth = '80%';
    }

    if (config.position === 'fill') {
      layer.style.opacity = (config.opacity_pct / 100) * 0.9;
    }

    frameEl.appendChild(layer);
  }

  return { clear, setBaseMedia, render };
})();
