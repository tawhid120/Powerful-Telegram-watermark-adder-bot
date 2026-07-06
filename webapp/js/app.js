/**
 * WMark Studio — Mini App main controller.
 * Handles navigation, state, and wiring between screens, forms, and the API.
 */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  // ---------------- Global state ----------------
  const state = {
    profile: null,
    templates: [],
    tails: [],
    channels: [],
    selectedTemplateId: null,
    selectedTailId: null,
    mediaFile: null,
    isVideo: false,
    editingTemplate: null, // null = new, object = editing existing
    tplKind: 'text',
    tplPosition: 'bottom-right',
    tplImageFile: null,
    tplImagePreviewUrl: null,
  };

  // ---------------- Utilities ----------------
  function toast(msg, type = '') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'show' + (type ? ' ' + type : '');
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.className = ''; }, 2600);
  }

  function showLoading(msg = 'Processing…') {
    document.getElementById('loading-msg').textContent = msg;
    document.getElementById('loading-overlay').classList.add('show');
  }
  function hideLoading() {
    document.getElementById('loading-overlay').classList.remove('show');
  }

  function switchScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.toggle('active', s.id === id));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.screen === id));
    window.scrollTo(0, 0);
  }

  function fmtMB(bytes) { return (bytes / (1024 * 1024)).toFixed(1) + ' MB'; }

  // ---------------- Boot / auth ----------------
  async function boot() {
    try {
      const initData = tg?.initData || '';
      if (!initData) {
        // Not running inside Telegram — dev fallback message.
        document.getElementById('preview-empty').textContent =
          'Open this app from inside Telegram to sign in.';
        toast('Open via the Telegram bot to use WMark Studio', 'error');
        return;
      }
      const auth = await Api.authenticate(initData);
      updatePlanChip(auth.plan);
      await refreshAll();
    } catch (e) {
      toast(e.message || 'Failed to connect', 'error');
    }
  }

  function updatePlanChip(plan) {
    const chip = document.getElementById('plan-chip');
    chip.textContent = plan.toUpperCase();
    chip.className = 'plan-chip ' + plan;
  }

  async function refreshAll() {
    const [profile, templates, tails, channels] = await Promise.all([
      Api.getProfile(), Api.listTemplates(), Api.listTails(), Api.listChannels(),
    ]);
    state.profile = profile;
    state.templates = templates;
    state.tails = tails;
    state.channels = channels;
    updatePlanChip(profile.plan);
    renderTemplatePickerOnEditor();
    renderTemplatesList();
    renderTailPicker();
    renderChannelsList();
    renderProfile();
  }

  // ---------------- Editor screen ----------------
  const dropzone = document.getElementById('dropzone');
  const mediaInput = document.getElementById('media-input');
  const previewFrame = document.getElementById('preview-frame');
  const btnProcess = document.getElementById('btn-process');

  dropzone.addEventListener('click', () => mediaInput.click());
  mediaInput.addEventListener('change', () => {
    const file = mediaInput.files[0];
    if (!file) return;
    state.mediaFile = file;
    state.isVideo = file.type.startsWith('video/');
    document.getElementById('dropzone-filename').textContent = file.name;
    dropzone.classList.add('has-file');
    Preview.setBaseMedia(previewFrame, file, state.isVideo);
    document.getElementById('tail-card').style.display = state.isVideo ? 'block' : 'none';
    renderEditorPreview();
    updateProcessButton();
  });

  function renderTemplatePickerOnEditor() {
    const list = document.getElementById('template-picker-list');
    list.innerHTML = '';
    if (state.templates.length === 0) {
      list.innerHTML = `<div class="hint" style="margin:0;">No templates yet — create one in the Templates tab.</div>`;
      updateProcessButton();
      return;
    }
    if (!state.selectedTemplateId) {
      const def = state.templates.find(t => t.is_default) || state.templates[0];
      state.selectedTemplateId = def.id;
    }
    state.templates.forEach(t => {
      const item = document.createElement('div');
      item.className = 'list-item';
      item.style.marginBottom = '8px';
      item.innerHTML = `
        <div class="thumb">${t.kind === 'photo' ? '🖼️' : '🔤'}</div>
        <div class="meta">
          <div class="title">${escapeHtml(t.name)}</div>
          <div class="sub">${t.position} · ${t.width_pct}% width</div>
        </div>
        ${t.id === state.selectedTemplateId ? '<div class="badge-default">SELECTED</div>' : ''}
      `;
      item.addEventListener('click', () => {
        state.selectedTemplateId = t.id;
        renderTemplatePickerOnEditor();
        renderEditorPreview();
      });
      list.appendChild(item);
    });
    updateProcessButton();
  }

  function renderEditorPreview() {
    const tmpl = state.templates.find(t => t.id === state.selectedTemplateId);
    if (!tmpl || !state.mediaFile) return;
    Preview.render(previewFrame, {
      kind: tmpl.kind,
      text_content: tmpl.text_content,
      font_size: tmpl.font_size,
      font_color: tmpl.font_color,
      position: tmpl.position,
      offset_x_pct: tmpl.offset_x_pct,
      offset_y_pct: tmpl.offset_y_pct,
      width_pct: tmpl.width_pct,
      opacity_pct: tmpl.opacity_pct,
      rotation_deg: tmpl.rotation_deg,
      previewImageUrl: tmpl.kind === 'photo' ? `/api/templates/${tmpl.id}/thumb` : null,
    });
  }

  function updateProcessButton() {
    btnProcess.disabled = !(state.mediaFile && state.selectedTemplateId);
  }

  document.getElementById('btn-goto-templates').addEventListener('click', () => switchScreen('screen-templates'));

  const tailToggle = document.getElementById('tail-toggle');
  let tailEnabled = false;
  tailToggle.addEventListener('click', () => {
    tailEnabled = !tailEnabled;
    tailToggle.classList.toggle('on', tailEnabled);
    document.getElementById('tail-picker-list').style.display = tailEnabled ? 'block' : 'none';
  });

  function renderTailPicker() {
    const list = document.getElementById('tail-picker-list');
    list.innerHTML = '';
    if (state.tails.length === 0) {
      list.innerHTML = `<div class="hint" style="margin:0;">No tails uploaded yet.</div>`;
      return;
    }
    state.tails.forEach(t => {
      const item = document.createElement('div');
      item.className = 'list-item';
      item.style.marginBottom = '6px';
      item.innerHTML = `<div class="thumb">🎬</div><div class="meta"><div class="title">${escapeHtml(t.name)}</div></div>`;
      item.addEventListener('click', () => {
        state.selectedTailId = t.id;
        [...list.children].forEach(c => c.style.borderColor = 'var(--ink-700)');
        item.style.borderColor = 'var(--cyan)';
      });
      list.appendChild(item);
    });
  }

  btnProcess.addEventListener('click', async () => {
    if (!state.mediaFile || !state.selectedTemplateId) return;
    const fd = new FormData();
    fd.append('template_id', state.selectedTemplateId);
    if (tailEnabled && state.selectedTailId) fd.append('tail_id', state.selectedTailId);
    fd.append('file', state.mediaFile);

    showLoading(state.isVideo ? 'Rendering video… this can take a moment' : 'Applying watermark…');
    try {
      const blob = await Api.processMedia(fd);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = state.isVideo ? 'watermarked.mp4' : 'watermarked.png';
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast('Watermark applied — check your downloads', 'success');
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
      await refreshAll(); // usage counters changed
    } catch (e) {
      toast(e.message || 'Processing failed', 'error');
    } finally {
      hideLoading();
    }
  });

  // ---------------- Templates list screen ----------------
  function renderTemplatesList() {
    const list = document.getElementById('templates-list');
    const empty = document.getElementById('templates-empty');
    list.innerHTML = '';
    empty.style.display = state.templates.length ? 'none' : 'block';
    state.templates.forEach(t => {
      const item = document.createElement('div');
      item.className = 'list-item';
      item.innerHTML = `
        <div class="thumb">${t.kind === 'photo' ? '🖼️' : '🔤'}</div>
        <div class="meta">
          <div class="title">${escapeHtml(t.name)}</div>
          <div class="sub">${t.kind === 'text' ? escapeHtml(t.text_content || '') : t.position}</div>
        </div>
        ${t.is_default ? '<div class="badge-default">DEFAULT</div>' : ''}
      `;
      item.addEventListener('click', () => openTemplateEditor(t));
      list.appendChild(item);
    });
  }

  document.getElementById('fab-new-template').addEventListener('click', () => openTemplateEditor(null));

  // ---------------- Template editor screen ----------------
  const tplPreviewFrame = document.getElementById('tpl-preview-frame');

  function openTemplateEditor(tmpl) {
    state.editingTemplate = tmpl;
    state.tplImageFile = null;
    state.tplImagePreviewUrl = tmpl && tmpl.kind === 'photo' ? `/api/templates/${tmpl.id}/thumb` : null;

    document.getElementById('template-editor-title').textContent = tmpl ? 'Edit template' : 'New template';
    document.getElementById('btn-delete-template').style.display = tmpl ? 'block' : 'none';

    document.getElementById('tpl-name').value = tmpl?.name || '';
    state.tplKind = tmpl?.kind || 'text';
    setKindUI(state.tplKind);

    document.getElementById('tpl-text-content').value = tmpl?.text_content || '';
    document.getElementById('tpl-font-size').value = tmpl?.font_size ?? 32;
    document.getElementById('tpl-font-size-val').textContent = (tmpl?.font_size ?? 32) + 'px';
    document.getElementById('tpl-font-color').value = tmpl?.font_color || '#ffffff';
    document.getElementById('tpl-dropzone-filename').textContent = tmpl?.image_path ? 'Current image kept' : '';
    document.getElementById('tpl-dropzone').classList.toggle('has-file', !!tmpl?.image_path);

    state.tplPosition = tmpl?.position || 'bottom-right';
    setPositionUI(state.tplPosition);

    const movementOn = !!tmpl?.screen_movement;
    document.getElementById('tpl-movement-toggle').classList.toggle('on', movementOn);

    setSlider('tpl-offset-x', 'tpl-ox-val', tmpl?.offset_x_pct ?? 5, '%');
    setSlider('tpl-offset-y', 'tpl-oy-val', tmpl?.offset_y_pct ?? 5, '%');
    setSlider('tpl-width', 'tpl-width-val', tmpl?.width_pct ?? 25, '%');
    setSlider('tpl-opacity', 'tpl-opacity-val', tmpl?.opacity_pct ?? 100, '%');
    setSlider('tpl-rotation', 'tpl-rotation-val', tmpl?.rotation_deg ?? 0, '°');

    renderTemplatePreview();
    switchScreen('screen-template-editor');
  }

  function setSlider(inputId, labelId, value, suffix) {
    document.getElementById(inputId).value = value;
    document.getElementById(labelId).textContent = value + suffix;
  }

  function setKindUI(kind) {
    document.querySelectorAll('#tpl-kind-segmented button').forEach(b => b.classList.toggle('active', b.dataset.kind === kind));
    document.getElementById('tpl-text-fields').style.display = kind === 'text' ? 'block' : 'none';
    document.getElementById('tpl-photo-fields').style.display = kind === 'photo' ? 'block' : 'none';
  }

  function setPositionUI(pos) {
    document.querySelectorAll('#tpl-position-grid button, .position-extra button')
      .forEach(b => b.classList.toggle('active', b.dataset.pos === pos));
  }

  document.querySelectorAll('#tpl-kind-segmented button').forEach(btn => {
    btn.addEventListener('click', () => { state.tplKind = btn.dataset.kind; setKindUI(state.tplKind); renderTemplatePreview(); });
  });

  document.querySelectorAll('#tpl-position-grid button, .position-extra button').forEach(btn => {
    btn.addEventListener('click', () => { state.tplPosition = btn.dataset.pos; setPositionUI(state.tplPosition); renderTemplatePreview(); });
  });

  document.getElementById('tpl-movement-toggle').addEventListener('click', (e) => {
    e.target.classList.toggle('on');
  });

  ['tpl-offset-x:tpl-ox-val:%', 'tpl-offset-y:tpl-oy-val:%', 'tpl-width:tpl-width-val:%',
   'tpl-opacity:tpl-opacity-val:%', 'tpl-rotation:tpl-rotation-val:°', 'tpl-font-size:tpl-font-size-val:px']
    .forEach(spec => {
      const [inputId, labelId, suffix] = spec.split(':');
      document.getElementById(inputId).addEventListener('input', (e) => {
        document.getElementById(labelId).textContent = e.target.value + suffix;
        renderTemplatePreview();
      });
    });

  document.getElementById('tpl-text-content').addEventListener('input', renderTemplatePreview);
  document.getElementById('tpl-font-color').addEventListener('input', renderTemplatePreview);

  const tplDropzone = document.getElementById('tpl-dropzone');
  const tplImageInput = document.getElementById('tpl-image-input');
  tplDropzone.addEventListener('click', () => tplImageInput.click());
  tplImageInput.addEventListener('change', () => {
    const file = tplImageInput.files[0];
    if (!file) return;
    state.tplImageFile = file;
    state.tplImagePreviewUrl = URL.createObjectURL(file);
    document.getElementById('tpl-dropzone-filename').textContent = file.name;
    tplDropzone.classList.add('has-file');
    renderTemplatePreview();
  });

  function renderTemplatePreview() {
    Preview.setBaseMedia(tplPreviewFrame, 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=600&q=60');
    Preview.render(tplPreviewFrame, {
      kind: state.tplKind,
      text_content: document.getElementById('tpl-text-content').value || 'Sample watermark',
      font_size: Number(document.getElementById('tpl-font-size').value),
      font_color: document.getElementById('tpl-font-color').value,
      position: state.tplPosition,
      offset_x_pct: Number(document.getElementById('tpl-offset-x').value),
      offset_y_pct: Number(document.getElementById('tpl-offset-y').value),
      width_pct: Number(document.getElementById('tpl-width').value),
      opacity_pct: Number(document.getElementById('tpl-opacity').value),
      rotation_deg: Number(document.getElementById('tpl-rotation').value),
      previewImageUrl: state.tplImagePreviewUrl,
    });
  }

  document.getElementById('btn-save-template').addEventListener('click', async () => {
    const name = document.getElementById('tpl-name').value.trim();
    if (!name) return toast('Give the template a name', 'error');
    if (state.tplKind === 'photo' && !state.tplImageFile && !state.editingTemplate?.image_path) {
      return toast('Upload a PNG image for a photo watermark', 'error');
    }
    if (state.tplKind === 'text' && !document.getElementById('tpl-text-content').value.trim()) {
      return toast('Enter the watermark text', 'error');
    }

    const common = {
      name,
      kind: state.tplKind,
      text_content: document.getElementById('tpl-text-content').value,
      font_family: 'default',
      font_size: Number(document.getElementById('tpl-font-size').value),
      font_color: document.getElementById('tpl-font-color').value,
      position: state.tplPosition,
      offset_x_pct: Number(document.getElementById('tpl-offset-x').value),
      offset_y_pct: Number(document.getElementById('tpl-offset-y').value),
      width_pct: Number(document.getElementById('tpl-width').value),
      opacity_pct: Number(document.getElementById('tpl-opacity').value),
      rotation_deg: Number(document.getElementById('tpl-rotation').value),
      screen_movement: document.getElementById('tpl-movement-toggle').classList.contains('on'),
    };

    showLoading('Saving template…');
    try {
      if (state.editingTemplate) {
        await Api.updateTemplate(state.editingTemplate.id, common);
        toast('Template updated', 'success');
      } else {
        const fd = new FormData();
        Object.entries(common).forEach(([k, v]) => fd.append(k, v));
        if (state.tplImageFile) fd.append('image', state.tplImageFile);
        await Api.createTemplate(fd);
        toast('Template created', 'success');
      }
      await refreshAll();
      switchScreen('screen-templates');
    } catch (e) {
      toast(e.message || 'Save failed', 'error');
    } finally {
      hideLoading();
    }
  });

  document.getElementById('btn-set-default-template').addEventListener('click', async () => {
    if (!state.editingTemplate) return toast('Save the template first', 'error');
    try {
      await Api.setDefaultTemplate(state.editingTemplate.id);
      toast('Set as default template', 'success');
      await refreshAll();
    } catch (e) { toast(e.message, 'error'); }
  });

  document.getElementById('btn-delete-template').addEventListener('click', async () => {
    if (!state.editingTemplate) return;
    if (!confirm('Delete this template? This cannot be undone.')) return;
    try {
      await Api.deleteTemplate(state.editingTemplate.id);
      toast('Template deleted', 'success');
      await refreshAll();
      switchScreen('screen-templates');
    } catch (e) { toast(e.message, 'error'); }
  });

  // ---------------- Channels screen ----------------
  function renderChannelsList() {
    const list = document.getElementById('channels-list');
    const empty = document.getElementById('channels-empty');
    list.innerHTML = '';
    empty.style.display = state.channels.length ? 'none' : 'block';
    state.channels.forEach(c => {
      const tmplName = state.templates.find(t => t.id === c.template_id)?.name || 'No template set';
      const item = document.createElement('div');
      item.className = 'list-item';
      item.innerHTML = `
        <div class="thumb">📺</div>
        <div class="meta">
          <div class="title">${escapeHtml(c.title)}</div>
          <div class="sub">${escapeHtml(tmplName)}</div>
        </div>
        <div class="badge-default" style="background:${c.is_active ? 'rgba(79,191,138,0.12)' : 'rgba(232,97,92,0.12)'}; color:${c.is_active ? 'var(--green)' : 'var(--coral)'};">
          ${c.is_active ? 'ACTIVE' : 'PAUSED'}
        </div>
      `;
      item.addEventListener('click', () => openChannelTemplatePicker(c));
      list.appendChild(item);
    });
  }

  function openChannelTemplatePicker(channel) {
    if (state.templates.length === 0) {
      return toast('Create a template first', 'error');
    }
    const names = state.templates.map((t, i) => `${i + 1}. ${t.name}`).join('\n');
    const choice = prompt(`Pick a template number for "${channel.title}":\n${names}`);
    const idx = parseInt(choice, 10) - 1;
    if (isNaN(idx) || !state.templates[idx]) return;
    Api.updateChannel(channel.id, {
      template_id: state.templates[idx].id,
      tail_id: channel.tail_id,
      is_active: true,
    }).then(() => { toast('Channel updated', 'success'); refreshAll(); })
      .catch(e => toast(e.message, 'error'));
  }

  // ---------------- Profile screen ----------------
  function renderProfile() {
    const p = state.profile;
    if (!p) return;
    document.getElementById('usage-text').textContent = `${fmtMB(p.daily_bytes_used)} / ${fmtMB(p.daily_limit_bytes)}`;
    const pct = Math.min(100, Math.round((p.daily_bytes_used / p.daily_limit_bytes) * 100));
    document.getElementById('usage-pct').textContent = pct + '%';
    document.getElementById('usage-bar').style.width = pct + '%';
    document.getElementById('tpl-count').textContent = p.template_count;
    document.getElementById('tpl-limit').textContent = p.template_limit;
    document.getElementById('chan-count').textContent = p.channel_count;
    document.getElementById('chan-limit').textContent = p.channel_limit;

    document.querySelectorAll('.plan-card').forEach(card => {
      card.classList.toggle('current', card.dataset.plan === p.plan);
    });
  }

  document.getElementById('btn-contact-upgrade').addEventListener('click', () => {
    if (tg) tg.close();
  });

  // ---------------- Nav wiring ----------------
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => switchScreen(btn.dataset.screen));
  });

  function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str ?? '';
    return d.innerHTML;
  }

  boot();
})();
