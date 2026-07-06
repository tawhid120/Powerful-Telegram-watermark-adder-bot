/**
 * Thin fetch wrapper around the WMark Bot API.
 * Handles auth token storage and JSON/multipart requests uniformly.
 */
const Api = (() => {
  let token = null;

  function setToken(t) { token = t; }

  async function authenticate(initData) {
    const res = await fetch('/api/auth', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: initData }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Auth failed');
    const data = await res.json();
    setToken(data.token);
    return data;
  }

  function authHeaders(extra = {}) {
    return { Authorization: `Bearer ${token}`, ...extra };
  }

  async function request(path, opts = {}) {
    const res = await fetch(path, { ...opts, headers: { ...authHeaders(), ...(opts.headers || {}) } });
    if (!res.ok) {
      let detail = 'Request failed';
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.blob();
  }

  return {
    setToken,
    authenticate,

    getProfile: () => request('/api/profile'),

    listTemplates: () => request('/api/templates'),
    createTemplate: (formData) => request('/api/templates', { method: 'POST', body: formData }),
    updateTemplate: (id, body) => request(`/api/templates/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
    deleteTemplate: (id) => request(`/api/templates/${id}`, { method: 'DELETE' }),
    setDefaultTemplate: (id) => request(`/api/templates/${id}/set-default`, { method: 'POST' }),

    listTails: () => request('/api/tails'),
    createTail: (formData) => request('/api/tails', { method: 'POST', body: formData }),
    deleteTail: (id) => request(`/api/tails/${id}`, { method: 'DELETE' }),

    listChannels: () => request('/api/channels'),
    updateChannel: (id, body) => request(`/api/channels/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),

    processMedia: (formData) => request('/api/process', { method: 'POST', body: formData }),
  };
})();
